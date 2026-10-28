# Compat impact of parsing SVG/MathML `style`, `script`, etc. like HTML (whatwg/html#11397)

Proposed change: in foreign content, a non-self-closing start tag for `style`, `script`, `title`,
`textarea`, `xmp`, `iframe`, `noembed`, `noframes`, `noscript` or `plaintext` still creates the
SVG/MathML element, but switches the tokenizer so its contents can't become markup. Then
something that was text in one namespace can't parse as markup after a serialize and reparse puts
it in the other (namespace-confusion mXSS). Three variants, plus a fourth in section 6:

- **raw** (pref mode 1): exactly like the HTML element (RAWTEXT, script data, RCDATA for
  `title`/`textarea`, PLAINTEXT). The raw text elements' text also serializes literally.
- **rcdata** (mode 2): RCDATA for all of them (`plaintext` stays PLAINTEXT). Character references
  are still decoded, and serialization is unchanged (escaped).
- **rcdata-dc** (mode 3): rcdata, plus everything from `<!--` to the next `-->` is dropped from
  the text. An end tag inside still ends the element.
- **rcdata-c** (html5lib only, section 6): rcdata, but `<!--`…`-->` is parsed as a comment node,
  as today. An end tag inside still ends the comment and the element.

All three variants also drop `<![CDATA[` and the next `]]>` inside these elements, and don't
decode character references between them. The element's end tag still ends it even inside the
markers. Self-closing tags (`<svg><style/>`) keep today's behavior.

## Summary

HTTP Archive, 2026-10-01 crawl, mobile, root pages, main documents: 15,360,905 pages.

