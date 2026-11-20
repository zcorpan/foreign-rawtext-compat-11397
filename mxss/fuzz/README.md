# Differential mXSS fuzzer ([whatwg/html#11397](https://github.com/whatwg/html/issues/11397))

Question: with [#11397](https://github.com/whatwg/html/issues/11397) (breakout for `textarea`, `xmp`, `iframe`, `noembed`, `noframes`, `plaintext`;
RCDATA for SVG/MathML `title`, `style`, `script`, `noscript`), [#6362](https://github.com/whatwg/html/issues/6362) (`<`/`>` escaped in
attributes) and [#9426](https://github.com/whatwg/html/issues/9426) (one scripting flag), is HTML parse, serialize, parse mXSS closed for trees the parser builds? This
fuzzer looks for counterexamples and, on baseline engines, checks that it can rediscover the known
classes (`mxss/literature.md`, M1 to M16). XML and XHTML are out of scope.

## Memory warning

Each Firefox worker's memory grows with the batch size, because the page keeps the batch's cases, the corpus and
the statistics. On a 48 GB Apple silicon machine, one worker (mode 4, summed RSS of all its processes, which
double-counts some shared pages) reached about 23 GB with the default `--batch 100000` and plateaued around
6.5 GB with `--batch 10000`. Four workers at the default would not fit in 48 GB, and a long campaign that also
runs a build can exhaust memory and crash macOS (two such crashes happened while this was developed; the
cause was not confirmed, but the numbers match). Before running it for hours:
- use `--batch 10000` or smaller, and 2 to 4 workers, and keep total RSS under about half of RAM
  (`ps -axo rss,command | grep firefox`);
- don't run it next to a build;
- an interrupted run leaves Firefox processes behind: `reap.py` kills them. Older versions of the driver
  leaked a browser each time a worker restarted after a crash or hang; the current driver reaps them.

Firefox mode 5 build, 3 workers at `--batch 10000`: summed RSS of all Nightly processes peaked at about 26 GB
(same caveats; roughly 8-9 GB per worker, so keep to 3 workers on a 48 GB machine). The fixed mode 5 builds peaked at about 24.6 GB (5b) and 27.5 GB (5c).

Chrome Canary 160 (headless, 3 workers, `--batch 10000`): summed RSS of all Canary processes peaked at about
9.4 GB (about 3 GB per worker; the sum double-counts shared pages and includes any other Canary on the machine).
`memwatch.py OUT` logs it every 15 s. Chrome workers use `--user-data-dir` under `mxss/private/profiles/`.

Batch size changes which cases a label generates, so keep the same `--batch` when resuming a label.

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
   `wrap`, `rawctx` and `dom` are out of scope for it (M6, M9 and
   enumeration rows 19 to 23): not parse-serialize-parse mismatches of parser output.
6. Non-security statistic: T2 parsed in T1's context with a different element name multiset,
   grouped by the changed names.

Scripting flag: documents from `DOMParser` have scripting disabled for parse and serialization in
Firefox and Chrome, but Firefox always parses fragments (`innerHTML`) with scripting enabled
(`nsHtml5StringParser::ParseFragment`), unlike Chrome. To emulate [#9426](https://github.com/whatwg/html/issues/9426), cases containing
`noscript` use only `DOMParser` documents (T1 and T2) in the main runs. Separate `noscriptmix`
runs lift this to measure the pre-[#9426](https://github.com/whatwg/html/issues/9426) differential (expected to be flagged in every mode).
Serialization is the browser's own, or (calibration only) a JS implementation of the spec
algorithm. It matches Firefox byte for byte (20,000 cases) but not Chrome (7% differ), so Chrome runs use
its native serializer. The `legacy` option drops [#6362](https://github.com/whatwg/html/issues/6362) escaping, to rediscover pre-[#6362](https://github.com/whatwg/html/issues/6362) classes.

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
  those cases are out of scope for the proposal anyway.
- No `template for`, declarative shadow DOM or HTML PI parsing in the Firefox build; `selectedcontent`
  re-cloning is not modelled; no `document.write` or sanitize-while-parsing.
- Contexts: 8 of 30+ T2 contexts per case; T1 contexts are fewer. Cases with `noscript`
  are restricted to documents in the main runs. The canary alphabet is small; payload closers
  are drawn from a fixed list.
- A clean run is evidence of absence only for what the generator reaches. Calibration shows which
  known classes it reaches; see RESULTS.md.
- Seeds that can't be flagged on any modern baseline (sanitizer-side parser bugs, historic engine
  bugs, DOM-created nodes, parse-time cloning) mark the oracle's scope, not failures.

## PIs and `template for` (Chrome Canary, [whatwg/html#12118](https://github.com/whatwg/html/issues/12118) and [#11818](https://github.com/whatwg/html/issues/11818))

Entry points that parse HTML PIs as nodes and patch `template for` in Canary 160: `DOMParser`, `innerHTML` (fragment parsing,
any context element), `setHTMLUnsafe`, `Document.parseHTMLUnsafe`, `document.write` into a `createHTMLDocument` document, and
`iframe` `srcdoc`. They behave the same, so the fuzzer uses `DOMParser`/`innerHTML` for T1 and adds `u:doc`
(`parseHTMLUnsafe`), `u:h:div` (`setHTMLUnsafe`) and `dw` (`document.write`) as extra T2 entry points (`cfg.t2extra`).
Navigation and `srcdoc` were not needed. Facts checked by hand (payload-free probes):
- A PI ends at the first `>`; target must be an ASCII-letter name (`<?-x y?>`, `<?1 y?>`, `<?x:y z?>`, `<??>`, `<?>`, `<?x/>`, `<?xml ...?>`
  become bogus comments); `<?x?`, at EOF swallows the rest of the input; a trailing `?` in the data is dropped. PIs aren't created
  inside RCDATA/RAWTEXT (`title`, `textarea`, `style`, `script`, `xmp`...), where they are text.
- Patching happens while parsing: when a `template` start tag with `for` is seen, the marker is looked up among the descendants of the
  adjusted insertion location's parent. The marker must come before the template in the tree (a template before the marker stays
  an ordinary template). Marker names need a quoted `name="m"` value. The template contents are tokenized and tree-built as HTML and inserted
  in place of the marker (or between `<?start ...?>` and `<?end?>`), under whatever parent the marker has. The first template to match
  consumes the marker.

Generators (`cfg.pPitf`, kind `pitf`): PI shapes with canaries in the target, the data, and around `>`/`?>`; marker PIs (case, quoting,
unquoted, odd names); range markers; `template for` with comments, PIs, elements, raw elements, text and nested templates; markers inside
foreign `title`/`style`/`script`/`noscript`/`textarea`, `select`, table family, `template`; templates before and after the marker; several
templates per marker. The oracle is unchanged (T1 = patched tree), plus: PI node counts and `(target, data)` multisets compared in the same
context (`piRT`, with causes), patched/unpatched counts, and an ablation (`ablate.py`) that replaces `<?` by `<!` and `for` by `data-for`
and re-evaluates each minimized finding to see whether PI parsing or patching is necessary. `tfclass.py` summarizes marker parents and
patched node kinds. `pi_roundtrip.py` runs a fixed table of PI shapes in 16 containers. `cfg.noPitf` removes `<?` tokens and `template for`
from every generator (baseline).

## Direct invariants (I1 to I3)

Besides the round-trip canary oracle, every parse (T1 and each T2, any context, including fragment parsing into any context
element) is checked directly, without serializing:
- I1: a foreign (SVG/MathML) `title`, `style`, `script` or `noscript` has only text, comment and PI children. I1f (fragment case): after
  parsing into such a context element, its children are only text.
- I2: no comment or PI child of such an element has data containing `</` + the element's name (ASCII case-insensitive) followed by
  ASCII whitespace (tab, LF, FF, CR, space), `/` or `>` (not JS `\s`: NBSP and BOM are not HTML whitespace; an early version used `\s` and
  flagged 6 false positives).
- I3: no foreign `textarea`, `xmp`, `iframe`, `noembed`, `noframes` or `plaintext` element exists (the context element itself is exempt).
Violations are counted per key `T1@ctx|I..:ns:name:kind` / `T2@ctx|...` in the batch stats (`inv`) and the first case per key is minimized
(`sig` starts with `inv:`; log entries have `invKind`). DOM-built cases are not checked. Not observable from the DOM, so not
recorded: a foreign RCDATA element still open at EOF while the tokenizer is back in the data state.
Calibration (`private/invcal.py`, payload-free probes): the invariant oracle flags the old mode 4/5 binary on the desync repro (I1) and
mode 4 on a self-closing foreign `xmp` (I3); mode 0 violates I1 to I3 on foreign title/textarea/xmp/plaintext/comment cases (detection power
only); the fixed mode 5 binary passes all of them.

Desync generator (`cfg.tk = "desync"`, also 18% of the default targeted generator): formatting elements and adoption agency / foster parenting /
table, select and template shapes left open, closers, integration points, then a foreign `title`/`style`/`script`/`noscript`
(also `textarea`/`xmp`), its end tag, and comments, PIs, CDATA and bogus comments holding that end tag; T1 contexts include
`svg`, `math`, `g`, `mrow`, `foreignObject`, `desc`, `mtext`, `annotation-xml` and documents.

Fragment-context generator (`cfg.tk = "frag"`): T1 and T2 contexts from a list of 41 context elements (foreign and HTML title/style/script/noscript, textarea,
xmp, iframe, noembed, noframes, plaintext, foreignObject, desc, mtext, annotation-xml, template, select, table family, colgroup, head, frameset, ...), content
made of comments (also unclosed), PIs, bogus comments, CDATA markers, end tags of raw/RCDATA names, character references, nested and unclosed constructs.
