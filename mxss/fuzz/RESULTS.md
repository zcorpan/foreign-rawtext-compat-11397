# Fuzzer results (class level, no payloads)

Oracle, generators and limits: see README.md. Raw logs and minimized repros: `mxss/private/runs/` (git-ignored).
Case counts are cases generated; "tested" excludes cases discarded because T1 already had a live canary or the
canary didn't survive serialization. Scripting flag emulated as in README.md.

## Summary

- Mode 4 (the full proposal) with #6362: no finding in the parser-produced HTML-to-HTML space that involves
  text, comment, PI or attribute carriers and a namespace pivot (M1 to M4 classes), in 12,000,000 from-scratch
  cases, 2,000,000 seeded, 3,000,000 targeted. Two other mechanisms still work (below), plus the known
  not-addressed ones (sink wrappers M6, DOM-built trees M9, fragment parsing into raw or foreign-raw context
  elements, scripting-flag differential M5).
- Baseline Firefox (mode 0) and Chrome Canary rediscover M1, M3/M7-style comment carriers via structure, M4 (comment/PI
  holds the end tag in foreign `title`/`style`/`script`/...), M6, M9 from scratch. M2/M3 attribute carriers
  need pre-#6362 serialization (emulated by the JS serializer without `<`/`>` escaping; 2,100,000 cases).
- Known-bypass calibration: all 31 published seeds evaluated; mode 0 flags 15, Chrome 13. The remaining seeds are outside
  what a same-engine canary oracle can express (sanitizer-side parser bugs M15, historic engine bugs M12 to M14,
  DOM-created nodes M9, parse-time cloning M10, structural-only seeds M7/M11 without a canary).

## What still works under mode 4 (class level)

1. Self-closed breakout element. In SVG/MathML, `textarea`, `xmp`, `iframe`, `noembed`, `noframes` or `plaintext`
   written self-closing keep today's behavior (stay foreign, empty). The serializer always writes start and end
   tags, so on reparse the element breaks out of the foreign subtree, and the namespace of what follows
   (ancestors popped, later `math`/`foreignObject`/`noscript` re-parented to HTML or MathML) changes. Carrier: text of an
   HTML `plaintext` (or raw element) inside an HTML `noscript` (scripting disabled) in an SVG
   integration point. Pivot: element identity and namespace flip of an ancestor. Same context, DOMParser document to
   DOMParser document, no pruning, 82 cases in 3,000,000 targeted cases (9 signatures), 1 case in 12,000,000 untargeted.
2. HTML `script` text versus foreign RCDATA `script` (enumeration row 5, M16). HTML script data double escape
   (`<!--` then `<script>`), or a `<?`-style bogus comment in script text, is one text node in an HTML `script`; reparsed as
   SVG/MathML `script` (RCDATA, comment and PI nodes split out or the first end tag ends it) the remainder becomes markup or
   the executed text changes. Carrier: HTML script data text. Pivot: namespace of the `script` at parse 2 (foreign
   fragment context, annotation-xml/foreignObject structure, table foster parenting). Needs an HTML `script` that survives
   sanitizing. Also present in modes 2 and 3 (RCDATA without comment nodes), so it is introduced by RCDATA tokenization.
3. HTML `noscript` with scripting disabled versus foreign `noscript` (RCDATA regardless of the flag), with a raw child
   (`xmp`, `plaintext`, `style`...) holding `</noscript>`: a namespace pivot (`mglyph`/`mtext`/`table` foster parenting)
   makes the `noscript` foreign on reparse. Seen in mode 4 seeded runs (2 signatures, 26 cases) in DOMParser documents
   both sides, and in the self-closed runs (3 cases).

Not closed by design, seen in every mode: sink wrappers (M6), DOM-built trees (M9, foreign RCDATA/raw elements with
comment/PI/element children, row 21), fragment parsing with a raw or foreign-raw context element (rows 19/22), the scripting-flag
differential when the restriction is lifted (M5, `noscriptmix` runs).