| | Pages that parse differently | Visible breakage (live sample) |
|---|---|---|
| raw | ~225,800 (1.47%), essentially all Wix | icons recolored on 5/100 Wix pages → ~11,300 pages (95% CI 3,700–25,500) |
| rcdata | 1,449 (0.0094%) | 1/100 → ~14 pages (CI 0–79), plus 3 pages with an unclosed element |
| rcdata-dc | 1,449: 346 (0.0023%) with other changes, 1,103 that lose only comment nodes | 0/100 (CI 0–52), plus the same 3 pages |
| rcdata-c | 348 (0.0023%) | not run live; the DOM matches rcdata-dc's apart from comment nodes, plus the same 3 pages |

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
- **Foreign `script`: script data states or RCDATA?** The HTML script data escape states
  (`<!--` … `<script>` … `</script>` doesn't end the element) would only matter if an SVG
  script's content had `<!--` followed by `<script`. In the fully parsed pages, 97 foreign
  scripts on 47 pages parse differently from today. One has that pattern: an
  `<svg><script xmlns="">` wrapping SVG path markup, which parses the same either way. Script data
  plus decoded character references gives the same text as RCDATA for 93 of the 97; the other 4
  are truncated bodies or character-reference decoding differences (`ha/script_states.py` →
  `ha/script_states.txt`). Today `<!--` in an SVG script is a comment, so the
  `document.write('<script>…')` idiom can't be working in SVG content. RCDATA is enough. It also
  avoids adding character references to the script data states, and it avoids a clash with
  comment dropping, since `<!--` means "escape" in script data. The one boundary difference left
  is HTML `<script><!--<script></script>…`; sanitizers drop `script`, so I don't think mXSS can
  reach it.

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

## 4. HTML `<plaintext>` as a normal raw text element

Question: would ending HTML `<plaintext>` at `</plaintext>` (like `xmp`) be web compatible? Only
pages with `</plaintext` after a `<plaintext>` would change.

- Common Crawl (`cc/plaintext_scan.py` → `out-cc/plaintext.jsonl`): 0 of 255,716 HTML pages have a
  `plaintext` element in static markup. 34 write one with `document.write` to swallow the rest of
  the page: 30 forum pages when framed, 2 mobile-site switchers, 2 others. None has `</plaintext`
  anywhere after it.
- HTTP Archive, 2026-10-01, root pages (`queries/plaintext.sql` → `queries/plaintext.csv`): the
  `element_count` custom metric counts the rendered DOM by tag name, so it includes
  `document.write`. It finds `plaintext` on 6 of 15,366,242 mobile pages and 3 of 11,650,352
  desktop pages, 7 sites in all. In live copies (fetched 2026-10-27), tesera.io has a static
  `<plaintext style="display: none;">`, and toothcorner.com, theatreinminneapolis.com and
  sinexsystems.com use mobile-switcher `document.write`. None has `</plaintext`.
  petugas.haji.go.id served a 1 KB page and scuonlinebanking.com no longer has `<plaintext>`, so
  those two couldn't be checked.
- No SVG/MathML `<plaintext>` occurs in either corpus (`queries/kinds.csv`, `out-cc/summary.txt`).

So no page in either corpus would change. Ending the element at `</plaintext>` also removes the
need for `plaintext` to switch to PLAINTEXT in foreign content.

Why pages write it: none of the uses found is a security feature. Each one stops the rest of the
page from rendering:

- The forum platform writes `</head><body style="display:none"><plaintext>` only when a same-host
  parent that is itself framed embeds the page, which stops the forum from nesting inside itself.
  With a cross-origin parent, reading `parent.document` throws, the error is caught, and nothing
  is written, so it isn't a clickjacking defense.
- The mobile switchers (WompMobile, and 163.com's own) write a hidden `<plaintext>` on phones so
  the desktop page stops parsing and loading, then load the mobile site.
- tesera.io's static one hides leftover loader markup.

What follows `<plaintext>` is always the page's own markup. Where it includes user content
(forum posts), that content renders as normal HTML whenever the condition doesn't hold, so an
early `</plaintext>` gives an injector nothing new.

mXSS: this goes in the opposite direction from #11397. PLAINTEXT is the one mode where nothing in
the text can become markup on a reparse. With an end tag, `plaintext` gets the same weakness as
`xmp` and `style`: text that contains `</plaintext>` breaks out when it's serialized (literally)
and reparsed. Such text can come from DOM APIs, or from today's parsers during the transition:
`<plaintext></plaintext><img src=x onerror=…>` gives text containing `</plaintext><img …>`. The
transition case only bites sanitizers that allow `plaintext`. DOMPurify and sanitize-html don't
by default, and DOMPurify's literal-text guard already removes a `plaintext` whose text looks like
markup.

If the problem is `plaintext` in foreign content, two options keep the namespaces consistent
without adding a vector, and neither corpus has any SVG/MathML `plaintext`:

- keep PLAINTEXT there, as all three modes do;
- make `plaintext` a breakout tag in foreign content (like `p` or `div`), so it's always the HTML
  element.

## 5. Breaking out instead, for elements SVG/MathML doesn't need

Alternative for `textarea`, `xmp`, `iframe`, `noembed`, `noframes` and `plaintext`: make them
break out of foreign content (like `p` or `div`), so they're always HTML elements. `noscript`
can't break out (see below), so it would stay an SVG/MathML element, parsed as RCDATA like the
other elements that stay (`title`, `style`, `script`).

Why RCDATA for the elements that stay: with the escaped serialization foreign elements already
get, RCDATA round-trips (character references are decoded on parsing and escaped on
serializing). In document parsing, HTML parsers following the current spec also read that
serialization back as the same text-only element. The alternatives don't work as well:

- Raw text (like HTML `noscript` with scripting enabled) with escaped serialization doesn't
  round-trip: `&amp;` stays literal text, serializes as `&amp;amp;`, and grows on every
  parse and serialize.
- Raw text with literal serialization (like HTML) round-trips in updated parsers, but current
  parsers turn the literal text back into elements.

- Common Crawl's exact parse has none of these seven as SVG/MathML elements in 256,037 pages
  (`out-cc/summary.txt`).
- HTTP Archive downloaded bodies (`ha/breakout_check.py` → `ha/breakout_check.txt`): 22 SVG
  `noscript` and 15 SVG `iframe`, every `iframe` inside such a `noscript`. They're Google Tag
  Manager's `<noscript><iframe …>` snippet, or WordPress's `<noscript><link …>` font fallback,
  injected just inside a hidden SVG sprite at the start of `<body>`. On 15 of the 22 `noscript`
  elements, SVG content (`symbol`, `g`, gradients) follows. Breaking out of `noscript` would close
  the sprite there and lose its symbols, so the icons using them would disappear. Keeping
  `noscript` in SVG, parsed as RCDATA, turns the snippet into inert text. That matches what it
  does today: an SVG-namespace `iframe` or `link` does nothing.
- HTTP Archive, every root page with `textarea`, `xmp`, `iframe`, `noembed`, `noframes` or
  `plaintext` inside an SVG/MathML block at regex level (`queries/breakout-candidates.sql` on the
  candidate table → `queries/breakout-candidates.json`, 2,987 pages). Fetched live on 2026-10-27
  and parsed today's way (`ha/breakout_live.py` → `out-ha-breakout-live.jsonl`; 27 fetch errors).
  One real SVG/MathML element turned up: an SVG `iframe` embedding YouTube on
  petrovskaja-school.ru, with nothing in SVG after it. Breaking out would make that video load. No
  real SVG/MathML `textarea`, `xmp`, `noembed`, `noframes` or `plaintext` turned up.

Regex recall: `queries/candidates.sql` matches each element with up to 40 characters of
trailing context, which hides an element-of-interest start tag right after it (e.g.
`<noscript><iframe`, `</title><style`). Measured on the Common Crawl pages whose exact parse
differs (`ha/regex_recall.py` → `ha/regex_recall.txt`), it flags 548 of 550 raw-only pages and 26
of 28 rcdata pages. One of the two rcdata misses is an html5lib artifact. So the HTTP Archive
counts in section 1 may undercount by a few percent.

## 6. Keeping comments as comment nodes, and PIs

Variant **rcdata-c**: like rcdata, but `<!--`…`-->` inside these elements is parsed as a comment
node, as today. Between CDATA markers it stays text, as in a CDATA section today. The element's
end tag still ends the comment and then the element. `<!-->` and `<!--->` are empty comments, as
in HTML. html5lib's patch: `cc/frparse.py` (mode `rcdata-c`).

- mXSS: as with rcdata-dc, a comment created by the parser can never contain the element's end
  tag. It serializes literally, and a reparse as the HTML element yields only text.
  `<svg><title>a<!-- </title><img src=x> -->b` gives an `img`, as HTML `<title>` would. A comment
  created through the DOM with the end tag inside can still break out, as in every variant (and as
  text in HTML `style` does today).
- Compat, exact child-node comparison with today on the 7,621 downloaded HTTP Archive bodies
  (`ha/mode_c.py` → `ha/mode_c.txt`, `ha/mode_c.json`):
  - rcdata: 1,450 differ. Section 1's count is 1,449, because it compares text and child kinds rather than exact child nodes.
  - rcdata-dc: 1,449 differ. 346 have changes other than lost comment nodes; 1,103 only lose
    comment nodes; 7 are truncated-body artifacts (`ha/dc_exact.py` → `ha/dc_exact.txt`).
  - rcdata-c: 348 differ, 5 more are truncated-body artifacts, and the other 7,268 match today
    exactly.
- So the 1,103 pages where rcdata-dc only drops comment nodes are identical to today with
  rcdata-c. Those are React's `<!-- -->` text separators, Angular/Lit markers and kbb.com's
  `<!--t.…-->`. The React hydration errors and the duplicated titles seen live in rcdata-dc
  probably come from the missing comment nodes, so they should go away. Not checked in a browser.
- The rest are the same pages rcdata-dc changes beyond comments: tags, PIs and SVG scripts with a
  raw `<` all become text, and unclosed elements swallow the page. One page differs only in a
  comment: on cral.ehess.fr an unclosed `<!--` in SVG `<style>` swallows `</style>` and the
  following SVG paths today. With rcdata-c the comment ends at `</style>` and the paths render.
- Common Crawl: 5 of the 28 rcdata pages still differ with rcdata-c.

Correction: earlier versions of this README gave 327 pages for rcdata-dc text changes. That
metric compared text truncated to 400 characters, which hid changes in long SVG scripts. The
exact count is 346.

PIs (`<?target data?>`, which the spec now parses outside raw text elements) could be kept as
nodes the same way, with the end tag still closing the element. The security argument is the
same as for comments. The benefit is small: PIs occur inside these elements on 11 of the
downloaded HTTP Archive bodies (10 SVG `title`, 1 `style`; `ha/patterns-rcdata.txt`) and on 1
Common Crawl page (`out-cc/pi-and-cdata-endtag.txt`). All of them are unprocessed `<?php … ?>` in
SVG `<title>`, where RCDATA turns them into tooltip text. Today's baseline also varies: engines
without HTML PI parsing (the Firefox build used here) make a bogus comment, while the spec makes a
PI node. Keeping PIs would need PI states inside foreign RCDATA in every parser. Bogus comments
(`<!foo>`), which also make comment nodes today, are rarer still inside these elements.

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
| `queries/plaintext.sql` (both clients) | 11.2 GB |
| `queries/breakout-candidates.sql` (candidate table, restored) | 0.6 GB |
