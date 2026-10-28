# Compat impact of parsing SVG/MathML `style`, `script`, etc. like HTML (whatwg/html#11397)

Namespace-confusion mXSS relies on `style`, `script`, `title`, `textarea`, `xmp`, `iframe`,
`noembed`, `noframes`, `noscript` and `plaintext` parsing as markup in SVG/MathML but as text in
HTML. Text in one namespace then becomes markup after a serialize and reparse puts it in the other.
This repo measures ways to make them consistent.

**Where it ended up:** `textarea`, `xmp`, `iframe`, `noembed`, `noframes` and `plaintext` break
out of foreign content (like `p`). `title`, `style`, `script` and `noscript` stay SVG/MathML
elements, parsed as RCDATA, with comments and PIs kept as nodes. The element's end tag still
closes it, even inside a comment, PI or CDATA markers. `<![CDATA[`/`]]>` markers are dropped, and
self-closing tags keep today's behavior. HTML `<plaintext>` stays PLAINTEXT.

## Variants

| Variant | Tokenizing in SVG/MathML | Pref mode (Firefox build) |
|---|---|---|
| raw | exactly like HTML (RAWTEXT, script data, RCDATA for `title`/`textarea`, PLAINTEXT), literal serialization | 1 |
| rcdata | RCDATA for all (`plaintext`: PLAINTEXT), serialization unchanged (escaped) | 2 |
| rcdata-dc | rcdata, and everything from `<!--` to `-->` is dropped | 3 |
| rcdata-c | rcdata, and `<!--`…`-->` stays a comment node (PIs should too; not implemented) | html5lib only |
| breakout | `textarea`, `xmp`, `iframe`, `noembed`, `noframes`, `plaintext` close the SVG/MathML subtree | data only |

In all variants:
- `<![CDATA[` and the next `]]>` are dropped inside these elements, and character references
  between them aren't decoded.
- The element's end tag ends it, even inside comments or CDATA markers.
- Self-closing tags keep today's behavior.

## Results

HTTP Archive, 2026-10-01, mobile, root pages' main documents (15,360,905):

| Variant | Pages that parse differently | Visible breakage, live sample |
|---|---|---|
| raw | ~225,800 (1.47%), essentially all Wix | 5/100 Wix pages recolored → ~11,300 (95% CI 3,700–25,500) |
| rcdata | 1,449 (0.0094%) | 1/100 → ~14 (CI 0–79), plus 3 unclosed pages |
| rcdata-dc | 1,449: 346 (0.0023%) with other changes, 1,103 only lose comment nodes | 0/100 (CI 0–52), plus the same 3 |
| rcdata-c | 348 (0.0023%) | not run live; same DOM as rcdata-dc apart from comment nodes |
| breakout (6 elements) | 1 page with a real SVG/MathML one | an SVG `iframe` embedding YouTube would start loading |

Common Crawl (12 seeded WARCs of CC-MAIN-2026-39, 256,037 HTML pages, 20,980 with an SVG/MathML
element of interest) agrees: raw 578 (0.23%),
rcdata 28 (0.011%), rcdata-c 5.

In review images, today is on the left.

## Findings

- **Wix (raw)**: server rendering escapes `"` as `&quot;` inside SVG `<style>`
  (`#comp-… svg [data-color=&quot;1&quot;] {fill: …}`, `#BACK_TO_TOP_BUTTON …`). Today's
  foreign-content parsing decodes it, but raw text doesn't. Wix re-renders most SVGs after
  hydration. On 17/100 sampled pages the escaped text survived, and on 5 of those the icons lost
  the site's colors ([review/raw-wix-deafplus.png](review/raw-wix-deafplus.png)). Raw also breaks
  SVG `<script>` containing `&amp;&amp;` (SyntaxError on 2 Common Crawl pages).
