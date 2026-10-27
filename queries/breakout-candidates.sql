-- From the candidate table (queries/candidates.sql): root pages (2026-10-01, mobile) with a
-- textarea, xmp, iframe, noembed, noframes or plaintext start tag inside an <svg>/<math> block
-- (regex level, any kind), for checking whether making them break out of foreign content is
-- compatible.
SELECT page, rank, ARRAY_AGG(STRUCT(k.name, k.kind, k.n)) AS kinds
FROM `test.fr11397_2026_10_mobile`, UNNEST(kinds) AS k
WHERE k.name IN ('textarea', 'xmp', 'iframe', 'noembed', 'noframes', 'plaintext')
GROUP BY page, rank
