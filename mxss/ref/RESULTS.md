# Reference parser results (whatwg/html#11397)

`frnew.py` is html5lib 1.1 with a "new" mode that follows the spec text on
`zcorpan/foreign-rcdata-parse`. `run_dat.py` runs `.dat` files in `old`
(unpatched html5lib), `new` or `both`.

    python3 run_dat.py --mode both --quiet-fails <resources dir>     # about 1 minute, one process
    python3 run_dat.py --mode new --last 34 <dir>/pending-spec-changes.dat
    python3 run_dat.py --mode new --show pending-spec-changes.dat:3 <dir>/pending-spec-changes.dat

Pass means tree equal and parse-error count equal. `#new-errors` repeats the
`#errors` codes in the existing files, so the expected count is
`max(#errors, #new-errors)` by default (`--count sum` adds them). Files with no
`#errors` lines at all (processing-instructions.dat) are compared on tree only.
Scripting is on; `#script-off` entries are skipped.

## Baseline (62 files, 1979 runnable tests)

| | old | new |
|---|---|---|
| pass (tree + count, max rule) | 1387 | 1526 |
| pass (sum rule) | 1204 | 1322 |
| tree equal | 1629 | 1745 |

Old failures are mostly html5lib 1.1 staleness: no `<template>` content
(template.dat 124 fail), no PIs, old comment/CDATA/entity/doctype handling,
select, isindex, error-code counts.

## Old to new differences on pre-existing tests (182 changed in total: 83 in processing-instructions.dat, 24 in pending-spec-changes.dat, the rest listed below)

Intended by #11397 (tests need updating if they stay as written):
- svg.dat 0-4 (`<svg>...<title><tr>`), tests10:35, webkit01:41-43, webkit02:20:
  SVG `title` is no longer an HTML integration point, so its content is text.
- tests18:21-22: `plaintext` is now in the breakout list; `<svg><title><plaintext>` is text.
- foreign-fragment.dat 7, 44, 45 and plain-text-unsafe.dat:43 (context `svg title`):
  foreign title context now uses the RCDATA state (text, NUL becomes U+FFFD).

Not caused by #11397, fixes of html5lib 1.1 staleness against the current spec
(PIs, comment states, CDATA in foreign content, `</p>`/`</br>` in foreign content,
fragment contexts with a foreign adjusted current node): comments01, tests21,
tests26:16-19, tests19:85, tests1:43/46, html5test-com:11-12, plain-text-unsafe:11/12/42/45,
foreign-fragment (fragment-case breakout, 0-2, 18-65), processing-instructions.dat
(tree-ok 40 -> 121 of 123; the two left are `<template>` content).
tests1:39 (`<?`) now has 2 errors (eof-in-processing-instruction) vs 1 expected: PI states
predate #11397.

## pending-spec-changes.dat, last 34 entries

All 34 pass (tree and error count). An earlier draft of the tests failed 8 on error count only: the input
ended `<rect></svg>` with `rect` still open, and the foreign-content "any other end tag" rule gives
`unexpected-end-tag` for `</svg>` then (node `rect`, token `svg`). The tests now use `<rect/>`.

## Limitations

`<template>` content is not modelled. Foreign fragment contexts (`svg x`, `math x`) get the
spec's tokenizer state and adjusted current node, with the "in body" insertion-mode fallback;
a few pre-existing foreign-fragment error counts (e.g. :3) differ from the .dat for
that reason or because the .dat counts come from another checker.

## Update: "old1" mode and differential check (step 1 parse errors)

`frnew.make_parser("old1")`: today's spec (no foreign RCDATA state, old breakout list, SVG `title` still an
HTML integration point, fragment contexts as before) using the same spec-faithful tokenizer states as "new",
plus the step 1 errors, recorded as `step1-*` codes: `step1-start-tag-in-foreign-rcdata-element` (dispatcher),
`step1-foreign-start-tag-html-rawtext`, `step1-comment-contains-end-tag`, `step1-pi-contains-end-tag`,
`step1-end-tag-in-cdata-section`. Parsers are cached per mode, so one parse takes about 0.1 ms.

    python3 differential.py --n 40000 --max-min 500     # about 1 minute of CPU

Corpus: every `#data` in resources/*.dat (1934 distinct) plus 40000 seeded generated tag-soup inputs, each in 11
contexts (document, `div`, `svg`, `math`, `svg title|style|script|noscript`, `math title`, `svg desc`,
`svg foreignObject`): 461261 cases, 0 crashes. A = trees differ between old1 and new; B = old1 has a step1 error.

| | cases |
|---|---|
| A | 269687 |
| B | 263728 |
| A and B | 263711 |
| A without B | 5976 |
| B without A | 17 |

Every A-without-B case already has an ordinary parse error in old1 (0 cases with no error at all, besides a missing
doctype), so "every input whose parse changes has a parse error today" holds on this corpus. Two earlier gaps were
closed in the step 1 text: markup in fragment parses into a foreign title/style/script/noscript context (the fragment
context paragraph), and a processing instruction or bogus comment that ends at the `>` of the end tag, whose data ends
with `</name` without the delimiter (the "ends with" clause; the balanced input
`<svg><style><?a b</style></style></svg>` had no error at all before).

The A-without-B cases carry an ordinary tokenizer error; the tree changes but no `step1-*` error is added:
- Start tag cut off by EOF inside the element (`<svg><style><l`): new turns the partial tag into text.
- `</>`, `</` + non-letter (`<svg><title></ `), `<!` (incorrectly-opened-comment), `<?` at EOF.
- A bogus comment with an invalid-target PI that ends at the `>` of the end tag (`<svg><style><!</Style>`).
- NUL in an SVG `title` (today an HTML integration point, so in body drops it; new gives U+FFFD).
- The same constructs in the fragment contexts above.

B without A (17 cases): `step1-end-tag-in-cdata-section` for `<![CDATA[</title>` in a fragment
with context `svg title` (and style/script/noscript, `math title`). The fragment parse leaves the flag unset, so
the CDATA text is the same in both; the error is reported but the tree does not change (harmless over-report).
The 6 document cases are `<svg><Title><?</title` at EOF: the bogus comment data ends with `</title` because the input
ended, and the tree is the same in both. "Ends with" cannot tell EOF from the end tag's `>`, so truncated input is
over-reported (harmless).
