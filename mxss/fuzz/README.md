# Differential mXSS fuzzer (whatwg/html#11397)

Question: with #11397 (breakout for `textarea`, `xmp`, `iframe`, `noembed`, `noframes`, `plaintext`;
RCDATA for SVG/MathML `title`, `style`, `script`, `noscript`), #6362 (`<`/`>` escaped in
attributes) and #9426 (one scripting flag), is HTML parse, serialize, parse mXSS closed? This
fuzzer looks for counterexamples and, on baseline engines, checks that it can rediscover the known
classes (`mxss/literature.md`, M1 to M16). XML and XHTML are out of scope.

## Files

- `fuzz.js`: generator, oracle, minimizer, all in the page (`window.FZ`). A seeded PRNG makes case
  `i` of a worker a function of `(base seed, i)`; mutation also depends on a corpus, which the
  driver snapshots per batch so crash replays are exact.
- `driver.py`: Selenium start-up (Firefox with binary and pref `dom.parser.foreign_rawtext.mode`,
  Chrome Canary, Safari best effort), one profile directory per instance.
- `run.py`: N parallel workers for one configuration. Append-only logs in
  `mxss/private/runs/LABEL/w<k>.jsonl` (batch stats, minimized findings, errors, crashes). Resumable:
  each worker continues from its last logged case index.
- `campaign.py`: the sequence of configurations. `calibrate.py`: known-bypass seeds.
  `seeds_cc.py`: SVG/MathML blocks from Common Crawl. `bucket.py`, `tables.py`: mechanism buckets and tables. `reap.py`: kills orphaned browsers. `crashcheck.py`: crash replay. `chain*.py`, `topup.py`: run orchestration. `report.py`, `summarize.py`: class tables
  without payloads.

## Oracle

A case is a token list (tags, comments, PIs, CDATA, text, character references, canaries).
Canaries carry unique ids (`X7Q<n>`) and are `img onerror`, `svg onload`, `body onload` or
`script` text, usually prefixed with a closer (`"`, `'`, `-->`, `]]>`, `?>`, `</style>` and so on).

1. T1 = parse(input) in a context: a `DOMParser` document, or `innerHTML` on a context element
   (`div`, `svg`, `math`, `template`, `td`, `select`, `table`, and raw/foreign-raw elements) of a
   document made by `createHTMLDocument`. If T1 has a live canary, the case is discarded. "Live" =
   `onerror`/`onload` carrying a marker on `img`/`svg`/`body`/`iframe`/..., or an element
   `script` whose text is exactly a marker. Template contents are scanned.
2. Optional sanitizer model: prune T1 with a random allowlist of names (optionally namespace
   aware) and attributes; removed elements are dropped or replaced by their children; comments kept
   or dropped.
3. S = serialization (`innerHTML` of the context or of `body`).
4. T2 = parse(S) in a random subset (8) of 30+ contexts: doc, div, body, svg, math, template,
   table, tbody, tr, td, select, foreignObject, mtext, annotation-xml (HTML encoding), SVG title,
   raw and foreign-raw contexts, and "wrap" sinks (`<xmp>`+S+`</xmp>`, same for iframe, noembed,
   noframes, noscript, style, script, textarea, title, select, table, svg, math, template,
   plaintext). Second-order: 30% of cases also serialize/parse again, up to 3 times.
5. FINDING = live canary in T2 (or a later round) but not in T1. The signature is
   `pair class : carrier kind @ carrier element | namespaces of the carrier element's name T1>T2`.
   Pair classes: `same` (T2 context equals T1's, or both HTML body-like), `toHtml`, `toForeign`
   (T2 context is SVG/MathML), `wrap` (sink wrapper), `rawctx` (T1 context is a raw or
   foreign-raw element), `dom` (DOM-built tree).
   Only `same`/`toHtml`/`toForeign` with parser-made T1 trees speak to the proposal directly;
   `wrap`, `rawctx` and `dom` are known not to be closed by it (M6, M9 and
   enumeration rows 19 to 23).
6. Non-security statistic: T2 parsed in T1's context with a different element name multiset,
   grouped by the changed names.

Scripting flag: documents from `DOMParser` have scripting disabled for parse and serialization in
Firefox and Chrome, but Firefox always parses fragments (`innerHTML`) with scripting enabled
(`nsHtml5StringParser::ParseFragment`), unlike Chrome. To emulate #9426, cases containing
`noscript` use only `DOMParser` documents (T1 and T2) in the main runs. Separate `noscriptmix`
runs lift this to measure the pre-#9426 differential (expected to be flagged in every mode).
Serialization is the browser's own, or (calibration only) a JS implementation of the spec
algorithm. It matches Firefox byte for byte (20,000 cases) but not Chrome (7% differ), so Chrome runs use
its native serializer. The `legacy` option drops #6362 escaping, to rediscover pre-#6362 classes.

## Generators

Pure grammar (nested elements with weighted names, mismatched end tags, carriers with
malformed endings, attributes, character references, special characters); mutation of corpus cases
(delete, duplicate, swap, splice, insert fragment) where the corpus keeps cases that produced new
structural non-round-trip classes or findings; seeds (Common Crawl SVG/MathML blocks and the known
bypass inputs) with canaries injected into attribute values, comments and text; targeted
generators: namespace pivots (`form`, `mtext`, `mglyph`, `annotation-xml`, `foreignObject`, `table`,
`template`, `select`...) around a raw/RCDATA element holding a comment, PI, CDATA, bogus comment or
element child with the element's end tag; HTML `script` double escape (`<!--<script>...</script>`)
followed by pivots; DOM-built trees (comment, PI, text, element children in raw/RCDATA elements of
each namespace).

## Minimizer

In page: token-level ddmin, then character-level ddmin, keeping the same signature, then
shrinking the prune allowlist. Findings go to `mxss/private/runs/*/w*.jsonl` only.

## Crashes and hangs

A content-process crash makes the Selenium call hang. The worker restarts the browser, reloads
the batch's corpus snapshot, replays the batch with a per-case index beacon to a local server,
then regenerates the crashing case (`crash` log lines). Where replay doesn't reproduce, the batch
range is skipped.

## Limits of the oracle

- Only canary elements count. Other dangerous constructs (`javascript:` URLs, `srcdoc`, `form`
  actions, CSS, dangling markup, DOM clobbering) are not detected.
- Parser differentials between engines or against server-side parsers are out of scope: all parses
  are in one engine. Old engines and non-conformant serializers are not modelled.
- Nodes the parser cannot produce are covered only by the small DOM-built generator, and
  those cases are not closed by the proposal anyway.
- No `template for`, declarative shadow DOM or HTML PI parsing in the Firefox build; `selectedcontent`
  re-cloning is not modelled; no `document.write` or sanitize-while-parsing.
- Contexts: 8 of 30+ T2 contexts per case; T1 contexts are fewer. Cases with `noscript`
  are restricted to documents in the main runs. The canary alphabet is small; payload closers
  are drawn from a fixed list.
- A clean run is evidence of absence only for what the generator reaches. Calibration shows which
  known classes it reaches; see RESULTS.md.
- Seeds that can't be flagged on any modern baseline (sanitizer-side parser bugs, historic engine
  bugs, DOM-created nodes, parse-time cloning) mark the oracle's scope, not failures.
