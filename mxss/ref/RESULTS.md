# Reference parser results (whatwg/html#11397)

`frnew.py` is html5lib 1.1 with a "new" mode that follows the spec text on
`zcorpan/foreign-rcdata-parse`. `run_dat.py` runs `.dat` files in `old`
(unpatched html5lib), `new` or `both`.

    python3 run_dat.py --mode both --quiet-fails <resources dir>     # about 1 minute, one process
    python3 run_dat.py --mode new --last 63 <dir>/pending-spec-changes.dat
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

## pending-spec-changes.dat, new entries

The 63 new entries (the last 63 in the file) all match on tree. 62 match on error count; the exception is
`<svg><title>&x</title>`, where html5lib reports a stale `expected-named-entity` error that the spec doesn't have (see
"Known deviations"). An earlier draft of the tests failed 8 on error count only: the input ended `<rect></svg>` with
`rect` still open, which gives `unexpected-end-tag` for `</svg>`; the tests now use `<rect/>`.

## Limitations

`<template>` content is not modelled. Foreign fragment contexts (`svg x`, `math x`) get the
spec's tokenizer state and adjusted current node, with the "in body" insertion-mode fallback;
a few pre-existing foreign-fragment error counts (e.g. :3) differ from the .dat for
that reason or because the .dat counts come from another checker.

## Update: "old1" mode and differential check (step 1 parse errors)

`frnew.make_parser("old1")`: today's spec (no foreign RCDATA state, old breakout list, SVG `title` still an
HTML integration point, fragment contexts as before) using the same spec-faithful tokenizer states as "new",
plus the step 1 errors, recorded as `step1-*` codes: `step1-start-tag-in-foreign-rcdata-element` (dispatcher),
`step1-fragment-context-non-start-tag` (fragment paragraph), `step1-foreign-start-tag-html-rawtext`, and
`step1-end-tag-in-comment-cdata-or-processing-instruction` (tokenizer: a `<` in a comment, bogus comment, PI or CDATA
section followed by `/`, the element's name and a delimiter). Parsers are cached per mode, so one parse takes about
0.1 ms.

    python3 differential.py --n 40000 --max-min 500     # about 1 minute of CPU

Corpus: every `#data` in resources/*.dat (1960 distinct) plus 40000 seeded generated tag-soup inputs, each in 11
contexts (document, `div`, `svg`, `math`, `svg title|style|script|noscript`, `math title`, `svg desc`,
`svg foreignObject`): 461552 cases, 0 crashes. A = trees differ between old1 and new; B = old1 has a step1 error.

| | cases |
|---|---|
| A | 269875 |
| B | 263905 |
| A and B | 263894 |
| A without B | 5981 |
| B without A | 11 |

Every A-without-B case already has an ordinary parse error in old1 (0 cases with no error at all, besides a missing
doctype), so "every input whose parse changes has a parse error today" holds on this corpus. Earlier gaps closed in the
step 1 text: markup in fragment parses into a foreign title/style/script/noscript context (the fragment context
paragraph), and a PI or bogus comment that ends at the `>` of the end tag (the balanced input
`<svg><style><?a b</style></style></svg>` had no error at all at first). The comment and PI check is now in the
tokenizer, at the same point where step 2 ends the element, so `<svg><title><!--</title-->` and `<?x </title?>`
(where step 2 parses the same) aren't reported.

The A-without-B cases carry an ordinary tokenizer error; the tree changes but no `step1-*` error is added:
- Start tag cut off by EOF inside the element (`<svg><style><l`): new turns the partial tag into text.
- `</>`, `</` + non-letter (`<svg><title></ `), `<!` (incorrectly-opened-comment), `<?` at EOF.
- NUL in an SVG `title` (today an HTML integration point, so in body drops it; new gives U+FFFD).
- The same constructs in the fragment contexts above.

B without A (11 cases): the parse error for `<![CDATA[</title>` in a fragment with context `svg title` (and
style/script/noscript, `math title`). The fragment parse leaves the flag false, so the CDATA text is the same in both;
the error is reported but the tree does not change (kept on purpose).

## Known deviations of the reference parser (audit)

These don't change any verdict for the 63 new tree construction tests, but they limit what the differential shows:
- Character references go through html5lib's `consumeEntity`, which reports an error for `&foo` and `&;` where the spec
  has none (only `&foo;` is an error). Test entries are checked against the spec, not this.
- NUL inside a CDATA section is replaced with U+FFFD in the tokenizer; the spec leaves it to tree construction (in body
  drops it, foreign content replaces it). So `<svg><title><![CDATA[\0]]>` doesn't show up as a changed tree.
- html5lib still has the "in select" insertion mode, so generated inputs starting with `<select><svg>` never reach foreign
  content; and html5lib's in body "any other end tag" matches by name only, which affects some old1 trees that already
  have a step 1 error.
- Content patching (`template for`) and template contents aren't modelled, so the step 2 patching rules and the step 1
  errors for patches are checked by reading the spec, not here.
- The "no other parse error" check accepts any error html5lib reports, including stale ones; the minimized groups above
  only show errors the spec also has.
- `#errors` + `#new-errors` is the count per the format's README; run_dat.py's default is now `sum` (the baseline table
  above shows both rules; the new entries have no `#new-errors`).

