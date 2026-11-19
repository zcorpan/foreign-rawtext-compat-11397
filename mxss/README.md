# Does whatwg/html#11397 close HTML mXSS?

Question: with #11397 (the proposal in the top-level README), #6362 (`<` and `>` escaped in attribute values)
and #9426 (the scripting flag independent of the document), is parse-serialize-parse mXSS in HTML closed, or is
there another root cause left? Out of scope: XML vs HTML, charset/encoding confusion, DOM clobbering, CSS and URL
schemes.

All files here are class-level, with no working markup. Fuzzer logs, minimized repros and seed vectors are
in `mxss/private/` (git-ignored).

## Answer

**Not quite the last one.** The proposal closes the class that every published post-#6362 bypass relied on:
text, comment, PI or attribute carriers hiding markup in raw text or RCDATA, with a namespace pivot changing how
the element's end tag is read. In 17.4M Firefox cases with the full proposal there is no finding of that kind. It
leaves three parser-producible corners, two of which the spec PR can close:

| # | Corner | Introduced by proposal? | Closable in the spec PR? |
|---|---|---|---|
| 1 | Self-closing `textarea`, `xmp`, `iframe`, `noembed`, `noframes` or `plaintext` in SVG/MathML stays foreign and empty, but serializes with start and end tags, so on reparse it breaks out and what follows changes namespace. Verified by hand: `<svg><xmp/><rect/></svg>` round-trips today, not under the proposal | yes | yes: break out regardless of the self-closing flag. Compat cost looks nil: the live check of 2,987 candidate pages found no real SVG/MathML element of these six, self-closing or not, except one non-self-closing `iframe` |
| 2 | HTML `script` text (script data double-escape, or `<?`/bogus-comment prefix) vs foreign RCDATA `script`: one text node in HTML, split at the first end tag after a namespace pivot. Needs a sanitizer that keeps `script`. Also appears in the RCDATA-only modes | yes | accepted as an exception (decided): closing it would need script data states with character references, which makes `<!--` text in SVG scripts, or about 10 or more new states for comment nodes that track the double-escape state. Sanitizers that keep `script` must reject text containing `<!--` or `<script`, and drop its element, comment and PI children |
| 3 | HTML `noscript` parsed with scripting off (markup children) vs foreign `noscript` (RCDATA always), after a namespace pivot | partly: #9426 fixes it inside one browser; server-side libraries that default to scripting off still differ | depends on #9426's final text |

Also found by reading the spec (not reproduced: the build has no PIs, `template for` or declarative shadow DOM):
`template for` patching can put a comment or PI node into a foreign RCDATA element, and a comment from a patch
(parsed outside the element) can contain the end tag; the spec needs a rule keeping patches out of these elements.
Fragment parsing with a foreign context element (`title`, `style`, `script`, `noscript`; the six breakout elements)
must be namespace-aware.

Not addressed by any parser change, and present in every configuration including today's:
- DOM-built trees the parser can't produce (comment data with `-->`, PI data with `>`, raw text with its end tag),
  which the serializer emits literally. A serializer guard is a separate issue.
- Sink-context mismatch: output inserted inside a raw-text wrapper the application adds.
- Browser-generated DOM after a sanitizer walk (`selectedcontent`, `template for`, shadow DOM).
- Sanitizer-side parser or serializer non-conformance.
- Structural pivots (form nesting, foster parenting): they remain, but with no raw-text carrier they only
  rearrange structure.

Confidence (the enumeration's estimate, adjusted for the fuzz results): about 90% that the namespace-confusion
class is closed once corners 1 and 2 are handled; about 70% that corners 1 to 3 and the spec-reading items are the only other
parser-producible sources. Everything above applies only to updated engines; stored or server-sanitized content
stays exposed to the old classes until old browsers go away (see "Transition risk" in the top-level README).

## Evidence

| Method | What | Files |
|---|---|---|
| Literature catalog | 16 root-cause classes (M1 to M16), 2013 to 2026, with status under today / #6362 / #9426 / the proposal | `literature.md` |
| Spec enumeration | every place the serializer is not the exact inverse of the parser for parser-built and DOM-built trees; recent features | `enumeration.md` |
| Differential fuzzer | canary oracle: a live canary element in the reparse that wasn't live in parse 1 | `fuzz/README.md`, `fuzz/RESULTS.md` |

Fuzzer, Firefox with `dom.parser.foreign_rawtext.mode` (0 today, 2 RCDATA, 3 RCDATA with comments dropped, 4 the
full proposal): about 19.5M, 13.4M, 16.4M and 17.4M cases; Chrome Canary 2.6M baseline cases. Generators:
grammar-based tag soup, mutation, real-page seeds, and dedicated ones for namespace pivots, script double-escape,
self-closing breakout, foreign fragment contexts and DOM-built trees. 30+ reparse contexts, up to three rounds, a
sanitizer-pruning model, and a JS serializer for emulating pre-#6362 output.

Calibration (what a "no finding" is worth):
- Known published seeds: of 31 vectors, mode 0 flags 15 and Chrome 13. Modes 2, 3 and 4 flag 4 (the noscript and sink-context
  seeds only). The other 16 are outside what a same-engine canary oracle can express (sanitizer-side bugs, historic engine bugs,
  DOM-built nodes, structural-only seeds).
- From scratch with no seeds, today's Firefox and Chrome rediscover namespace-pivot findings by the hundreds of thousands (about
  168,000 in 12M cases in mode 0), so the fuzzer has power. In mode 4 that class falls to HTML `script` text
  (~1,300) plus the self-closing corner above.
- The fuzzer rediscovered corner 2 independently of the spec enumeration, which predicted it.

Limits:
- Canary elements only: no `javascript:` URLs, CSS, or clobbering.
- One engine per case; no Safari run.
- This build has no HTML PI parsing, `template for` or declarative shadow DOM, and the PI handling in mode 4
  treats `<?…>` as a bogus comment.
- 8 of 30+ reparse contexts are tried per case.
- 23 content-process crashes in long batches (17 in mode 0, 6 in mode 4) that don't reproduce when replayed
  alone.

## Suggested changes to the proposal

1. Break out the six elements regardless of the self-closing flag (corner 1).
2. Corner 2: document it as an exception, and have the outreach tell sanitizers to reject `script` text containing
   `<!--` or `<script` even when the config allows `script` (the opt-in serializer mode omits such text too, and drops element, comment and PI children of `script`: a nested `script` element's end tag would end an HTML `script` early). The
   Sanitizer API's safe methods remove `script` regardless of the config, so they need no change.
3. Add a rule that `template for` patching never inserts comments, PIs or elements into a foreign RCDATA element.
4. Make fragment parsing's context-element handling namespace-aware for these elements.
5. Corner 3: define #9426 so only a browser whose user or sandbox actually disabled scripting parses with the flag off,
   and everything else (including `DOMParser`, `createHTMLDocument`, fragment parsing and server-side parsers)
   parses with scripting enabled. Tell sanitizer maintainers to parse with scripting enabled and drop `noscript`,
   because a scripting-disabled user's browser reads its children as markup the sanitizer saw as text.