Crashes: 23 content-process crashes in Firefox modes 0 and 4 during long batches (17 and 6); none reproduce
when the logged case is replayed alone in a fresh browser in modes 0, 2, 3 or 4 (0 of 23 each), so they look
state- or resource-dependent, not input-determined.

## Calibration (known-bypass seeds, flagged / seeds)

| class | seeds | Firefox mode 0 | Chrome Canary | mode 2 | mode 3 | mode 4 |
|---|---|---|---|---|---|---|
| M1 | 3 | 2/3 | 2/3 | 0/3 | 0/3 | 0/3 |
| M2 | 2 | 2/2 | 2/2 | 0/2 | 0/2 | 0/2 |
| M3 | 4 | 3/4 | 3/4 | 0/4 | 0/4 | 0/4 |
| M4 | 1 | 1/1 | 1/1 | 0/1 | 0/1 | 0/1 |
| M5 | 3 | 2/3 | 1/3 | 2/3 | 2/3 | 2/3 |
| M6 | 2 | 2/2 | 1/2 | 2/2 | 2/2 | 2/2 |
| M7 | 3 | 1/3 | 1/3 | 0/3 | 0/3 | 0/3 |
| M8 | 2 | 1/2 | 1/2 | 0/2 | 0/2 | 0/2 |
| M9 | 1 | 0/1 | 0/1 | 0/1 | 0/1 | 0/1 |
| M10 | 2 | 1/2 | 1/2 | 0/2 | 0/2 | 0/2 |
| M11 | 1 | 0/1 | 0/1 | 0/1 | 0/1 | 0/1 |
| M12 | 2 | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 |
| M13 | 1 | 0/1 | 0/1 | 0/1 | 0/1 | 0/1 |
| M14 | 1 | 0/1 | 0/1 | 0/1 | 0/1 | 0/1 |
| M15 | 3 | 0/3 | 0/3 | 0/3 | 0/3 | 0/3 |
| total | 31 | 15/31 | 13/31 | 4/31 | 4/31 | 4/31 |

Notes: modes 2 to 4 still flag M5 (scripting flag, calibration lifts the noscript restriction) and M6 (sink wrappers), as
the class table predicts. Pre-#6362 emulation (legacy serializer) is used in calibration only.

## Runs

Format: cases (distinct signatures) per mechanism bucket; buckets are heuristic regexes on the minimized repro
(`fuzz/bucket.py`). `unclassified` in mode 0 and Chrome are the baseline M1/M4 classes. `rawctx`: T1 context is a raw or
foreign-raw element. `wrap`: sink wrapper. `dom`: DOM-built.

