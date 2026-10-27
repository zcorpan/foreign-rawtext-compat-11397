# Compat impact of parsing SVG/MathML `style`, `script`, etc. like HTML (whatwg/html#11397)

Proposed change: in foreign content, a non-self-closing start tag for `style`, `script`, `title`,
`textarea`, `xmp`, `iframe`, `noembed`, `noframes`, `noscript` or `plaintext` still creates the
SVG/MathML element, but switches the tokenizer so its contents can't become markup. Then
something that was text in one namespace can't parse as markup after a serialize and reparse puts
it in the other (namespace-confusion mXSS). Three variants:

- **raw** (pref mode 1): exactly like the HTML element (RAWTEXT, script data, RCDATA for
  `title`/`textarea`, PLAINTEXT). The raw text elements' text also serializes literally.
- **rcdata** (mode 2): RCDATA for all of them (`plaintext` stays PLAINTEXT). Character references
  are still decoded, and serialization is unchanged (escaped).
- **rcdata-dc** (mode 3): rcdata, plus everything from `<!--` to the next `-->` is dropped from
  the text. An end tag inside still ends the element.

All three variants also drop `<![CDATA[` and the next `]]>` inside these elements, and don't
decode character references between them. The element's end tag still ends it even inside the
markers. Self-closing tags (`<svg><style/>`) keep today's behavior.

## Summary

HTTP Archive, 2026-10-01 crawl, mobile, root pages, main documents: 15,360,905 pages.

| | Pages that parse differently | Visible breakage (live sample) |
|---|---|---|
| raw | ~225,800 (1.47%), essentially all Wix | icons recolored on 5/100 Wix pages → ~11,300 pages (95% CI 3,700–25,500) |
| rcdata | 1,449 (0.0094%) | 1/100 → ~14 pages (CI 0–79), plus 3 pages with an unclosed element |
| rcdata-dc | 327 (0.0021%) with text changes; 1,122 more lose only comment nodes | 0/100 (CI 0–52), plus the same 3 pages |

What's behind it:

- **raw**: Wix's server rendering escapes `"` as `&quot;` in SVG `<style>`
  (`#comp-… svg [data-color=&quot;1&quot;] {fill: …}`, `#BACK_TO_TOP_BUTTON …`). Today's
  foreign-content parsing decodes that, but raw text doesn't. Wix re-renders most SVGs after
  hydration. On 17 of 100 sampled pages the escaped text survived, and on 5 of those the icons
  visibly lost the site's colors ([review/raw-wix-deafplus.png](review/raw-wix-deafplus.png);
  in every review image, today is on the left and the variant on the right).
