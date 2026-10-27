-- One scan of the 2026-10-01 mobile crawl: every root page's main document, with
-- 1. denominators (has a body, has an <svg>/<math> tag), and
-- 2. for each <svg ...>...</svg> / <math ...>...</math> block (lazy match to the first closing tag,
--    JSON-escaped <\/svg> included, or to the end of the document), each style/script/title/textarea/xmp/iframe/noembed/
--    noframes/noscript/plaintext start tag in it, classified by what follows its text:
--    its own end tag ("plain": parses the same in all three variants), or the first thing that can
--    parse differently: "&" (raw text only; not for title/textarea), a comment, CDATA, PI,
--    another end tag, a start tag, another "<", or the end of the block.
-- Pages with any non-plain element keep their candidate blocks and full body, so the exact
-- classification (cc/frparse.py, all modes) runs offline without another scan.
-- Approximate on purpose (superset): ignores integration points and script-string contexts;
-- misses elements after a nested </svg> inside an outer <svg>.
CREATE TEMP FUNCTION classify(el STRING) AS ((
  SELECT AS STRUCT
    name,
    CASE
      WHEN REGEXP_CONTAINS(tag, r'/\s*>$') THEN 'self-closing'
      WHEN rest = '' THEN 'unterminated'
      WHEN REGEXP_CONTAINS(LOWER(rest), CONCAT(r'^</', name, r'[\s/>]')) THEN 'plain'
      WHEN STARTS_WITH(rest, '&') THEN 'charref'
      WHEN STARTS_WITH(rest, '<!--') THEN 'comment'
      WHEN STARTS_WITH(UPPER(rest), '<![CDATA[') THEN 'cdata'
      WHEN STARTS_WITH(rest, '<?') THEN 'pi'
      WHEN STARTS_WITH(rest, '<!') THEN 'bogus-comment'
      WHEN REGEXP_CONTAINS(rest, r'^</[A-Za-z]') THEN 'other-end-tag'
      WHEN REGEXP_CONTAINS(rest, r'^<[A-Za-z]') THEN 'start-tag'
      ELSE 'other-lt'
    END AS kind,
    SUBSTR(el, 1, 300) AS snippet
  FROM (SELECT
    LOWER(REGEXP_EXTRACT(el, r'^<([A-Za-z]+)')) AS name,
    REGEXP_EXTRACT(el, r'^(<[^>]*>)') AS tag,
    REGEXP_EXTRACT(el, r'^<[^>]*>[^<&]*([\s\S]*)$') AS rest0)
  -- title/textarea are RCDATA in every variant, so "&" doesn't matter there: skip past it.
  , UNNEST([IF(name IN ('title', 'textarea'), REGEXP_EXTRACT(el, r'^<[^>]*>[^<]*([\s\S]*)$'), rest0)]) AS rest
));

CREATE OR REPLACE TABLE `test.fr11397_2026_10_mobile` AS
WITH docs AS (
  SELECT page, rank, response_body AS body
  FROM `httparchive.crawl.requests`
  WHERE date = '2026-10-01'
    AND client = 'mobile'
    AND is_root_page
    AND is_main_document
),
b AS (
  SELECT page, rank, body,
    REGEXP_CONTAINS(body, r'(?i)<(?:svg|math)[\s/>]') AS has_foreign_tag
  FROM docs
),
blocks AS (
  SELECT page, rank, body, has_foreign_tag,
    ARRAY(
      SELECT AS STRUCT
        SUBSTR(blk, 1, 200000) AS block,
        ARRAY(
          SELECT classify(el)
          FROM UNNEST(REGEXP_EXTRACT_ALL(blk,
            r'(?i)(<(?:style|script|xmp|iframe|noembed|noframes|noscript|plaintext|title|textarea)\b[^>]*>[^<&]*(?:[<&][\s\S]{0,40})?)')) AS el
        ) AS elements
      FROM UNNEST(IF(has_foreign_tag,
        REGEXP_EXTRACT_ALL(body, r'(?is)(<(?:svg|math)[\s/>][\s\S]*?(?:</(?:svg|math)\s*>|<\\/(?:svg|math)|$))'),
        [])) AS blk
      WHERE REGEXP_CONTAINS(blk, r'(?i)<(?:style|script|xmp|iframe|noembed|noframes|noscript|plaintext|title|textarea)\b')
    ) AS blks
  FROM b
)
SELECT
  page, rank,
  body IS NOT NULL AS has_body,
  has_foreign_tag,
  ARRAY_LENGTH(blks) AS n_blocks,
  (SELECT COUNT(*) FROM UNNEST(blks) x, UNNEST(x.elements)) AS n_elements,
  ARRAY(SELECT AS STRUCT e.name, e.kind, COUNT(*) AS n FROM UNNEST(blks) x, UNNEST(x.elements) e GROUP BY 1, 2) AS kinds,
  ARRAY(SELECT e FROM UNNEST(blks) x, UNNEST(x.elements) e WHERE e.kind NOT IN ('plain', 'self-closing') LIMIT 50) AS risky,
  IF(EXISTS(SELECT 1 FROM UNNEST(blks) x, UNNEST(x.elements) e WHERE e.kind NOT IN ('plain', 'self-closing')),
     ARRAY(SELECT x.block FROM UNNEST(blks) x WHERE EXISTS(SELECT 1 FROM UNNEST(x.elements) e WHERE e.kind NOT IN ('plain', 'self-closing'))),
     []) AS risky_blocks,
  IF(EXISTS(SELECT 1 FROM UNNEST(blks) x, UNNEST(x.elements) e WHERE e.kind NOT IN ('plain', 'self-closing')),
     body, NULL) AS body
FROM blocks