| configuration | cases | tested | crashes | PI-like | attribute carrier | dom | rawctx | script-double-escape vs foreign script | self-closed breakout element, reparsed as breakout | unclassified | unminimized/rawctx | wrap |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ff-m0-scratch | 12,015,451 | 6,384,097 | 7 | 127 (28) | 0 | 207,169 (376) | 392,290 (718) | 0 | 0 | 172,603 (597) | 0 | 90,366 (596) |
| ff-m2-scratch | 12,000,000 | 7,964,475 | 1 | 0 | 0 | 217,368 (354) | 213,252 (6) | 510 (12) | 0 | 0 | 0 | 25,273 (381) |
| ff-m3-scratch | 12,000,000 | 7,653,425 | 1 | 0 | 0 | 217,458 (354) | 212,915 (6) | 520 (12) | 0 | 0 | 0 | 25,190 (368) |
| ff-m4-scratch | 12,000,000 | 7,660,623 | 2 | 0 | 0 | 217,441 (298) | 245,922 (254) | 1,314 (16) | 1 (1) | 0 | 1 (1) | 31,088 (428) |
| chrome-scratch | 2,000,000 | 1,100,017 | 0 | 15 (11) | 0 | 33,394 (426) | 89,185 (506) | 0 | 0 | 42,408 (404) | 0 | 24,999 (465) |
| ff-m0-seeded | 2,000,000 | 1,132,388 | 0 | 4 (1) | 109 (8) | 34,456 (350) | 68,930 (533) | 0 | 0 | 29,209 (457) | 0 | 16,976 (472) |
| ff-m2-seeded | 1,200,000 | 841,035 | 0 | 0 | 0 | 21,804 (320) | 23,321 (6) | 59 (5) | 0 | 0 | 0 | 3,718 (206) |
| ff-m3-seeded | 1,200,000 | 795,066 | 0 | 0 | 0 | 21,804 (320) | 23,590 (6) | 87 (7) | 0 | 0 | 0 | 4,085 (215) |
| ff-m4-seeded | 2,000,000 | 1,377,539 | 0 | 39 (4) | 0 | 36,288 (274) | 43,390 (141) | 266 (6) | 12 (2) | 26 (2) | 0 | 7,965 (294) |
| chrome-seeded | 600,000 | 332,593 | 0 | 28 (1) | 0 | 10,046 (359) | 23,669 (379) | 0 | 0 | 8,993 (251) | 0 | 6,330 (355) |
| ff-m0-selfclose | 3,000,000 | 1,830,911 | 0 | 14 (3) | 0 | 51,951 (364) | 168,867 (408) | 0 | 38 (10) | 157,102 (424) | 0 | 78,199 (350) |
| ff-m3-selfclose | 3,000,000 | 2,443,481 | 0 | 0 | 0 | 54,730 (342) | 35,924 (5) | 1 (1) | 0 | 0 | 0 | 45,221 (90) |
| ff-m4-selfclose | 3,000,000 | 2,493,950 | 0 | 0 | 0 | 54,755 (287) | 50,480 (71) | 0 | 82 (9) | 3 (1) | 0 | 74,163 (147) |
| ff-m0-noscriptmix | 400,000 | 201,098 | 0 | 6 (5) | 0 | 6,904 (305) | 21,078 (389) | 0 | 0 | 10,304 (278) | 0 | 6,970 (351) |
| ff-m2-noscriptmix | 200,000 | 136,263 | 0 | 0 | 0 | 3,663 (268) | 5,079 (6) | 59 (2) | 0 | 21 (9) | 0 | 1,399 (137) |
| ff-m3-noscriptmix | 200,000 | 127,944 | 0 | 0 | 0 | 3,663 (268) | 5,156 (6) | 56 (2) | 0 | 24 (11) | 0 | 1,530 (145) |
| ff-m4-noscriptmix | 400,000 | 268,911 | 0 | 0 | 0 | 7,279 (233) | 13,706 (139) | 276 (6) | 0 | 22 (11) | 0 | 5,375 (236) |
| ff-m0-legacyser | 2,100,000 | 1,090,168 | 0 | 56 (29) | 398 (67) | 36,054 (355) | 87,087 (981) | 0 | 2 (2) | 37,391 (391) | 0 | 33,123 (921) |