- **Comments and tags become text (rcdata, rcdata-dc)**:
  - React's `<!-- -->` text separators in SVG `<title>`/`<style>` give React hydration errors
    (#418/#423/#425, client-side recovery) on ~58 pages (CI 16–143) in both modes.
  - The same applies to Angular/Lit markers and kbb.com's `<!--t.…-->`, which duplicated titles
    live.
  - Translation-widget elements (`<ly-as-N>`), `<span>`/`<br>` in titles, `<tspan>` in `<style>`.
  - Drupal-style `<!--/*--><![CDATA[/* ><!--*/` wrappers.
  - PIs (`<?php`): 11 pages.
- **Commented-out CSS becomes active (rcdata only)**: `<!-- .st0{fill:none;} -->` inside SVG
  `<style>` made icons invisible
  ([review/rcdata-vcsdurability-commented-css-activated.png](review/rcdata-vcsdurability-commented-css-activated.png)).
  rcdata-dc and rcdata-c keep such rules inert.
- **Keeping comments (rcdata-c)**:
  - Of the 7,621 downloaded HTTP Archive bodies, 7,268 match today exactly. That includes the
    1,103 where rcdata-dc only loses comment nodes, so the hydration errors and duplicated titles
    should go away (not checked in a browser).
  - One page differs only in a comment: on cral.ehess.fr an unclosed `<!--` in SVG `<style>`
    swallows `</style>` and the following paths today. With rcdata-c the comment ends at
    `</style>` and the paths render.
- **Unclosed elements (every variant)**: 5 pages have a genuinely unclosed SVG `<style>`/`<title>`:
  `<style>` closed only by `</defs>`, `<style>` typed for `</style>`, `</a>` for `</title>`.
  - On 3 of them the rest of the page becomes text
    ([review/unclosed-style-greenplaceamsterdam.png](review/unclosed-style-greenplaceamsterdam.png),
    [review/unclosed-style-agua-eshop.png](review/unclosed-style-agua-eshop.png)).
  - Another page loses one icon; the fifth shows no visible change.
  - 80 more pages differ only because the crawl truncated their body inside such an element.
    They're excluded from the counts.
- **CDATA**: `<![CDATA[` occurs in these SVG elements on ~7k pages (regex). With the markers
  dropped, they parse as today. No page in either corpus had the element's own end tag inside a
  CDATA section.
- **Self-closing**: `<svg><title/>`, `<style/>`, `<script/>` etc. occur on ~6k pages (regex).
  Treating them as start tags would swallow the rest of the page.
- <a id="5-breaking-out-instead-for-elements-svgmathml-doesnt-need"></a>**Breakout**:
  - Common Crawl's exact parse has none of the seven (the six plus `noscript`) as SVG/MathML
    elements.
  - Of the 2,987 HTTP Archive pages with one of the six inside an SVG/MathML block (regex), fetched
    live and parsed (27 fetch errors), only petrovskaja-school.ru has a real one: an SVG `iframe`
    embedding YouTube, with nothing in SVG after it.
  - `noscript` can't break out. In the downloaded bodies, 22 SVG `noscript` hold Google Tag
    Manager's `<noscript><iframe …>` (all 15 SVG `iframe`s are inside one) or WordPress's
    `<noscript><link …>` font fallback, injected just inside a hidden SVG sprite at the start of
    `<body>`. On 15 of the 22, SVG content follows (`symbol`, `g`, gradients). Breaking out would
    close the sprite and lose its icons. As RCDATA the snippet becomes inert text, as it
    effectively is today (an SVG-namespace `iframe` or `link` does nothing).
- **mXSS check** (`mxss-check.html`, `mxss-run.py`):
  - Shape A is securitum's `form`/`mglyph` mutation, HTML to MathML. Today it creates an `img` for
    `style`, `xmp`, `iframe`, `noembed`, `noframes` and `noscript`.
  - Shape B is a comment carrying `</title><img …>` inside the SVG element, with its serialization
    reparsed as HTML. Today it creates an `img` for every element except `noscript`, so `title`
    and `textarea` need to be included.
  - The variants close both shapes for every element except `noscript`. `noscript` still differs
    between scripting-enabled and scripting-disabled parsers, a separate, existing issue.

## Design notes

- **RCDATA rather than raw text for the elements that stay**: with the escaped serialization
  foreign elements already get, RCDATA round-trips. In document parsing, HTML parsers following
  the current spec read the serialization back as the same element.
  - Raw text with escaped serialization grows `&amp;` into `&amp;amp;` on every round trip.
  - Raw text with literal serialization breaks with current parsers, which turn the text back into
    elements.
  - For the breakout elements, current parsers likewise parse the serialized tree the same way.
- **Comments and PIs as nodes**:
  - A parser-created comment or PI can't contain the element's end tag, so a reparse as the HTML
    element yields only text. `<svg><title>a<!-- </title><img src=x> -->b` gives an `img`, as HTML
    `<title>` would.
  - A DOM-created comment containing the end tag can still break out, as in every variant and as
    text in HTML `style` does today.
  - For PIs, compat doesn't require it: the 11 pages are all unprocessed `<?php … ?>` in SVG
    `<title>`, plus 1 in Common Crawl. Consistency does: HTML now parses PIs (whatwg/html#12118)
    for `<template for>` (whatwg/html#11818), and whatwg/html#13100 would allow `<template>` in
    SVG/MathML. It would be odd for PIs to work in most SVG elements but not in `<title>`, where
    comments work.
  - Engines without HTML PI parsing yet (the Firefox build used here) make a bogus comment for
    those PIs today. Bogus comments (`<!foo>`) are rarer still inside these elements.
- **Foreign `script`: RCDATA, not the script data states**:
  - The escape states (`<!--<script>` hiding `</script>`) only matter if content has `<!--`
    followed by `<script`. Of the 97 foreign scripts on 47 fully parsed pages that differ from
    today, one does: an `<svg><script xmlns="">` wrapping SVG paths, which parses the same either
    way.
  - Script data with decoded references matches RCDATA for 93 of the 97; the other 4 are truncated
    bodies or reference decoding.
  - Today `<!--` in SVG script is a comment, so the `document.write('<script>…')` idiom can't be
    in use there.
  - RCDATA also avoids adding character references to the script data states and a clash with
    comment handling.
  - The remaining boundary difference, HTML `<script><!--<script></script>…`, is out of mXSS
    reach because sanitizers drop `script`.
- **HTML `<plaintext>` should stay PLAINTEXT**:
  - Ending it at `</plaintext>` would change no page found:
    - Common Crawl has it in static markup on 0 of 255,716 pages.
    - 34 Common Crawl pages `document.write` it: 30 forum pages when framed, 2 mobile-site
      switchers, 2 others.
    - The HTTP Archive `element_count` metric (rendered DOM, so including `document.write`) finds
      it on 6 of 15,366,242 mobile and 3 of 11,650,352 desktop root pages, 7 sites.
    - None has `</plaintext` after it. Live checks: tesera.io static; toothcorner.com,
      theatreinminneapolis.com and sinexsystems.com mobile-switcher `document.write`.
      petugas.haji.go.id served a 1 KB page and scuonlinebanking.com no longer has it.
  - None of these uses is a security feature. Each stops the rest of the page from rendering:
    - The forum writes `</head><body style="display:none"><plaintext>` only inside a same-host,
      itself-framed parent, to stop nesting itself. A cross-origin parent throws, the error is
      caught, and nothing is written, so it isn't a clickjacking defense.
    - WompMobile and 163.com stop the desktop page before loading the mobile site.
    - tesera.io hides leftover loader markup.
  - User content after it renders as HTML whenever the condition doesn't hold, so an early
    `</plaintext>` gives an injector nothing new.
  - mXSS-wise it would go backwards. PLAINTEXT is the one mode where nothing in the text can
    become markup on reparse, and an end tag gives `plaintext` `xmp`'s weakness. That covers text
    from DOM APIs, or from today's parsers during the transition
    (`<plaintext></plaintext><img src=x onerror=…>`) if a sanitizer allows `plaintext`.
    DOMPurify and sanitize-html don't by default, and DOMPurify's literal-text guard covers it.
  - No SVG/MathML `plaintext` occurs in either corpus, hence breakout for it.

## Method

| Step | Files |
|---|---|
| One scan of `httparchive.crawl.requests` (7.29 TB). It finds `<svg>`/`<math>` blocks, each element of interest in them, and what follows its text ("plain" if its own end tag); candidate pages keep blocks and body in a scratch table | `queries/candidates.sql`, `queries/totals.csv`, `queries/kinds.csv` |
| html5lib patched per variant | `cc/frparse.py`, `cc/selftest.py` |
| Classify candidate blocks, then full bodies of all 7,121 pages differing in rcdata/rcdata-dc plus a seeded 500 of the 224,159 raw-only pages | `ha/classify.py`, `ha/selected.csv`, `ha/summary-blocks.txt`, `ha/summary-full.txt` |
| Raw: all 500 sampled pages confirmed (499 Wix), so ~1,742 + 224,159 | `ha/summary-full.txt`, `ha/patterns-raw-sample.txt` |
| Patterns; counts without truncated-body artifacts | `ha/patterns.py` → `ha/patterns-rcdata.txt`; `ha/counts.py` → `ha/counts.txt` |
| Exact child-node comparison, all RCDATA modes, comments included | `ha/mode_c.py` → `ha/mode_c.txt`, `ha/mode_c.json`; `ha/dc_exact.py` → `ha/dc_exact.txt` |
| Foreign script states | `ha/script_states.py` → `ha/script_states.txt` |
| Breakout: downloaded bodies, then all regex-level candidate pages fetched live (2026-10-27) | `ha/breakout_check.py` → `ha/breakout_check.txt`; `queries/breakout-candidates.sql` → `queries/breakout-candidates.json`; `ha/breakout_live.py` → `out-ha-breakout-live.jsonl` |
| `plaintext` | `cc/plaintext_scan.py` → `out-cc/plaintext.jsonl`; `queries/plaintext.sql` → `queries/plaintext.csv` |
| Common Crawl: every HTTP 200 `text/html` response up to 3 MB in the 12 WARCs | `cc/` (`pick_warcs.py`, `download.py`, `run_all.py`, `analyze_warc.py`, `summarize.py`, `recheck_dc.py`), `out-cc/summary.txt`, `out-cc/differs.jsonl`, `out-cc/raw-patterns.txt`, `out-cc/cdata-and-misc.txt`, `out-cc/pi-and-cdata-endtag.txt` |
| Regex recall, measured on the Common Crawl pages that differ | `ha/regex_recall.py` → `ha/regex_recall.txt` |
| Intervals | `ha/extrapolate.py` → `ha/extrapolate.txt` |

**Regex recall:** each element is matched with up to 40 characters of trailing context, which
hides an element-of-interest start tag right after it (`<noscript><iframe`, `</title><style`).
On Common Crawl it flags 548/550 raw-only and 26/28 rcdata pages; one rcdata miss is an html5lib
artifact. So the HTTP Archive counts may undercount by a few percent.

**Checks against the Gecko build:**
- `ff_sanity.py` checks that each pref mode takes effect.
- The rcdata-dc shim was checked on Drupal's CDATA wrapper (comments between CDATA markers aren't
  dropped).

**Exact counts:**
- rcdata is 1,450 in the exact child-node comparison, against 1,449 in the text-and-kinds
  comparison.
- An earlier version gave 327 for rcdata-dc text changes, from a comparison that truncated text to
  400 characters. The exact count is 346.

### Live comparison

- `ff_compare.py` uses Selenium against the Firefox build with `dom.parser.foreign_rawtext.mode`,
  headless, 1366×768, with a 5 s wait. It loads each page twice in mode 0 (A, A2) and once in the
  variant (B).
- `ff_final_diff.py` and `ff_analyze.py` list persistent element and JS-error differences not
  seen between A and A2, and make the crops reviewed by eye.

| Run | Pages | Persistent element change | New JS errors | Visible change |
|---|---|---|---|---|
| rcdata, seeded sample of the 1,444 rcdata pages (`sample-ha-rcdata.jsonl`) | 100 | 85 | 4 React hydration | 1 broken |
| rcdata-dc, same pages | 100 | 85 | 4 React hydration | 0 (one diff was timing noise; a recheck matched) |
| rcdata and rcdata-dc, the 5 unclosed pages | 5 | 5 | 0 | 3 broken, 1 minor |
| raw, seeded raw-only Wix sample (`sample-ha-wix.jsonl`) | 100 | 17 | 0 | 5 worse |

Common Crawl live runs: `out-rcdata-m2`, `out-rcdata-m3`, `out-wix-m1`, `out-rawother-m1`
(`out-final-diff.txt`).

## Not covered

- Desktop and non-root pages, except for `plaintext`.
- Interaction: tooltips weren't hovered.
- States before hydration: only the final state was screenshotted.
- Assistive technology output.
- Other engines.
- Parsers outside browsers, which would need the same change.
- Live runs used a desktop viewport on mobile-crawl pages.

## Query bytes

2026-10-01 crawl, run 2026-10-27: `queries/candidates.sql` 7.29 TB; totals 271 GB; kinds 0.5 GB;
blocks copy 3.2 GB; bodies copy for selected pages 268 GB; `queries/plaintext.sql` (both
clients) 11.2 GB; `queries/breakout-candidates.sql` (restored candidate table) 0.6 GB.
