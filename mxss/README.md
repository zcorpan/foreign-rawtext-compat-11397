# Does [whatwg/html#11397](https://github.com/whatwg/html/issues/11397) close HTML mXSS?

Question: with [#11397](https://github.com/whatwg/html/issues/11397) (the proposal in the top-level README), [#6362](https://github.com/whatwg/html/issues/6362) (`<` and `>` escaped in attribute values)
and [#9426](https://github.com/whatwg/html/issues/9426) (the scripting flag independent of the document), is parse-serialize-parse mXSS in HTML closed, or is
there another root cause left? Out of scope: XML vs HTML, charset/encoding confusion, DOM clobbering, CSS and URL
schemes.

All files here are class-level, with no working markup. Fuzzer logs, minimized repros and seed vectors are
in `mxss/private/` (git-ignored).

## Answer

**Yes, for parser-built trees.** With the plan below, no text, comment, PI or attribute value that is inert in one
parse of HTML can become markup in the next, in every context we tried, for trees the parser builds (including
`template for` patches), apart from the two accepted exceptions listed under Scope. The proposal itself closes the class
that every published post-[#6362](https://github.com/whatwg/html/issues/6362) bypass relied on: markup hidden in raw text or RCDATA, with a namespace pivot changing how
the element's end tag is read. Fuzzing and a spec enumeration found a few gaps in the first version of the proposal; the
plan includes their fixes, and "How we got here" below shows how.

**The plan** (reasoning in "The plan in detail"):
- [#11397](https://github.com/whatwg/html/issues/11397)'s tokenization: SVG/MathML `title`, `style`, `script` and `noscript` are RCDATA, with comments and PIs kept as
  nodes (the element's end tag still ends them), and `textarea`, `xmp`, `iframe`, `noembed`, `noframes` and `plaintext`
  break out of foreign content, whether or not the start tag is self-closing.
- Fragment parsing into a foreign `title`, `style`, `script` or `noscript` context element yields text only, SVG `title`
  stops being an HTML integration point, and the tree builder pops a foreign RCDATA element when its end tag ends RCDATA.
- `template for` patching into those elements keeps text, keeps comments and PIs without `</`, and drops element
  children.
- [#9426](https://github.com/whatwg/html/issues/9426): only a browser whose user or sandbox actually disabled scripting parses with the scripting flag off.
- [#11397](https://github.com/whatwg/html/issues/11397)'s tokenization lands before or with [#13100](https://github.com/whatwg/html/issues/13100)'s `contentnamespace`, and [#13100](https://github.com/whatwg/html/issues/13100) is aligned with it.
- For stored content and server-side sanitizers: an opt-in serializer mode, and sanitizer rules (reject `script` text
  containing `<!--` or `<script` (ASCII case-insensitive) and drop `script` children that aren't text, parse with scripting enabled, drop `noscript`).

**Evidence.** 23.5M Firefox cases on the implementation of the plan found no violation of a direct invariant check (foreign
RCDATA elements hold only text, comments and PIs, none containing the start of the element's end tag; fragment parsing into
one yields only text) in documents and in every fragment context, with the canary oracle showing only the leftovers
listed under Scope. The same checks flag today's parsing by the hundreds of thousands and the earlier builds of the
proposal, so a clean result means something. The fuzzing is backed by a catalog of 16 published root-cause classes
(`literature.md`) and a spec enumeration of every place serialization isn't the inverse of parsing (`enumeration.md`).

**Scope.**
- Accepted exceptions: the HTML `script` double-escape (needs a sanitizer that keeps `script`, which must reject its text when
  it contains `<!--` or `<script`) and `noscript` across scripting flags (depends on [#9426](https://github.com/whatwg/html/issues/9426)).
- Specified but not in any build yet: the `template for` patching rule and the opt-in serializer mode.
- Out of scope: DOM-built trees (comment data with `-->` already breaks them), inserting the output into a different context
  than the sanitizer parsed it for (such as a `<textarea>` the application adds around it), sanitizer-side parser or
  serializer bugs, browser-generated DOM after a sanitizer walk (`selectedcontent`, shadow DOM), structural pivots (form
  nesting, foster parenting: they rearrange structure but have no raw-text carrier to hide markup in).
- This applies to updated engines. Stored or server-sanitized content stays exposed to the old classes until old browsers go
  away (see "Transition risk" in the top-level README).

## How we got here

### Corners found by fuzzing

The proposal as first implemented already had no finding of the published kind (text, comment, PI or attribute carriers hiding
markup in raw text or RCDATA, with a namespace pivot) in 17.4M Firefox cases. The fuzzing found three parser-producible corners, plus two implementation gaps that the
proposal's spec text has to rule out (the title end-tag desync and fragment contexts, below). With those fixed in the Gecko build
(mode 5, commit `5873e678`), 23.5M further cases with a direct invariant oracle (foreign RCDATA elements hold only text,
comments and PIs, none of which contains the start of the element's end tag; fragment parsing into one yields only text)
found no violation in any document or fragment context. The `template for` patching rule is specified but not
implemented in any build:

| # | Corner | Introduced by proposal? | Closable in the spec PR? |
|---|---|---|---|
| 1 | Self-closing `textarea`, `xmp`, `iframe`, `noembed`, `noframes` or `plaintext` in SVG/MathML stays foreign and empty, but serializes with start and end tags, so on reparse it breaks out and what follows changes namespace. Verified by hand: `<svg><xmp/><rect/></svg>` round-trips today, not under the proposal | yes | yes: break out regardless of the self-closing flag. Compat cost looks nil: the live check of 2,987 candidate pages found no real SVG/MathML element of these six, self-closing or not, except one non-self-closing `iframe` |
| 2 | HTML `script` text (script data double-escape, or `<?`/bogus-comment prefix) vs foreign RCDATA `script`: one text node in HTML, split at the first end tag after a namespace pivot. Needs a sanitizer that keeps `script`. Also appears in the RCDATA-only modes | yes | accepted as an exception (decided): closing it would need script data states with character references, which makes `<!--` text in SVG scripts, or about 10 or more new states for comment nodes that track the double-escape state. Sanitizers that keep `script` must reject text containing `<!--` or `<script` (ASCII case-insensitive), and drop its element, comment and PI children |
| 3 | HTML `noscript` parsed with scripting off (markup children) vs foreign `noscript` (RCDATA always), after a namespace pivot | partly: [#9426](https://github.com/whatwg/html/issues/9426) fixes it inside one browser; server-side libraries that default to scripting off still differ | depends on [#9426](https://github.com/whatwg/html/issues/9426)'s final text |

Also found by reading the spec (the Firefox build has no PIs, `template for` or declarative shadow DOM; the patching
itself was confirmed by hand in Chrome Canary 160):
`template for` patching can put comment, PI and element nodes into a foreign RCDATA element, and the patch content
(parsed outside the element) can contain the end tag anywhere in its subtree: in a comment or PI, or in the text of a raw-text
element, which the serializer emits literally. A comment nested in an element child is enough (verified: under the proposal the
serialized form ends the title inside the nested comment and the text after it leaves the title). So patching must
keep only the safe parts there (suggested change 3). DOM-built trees aren't a goal: comment data with `-->` already breaks them.
Fragment parsing with a foreign context element (`title`, `style`, `script`, `noscript`; the six breakout elements)
must be namespace-aware.

What the parser change doesn't address is listed under Scope above.

Earlier confidence estimate (the enumeration's, made before the final campaign, which found no further class): about 90%
that the namespace-confusion class is closed once corners 1 and 2 are handled; about 70% that corners 1 to 3 and the
spec-reading items are the only other parser-producible sources.

### `template for` and template namespaces ([#11818](https://github.com/whatwg/html/issues/11818), [#12976](https://github.com/whatwg/html/issues/12976), [#13100](https://github.com/whatwg/html/issues/13100))

Fuzzed in Chrome Canary 160 (today's parsing, which has HTML PIs and `template for`; 4M baseline cases and 5.5M with PI
and patching content; `fuzz/RESULTS.md`), and [#13100](https://github.com/whatwg/html/issues/13100) read from its diff (not implemented in any engine yet).

- **PIs alone add no class in today's Chrome.** Every finding signature that contains a PI still occurs with `<?` replaced by
  `<!`, and 29 PI shapes in 16 containers round-trip unchanged. DOM-built PIs with `>` in the data still don't (M9).
- **PIs can carry the start of an end tag, for the proposal.** Today's parser ends a PI at its first `>`, so its data can hold
  `</title` followed by whitespace or `/` (or end with `</title`, the `>` being the PI's own terminator). The serializer adds
  `?>`: data ending in `</title` becomes `</title?>`, which tokenizes as a tag named `title?`, so that case is defused (verified).
  `</title x`, `</title ` and `</title/` become `</title x?>` and so on, which a proposal tokenizer reads as an end tag, ending
  the PI and the element, and the text after it becomes markup (verified in mode 4, with `<?` read as a bogus comment). A PI
  parsed under the proposal can't hold those, so this is the stored-content and old-parser class (M4), and the opt-in serializer mode and the sanitizer rules
  must test PIs for `</name` followed by whitespace, `/` or `>`, not for the plain end tag.
- **Patching builds trees the parser can't.** The template contents are parsed as HTML and inserted under the marker's
  parent, so HTML elements can end up under SVG/MathML parents (see [#12976](https://github.com/whatwg/html/issues/12976)), and the same element name is foreign when such
  a tree is serialized and parsed again.
- **The proposal removes the difference** (tokenization of the same names no longer depends on the namespace; the six break out), apart from
  the `script` and `noscript` corners already listed. **So does [#13100](https://github.com/whatwg/html/issues/13100)**, in engines that implement it: a patch inherits the
  target's namespace, so a patched `style` under an SVG parent is an SVG `style`, not an HTML one. They're independent
  fixes; stored content and old parsers only get the first.
- **`contentnamespace` is a new, attacker-supplied namespace pivot for old parsers.** A parser that doesn't know the
  attribute parses the template contents in the HTML namespace, and a browser that does parses them in SVG or MathML. With
  today's tokenization that is M1 (raw-text elements are text in one and markup in the other). An allowlist doesn't help when
  the sanitizer parses with something that knows the attribute: the contents are parsed as SVG, the allowlist drops the unknown
  attribute, and if the serialization doesn't carry it (the spec's serializer re-emits it from the template's content
  namespace, so this needs a sanitizer that rebuilds nodes or serializes itself) they reparse as HTML. The reverse (an
  old parser, a sanitizer that keeps the attribute: a blocklist, or an allowlist whose config allows it) is exposed too.
  [#11397](https://github.com/whatwg/html/issues/11397) makes tokenization namespace-independent and so removes the carrier, except for the `script` and `noscript` corners. So [#11397](https://github.com/whatwg/html/issues/11397) should be implemented before, or
  in the same release as, [#13100](https://github.com/whatwg/html/issues/13100)'s `contentnamespace`. (The Sanitizer API's safe default would allow the attribute, but it
  sanitizes while parsing, so both sides agree.)
- **Coordination points in [#13100](https://github.com/whatwg/html/issues/13100)'s text:**
  - `resolve a parser context namespace` lists SVG `title` with `foreignObject` and `desc` as an HTML-namespace context. Under
    [#11397](https://github.com/whatwg/html/issues/11397) SVG `title` is no longer an HTML integration point, so the lists must agree on what a patch into a `title` does.
  - Its content model lets `template` be a child of any SVG element except `script` and `style`. Under [#11397](https://github.com/whatwg/html/issues/11397) SVG `title`
    (and the six breakout elements and `noscript`) can't have element children from the parser, so `template` should be excluded
    there too.
  - Self-closing `template` in foreign content and "stop foreign end-tag recovery at open `template` boundaries" change tree
    construction between old and new parsers (a structural pivot, M7, without a raw-text carrier).
  - Serializing `contentnamespace` on every `template` is good for round trips and harmless to old parsers (an unknown attribute).
- **Not tested:** the proposal in Chrome (not built), and [#13100](https://github.com/whatwg/html/issues/13100) anywhere.

### Evidence and calibration

| Method | What | Files |
|---|---|---|
| Literature catalog | 16 root-cause classes (M1 to M16), 2013 to 2026, with status under today / [#6362](https://github.com/whatwg/html/issues/6362) / [#9426](https://github.com/whatwg/html/issues/9426) / the proposal | `literature.md` |
| Spec enumeration | every place the serializer is not the exact inverse of the parser for parser-built and DOM-built trees; recent features | `enumeration.md` |
| Differential fuzzer | canary oracle: a live canary element in the reparse that wasn't live in parse 1 | `fuzz/README.md`, `fuzz/RESULTS.md` |

Fuzzer, Firefox with `dom.parser.foreign_rawtext.mode` (0 today, 2 RCDATA, 3 RCDATA with comments dropped, 4 the
full proposal, 5 mode 4 plus self-closing breakout, with two later fixes): about 19.5M, 13.4M, 16.4M and 17.4M cases for
modes 0, 2, 3 and 4, about 20M for mode 5 before the fixes and 23.5M after; Chrome Canary 2.6M baseline cases and a further
9.5M with PIs and `template for`. Generators:
grammar-based tag soup, mutation, real-page seeds, and dedicated ones for namespace pivots, script double-escape,
self-closing breakout, foreign fragment contexts and DOM-built trees. 30+ reparse contexts, up to three rounds, a
sanitizer-pruning model, and a JS serializer for emulating pre-[#6362](https://github.com/whatwg/html/issues/6362) output.

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

## The plan in detail

The same items with the reasons and the evidence behind each.

1. Break out the six elements regardless of the self-closing flag (corner 1).
2. Corner 2: document it as an exception, and have the outreach tell sanitizers to reject `script` text containing
   `<!--` or `<script` (ASCII case-insensitive), and drop element, comment and PI children of `script` (a nested `script` element's end tag would end an HTML `script` early), even when the config allows `script`; the opt-in serializer mode does both. The
   Sanitizer API's safe methods remove `script` regardless of the config, so they need no change.
3. Make `template for` patching into an SVG/MathML `title`, `style`, `script` or `noscript` insert the patch's text nodes as
   they are, its comments and PIs unless their data contains `</`, and drops element children (a comment
   nested in an element child would otherwise reach the serialization as markup text). Text in these elements is escaped on
   serialization, and a comment or PI can only end the element through the start of an end tag (comment data with `<`, `x</`
   or `</titlex y` round-trips in mode 4), so patched trees stay as safe as parser-built ones, markers for later patches
   (`<?marker name="m"?>`) and comment markers still work, and a streamed `title` text works. `</` is name-independent and
   slightly more conservative than the exact test (`</` plus the element's name, then whitespace, `/` or `>`). The check is
   only in patching, so ordinary parsing pays nothing, and since `template for` is new there is no existing content to
   break and no ordering constraint with the parser change. Parser-built trees, including patched ones, are the goal;
   DOM-built trees aren't (comment data with `-->` already breaks them), so there is no default serializer rule. Stored
   content from old parsers is covered by the opt-in serializer mode and the sanitizer rules.
4. Make fragment parsing's context-element handling namespace-aware for these elements: for a foreign (SVG or MathML)
   `title`, `style`, `script` or `noscript` context element, set the tokenizer to RCDATA and disable recognition of
   comments, PIs and bogus comments, so the whole input is text, as for an HTML `title` or `textarea` context. Otherwise
   a comment child of the context element can hold the element's end tag (found by fuzzing, closed in the Gecko build).
   Also remove SVG `title` from the HTML integration point list: while it stays one, characters inside it run the "in body"
   rules, reconstruct the active formatting elements, and the title's matching end tag is processed against an HTML current
   node and ignored, leaving the title open after the tokenizer has left RCDATA (found by fuzzing, closed in the Gecko build).
   As defence in depth, have the tree builder pop a foreign RCDATA element whenever its appropriate end tag ends RCDATA,
   like the HTML "text" insertion mode does.
5. Corner 3: define [#9426](https://github.com/whatwg/html/issues/9426) so only a browser whose user or sandbox actually disabled scripting parses with the flag off,
   and everything else (including `DOMParser`, `createHTMLDocument`, fragment parsing and server-side parsers)
   parses with scripting enabled. Tell sanitizer maintainers to parse with scripting enabled and drop `noscript`,
   because a scripting-disabled user's browser reads its children as markup the sanitizer saw as text.
6. Implement [#11397](https://github.com/whatwg/html/issues/11397)'s tokenization before or with [#13100](https://github.com/whatwg/html/issues/13100)'s `contentnamespace`, and align [#13100](https://github.com/whatwg/html/issues/13100) with it: SVG `title` is
   no longer an HTML integration point (its parser-context-namespace list), and `template` shouldn't be allowed as a child of
   SVG `title`.