Run names: `scratch` = pure grammar, targeted and mutation generators, no seeds; `seeded` = Common Crawl SVG/MathML blocks and
the published seeds with injected canaries (4,000 blocks from 4 WARCs of CC-MAIN-2026-39); `selfclose` = targeted
self-closed-breakout generator; `noscriptmix` = noscript allowed in fragment contexts (scripting flag differs);
`legacyser` = serializer without `<`/`>` attribute escaping (pre-#6362).
Totals per Firefox mode (all labels): mode 0 19,515,451, mode 2 13,400,000, mode 3 16,400,000, mode 4 17,400,000 cases.

## PIs and `template for` in Chrome Canary 160 (baseline, no proposal)

Runs (`--batch 10000`, 3 workers): `chrome-nopitf` 4,050,000 cases (no PI or `template for` tokens), `chrome-pitf` 4,050,000 (half the cases are
PI/template-for constructs; 458,000 cases contained a `template for` that patched), `chrome-pitf-focus` 1,500,000 (95% PI/template-for;
337,000 patched). Extra T2 entry points: `parseHTMLUnsafe`, `setHTMLUnsafe`, `document.write`.

Conclusions:
- PIs alone add no mXSS class. No finding needs PI parsing without `template for`. Of the 18 minimized finding signatures that contain a PI but no
  patching, all still produced a finding after replacing `<?` by `<!`, so the PI was incidental. Correction (added later): today's parser can make a PI whose data holds `</name`
  followed by whitespace or `/`, which after the serializer's `?>` is an end tag for a parser that implements the proposal; that is the
  stored-content class, not covered by this baseline run (see mxss/README.md). Data that only ends in `</name` is defused by the
  serializer's `?`. In this baseline no case became live. PIs are text inside RCDATA/RAWTEXT, so within one engine there is no PI-vs-bogus-comment pivot.
- Parser-made PIs round-trip: 29 PI shapes in 16 containers (div, svg, math, foreign title/style/script, select, table, tr, p,
  template, head, frameset, HTML title/style/textarea): no changes in target or data. Mismatches in the fuzz runs have three causes:
  PIs that are children of the Document or `head` aren't in `body.innerHTML`; marker and range-marker PIs are consumed by patching (so counts
  differ when patching succeeds in one parse and not the other); and the `frameset` document has no `body`. DOM-built PIs whose data contains `>` or ends with `?`
  don't round-trip, as before (row 15, M9).
- `template for` adds one mechanism, class M10 in `literature.md` realised in practice: the patch inserts HTML-parsed content under the marker's parent without
  re-running namespace or content-model rules. Verified shapes (class level): HTML elements (`b`, `div`, `xmp`, `style`, ...) as children of
  SVG/MathML elements, including foreign `title` and `style` (together with comment and text children); any element directly under `select`,
  `table`, `tbody`, `tr` (no foster parenting, no select content model). Range markers delete the nodes between `start` and `end`.
  Nested patching in template contents works when the inner marker is inside; a second template for a consumed marker doesn't patch.
- The new finding class (needs both a marker PI and `template for`): HTML raw/RCDATA elements (`xmp`, `style`, `iframe`, `noembed`, `noframes`,
  `plaintext`, `script`) as children of an SVG or MathML element, created by a patch. Carrier: text of the HTML raw element. Pivot: the
  parent is foreign, so on reparse the same element is foreign and its text is markup (M1 mechanism, supplied by patching instead of
  `form`/`mglyph`). Seen with the DOMParser document as both T1 and T2 (`same`), HTML to HTML (`toHtml`), and foreign contexts; 52 distinct
  signatures across the two PI runs (20 and 32), 1,517 finding cases (458 and 1,064). Marker parents in the minimized findings: SVG and MathML elements (including
  `textarea`, `style`, `plaintext` under foreign parents). Reached in every entry point tried. It doesn't involve a foreign raw
  element with PI/comment children, so it is M1 via M10, not M4.
- Patches that introduce nodes the parser can't produce: yes (see the shapes above). For foreign `title`/`style`/`script`, a patch can add
  comment, PI and element children; in baseline Canary foreign `title`/`style` are markup, so these serialize and reparse to the same tree.
  They become row-21 trees under RCDATA tokenization of foreign `title`/`style`/`script`/`noscript` (the proposal), and I could not test
  that in Chrome. Whether a patch can change the namespace/context of markup: yes, template contents are tokenized as HTML and inserted under
  the marker's parent regardless of its namespace; I did not see a patch change the namespace of an element already in the tree.
- Marker PIs that are not consumed in parse 1 (template before the marker, unquoted `name`)
  can be consumed in parse 2, or vice versa; so patching itself is not idempotent under serialize and reparse. I saw this as PI count
  mismatches only; no canary became live through it alone.
