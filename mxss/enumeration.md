# Where serialize-then-parse is not the identity (HTML), and what [whatwg/html#11397](https://github.com/whatwg/html/issues/11397) closes

Scope: the HTML fragment serialization algorithm followed by an HTML parse. Out of scope: XML
serialization and XHTML parsing, charset/encoding confusion, DOM clobbering. "The proposal" means
[whatwg/html#11397](https://github.com/whatwg/html/issues/11397) as in the README (breakout for `textarea`, `xmp`, `iframe`, `noembed`,
`noframes`, `plaintext`; RCDATA with comments and PIs kept and ended by the element's end tag for
`title`, `style`, `script`, `noscript`; CDATA markers dropped; the six break out whether or not the start tag is
self-closing), plus
[#6362](https://github.com/whatwg/html/issues/6362) (merged, `<` and `>` escaped in attribute values) and [#9426](https://github.com/whatwg/html/issues/9426) (one scripting flag for all
documents of a browser, assumed fixed).

Terms: carrier = where markup hides in parse 1; pivot = what differs between the parses so the
carrier's end is read differently.

Method, all from the spec text in `source` (serializer at "Serializing HTML fragments", fragment
parser setup, every tokenizer state, every insertion mode, foreign content) plus tests:

- Firefox build, pref `dom.parser.foreign_rawtext.mode` 0 (today), 2 (RCDATA, comments as text) and 3
  (RCDATA, comments dropped) for this enumeration. The later campaign (`fuzz/RESULTS.md`) used modes 4 and 5 (kept comments,
  breakout, self-closing breakout, fragment-context fixes). The build has no PI parsing and no `template for`.
- html5lib shim `cc/frparse.py` (`rcdata-c` = comments kept, plus a local breakout patch). html5lib is
  an old parser: no `template`, PIs, customizable `select`, DSD.
- Round-trip fuzz (parse 1 by `innerHTML`, serialize, parse 2 in 12 to 25 different context
  elements, marker elements `img`, `script`, `iframe`, `embed` counted): about 1.1M parse-2 runs in
  Firefox modes 2 and 3, about 100k in the shim.
- Exhaustive carrier enumeration: every string up to 4 characters over an 11-symbol alphabet
  (`<`, `!`, `-`, `>`, `?`, letter, space, `/`, `"`, `=`, `&`) after 13 prefixes (comment, bogus
  comment, end-tag-open, PI, CDATA, tag, attribute-value openers), with and without trailing
  markup, 418,730 strings, parse 1 then parse 2 in 5 contexts.
- DOM-built trees (comment, PI, text, element children in every raw/RCDATA element in each namespace).
- Sanitizer-style surgery (unwrap `svg`/`math`, keep the child).

## Table of non-round-trip sources