- **rcdata** and **rcdata-dc**: comments and tags inside these elements become text:
  - React's `<!-- -->` text separators in SVG `<title>`/`<style>`. They cause React hydration
    errors (#418/#423/#425, with client-side recovery) on ~58 pages (CI 16–143) in both modes.
  - Translation-widget elements (`<ly-as-N>`), `<span>`/`<br>` and the like in titles.
  - `<tspan>` inside `<style>`.
  - Drupal-style `<!--/*--><![CDATA[/* ><!--*/` wrappers.
  - PIs (`<?php`): 11 pages.
- **rcdata only**: CSS commented out with `<!-- -->` inside SVG `<style>` becomes active. In the
  sample, `.st0{fill:none}` made icons invisible
  ([review/rcdata-vcsdurability-commented-css-activated.png](review/rcdata-vcsdurability-commented-css-activated.png)).
  rcdata-dc keeps those rules inert.
- **All three variants**: 5 pages have a genuinely unclosed SVG `<style>`/`<title>`. Examples:
  `<style>` closed only by `</defs>`, `<style>` typed for `</style>`, `</a>` typed for
  `</title>`. On 3 of them, everything after the SVG becomes text and the page goes blank
  ([review/unclosed-style-greenplaceamsterdam.png](review/unclosed-style-greenplaceamsterdam.png),
  [review/unclosed-style-agua-eshop.png](review/unclosed-style-agua-eshop.png)). Another 80 pages
  differ only because their crawled body is truncated inside such an element; they're excluded
  from the counts (`ha/counts.py` → `ha/counts.txt`).
- **CDATA**: `<![CDATA[` occurs inside these SVG elements on ~7k pages (regex,
  `queries/kinds.csv`). With the markers dropped, they parse as today. No page in either corpus
  had the element's own end tag inside a CDATA section.
- **Self-closing**: `<svg><title/>`, `<style/>`, `<script/>` etc. occur on ~6k pages (regex).
  They must keep today's behavior, or the rest of the page is swallowed.
- **mXSS check**: I ran each element in two shapes in this build.
  - (A) securitum's `form`/`mglyph` mutation, HTML to MathML. Today it pops an `img` for `style`,
    `xmp`, `iframe`, `noembed`, `noframes` and `noscript`.
  - (B) a comment carrying `</title><img …>` inside the SVG element, with the element's
    serialization reparsed as HTML. Today it pops an `img` for all of them except `noscript`, so
    `title` and `textarea` need to be in the list too.

  All three variants close both shapes for every element except `noscript`. `noscript` still
  differs between scripting-enabled and scripting-disabled parsers, which is a separate, existing
  issue. Test: `mxss-check.html`.

Common Crawl (12 seeded WARCs of CC-MAIN-2026-39, 256,037 HTML pages; section 3) agrees: raw
0.23%, rcdata 0.011%.

## 1. HTTP Archive

- `queries/candidates.sql` scans every root page's main document once (7.29 TB). It finds
  `<svg>`/`<math>` blocks, then each element of interest in them, and classifies what follows the
  element's text: its own end tag ("plain"), or the first thing that could parse differently.
  Candidate pages keep their blocks and body in a scratch table.
  - Totals: `queries/totals.csv`.
  - Per element name and kind (regex level): `queries/kinds.csv`.
- `ha/classify.py` parses each candidate block standalone, then the full body for selected pages,
  today's way and in each variant, with `cc/frparse.py` (html5lib patched per variant).
  - Selected pages (`ha/selected.csv`): all 7,121 pages whose blocks differ in rcdata or
    rcdata-dc, plus a seeded sample of 500 of the 224,159 raw-only pages.
  - Summaries: `ha/summary-blocks.txt`, `ha/summary-full.txt`, `ha/patterns-rcdata.txt`,
    `ha/patterns-raw-sample.txt`.
- All 500 raw-only sample pages were confirmed on the full parse (499 are Wix), so raw is
  about 1,742 + 224,159 pages, minus the truncated-body artifacts.
- `ha/patterns.py` gives the patterns behind the differences (`ha/patterns-rcdata.txt`), and
  `ha/counts.py` gives the counts without truncated-body artifacts (`ha/counts.txt`).
- The html5lib patch's rcdata-dc mode was checked against the Gecko build, including Drupal's
  `<!--/*--><![CDATA[/* ><!--*/ … /*]]>*/-->` wrapper (comments between CDATA markers aren't
  dropped).

## 2. Live comparison

The live runs use a Firefox build with `dom.parser.foreign_rawtext.mode`.

- `ff_compare.py` (Selenium, headless, 1366×768, 5 s wait) loads each page twice in mode 0 (A,
  A2) and once in the variant (B).
- `ff_final_diff.py` and `ff_analyze.py` list persistent element and JS-error differences not
  seen between A and A2, and make the crops, which were reviewed by eye.
- Intervals: `ha/extrapolate.py` → `ha/extrapolate.txt`.

| Run | Pages | Persistent element change | New JS errors | Visible change |
|---|---|---|---|---|
| rcdata, seeded sample of the 1,444 rcdata pages (`sample-ha-rcdata.jsonl`) | 100 | 85 | 4 React hydration | 1 broken |
| rcdata-dc, same pages | 100 | 85 | 4 React hydration | 0 |
| rcdata and rcdata-dc, the 5 genuinely unclosed pages | 5 | 5 | 0 | 3 broken, 1 minor |
| raw, seeded sample of raw-only Wix pages (`sample-ha-wix.jsonl`) | 100 | 17 | 0 | 5 worse (recolored icons) |

One carters.com.br diff in rcdata-dc was timing noise; a recheck matched mode 0.

## 3. Common Crawl

Common Crawl was the first corpus, run before BigQuery was available again: every HTTP 200
`text/html` response up to 3 MB in 12 seeded WARCs (`cc/`; outputs in `out-cc/`). Live runs of
its differing pages are in `out-rcdata-m2`, `out-rcdata-m3`, `out-wix-m1` and `out-rawother-m1`
(`out-final-diff.txt`).

| | Pages |
|---|---|
| HTML responses | 256,037 |
| with an SVG/MathML element of interest | 20,980 |
| differs, raw | 578 |
| differs, rcdata | 28 |

## Not covered

- Desktop pages and non-root pages.
- Interaction: tooltips weren't hovered.
- Visual changes before hydration: only the final state was screenshotted.
- Assistive technology output.
- Other engines.
- Parsers outside browsers (sanitizers, server-side libraries), which would need the same change.
- Live runs used a desktop viewport on mobile-crawl pages.

## Query bytes

All on the 2026-10-01 crawl, run 2026-10-27:

| Query | Bytes processed |
|---|---|
| `queries/candidates.sql` | 7.29 TB |
| totals (`queries/totals.csv`) | 271 GB |
| `queries/kinds.csv` | 0.5 GB |
| blocks copy for download | 3.2 GB |
| bodies copy for selected pages | 268 GB |
