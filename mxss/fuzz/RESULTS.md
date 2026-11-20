# Fuzzer results (class level, no payloads)

Oracle, generators and limits: see README.md. Raw logs and minimized repros: `mxss/private/runs/` (git-ignored).
Case counts are cases generated; "tested" excludes cases discarded because T1 already had a live canary or the
canary didn't survive serialization. Scripting flag emulated as in README.md.

## Summary

- Final state, Firefox mode 5c (the implementation of the plan): 0 violations of the direct invariants (I1, I1f, I2, I3) in about 23,500,000
  cases (T1 checked in every parser-built case, the reparses in the 14,265,420 cases that weren't discarded), in documents and the fuzzer's
  fixed lists of fragment contexts. The build makes no PI nodes, so I2 was only exercised on comments. The canary oracle shows only HTML `script` text vs foreign `script` (accepted exception),
  HTML `noscript` across scripting flags (depends on #9426), and the out-of-scope classes (sink wrappers, DOM-built trees, raw
  fragment contexts, sink-context insertion modes, an `image`/`img` identity flip). The sections below are in the order the findings
  came, from mode 4 to 5c.
- Mode 4 (the full proposal) with [#6362](https://github.com/whatwg/html/issues/6362): no finding in the parser-produced HTML-to-HTML space that involves
  text, comment, PI or attribute carriers and a namespace pivot (M1 to M4 classes), in 12,000,000 from-scratch
  cases, 2,000,000 seeded, 3,000,000 targeted. Two other mechanisms still work (below), plus the known
  out-of-scope ones (sink wrappers M6, DOM-built trees M9, fragment parsing into raw or foreign-raw context
  elements, scripting-flag differential M5).
- Baseline Firefox (mode 0) and Chrome Canary rediscover M1, M3/M7-style comment carriers via structure, M4 (comment/PI
  holds the end tag in foreign `title`/`style`/`script`/...), M6, M9 from scratch. M2/M3 attribute carriers
  need pre-[#6362](https://github.com/whatwg/html/issues/6362) serialization (emulated by the JS serializer without `<`/`>` escaping; 2,100,000 cases).
- Known-bypass calibration: all 31 published seeds evaluated; mode 0 flags 15, Chrome 13. Per the seed notes, the 16 seeds mode 0
  misses are mostly outside what a same-engine canary oracle can express: sanitizer-side parser bugs (3 M15, 1 M1), historic
  engine bugs (M12 to M14, 4), a server parser vs a scripting-enabled browser (1 M5), a DOM-created node (M9),
  `selectedcontent` re-cloning (1 M10), and seeds that are structural-only or lack a working gadget (2 M7, 1 M8, M11 with a
  template-engine sink). For one M3 seed the notes give no reason. Chrome also misses one M5 and one M6 seed that mode 0 flags.

## What still worked under mode 4 (class level; history, see mode 5c for the final state)

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

Out of scope (not parse-serialize-parse mismatches of parser output), seen in every mode: sink wrappers (M6), DOM-built trees (M9, foreign RCDATA/raw elements with
comment/PI/element children, row 21), fragment parsing with a raw or foreign-raw context element (rows 19/22), the scripting-flag
differential when the restriction is lifted (M5, `noscriptmix` runs).

Crashes: 23 content-process crashes in Firefox modes 0 and 4 during long batches (17 and 6, collected in
`private/crash-specs.json`); none reproduce when the logged case is replayed alone in a fresh browser in modes 0,
2, 3 or 4 (0 of 23 each), so they look state- or resource-dependent, not input-determined. The current logs also
have one crash each in the mode 2 and mode 3 scratch runs, which weren't replayed.

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
the class table predicts. Pre-[#6362](https://github.com/whatwg/html/issues/6362) emulation (legacy serializer) is used in calibration only.

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
| chrome-seeded | 600,000 | 332,593 | 0 | 0 | 0 | 10,046 (359) | 23,669 (379) | 0 | 0 | 8,993 (251) | 0 | 6,330 (355) |
| ff-m0-selfclose | 3,000,000 | 1,830,911 | 0 | 14 (3) | 0 | 51,951 (364) | 168,867 (408) | 0 | 38 (10) | 157,102 (424) | 0 | 78,199 (350) |
| ff-m3-selfclose | 3,000,000 | 2,443,481 | 0 | 0 | 0 | 54,730 (342) | 35,924 (5) | 1 (1) | 0 | 0 | 0 | 45,221 (90) |
| ff-m4-selfclose | 3,000,000 | 2,493,950 | 0 | 0 | 0 | 54,755 (287) | 50,480 (71) | 0 | 82 (9) | 3 (1) | 0 | 74,163 (147) |
| ff-m0-noscriptmix | 400,000 | 201,098 | 0 | 6 (5) | 0 | 6,904 (305) | 21,078 (389) | 0 | 0 | 10,304 (278) | 0 | 6,970 (351) |
| ff-m2-noscriptmix | 200,000 | 136,263 | 0 | 0 | 0 | 3,663 (268) | 5,079 (6) | 59 (2) | 0 | 21 (9) | 0 | 1,399 (137) |
| ff-m3-noscriptmix | 200,000 | 127,944 | 0 | 0 | 0 | 3,663 (268) | 5,156 (6) | 56 (2) | 0 | 24 (11) | 0 | 1,530 (145) |
| ff-m4-noscriptmix | 400,000 | 268,911 | 0 | 0 | 0 | 7,279 (233) | 13,706 (139) | 276 (6) | 0 | 22 (11) | 0 | 5,375 (236) |
| ff-m0-legacyser | 2,100,000 | 1,090,168 | 0 | 56 (29) | 398 (67) | 36,054 (355) | 87,087 (981) | 0 | 2 (2) | 37,391 (391) | 0 | 33,123 (921) |

chrome-seeded also has 28 cases (1 signature) in `bucket.py`'s `template-for patch (with PI/marker)` bucket: `template for`
patching with a marker PI, not a PI-like carrier.

Run names: `scratch` = pure grammar, targeted and mutation generators, no seeds; `seeded` = Common Crawl SVG/MathML blocks and
the published seeds with injected canaries (4,000 blocks from 4 WARCs of CC-MAIN-2026-39); `selfclose` = targeted
self-closed-breakout generator; `noscriptmix` = noscript allowed in fragment contexts (scripting flag differs);
`legacyser` = serializer without `<`/`>` attribute escaping (pre-[#6362](https://github.com/whatwg/html/issues/6362)).
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
- Patching can create HTML raw/RCDATA elements (`xmp`, `style`, `iframe`, `noembed`, `noframes`, `plaintext`, `script`) as children
  of an SVG or MathML element (needs both a marker PI and `template for`); the same element name is foreign on reparse. Reached in
  every entry point tried.
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

- Corner 1 (self-closed breakout element) is gone: the targeted self-closing run has 0 findings outside the out-of-scope classes
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
| corner 3: HTML `noscript` (scripting off) with raw/comment child vs foreign `noscript`, after an `mglyph`/`table` pivot (DOMParser docs both sides) | 1 (1) | most of 788 (28) | 0 | most of 68 (14) |
| NEW: foreign RCDATA `title` ended early (see below) | 26 cases (6 signatures) | 0 | 0 | 0 |

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

## Mode 5 fixed build (SVG `title` no longer an HTML integration point) with invariant oracle

What the desync was (class level): in fragment parsing with an SVG or MathML context element, SVG `title` was still an HTML integration point in the tree
builder. Characters inside it reconstructed the active formatting elements, so an HTML element ended up inside the foreign RCDATA `title`, and the title's
end tag, already consumed by the tokenizer, was ignored by the tree builder (no HTML element of that name on the stack). The title stayed open with the
tokenizer back in the data state, so a following comment or bogus comment containing the end tag became a child of the title.

Runs on the fixed binary (commit d18f3ac3, mode 5, `--batch 10000`, 3 workers): scratch 12,000,000, seeded 2,100,000, noscriptmix 400,000,
targeted self-closing 3,000,000, targeted desync 3,000,000. The old mode 5 binary was run on the desync generator too (3,000,000).

Invariant oracle (I1 to I3, see README.md):
- Fixed binary: 0 violations of I1 and I3 in any run, in documents and in fragment contexts other than foreign raw ones (svg, g, math, mrow,
  foreignObject, desc, mtext, annotation-xml, div, template, td, select, table...). I2 is violated only when the fragment context element is itself a
  foreign `title`, `style`, `script` or `noscript` (`svgTitle.innerHTML = ...`): the context element's comment child can hold the end tag.
  That is row 22 (fragment parsing with a foreign raw context element; the fragment parser setup is not applied to foreign context
  elements in this build, and the spec text is HTML-only); it is the fragment-context class already seen, but now stated as an invariant violation.
  Violations (T1 or T2 context a foreign raw element; summed over keys, so a case can count more than once): scratch 274,153, seeded 111,891,
  self-closing 39,970, noscriptmix 24,739, desync 207,765.
- Old mode 5 binary, desync run: 3,490 I1 violations (SVG `title` with an element child in svg, `g`, textarea and xmp contexts) plus
  the same fragment-context I2 violations (221,580). The fixed binary has no I1 violations.

Canary oracle on the fixed binary vs old mode 5 (cases, signatures):

| class | fixed scratch | fixed seeded | fixed self-closing | fixed noscriptmix | fixed desync | old desync |
|---|---|---|---|---|---|---|
| corner 1 (self-closed breakout) | 0 | 0 | 0 | 0 | 0 | 0 |
| title desync (comment holding end tag inside foreign title) | 0 | 0 | 0 | 0 | 0 | not separated from unclassified (165 cases, 32 signatures); I1 shows it |
| corner 2 (HTML script text vs foreign script; `<!`, `<?`, double escape) | 1,598 (28) + 33 (2) unclassified | 1,201 (35) | 1 (1) | 399 (7) | 448 (9) | 325 (6) |
| corner 3 (HTML noscript, scripting off, vs foreign noscript; pivots, also under `desc`) | 0 | in 3 (2) | 0 | in 36 (9) | in 6 (4) | 0 |
| DOM-built (M9) | 216,908 (298) | 37,954 (278) | 54,258 (283) | 7,279 (233) | 54,258 (283) | 54,258 (283) |
| sink wrappers (M6) | 50,318 (484) | 16,089 (384) | 127,283 (278) | 6,639 (234) | 20,856 (296) | 24,109 (295) |
| fragment context into raw or foreign-raw element | 185,464 (238) | 38,871 (184) | 35,367 (127) | 10,734 (104) | 20,840 (102) | 21,852 (114) |

Remaining unclassified fixed-binary signatures, all with single-digit case counts except one corner-2 signature with 32 cases: noscript/script corners above; one `image` element-identity flip
(MathML `image` with an `onerror` attribute inside an `annotation-xml` HTML context becomes `img` when reparsed in HTML; not a text carrier); and one
insertion-mode case (HTML `plaintext` text reparsed in a `template` context whose first element `col` switches the insertion mode, so the raw start tag is
ignored: enumeration rows 7/8, a sink-context mismatch). Calibration seeds: 4/31 flagged (M5, M6), unchanged.

## Mode 5c (fragment contexts that are foreign RCDATA elements parse as text) and summary of modes 4 to 5c

Mode 5c binary: commit 5873e678. With a foreign `title`/`style`/`script`/`noscript` context element the fragment parser now sets RCDATA and recognizes no
comments, PIs or bogus comments. `--batch 10000`, 3 workers (peak summed RSS about 27.5 GB). Canary oracle and invariant oracle (I1, I1f, I2, I3) in every run.

Cases: scratch 12,000,000, seeded 2,100,000, noscriptmix 400,000, targeted self-closing 3,000,000, targeted desync 3,000,000, new targeted fragment-context
generator 3,000,000. 31 calibration seeds: 4/31 flagged (M5, M6).

Invariants: 0 violations of I1, I1f, I2 and I3 in any run (T1 in every parser-built case, T2 and later rounds in the 14,265,420 cases that
weren't discarded; documents and the fixed fragment-context lists in `fuzz.js`; comments only, as the build makes no PI nodes). The context-element I2 violations of 5b are gone (calibration probes show
5b violating and 5c passing). A first run of the fragment generator reported 6 I2 violations; all were false positives of the oracle (U+00A0 and U+FEFF after the end tag
name counted as whitespace by JS `\s`, but they are not HTML whitespace, so the tokenizer doesn't end the element); fixed to ASCII whitespace, rerun: 0.

Canary oracle, 5c (cases, signatures) compared with 5b:

| class | 5c scratch | 5c seeded | 5c noscriptmix | 5c desync | 5c frag | 5b scratch |
|---|---|---|---|---|---|---|
| corner 1, title desync, foreign RCDATA context violations | 0 | 0 | 0 | 0 | 0 | desync 0, fragment-context I2 274,153 violations |
| corner 2 (HTML script text vs foreign script) | 1,384 (10) | 771 (15) + 139 (14) unclassified | 228 (6) | 344 (12) | 84 (4) + 223 (2) unclassified | 1,598 (28) + 33 (2) unclassified |
| corner 3 (HTML noscript, scripting off) | 0 | 298 (9) unclassified | within 37 (12) | within 5 (1) | 0 | 0 |
| DOM-built (M9) | 216,903 (298) | 37,954 (278) | 7,279 (233) | 54,258 (283) | 54,258 (283) | 216,908 (298) |
| sink wrappers (M6) | 48,720 (459) | 13,165 (381) | 6,151 (225) | 19,130 (274) | 13,978 (218) | 50,318 (484) |
| fragment context into raw/foreign-raw element, and HTML raw contexts | 166,008 (189) | 33,039 (135) | 8,345 (80) | 13,009 (65) | 236,412 (178) | 185,464 (238) |
| raw start tag ignored by the T2 `colgroup` context (see below) | 0 | 0 | 0 | 0 | 56 (7) | 0 |

Nothing new beyond the known classes. The raw-start-tag-ignored signatures appear only because the new generator uses a `colgroup` context in T2.
The 5c scratch and 5b scratch runs also each have the `template`-context insertion-mode case (1 case) as unclassified.

The two stray signatures, reduced (payload-free probes):
- `image` to `img`: any SVG or MathML fragment context (`svgEl.innerHTML`, `mathEl.innerHTML`, annotation-xml) keeps a foreign `image` element; serialized as
  `<image ...></image>` and reparsed in an HTML context (div sink, or after the foreign wrapper is unwrapped) it becomes an HTML `img`. Foreign `image` with
  an event-handler attribute is the carrier. Known class: element-identity flip with a sink-context mismatch (M6) or removal of the foreign wrapper (M8). Not related to
  the proposal; a sanitizer that drops event handlers is unaffected. Nothing to fix in the proposal. (Per the spec's "start tag token had an `encoding` attribute"
  wording, a context `annotation-xml` is never an HTML integration point, so even `encoding=text/html` contexts keep `image` foreign.)
- raw start tag ignored by a context's insertion mode (enumeration rows 7/8, M6): an HTML raw element (`plaintext`, `xmp`, `style`, `script`, `iframe`, `noembed`, `noframes`) whose
  text contains markup, serialized and reparsed with a `colgroup` or a `template` context where the first element (`col`) switches the insertion mode. The start tag is
  ignored (only `template` survives in column group), so the raw text becomes markup (`template` contents are live to a sanitizer walking `content`). With the breakout,
  `<col><plaintext>...` in a MathML fragment context gives a foreign `col` plus an HTML `plaintext`, so the serialization starts with `<col>` and triggers it
  in a template context. Known sink-context class; the proposal doesn't change it, and it is not something to fix in the proposal.

Summary of modes 4 to 5c (Firefox builds of the proposal; canary oracle, from-scratch 12,000,000 cases each):
- Mode 4: no M1 to M4 class (text, comment, PI or attribute carriers via namespace pivot). Residuals: corner 1 (self-closing breakout element reparsed as breakout, 82 cases in 3,000,000
  targeted), corner 2 (HTML script text vs foreign script), corner 3 (HTML noscript with scripting off vs foreign noscript), plus the by-design classes (M6, M9, fragment contexts).
- Mode 5 (self-closing breakout): corner 1 fixed (0 in 3,000,000 targeted). Found the title desync: a formatting element reconstructed inside foreign `title` (SVG `title` still treated as an
  HTML integration point), the tree builder ignored the title's end tag, a following comment holding the end tag became a child of the title (26 cases in 12,000,000).
- Mode 5b (SVG `title` no longer an HTML integration point): desync fixed (3,490 I1 violations on the old binary in 3,000,000 targeted cases, none on the fixed one). New invariant oracle found
  I2 violations with a foreign RCDATA fragment context element (comment child holding the end tag).
- Mode 5c (foreign RCDATA context elements parse as text): 0 invariant violations in 23,500,000 cases (reparses checked in the 14,265,420
  not discarded). Remaining canary classes are corner 2, corner 3 and the out-of-scope classes.