- Baseline comparison: `chrome-nopitf` and `chrome-pitf` have the same baseline classes (M1, M3/M7-style comment carriers, M4, M6, M9, rawctx);
  the only extra signatures in `chrome-pitf` are the `template for` ones above.

## Mode 5 (mode 4 plus self-closing breakout)

Binary: copy of the mode 4 build plus the six breakout elements (`textarea`, `xmp`, `iframe`, `noembed`, `noframes`, `plaintext`)
breaking out of foreign content even when self-closing (commit 58df02c3). `--batch 10000`, 3 workers.
Cases: scratch 12,000,000, seeded 2,100,000, noscriptmix 400,000, targeted self-closing 3,000,000, plus the 31 calibration seeds.
Mode 4 had 12,000,000 / 2,000,000 / 400,000 / 3,000,000 under the same configurations (mode 4's batch size was 100,000).

- Corner 1 (self-closed breakout element) is gone: the targeted self-closing run has 0 findings outside the not-closed-by-design classes
  (mode 4: 82 cases in 9 signatures), and scratch has 0 (mode 4: 1). `same`, `toHtml` and `toForeign` classes are empty in that run.
- Calibration: mode 5 flags 4/31 seeds, the same ones as modes 2 to 4 (M5 and M6).
- `plaintext` serialization (writes `</plaintext>`, reparses as text) produces no finding on its own: no `plaintext` signature appears
  outside the noscript/pivot cases of corner 3, the sink-wrapper and fragment-context classes.

Remaining signature classes in mode 5 (cases, signatures):

| class | scratch | seeded | selfclose | noscriptmix |
|---|---|---|---|---|
| sink wrappers (M6) | 40,541 (429) | 12,184 (358) | 101,171 (144) | 5,906 (203) |
| DOM-built (M9) | 216,908 (298) | 37,954 (278) | 54,258 (283) | 7,279 (233) |
| raw/foreign-raw fragment context | 241,920 (273) | 49,545 (193) | 43,662 (85) | 14,902 (120) |
| corner 2: HTML `script` text vs foreign `script` (double escape, `<!`/`<?` prefixes) | 1,113 (9) | 134 (8) + 108 (1) | 0 | 193 (5) |
| corner 3: HTML `noscript` (scripting off) with raw/comment child vs foreign `noscript`, after an `mglyph`/`table` pivot (DOMParser docs both sides) | 0 | most of 788 (28) | 0 | most of 68 (14) |
| NEW: foreign RCDATA `title` ended early (see below) | 27 cases (about 6 signatures) | 0 | 0 | 0 |

NEW class, not in the earlier corners: tokenizer/tree-builder desync on the end tag of a foreign RCDATA element. Fragment parsing with an SVG
or MathML context element (`svgEl.innerHTML = ...`), a formatting element (`a`, `strong`, ...) left open by an earlier `</p>`, then a foreign `title`:
the formatting element is reconstructed inside the title, so the current node is an HTML element. The title's end tag ends the
tokenizer's RCDATA state, but the tree builder ignores the end tag (no HTML element named `title` on the stack), so the title stays open and a
following comment or bogus comment, which holds that end tag, becomes a child of the title. The parser has produced a comment inside a foreign RCDATA
element that holds the element's end tag, which the proposal's rule is meant to rule out. Serialized and reparsed, the end tag ends the comment and the title, and
the markup after it is live (`toHtml`, `toForeign`, different T2 contexts, all with an SVG fragment context for T1). The same tree shape already appears in mode 0
and Chrome (formatting element and comment inside a foreign title), where it is harmless because foreign title is markup. A mode 4 binary isn't available any more,
and the 12M mode-4 scratch run didn't produce it, so whether mode 4 shows it is unconfirmed (it shares the tree builder). Likely an implementation or spec gap (the
tree builder must close the element when the tokenizer's appropriate end tag ends RCDATA); I didn't test other elements (`style`, `script`, `noscript`) separately.
