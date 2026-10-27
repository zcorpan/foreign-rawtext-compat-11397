# Compat impact of parsing SVG/MathML `style`, `script`, etc. like HTML (whatwg/html#11397)

Proposed change: in foreign content, a non-self-closing start tag for `style`, `script`, `title`,
`textarea`, `xmp`, `iframe`, `noembed`, `noframes`, `noscript` or `plaintext` still creates the
SVG/MathML element, but switches the tokenizer the way the HTML element does. Element boundaries
are then the same in every namespace, and namespace-confusion mXSS relies on them differing.
Three variants were measured:

- **raw**: like HTML (RAWTEXT, script data, RCDATA for `title`/`textarea`, PLAINTEXT), and the
  raw text elements' text serializes literally, like the HTML elements.
- **rcdata**: RCDATA for all of them (`plaintext` stays PLAINTEXT). Character references are still
  decoded and serialization is unchanged (escaped), so it round-trips.
- **rcdata-dc**: rcdata, plus everything from `<!--` to the next `-->` inside these elements is
  dropped from the text. An end tag inside still ends the element.

In all three, `<![CDATA[` and the next `]]>` are dropped inside these foreign elements, and
character references aren't decoded between them. Self-closing tags (`<svg><style/>`) keep
today's behavior.

## Summary

- **raw is not web compatible as is.** 578 of 256,037 HTML pages (0.23%) parse differently. 536
  of them are Wix sites, whose server rendering escapes `"` as `&quot;` inside SVG `<style>`
  (`[data-color=&quot;1&quot;]`); today's foreign-content parsing decodes that. Live, Wix
  re-renders most SVGs after hydration, but some stay broken and the icons lose the site's
  colors. That held on 1 of 30 sampled Wix pages
  ([review/raw-wix-spinplaygames.png](review/raw-wix-spinplaygames.png); today left, raw
  right). Emulating the parse without the client-side re-render shows the same effect:
  [review/raw-wix-firststepmenstherapy-emulated.png](review/raw-wix-firststepmenstherapy-emulated.png).
  SVG `<script>` containing `&amp;&amp;` throws a SyntaxError on 2 pages.
- **rcdata changes 28 of 256,037 pages (0.011%)**, and none of them visibly in the live
  comparison. The effects:
  - SVG `<title>` text (tooltip, accessible name) now shows comments or markup that used to be
    nodes: React, Angular, Lit and MotionPoint comment markers, `<sup>`, `</noindex>`, `<?php`.
  - A framework duplicates title text after hydration (kbb.com, xtool.cn).
  - React throws hydration errors #418/#423 and recovers by rendering on the client (reebelo.ca,
    reebelo.com).
  - On 2 pages, CSS wrapped in `<!-- -->` inside SVG `<style>` becomes active (planeo.ch,
    protesolutio.com).
- **rcdata-dc** removes the comment-text and activated-CSS cases. The React hydration errors and
  the kbb.com/xtool.cn duplication remain, because they depend on the comment nodes existing.
  The 4 markup-in-title pages remain too.
- **CDATA**: 117 pages use `<![CDATA[` in SVG `style`/`script`/`title` (362 elements). With the
  markers dropped, 116 of them parse identically; the remaining one differs because of a comment,
  not the CDATA. Without the marker dropping, all 117 would get broken CSS or a script
  SyntaxError.
- **Self-closing**: 125 pages have `<svg><title/>`, `<style/>` or `<script/>`. Treating those as
  start tags would swallow the rest of the page, so the change must keep honoring the slash.
- No page had one of these foreign elements still open at EOF, and none had them in MathML.

## 1. Corpus

HTTP Archive wasn't reachable because the BigQuery credentials had expired;
`queries/candidates.sql` is an unrun draft for a crawl-wide follow-up. The corpus instead is 12
seeded random WARC files of Common Crawl CC-MAIN-2026-39 (`cc/pick_warcs.py`, seed 11397, list in
`cc/warcs.txt`). It covers every HTTP 200 `text/html` response up to 3 MB.

How the corpus was analyzed:

- `cc/frparse.py` patches html5lib to implement each variant.
- `cc/analyze_warc.py` takes every page that has an `<svg`/`<math` tag followed by one of the
  element names, and parses it today's way and with each variant. It then aligns the foreign
  elements of interest and compares their child nodes and child text content.
- `cc/recheck_dc.py` reruns the pages that differ in rcdata with rcdata-dc; only those can differ.

Output files:

- `out-cc/summary.txt`: totals and per-mode counts.
- `out-cc/differs.jsonl`: the differing pages.
- `out-cc/raw-patterns.txt`: the patterns behind the raw-mode differences.
- `out-cc/cdata-and-misc.txt`: the CDATA and self-closing counts.

| | Pages |
|---|---|
| HTML responses | 256,037 |
| with an `<svg` or `<math` tag | 128,124 |
| with an SVG/MathML element of interest | 20,980 |
| differs, raw | 578 |
| differs, rcdata | 28 |

## 2. Live comparison

The live runs use a Firefox build with `dom.parser.foreign_rawtext.mode` (0 today, 1 raw,
2 rcdata, 3 rcdata-dc); `ff_sanity.py` checks that each mode takes effect.

- `ff_compare.py` (Selenium, headless, 1366×768, 5 s wait) loads each page twice in mode 0 (A,
  A2) and once in the variant (B). It records each foreign element's final child nodes, text and
  `cssRules` count, plus JS errors and full-page screenshots.
- `ff_final_diff.py` lists the differences that don't also show up between A and A2
  (`out-final-diff.txt`).
- `ff_analyze.py` makes the pixel diffs and crops, which were reviewed by eye.

One mode-3 run showed a "Server-side rendering timed out" page; a recheck matched mode 0.

| Run | Pages | Persistent element change | New JS errors | Visible change |
|---|---|---|---|---|
| rcdata (mode 2), all rcdata pages | 28 | 20 | 2 React hydration (+1 network) | 0 |
| rcdata-dc (mode 3), same pages | 28 | 19 | 2 React hydration (+1 network) | 0 |
| raw (mode 1), seeded sample of the 536 Wix pages | 30 | 4 | 0 (+1 abort) | 1 |
| raw (mode 1), all 14 other raw-only pages | 14 | 8 | 2 SyntaxError, 2 React hydration (+2 CSP) | 0 |

## Not covered

- Pages Common Crawl doesn't reach.
- Interaction: tooltips weren't hovered.
- Visual changes before hydration: only the final state was screenshotted.
- Assistive technology output.
- Other engines.
- Parsers outside browsers (sanitizers, server-side HTML libraries), which would need the same
  change.

## Reproduce

```sh
python3 -m venv .venv && .venv/bin/pip install warcio html5lib selenium pillow
python3 cc/pick_warcs.py warc.paths.gz 11397 12 > cc/warcs.txt  # warc.paths.gz of CC-MAIN-2026-39
python3 cc/download.py cc/warcs.txt "$DATA"
.venv/bin/python cc/run_all.py cc/warcs.txt "$DATA" out-cc
.venv/bin/python cc/summarize.py > out-cc/summary.txt
.venv/bin/python cc/recheck_dc.py out-cc "$DATA" > out-cc/dc.jsonl
.venv/bin/python ff_compare.py "$FIREFOX" sample-rcdata.jsonl out-rcdata-m2 2   # likewise m3, wix m1, rawother m1
.venv/bin/python ff_final_diff.py out-rcdata-m2 out-rcdata-m3 out-rawother-m1 out-wix-m1 > out-final-diff.txt
```
