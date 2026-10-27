-- Not run yet (BigQuery credentials expired during this research). Dry-run first.
-- Root-page main documents with an inline <svg>/<math> block that contains a
-- style/script/title/textarea/xmp/iframe/noembed/noframes/noscript/plaintext start tag (not
-- self-closing) whose content would parse differently as raw text: a character reference
-- (style/script/etc. only), a tag, a comment, or a CDATA marker. Approximate (regex, ignores
-- integration points); pages found here are then checked with cc/analyze_warc.py's parser
-- and in Firefox with the pref.
CREATE TEMP FUNCTION blocks(body STRING) AS (
  REGEXP_EXTRACT_ALL(body, r'(?is)<(?:svg|math)[\s>][\s\S]*?</(?:svg|math)\s*>')
);
SELECT
  client,
  page,
  rank,
  FARM_FINGERPRINT(response_body) AS body_fp,
  ARRAY(
    SELECT AS STRUCT
      LOWER(REGEXP_EXTRACT(el, r'^<(\w+)')) AS name,
      SUBSTR(el, 1, 300) AS snippet,
      REGEXP_CONTAINS(el, r'&[a-zA-Z#][a-zA-Z0-9]*;?') AS charref,
      REGEXP_CONTAINS(el, r'<!--') AS comment,
      REGEXP_CONTAINS(el, r'<!\[CDATA\[') AS cdata,
      REGEXP_CONTAINS(el, r'(?i)<(?:[a-z]|/[a-z])') AS tag
    FROM UNNEST(blocks(response_body)) AS b,
      UNNEST(REGEXP_EXTRACT_ALL(b,
        r'(?is)(<(?:style|script|title|textarea|xmp|iframe|noembed|noframes|noscript|plaintext)\b[^>]*[^/>]?>[\s\S]*?(?:</(?:style|script|title|textarea|xmp|iframe|noembed|noframes|noscript|plaintext)\s*>|$))'
      )) AS el
  ) AS elements
FROM `httparchive.crawl.requests`
WHERE date = '2026-10-01'
  AND is_root_page
  AND is_main_document
  AND REGEXP_CONTAINS(response_body, r'(?i)<(?:svg|math)[\s>]')
  AND REGEXP_CONTAINS(response_body,
    r'(?is)<(?:svg|math)[\s>][\s\S]*?<(?:style|script|title|textarea|xmp|iframe|noembed|noframes|noscript|plaintext)\b')
