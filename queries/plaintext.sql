-- Root pages whose rendered DOM (after load, main document) has a <plaintext> element, from the
-- element_count custom metric (HTTPArchive/custom-metrics dist/element_count.js: counts
-- document.querySelectorAll('*') by lowercased tagName, so it includes elements created by
-- document.write and can't tell HTML plaintext from SVG/MathML plaintext).
SELECT
  client,
  COUNT(*) AS pages,
  COUNTIF(custom_metrics.element_count IS NOT NULL) AS pages_with_metric,
  COUNTIF(SAFE.INT64(custom_metrics.element_count.plaintext) > 0) AS plaintext_pages,
  ARRAY_AGG(
    IF(SAFE.INT64(custom_metrics.element_count.plaintext) > 0,
       STRUCT(page, rank, SAFE.INT64(custom_metrics.element_count.plaintext) AS n), NULL)
    IGNORE NULLS ORDER BY rank LIMIT 5000) AS plaintext
FROM `httparchive.crawl.pages`
WHERE date = '2026-10-01'
  AND is_root_page
GROUP BY client