Classes: P = the parser can produce the tree, D = only the DOM can. Directions: M>T = markup becomes
text (benign), T>M = text, attribute or comment becomes markup (mXSS-relevant), S = structure moves
only. "Closed" is about the proposal + [#6362](https://github.com/whatwg/html/issues/6362) + [#9426](https://github.com/whatwg/html/issues/9426).

### Tokenizer and namespace pivots

| # | Source | (1) Producible | (2) Direction | (3) Carrier and pivot | (4) Closed? Why | (5) Confidence, test |
|---|---|---|---|---|---|---|
| 1 | SVG/MathML `style`, `script`, `title`, `textarea`, `xmp`, `iframe`, `noembed`, `noframes`, `noscript`, `plaintext` tokenized as markup, HTML ones as raw text/RCDATA/PLAINTEXT | P | T>M | Carriers: comment, PI/bogus comment, CDATA, text with entities, attribute (via [#6362](https://github.com/whatwg/html/issues/6362)). Pivot: namespace of the element at parse 2 (context element, foster parenting or `mglyph` re-nesting, unwrapping `svg`, ignored `<svg>`, template-for patching) | Yes. Tokenizer state depends on local name only: RCDATA for four, breakout for six (so no foreign element exists to pivot from or to). Escaped serialization of foreign text plus RCDATA decoding round-trips; HTML raw text can't contain an appropriate end tag. | High. Fuzz: 216k+345k parse-2 runs, 0 T>M in modes 2 and 3 (mode 0: hundreds). Unwrap surgery over 10 elements x 2 namespaces x 6 carriers: 0 leaks with `rcdata-c` (mode 0: 32). |
| 2 | Comment or PI inside foreign RCDATA element (new, from "kept as nodes") | P | T>M if the end tag can sit inside the node | Carrier: comment/PI data. Pivot: element read as HTML `title`/`style` (text) or as foreign | Yes, if "an appropriate end tag ends the comment/PI and the element" is implemented. Then parser-made comment/PI data never holds the element's end tag and serializes back identically. Implemented in Firefox modes 4 and 5 (mode 3 drops comments, mode 2 treats `<!--` as text), and in the shim. | Medium-high. Shim `rcdata-c` only. Implementation risk: PIs end at `>`, which is the end tag's last character, so the end-tag check must win over the PI/comment end. |
| 3 | CDATA section (only when the adjusted current node is foreign) vs bogus comment | P | M>T / comment | Carrier: CDATA text (raw `<`). Pivot: foreign or not at tokenization | Not needed. CDATA content becomes text and serializes escaped; in HTML the bogus comment ends at the first `>`; both re-serialize to something that reparses the same. Markers dropped inside the four elements. | High. Exhaustive carrier enumeration. |
| 4 | Self-closing foreign `textarea`, `xmp`, `iframe`, `noembed`, `noframes`, `plaintext` | P | T>M | The serializer never emits `/>`, always start and end tag, so a self-closed element stays foreign and empty in parse 1 but breaks out on reparse, changing the namespace of what follows | **Yes, once the six break out regardless of the self-closing flag** (found by fuzzing; Firefox mode 5). Keeping today's behavior for self-closing tags is not closed. | High (spec reading, by hand, fuzzing). |
| 5 | **HTML `script` double-escape**: text starting with a comment opener and a `script` start tag keeps the first `</script>` as text; serialized literally | P (needs an HTML `script` kept) | T>M | Carrier: HTML script data text. Pivot: parse 2 reads the same `script` as foreign RCDATA, which ends at the first end tag | **No, introduced by the proposal.** Today foreign script reparse is inert for this shape; with RCDATA it ends early. Only context pivots to SVG (e.g. `svgG.innerHTML`) hit it; MathML text integration points parse `script` as HTML. | High that it exists (Firefox modes 2 and 3 reproduce, mode 0 doesn't). Impact bounded: needs a sanitizer that keeps `script`. README already notes this. |
| 6 | `noscript` and the scripting flag: HTML `noscript` with scripting off has element/comment children, scripting on has RAWTEXT | P | T>M | Carrier: comment (attribute closed by [#6362](https://github.com/whatwg/html/issues/6362)), or literal text of a raw child element (`plaintext`, `xmp`, `style`...) inside `noscript`. Pivot: scripting flag at parse 2, or foreign `noscript` (RCDATA regardless of flag) | [#9426](https://github.com/whatwg/html/issues/9426) closes it inside one browser. Survives across parsers with different flags (server-side libraries default to scripting off; users with JS off) and foreign `noscript` is flag-independent, so scripting-off HTML `noscript` reparsed as foreign still differs. Also seen in the Firefox build: `noscript` in `template` contents is parsed scripting-on but serialized scripting-off. | High for the mechanism (shim reproduces). Not tested in a scripting-off browser (selenium `innerHTML` ignored the pref). |
| 7 | `plaintext`: serializer appends `</plaintext>` and the ancestors' end tags, which parse 2 reads as text | P | M>T (benign growth); T>M only where parse 2 ignores `plaintext` | Carrier: PLAINTEXT text. Pivot: fragment context whose insertion mode ignores the start tag (`colgroup`, `frameset`) | Not addressed, and nothing new. Fuzz: only inert gain (content ends up in `template` contents, which `colgroup` accepts), never live. | Medium-high. Fuzz over 25 contexts plus per-element context matrix. |
| 8 | Raw/RCDATA start tag ignored by parse 2's insertion mode (`colgroup`, `frameset`, `in head noscript`) | P (context mismatch) | T>M only if the mode ignores the raw tag but not what's inside | Carrier: raw text. Pivot: insertion context | Not addressed, not newly reachable: modes that ignore `style` also ignore `img`, `iframe`, etc. Only `template` start tags survive in `colgroup`, giving inert content. Old `in select` mode (which ignored `style`) is gone. | Medium. Matrix of 10 elements x 60 contexts: no live leak in modes 2 and 3. |
| 9 | SVG `title` no longer an HTML integration point | P | M>T (element children become text) | Compat/content-model effect, not an inverse failure | n/a | Spec reading. |

### Attribute, name, comment, PI and doctype carriers

| # | Source | (1) Producible | (2) Direction | (3) Carrier and pivot | (4) Closed? Why | (5) Confidence, test |
|---|---|---|---|---|---|---|
| 10 | Attribute values containing `<`, `>`, `"` | P | T>M (before [#6362](https://github.com/whatwg/html/issues/6362)) | Carrier: attribute value. Pivot: any raw/RCDATA ancestor at parse 2 | Yes by [#6362](https://github.com/whatwg/html/issues/6362): serializer emits no `<` or `>` in attributes, `"` as `&quot;`, `&` as `&amp;`. Tree-level: attribute text can't contain an end tag. | High. Part of every fuzz run, exhaustive attribute openers. |
| 11 | Tag and attribute names with odd characters (`<`, `"`, `'`, leading `=`) | P | none | Names can't contain `/`, `>`, whitespace or (except a leading one) `=`, so serialized verbatim they tokenize the same and never hold an end tag. DOM names are validated by the Name production. | Not needed. | High. Exhaustive 4-character strings. |
| 12 | Parser comments and bogus comments (`<!`, `</x`, `<?` forms; EOF in comment) | P | none | Parser data can't contain `-->`, `--!>`, a leading `>` or `->`; serialized `<!--`data`-->` reparses to the same data | Not needed. | High. 418,730 carrier strings, parse 2 in 5 contexts: 0 round-trip failures, 0 extra elements. |
| 13 | Parser PIs (`<?target data?>`) | P | none | PIs end at the first `>`, the same extent as the bogus comment a PI-unaware parser makes; target grammar excludes `xml`, `xml-stylesheet` and odd targets (those become comments, same extent) | Not needed (skew PI-aware vs PI-unaware parsers only changes node type). | Medium: spec reading; the Firefox build has no PI parsing. |
| 14 | DOM comment with `-->`, `--!>`, leading `>`, trailing `--!` | D | T>M | Carrier: comment data | No, out of scope (DOM content). Mentioned in the spec's warning. | High. Firefox dom battery. |
| 15 | DOM PI whose data contains `>` (DOM only forbids `?>`) | D | T>M | Carrier: PI data; PI ends at first `>` | No. | High. Firefox dom battery (bogus-comment extent). |
| 16 | DOM PI target that is not a tokenizer PI target (`xml`, non-ASCII, `:`) | D | PI to comment | benign | n/a | Spec reading. |
| 17 | Doctype in fragment, `<!DOCTYPE name>` serialization | D | M>T (ignored in fragments) | benign; name validated | n/a | Spec reading. |
| 18 | `\r`, NUL, `&#13;`, leading LF of `pre`, `textarea`, `listing`, adjacent text nodes | P | data changes only | no markup effect | n/a | High (fuzz minimizer: only these plus `plaintext` fail body-to-body round trip, apart from structural tags). |

### Raw-text and RCDATA content from the DOM or fragment context

| # | Source | (1) Producible | (2) Direction | (3) Carrier and pivot | (4) Closed? Why | (5) Confidence, test |
|---|---|---|---|---|---|---|
| 19 | HTML `style`, `script`, `xmp`, `iframe`, `noembed`, `noframes`, `plaintext`, `noscript` (scripting on) with text holding an end tag; literal serialization | D, and P through fragment parsing with a raw context element (`style.innerHTML = ...`, no appropriate end tag in fragments) | T>M | Carrier: raw text. No pivot needed. | No: by design the serializer emits text literally. | High. Firefox dom battery. |
| 20 | HTML `title`, `textarea` with comment or element children (comments literal, elements literal) | D | comment T>M; element M>T | Carrier: comment data holding the end tag | No. | High. dom battery. |
| 21 | **Foreign `title`, `style`, `script`, `noscript` with comment, PI or element children, or a foreign `textarea`/`xmp`/... with children at all** | D, and P through `template for` patching into a marker PI inside the element, and through a foreign fragment context if the fragment spec isn't updated (row 22) | T>M | Carrier: comment/PI data or the literal text of an HTML raw child. Pivot: none; same namespace is enough now | **No, and newly dangerous.** Today such children are inert in the same namespace and dangerous only after a namespace pivot. With RCDATA they are dangerous without a pivot. For the `template for` route the planned answer is that patching into these elements keeps text, keeps comments and PIs unless their data contains `</`, and drops element children (no default serializer rule: DOM-built trees aren't a goal, and the rule would miss comments nested in patched elements); flattening children stays in the opt-in serializer mode for stored content. | High for DOM-built (Firefox modes 2 and 3 leak, mode 0 doesn't, for comment child, element child holding raw text, PI with `>`). Medium for the `template for` route (spec reading, no engine). |
| 22 | Fragment parsing with a foreign raw element as context element (`svgStyle.innerHTML`) | P | T>M / structure | Spec text of "initialize an HTML fragment parser" switches on the context element's name, namespace-blind by convention (HTML only); Firefox mode 0 leaves the data state for SVG `style` | Yes, with the plan's change to this step: fragment parsing into a foreign `title`, `style`, `script` or `noscript` context yields text only (and SVG `title` is no longer an integration point). Otherwise elements and comments land inside foreign RCDATA elements (row 21). | High (tested in Firefox mode 5 in every fragment context). Spec edit needed. |
| 23 | DOM-only SVG/MathML `textarea`, `xmp`, ... (breakout elements) | D | S, then as row 21 | Pivot: breakout at parse 2 makes them HTML; trailing siblings and ancestors' end tags are read as text for `plaintext` | No (DOM content). Serializer opt-in mode drops them. | Medium-high. |

### Structure

| # | Source | (1) Producible | (2) Direction | (3) Carrier and pivot | (4) Closed? Why | (5) Confidence, test |
|---|---|---|---|---|---|---|
| 24 | Foster parenting, adoption agency, nested `form` (form pointer), `a`, `button`, `nobr`, implied end tags (`p`, `li`, `dd`), quirks-mode `p`/`table` | P | S | Pivot: re-nesting. Mattered for mXSS only because re-nesting changed a raw element's namespace | Raw-element consequence yes (row 1). Remaining effects: form association changes, attribute loss on ignored start tags. Not security-neutral for forms but not markup-from-text. | High. Fuzz STRUCT minimizer: round-trip failures are `form`/`a`/`button`/`table`-type only. |
| 25 | Fragment context element (`table`, `colgroup`, `frameset`, `head`, `html`, `select`) | P | S | Same bytes, different insertion mode | Not addressed; see rows 7, 8. | Medium-high. |
| 26 | `template`: contents vs children, form pointer ignored in contents, in-template mode switching | P / D | S, inert to live | Parse 1 inert contents become live children when parse 2 puts `template` in SVG/MathML (foreign `template` has no contents). Same markup, not a carrier. | No (not text to markup: the nodes were already markup, so sanitizers that walk `content` see them). | High. Fuzz classified as "inert to live", 0 T>M. |
| 27 | Shadow roots, DSD: serializer emits `<template shadowrootmode>` only for serializable roots (or listed `shadowRoots`) | P (parseHTMLUnsafe, `setHTMLUnsafe`) / D (`attachShadow`) | S: hidden subtree, then template contents (`innerHTML`) or shadow root again | Shadow content isn't visited by child-walking sanitizers; `innerHTML` omits it, `getHTML({serializableShadowRoots})` emits it | Not addressed. Safe path: `setHTML` never enables DSD. | Medium (spec reading; no test). |
| 28 | Void elements: serializer's list equals the parser's void list; DOM-only void element with children | D | M>T (children dropped) | benign | n/a | High (spec reading). |
| 29 | Integration points: `annotation-xml` depends on `encoding` at start tag, MathML text integration points (`mglyph`, `malignmark`), SVG `foreignObject`, `desc` | P / D | S | Attribute set after parse by DOM changes children's parsing at parse 2 | Raw consequence closed by row 1. | Medium. |
| 30 | Breakout list asymmetry (HTML-only names such as `div`, `p`, `font` with attributes made as foreign elements by the DOM) | D | S, M>T for `plaintext` | trailing content | n/a | Medium. |

## Features that are new or changing

- **Processing instructions (`320c05f6`, `2e477cf1`, `255188e5`).** Tokenizer states for PIs; handled
  like comments in every insertion mode, including `in head noscript` and `in template`. Extent: a PI
  ends at the first `>`, like a bogus comment, so PI-aware and PI-unaware parsers disagree on node
  type but not on where the construct ends (row 13). Serialization is `<?target data?>`. Risks:
  DOM-created PI data containing `>` (row 15); under the proposal a PI inside foreign RCDATA ends at
  the element's end tag, which has to take priority over the PI's own `>` (row 2); a PI as a
  `template for` marker inside such an element (row 21). Not testable in the Firefox build.
- **`<template for>` (`2ff023fb`).** Contents are patched into the range delimited by marker PIs, so a
  parser tree can have nodes in parents that never would have accepted them from a token stream:
  other namespaces (previously a new source of row 1, closed by the proposal) and, after the
  proposal, children inside foreign RCDATA elements (row 21). Spec reading only. I could not find a
  rule that rejects a marker whose parent is a foreign `title`, `style`, `script` or `noscript`.
  Patched HTML elements can sit under SVG/MathML parents (see `mxss/README.md`, "`template for` and template
  namespaces"). Confirmed by hand in Chrome Canary 160 that patching into a foreign `title` works, including a
  comment whose data contains the end tag, and (mode 4) that a comment nested in a patched element child
  also ends the title on reparse. The answer is in patching: into one of these elements, keep text,
  keep comments and PIs unless their data contains `</`, and drop element children. DOM-built trees aren't
  a goal, so there is no default serializer rule.
- **Declarative shadow DOM (`b9c11c55`, `7fe76d01`, `7da45dfa`, `b973c6ad`).** Row 27. The
  serializer's shadow-host step is written in terms of "current node" before the loop that defines
  it, an editorial slip. `shadowrootcustomelementregistry` is emitted only when registries differ.
- **Customizable `select` (`172cccf4`, `6e358abb`, `4ce63af1`).** The `in select` insertion mode is
  gone: `select` content is parsed in body with special cases for `input` (closes the `select`),
  nested `select`, `option`, `optgroup`, `hr`. No new inverse failure found: the fuzz included
  `select`, `option`, `optgroup`, `selectedcontent`, `hr`, `input` with no T>M. The visible effect is
  version skew: older parsers drop `style`, `script` and others inside `select` differently, so
  stored sanitized content parses differently between engines/libraries (not an inverse failure).
  `selectedcontent` clones the selected option's children (removing `script`, SVG `script`, `frame`,
  `iframe`, `embed`, `object`), so serialization contains the duplicate, reparse regenerates it.
- **`customelementregistry` and the `is` value.** `is` is re-emitted as an attribute, DSD registry
  attribute above. No effect on tokenization.
- **`setHTML` / sanitize-while-parsing (`94857062`).** The parser consults the config at element,
  comment and PI insertion; "Replace with children" redirects insertion, "Remove" skips it. The
  tokenizer and tree builder behave as if the element were there, so the tree equals a parser tree
  minus subtrees and with children promoted. Consequences: the p1 tree has parser-producible shapes
  only, text of removed raw elements becomes text under the parent (escaped on serialization),
  unwrapping `svg` leaves SVG-namespace `style` etc. under an HTML parent (row 1 surgery test: safe
  with the proposal; the escaped text then changes meaning inside an HTML `style`, which is a
  functional, not a security, difference). Sanitizer removal of comments/PIs removes the row-2
  carriers. DSD is off in `setHTML`.
- **Other parser changes since 2024:** coalesced text insertion (`61a2f780`), "HTML parser should not
  insert nodes the DOM would reject" (`8d149325`, `ca693db1`), form pointer ignored in template contents
  (`9ed7f277`), foster parenting honors a template's insertion target (`b17ff2b3`), scripting mode enum
  and defaults (`01c45ced`, `849de3b9`, `508706c8`, `c6867144`), fragment parser refactor (`4c4c8136`),
  DOCTYPE handling (`e7318c5e`). None adds an inverse failure beyond the rows above; the scripting-mode
  changes are the ones that touch row 6.

## What the proposal does not address

- DOM-only content: rows 14, 15, 19, 20, 21 (DOM-built part), 23, 28. The serializer can't be an inverse for trees
  whose raw/RCDATA elements hold comments, PIs, elements or text with end tags. The opt-in
  serializer mode (step 3 of the plan) is the mitigation, and has to be used by whoever serializes
  sanitizer output.
- Text from a raw-context fragment parse (`style.innerHTML = ...`), row 19.
- Structural mutations: form association, nested `a`/`button`, quirks, foster parenting, fragment
  context differences, `template` inert to live, hidden shadow trees (rows 24 to 27, 29, 30).
- HTML `script` double-escape against foreign RCDATA `script` (row 5), and parse-time `noscript`
  differences between parsers (row 6).
- Parser skew during rollout: unupdated browsers and server-side libraries, customizable `select` skew,
  PI-aware against PI-unaware parsers.
- Sinks that embed markup in raw-text parents by string concatenation (`<title>${html}</title>`),
  since there's no serializer to invert.
- Encoding/charset confusion, XML serialization and XHTML parsing, DOM clobbering (out of scope
  as stated).

## Conclusion

For trees the parser builds, in one updated browser with one scripting flag, [#6362](https://github.com/whatwg/html/issues/6362) and the plan
in `README.md` (RCDATA with kept comments and PIs, breakout for the six including self-closing, text-only foreign fragment
contexts, the `template for` patching rule), I could not make any tree round-trip into new markup. This enumeration's own
runs: 0 text/attribute/comment-to-markup cases in about 1.1M randomized parse-2 runs on Firefox modes 2 and 3, 0 in about
100k shim runs of `rcdata-c` with breakout, 0 in 418,730 exhaustive carrier strings, 0 after `svg`/`math` unwrap surgery. The
later campaign on the implementation of the plan (about 23.5M cases) found no violation of the direct invariant check.
The namespace/tokenizer pivot, the common cause, is closed because tokenization no longer depends on the element's
namespace for the ten element names.

What the enumeration found beyond the original proposal, and where each stands:

1. Row 4: self-closing breakout elements. Closed by breaking out regardless of the self-closing flag.
2. Rows 21 and 22: foreign RCDATA elements gaining element, comment or PI children, via `template for` patching or a foreign
   fragment context. Closed by the plan's patching rule and text-only fragment contexts (the patching rule is specified but
   not implemented in any build).
3. Row 5: HTML `script` double-escape against foreign RCDATA `script`. Accepted exception, with the sanitizer rule.
4. Row 6: `noscript` across scripting flags. Depends on [#9426](https://github.com/whatwg/html/issues/9426).

Rows 14, 15, 19, 20, 23 and 28 (DOM-built trees) and sink-context mismatches aren't parse-serialize-parse mismatches of
parser output, so they're out of scope for the question, not open gaps in the proposal. The opt-in serializer mode is the
mitigation for whoever serializes sanitizer output.

Confidence, as estimated from this enumeration before the later campaign: about 90% that the proposal closes the
namespace-confusion class it targets in the parser-producible space, about 70% that the rows above are the only other
parser-producible text-to-markup sources (the build lacked breakout, kept comments, `template for` and DSD, the shim is
html5lib, and `select` parse-1 fuzzing timed out). The campaign, run on the implementation of the plan, found no further class.

Not tested: `template for`, PIs and DSD in a Firefox build, other engines' parsers (Safari, Chromium with the proposal), and
a scripting-off run of the fuzzer. wpt tests for the tokenization, breakout and fragment-context rows exist only as tentative tests in the Gecko work (not
upstreamed); there are none for the `template for` rule.
