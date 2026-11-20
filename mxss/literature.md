# HTML mXSS root-cause catalog, 2007 to 2026

Class-level only: mechanisms in words and tag names, no working payloads. Calibration inputs are
kept separately (untracked) in `mxss/private/seeds.jsonl`.

Question: is [whatwg/html#11397](https://github.com/whatwg/html/issues/11397) (plus [whatwg/html#6362](https://github.com/whatwg/html/issues/6362), merged; plus [whatwg/html#9426](https://github.com/whatwg/html/issues/9426), assumed
fixed) the last known root cause of HTML-to-HTML parse, serialize, parse mXSS?

Short answer: plausibly yes, for what the question asks: parse-serialize-parse mismatches in trees the HTML parser
itself produces, in updated browsers, sanitizing and sinking in the same engine with the same context. It closes the last
known tokenization-driven class of those (with the two accepted exceptions in `README.md`). The cases below that it doesn't
touch aren't parse-serialize-parse mismatches of parser output, so they're out of scope: sink-context mismatch (the output is
inserted into a different context than it was parsed for), DOM-created nodes, parse-time DOM generation, and non-conformant
sanitizer parsers and serializers. They're listed for completeness, not as open gaps in the proposal. Details below.

## Terms

- **Carrier**: a place where markup-looking text sits inertly in parse 1 and the serializer
  writes it out verbatim. Possible carriers: attribute value (verbatim `<`/`>` before [#6362](https://github.com/whatwg/html/issues/6362)),
  text of an element the serializer writes literally (`style`, `script`, `xmp`, `iframe`,
  `noembed`, `noframes`, `plaintext`, `noscript` with scripting), comment, PI/bogus comment,
  CDATA section.
- **Pivot**: anything that changes how parse 2 treats the carrier compared with parse 1: a
  namespace flip of an ancestor, the scripting flag, the fragment context or insertion mode, an
  ancestry change (form nesting, foster parenting, depth flattening), removal or rewriting of
  nodes between the parses, or a node the parser cannot create.
- Status columns are cumulative: (a) the spec before [#6362](https://github.com/whatwg/html/issues/6362), which is the state the historical
  bypasses were found against; (b) plus [#6362](https://github.com/whatwg/html/issues/6362); (c) plus [#9426](https://github.com/whatwg/html/issues/9426) (scripting flag no longer depends on
  the document); (d) plus the [#11397](https://github.com/whatwg/html/issues/11397) proposal. "Closed" means closed for conformant, updated
  engines and parser-created trees. Old browsers, non-conformant serializers (shipping [#6362](https://github.com/whatwg/html/issues/6362)
  lagged: Nokogiri 1.19.5, Nov 2026) and server-side parsers keep their own status.

## Summary table

| ID | Class | Carriers | Pivots | (a) | (b) | (c) | (d) |
|---|---|---|---|---|---|---|---|
| M1 | HTML raw text/RCDATA text becomes markup when the element is foreign in parse 2 | text of `style`, `xmp`, `iframe`, `noembed`, `noframes`, `noscript`; `title`/`textarea` text only if entities decoded | namespace flip (nested form, `mglyph`/`malignmark` in text integration points, foster parenting, removal of integration points, depth flattening) | not closed | not closed | not closed | closed |
| M2 | Foreign element contents are markup in parse 1, raw text in parse 2: attribute-value carrier | attribute values on elements inside foreign `style`/`title`/etc. | same namespace pivots, in the other direction | not closed | closed | closed | closed |
| M3 | Delimiter spanning: comment or CDATA opener in raw text in parse 1, markup-level comment in parse 2, closer elsewhere | opener in raw text; closer in an attribute value (published), or in literal text or another comment (unpublished, derived) | namespace flip | not closed | closed for attribute closers; unsure for the derived ones | same as (b) | closed |
| M4 | Foreign element holds a comment/PI/CDATA containing the element's end tag; raw text in parse 2 | comment, PI, CDATA in foreign `style`/`title`/`script`/`textarea`/... | namespace flip | not closed | not closed | not closed | closed for parser-created nodes |
| M5 | `noscript` scripting-flag differential | attribute (parse 1 disabled, parse 2 enabled); comment, PI; reverse direction (enabled to disabled): literal text | scripting flag differs between parses (DOMParser, template, other documents, server-side parsers, user-disabled scripting) | not closed | closed for attributes only | closed for browser-internal parses; not closed for external parsers; unsure for users with scripting off | same as (c); foreign `noscript` part closed |
| M6 | Re-contextualization: sink context differs from parse-1 context | attribute (closed by [#6362](https://github.com/whatwg/html/issues/6362)), comment, PI, literal text of `style`/`script`/`xmp`/..., markup not valid in the sink's insertion mode | sink wraps output in or sets `innerHTML` on `textarea`, `title`, `xmp`, `iframe`, `noembed`, `noframes`, `noscript`, `style`, `script`, `plaintext`, `select`, `table`, `frameset`, SVG/MathML elements; `document.write` | not closed | closed for attributes only | not closed | not closed (SVG/MathML `style`/`title` sinks become consistent; the rest unchanged) |
| M7 | Spec-compliant structural non-roundtrip (pivot only) | none of its own; needs a carrier from another class; text adjacency (see M11) | form element pointer, foster parenting, adoption agency, `p` closed by block start tag, table/caption, select content model, implementation-defined nesting depth limits, integration points | pivot present | pivot present | pivot present | pivot present, but its published carriers are gone |
| M8 | Removal or rewrite between parses creates the pivot | same as M1 to M6 | sanitizer drops an element but keeps children, drops attributes that decide namespace (`annotation-xml` `encoding`), unwraps integration points | not closed | partly | partly | partly (tokenization carriers closed; element-identity flips unsure) |
| M9 | DOM-created nodes the parser cannot produce | text of HTML raw text element containing its end tag; comment containing `-->`; PI containing `>`; case-preserved or odd names; HTML-namespace element under SVG/MathML parent | none needed | not closed | not closed | not closed | not closed (except HTML `style`-like element under SVG/MathML parent, which becomes safe) |
| M10 | DOM that appears or changes after the sanitizer walk: parse-time cloning and patching | whatever the generated subtree holds | `selectedcontent` re-clone, `template for` patching, declarative shadow DOM, template contents document | not closed | not closed | partly (template owner document flag) | not closed |
| M11 | Text-node adjacency and merging | text fragments split by an element that vanishes on reparse | M7 pivots | not closed | not closed | not closed | not closed (threat is template-expression sinks, not markup) |
| M12 | Character-reference decoding differs by context | entity text in `style`/`title`/`noembed`/`noscript` | engine bug or context change | closed in spec; engine bugs historic | same | same | same (RCDATA decodes like today's foreign text) |
| M13 | Serializer quoting and name classes from 2013 (backtick, CSS escapes, unknown-element namespaces) | attribute delimiter, tag names | none | not applicable (old engines; closed in spec) | n/a | n/a | n/a |
| M14 | Engine parser/serializer non-conformance | varies | varies | not applicable (bugs) | n/a | n/a | n/a, but less to get wrong |
| M15 | Sanitizer-side parser/serializer non-conformance | raw text passthrough, wrong end-tag recognition, namespace-unaware tokenization, unescaped `<`/`>` | none needed | not applicable (implementation) | closes the serializer sub-case once implemented | n/a | helps namespace-unaware parsers for the ten elements only |
| M16 | HTML `script` data escape states vs foreign `script` (residual of the proposal) | text of an HTML `script` containing a comment opener followed by a `script` start tag | namespace flip | not closed | not closed | not closed | unsure; needs HTML `script` to survive sanitizing |

## Per-class details

### M1: HTML raw text becomes markup in foreign content

Mechanism: in parse 1 the element is in the HTML namespace, so its text is raw (or RCDATA) and
nothing inside is a tag. The serializer writes the text literally for `style`, `xmp`, `iframe`,
`noembed`, `noframes` (and `script`, `plaintext`, `noscript` with scripting). In parse 2 a pivot
has made the same element a child of `svg` or `math` content, where the tree builder creates a
foreign element and the tokenizer reads its content as ordinary markup, so the text now
contains elements. Sanitizers see only inert text in parse 1. The pivots in the literature are
nested `form` elements together with `math`/`mtext`/`mglyph` (securitum 2020), table foster
parenting with `mglyph`, removal of a disallowed `svg`/`math` wrapper by the sanitizer
(Bleach, ammonia, HtmlSanitizer), integration point elements, and deep nesting.

Years and sources: 2011 (Mozilla bug 650001, SVG `style` through `innerHTML`, listed in
[s1r1us' timeline](https://s1r1us.ninja/posts/mxss-101/)); 2020 DOMPurify <2.0.17
([securitum](https://research.securitum.com/mutation-xss-via-mathml-mutation-dompurify-2-0-17-bypass/));
DOMPurify 2.2.0 (Daniel Santos, listed in the
[Sonar cheatsheet](https://sonarsource.github.io/mxss-cheatsheet/examples/)); Bleach 3.1.1
(CVE-2020-6816, [GHSA-m6xf-fq7q-8743](https://github.com/advisories/GHSA-m6xf-fq7q-8743));
HtmlSanitizer 2023 (CVE-2023-44390,
[GHSA-43cp-6p3q-2pc4](https://github.com/advisories/GHSA-43cp-6p3q-2pc4), found by Sonar, see
[their post](https://www.sonarsource.com/blog/mxss-the-vulnerability-hiding-in-your-code/));
ammonia 2025 ([RUSTSEC-2025-0071](https://rustsec.org/advisories/RUSTSEC-2025-0071),
[GHSA-mm7x-qfjj-5g2c](https://github.com/advisories/GHSA-mm7x-qfjj-5g2c)); ammonia 2026
([GHSA-9jh8-v38h-cvhr](https://github.com/advisories/GHSA-9jh8-v38h-cvhr), CVE-2026-63430).
The ammonia advisories list exactly the ten elements of [#11397](https://github.com/whatwg/html/issues/11397) as the gadget set.

Status: not closed in (a) to (c): the carrier is text, so attribute escaping and the scripting
flag are irrelevant. Closed in (d): after the change every one of the ten elements is either
raw/RCDATA in foreign content too, or breaks out to HTML, so parse 2 reads the text the same way.
The repo's own check (`mxss-check.html`, shape A) shows this for the six HTML-literal elements.

### M2: foreign markup hides an end tag in an attribute

Mechanism: in parse 1 a foreign `style`, `title` and so on is an ordinary element whose children
are parsed as markup, so an element's attribute value can contain the end tag of the parent as
plain attribute text. Before [#6362](https://github.com/whatwg/html/issues/6362) the serializer wrote `<` and `>` raw in attributes. In parse 2
a pivot makes the parent an HTML element, whose raw text ends at the first matching end tag,
even inside the former attribute, and what follows is live markup.

Years and sources: 2019 DOMPurify 2.0.0, which used a Chrome parser bug as the pivot
([securitum](https://research.securitum.com/dompurify-bypass-using-mxss/), local copy in
`web-archive-org`); the example in
[Sonar's 2024 post](https://www.sonarsource.com/blog/mxss-the-vulnerability-hiding-in-your-code/);
DOMPurify 2.2.3 (Sonar cheatsheet); Google Search 2019 and the 2025 Google write-up
([Bughunters](https://bughunters.google.com/blog/escaping-and-in-attributes-how-it-helps-protect-against-mutation-xss),
[Chrome blog](https://developer.chrome.com/blog/escape-attributes)).

Status: not closed in (a). Closed by (b): the Bughunters post says [#6362](https://github.com/whatwg/html/issues/6362) blocks all vectors that
depend on unescaped `<`/`>` in attributes creating tags. Mizu's later note that two-parse
techniques broke after browsers started escaping attributes is consistent
([SMIL post](https://mizu.re/post/dompurify-bypass-smil-animatetransform-safari), as relayed by
search; I did not read it in full). Engines shipped it in Chrome 138, Firefox 140, Safari 26.

### M3: delimiter spanning (comment/CDATA opener in raw text)

Mechanism: in parse 1 the element is HTML raw text, so a comment opener inside is just text. In
parse 2 the element is foreign, so the opener starts a comment that swallows the element's end
tag and whatever follows, up to a closer that parse 1 held in a different carrier. Heyes and
Kinugawa used an attribute value for the closer; Firefox needed a CDATA opener and closer. Mizu
and others built the same shape with `foreignObject`/`annotation-xml` integration points, custom
elements, or an unbalanced `<!` opener.

Years and sources: Oct 2020
([Heyes, PortSwigger](https://portswigger.net/research/bypassing-dompurify-again-with-mutation-xss));
DOMPurify 2.0.17 variants by @sqrtrev et al.; 3.0.8 Mizu; 3.1.7 Kinugawa
([tweet](https://x.com/kinugawamasato/status/1843687909431582830)); 3.2.1 Yaniv Nizry; 3.2.2
Sean Ng ([post](https://nsysean.github.io/posts/dompurify-323-bypass/), not read); Bleach 3.2.3
(all in the Sonar cheatsheet). DOMPurify's `SAFE_FOR_XML` attribute regex exists because of this
shape ([wiki, section 9](https://github.com/cure53/DOMPurify/wiki/Attack-Classes-&-Bypass-History)).

Status: (a) not closed. (b) closed for every published instance (the closer was an attribute).
Derived and unpublished: the closer could also sit in the text of a *different* HTML raw-text
element that serializes literally, or in another comment; I think that is possible today, but I
did not find it published or test it. (d) closes the whole shape: in the proposal a comment in
foreign `style`/`title`/etc. ends at the element's end tag, so a foreign element cannot span
past its end tag, and the end of the element is the same in both parses.

### M4: comment/PI/CDATA inside a foreign element holds the end tag

Mechanism: in parse 1 the foreign element contains a comment, PI (as bogus comment) or CDATA
section whose data includes the element's own end tag, which is inert because the comment
tokenizer ignores it. The serializer writes comments and PIs verbatim. In parse 2 the element is
HTML raw text or RCDATA, which ignores the comment syntax, so the end tag inside ends the
element and the rest of the former comment is markup.

Years and sources: general shape documented as the reason DOMPurify scrubs comments (2.x release
notes, `SAFE_FOR_XML` in 2.5.0, 2024); Heyes noted DOMPurify's first fix checked text nodes but
not comments; the research repo's `mxss-check.html` (shape B) shows it works today for `style`,
`xmp`, `iframe`, `noembed`, `noframes`, and, for `title` and `textarea`, in the repo's variant
tests. I did not find a standalone advisory for a pure-comment instance without an attribute
involved.

Status: not closed through (c). Closed in (d) for parser-created nodes, because the proposal ends
the element and the comment at the end tag, so no parser-created comment or PI contains an
appropriate end tag. A DOM-created comment can still contain one (M9). One check for the spec
text: the comment's last characters and the serializer's closing `-->` must not combine into an
end tag (for example an end tag name followed by `--`); that works only if the tokenizer tests
for the end tag *inside* the comment states, as the proposal says.

### M5: `noscript` and the scripting flag

Mechanism: with scripting disabled `noscript` content is parsed as elements; with scripting
enabled it is raw text. A sanitizer parses in a scripting-disabled context (DOMParser, `template`,
`createHTMLDocument`, jsdom, Nokogiri, html5lib defaults, htmlparser2, ammonia options) and the
live page parses with scripting enabled. Carriers that survive serialization are attributes
(before [#6362](https://github.com/whatwg/html/issues/6362)), comments and PIs. In the other direction (parse 1 enabled, parse 2 disabled) text
in `noscript` is written literally by the serializer and becomes elements, which matters when the
output is later adopted into a live document.

Years and sources: Feb 2019 Google Closure and Google Search (Kinugawa;
[Acunetix summary](https://www.acunetix.com/blog/web-security-zone/mutation-xss-in-google-search/),
[timeline](https://s1r1us.ninja/posts/mxss-101/)); an early DOMPurify release that fixed `noscript`/`noembed` allow-listing (Kinugawa); Bleach 3.1.0
(CVE-2020-6802); Sanitize 2023
([GHSA-fw3g-2h3j-qmm7](https://github.com/advisories/GHSA-fw3g-2h3j-qmm7)); Joplin 2021
([GHSA-phj8-2p6x-hq5r](https://github.com/advisories/GHSA-phj8-2p6x-hq5r)); TinyMCE 2024
([GHSA-w9jx-4g6g-rp7x](https://github.com/advisories/GHSA-w9jx-4g6g-rp7x)); OWASP Java HTML
Sanitizer 2025 ([GHSA-g9gq-3pfx-2gw2](https://github.com/advisories/GHSA-g9gq-3pfx-2gw2));
Nokogiri HTML5 serializer 2026
([GHSA-4p39-36wj-23h4](https://github.com/advisories/GHSA-4p39-36wj-23h4)); sanitize-html 2026
([GHSA-x3q4-9hxx-gx8m](https://github.com/advisories/GHSA-x3q4-9hxx-gx8m)); the issue behind
[#9426](https://github.com/whatwg/html/issues/9426) itself ([whatwg/html#9426](https://github.com/whatwg/html/issues/9426)) names the Google
Search case.

Status: (a) not closed. (b) closes the attribute carrier only; comments and PIs still carry.
(c): per [#9426](https://github.com/whatwg/html/issues/9426)'s text, the flag then depends only on the user's setting, so DOMParser, `template`
and the live document agree, and the browser-internal parse-1 versus parse-2 mismatch goes away.
Not closed for server-side or library parsers that choose their own flag (the 2023 to 2026
advisories above are all of this kind), and unsure for users who disable scripting (parse 2 then
makes elements, but no script runs; resource loads and later adoption into a scripting-enabled
document are the risk, which I did not analyze). Also unsure whether [#9426](https://github.com/whatwg/html/issues/9426) leaves
`template`-contents behavior (Gecko and Blink differ today) fully aligned. (d) adds only the
foreign `noscript` part.

### M6: re-contextualization and fragment-context mismatch

Mechanism: parse 1 happens in one context (usually `body`), but the application inserts the
output somewhere else: wrapped inside `xmp`/`textarea`/`noscript`/`title`/`iframe`/... markup, set
as `innerHTML` of a `textarea`, `select`, `table`, `tr` or SVG element, or fed to `document.write`.
The sink context changes how comments, literal text and attributes are tokenized or whether start
tags are honored. Sonar calls this context-dependent mutation. DOMPurify's wiki lists it as
"context-bound output".

Years and sources: Gecko `innerHTML` versus `document.write` in 2015
([DOMPurify 0.6.7 notes](https://github.com/cure53/DOMPurify/releases/tag/0.6.7), Mozilla bug
1205631); Sonar 2024; DOMPurify "mXSS via Re-Contextualization", March 2026
([GHSA-h8r8-wccr-v5f2](https://github.com/cure53/DOMPurify/security/advisories/GHSA-h8r8-wccr-v5f2),
wrappers `script`, `xmp`, `iframe`, `noembed`, `noframes`, `noscript`); DOMPurify wiki sections 1
and 5.

Status: not closed in (a). (b) closes attribute carriers (the published case uses one). (c) does
not matter. (d) makes SVG/MathML `style`/`title`/`script`/`noscript` sink contexts consistent with
their HTML twins, but the HTML wrappers are unchanged, so comments, PIs and literal text of
`style`/`script`/`xmp`/... still break wrapper sinks. This is application composition; the spec
cannot close it. The Bughunters recommendation (return a DOM node, not a string) is the real fix.

### M7: spec-compliant structural non-roundtrips

Mechanism: some trees the parser builds do not reparse to themselves, with no browser bug
involved: a nested `form` created through the form element pointer, content moved by foster
parenting, formatting elements rearranged by the adoption agency algorithm, a `p` that holds a
block element via an integration point, table and `caption` handling, and implementation-defined
nesting limits that flatten deep trees (and so can differ on a second or third parse). The HTML
spec itself warns about this and gives the nested form and foster parenting examples
([serialization warning](https://html.spec.whatwg.org/multipage/parsing.html#warning-html-serializer-roundtrip)).
These are pivots, not carriers: alone they only change structure. They were the pivot in
securitum 2020, Mizu's depth-flattening, "elevator" and triple-parse bypasses (DOMPurify 3.1.0 to
3.1.2, [part 1](https://mizu.re/post/exploring-the-dompurify-library-bypasses-and-fixes)),
CVE-2024-47875 ([GHSA-gx9m-whjm-85jf](https://github.com/advisories/GHSA-gx9m-whjm-85jf), found
by icesfont), and the Kinugawa deep-nesting findings.

Status: the pivots exist in every column; none of the three changes touches them. What changes is
their payoff: every published instance needed a carrier from M1 to M4 (text, attribute, or comment
in an element whose tokenization flips with the pivot). Under (b)+(d) those carriers are gone for
namespace flips. What a structural pivot can still do without a carrier: change which element
owns a node (form owner, M11 text merging, element identity). I think that cannot yield markup
injection by itself, but I cannot prove it (see "classes that might survive").

### M8: removal or rewrite creates the pivot

Mechanism: the sanitizer deletes an element but keeps its children, strips an attribute that
decided the namespace of its subtree (`encoding` on `annotation-xml`), or unwraps a
`foreignObject`/`desc`/`title`/`mtext` integration point. Children then reparse in a different
namespace or scope. DOMPurify added `FORBID_CONTENTS` and element-removal mXSS checks for this
(2.0.6, 2.0.7, Kinugawa's forbidden-tag finding in the Sonar timeline); `foreignObject` was later
removed from the HTML entry points; ammonia 2025 and 2026 are the same mechanism.

Status: this supplies the pivot for M1 to M4, so the tokenization part follows their status
(closed in (d)). The element-identity part (an `image` element in SVG turns into HTML `img`; `a`,
`style`, `title`, `script` keep names but change semantics) is not closed by anything and I found
no published instance that needed it without a tokenization carrier. Unsure.

### M9: DOM-created nodes the parser cannot produce

Mechanism: script or a sanitizer builds nodes whose serialization does not reparse to the same
thing: text in an HTML raw-text element containing its own end tag, a comment containing the
comment terminator, a PI whose data contains the terminator character, a `textarea` with a
comment child, names whose case does not survive the HTML parser (case-preserved attribute names
set through DOM namespace APIs, upper-case foreign names), cloning or rebuilding that drops the
namespace (create an HTML element of the same name and copy children), and hook, `IN_PLACE` and
shadow-root edge cases. The HTML spec lists several of these as its own examples.

Years and sources: spec warning (above); Sonar's "desanitization" and "context-dependent" subclasses
([post](https://www.sonarsource.com/blog/mxss-the-vulnerability-hiding-in-your-code/));
DOMPurify `IN_PLACE` family 2026, including
[GHSA-6688-9rhm-gjv2](https://github.com/cure53/DOMPurify/security/advisories/GHSA-6688-9rhm-gjv2)
(a removed `style` root whose text holds markup is handed back; no foreign content involved),
and the wiki sections 12, 22 and 23.

Status: not closed in any column; the parser cannot make these trees, so no parser change
helps. One exception: a DOM-created HTML-namespace `style`-like element under an SVG/MathML parent
becomes safe in (d), because foreign `style` is no longer markup in parse 2. The reverse
(foreign element holding decoded text that contains an end tag, moved or rebuilt as an HTML
element) stays unsafe, as today.

### M10: DOM that appears after the sanitizer walk

Mechanism: the browser, not the parser, generates or moves nodes after sanitizing, so the
serialized result contains subtrees the sanitizer never visited: `selectedcontent` clones the
selected `option` and refreshes after the walk
([GHSA-87xg-pxx2-7hvx](https://github.com/cure53/DOMPurify/security/advisories/GHSA-87xg-pxx2-7hvx),
CVE-2026-47423); declarative partial updates (`template for`, PIs as markers) teleport content
into the tree; declarative shadow DOM and attached shadow roots are invisible to a light-DOM walk
(DOMPurify advisories GHSA-rp9w-3fw7-7cwq, GHSA-cg2g-xh64-v4q7); `template` contents use an owner
document whose scripting flag differs between engines (see [#9426](https://github.com/whatwg/html/issues/9426)). [Wiki sections 18 to
20](https://github.com/cure53/DOMPurify/wiki/Attack-Classes-&-Bypass-History) cover these.

Status: not closed, and orthogonal to [#6362](https://github.com/whatwg/html/issues/6362) and [#11397](https://github.com/whatwg/html/issues/11397). (c) helps only the `template` flag part. (d)
helps one thing: if patching inserts an HTML-namespace raw-text element into SVG/MathML, the
later serialization reparses safely (see M9).

### M11: text-node adjacency and merging

Mechanism: parse 1 yields several text nodes separated by an element that vanishes on reparse
(for instance an ignored nested `form` start tag), so adjacent fragments merge into one text
node that a template engine (Vue in-DOM templates, AngularJS) then evaluates. The pivot is M7's
nested form. Source: DOMPurify `SAFE_FOR_TEMPLATES` bypass, 2026
([GHSA-qm7q-q8h9-jg8q](https://github.com/cure53/DOMPurify/security/advisories/GHSA-qm7q-q8h9-jg8q)),
wiki section 13, CVE-2025-26791.

Status: not closed by anything; it is adjacent to mXSS (client-side template injection) and does
not need foreign content, attributes or a scripting flag. Out of reach of [#11397](https://github.com/whatwg/html/issues/11397).

### M12: character reference decoding differs by context

Mechanism: foreign `style` text was decoded for entities while the serializer wrote it back
raw (2013 paper, section 3.7), so an entity-encoded end tag became a literal one; later, Edge
decoded entities inside `title`, and Chrome (`noembed`) and Firefox (`noscript`) did inside
`DOMParser` (Kinugawa Feb 2019; both in the
[timeline](https://s1r1us.ninja/posts/mxss-101/)). Sources: the 2013 paper
([CCS'13](https://cure53.de/fp170.pdf)).

Status: the serializer rule (escape text unless the parent is an HTML raw-text element) closes
the 2013 form in the spec; later cases were engine bugs. RCDATA in (d) decodes like today's
foreign text, so (d) neither opens nor closes anything here. One small thing to keep in mind:
text from an HTML `style` that contains entity-looking text decodes when it lands in a foreign
`style` in parse 2. That changes text, not markup, unless a later step decodes again.

### M13: 2013 attribute and name classes

The paper lists seven subclasses: backtick as attribute delimiter (IE, Hasegawa 2007);
unknown elements with XML namespaces rewritten into unquoted pseudo-namespaces; backslashes in
CSS escapes; unrelated characters in entities breaking CSS strings; CSS escapes in property
names; entity mutation in non-HTML documents; entity mutation in the non-HTML context of HTML
documents (the SVG `style` case, which is M12). All were engine behaviors of that era; the
spec's serializer (always double-quoted attributes, qualified names only for non-HTML/SVG/MathML
elements) excludes them. Not applicable to the proposal.

### M14: engine non-conformance

Chrome 77 kept a `p` inside `svg` after a stray `</p>` (securitum 2019; fixed); Gecko's
`innerHTML` and `document.write` disagreed (2015); a Safari, Chrome and Edge `template` issue
(DOMPurify 2.0.3, 2019); Edge `title` entities; `DOMParser` entity decoding (Feb 2019); Chrome's
experimental DOM-import issue behind a flag (DOMPurify 2.2.0). Not closed or opened by spec
changes. A simpler foreign-content tokenization ([#11397](https://github.com/whatwg/html/issues/11397)) leaves fewer places to get wrong.

### M15: sanitizer-side parser or serializer non-conformance

Mechanism: the sanitizer's own parser does not match the browser's, so parse 1 is not the
browser's parse 1. Cases: namespace-unaware tokenizers (htmlparser2 in Joplin and
`sanitize-html`, the .NET and Typo3 sanitizers, ammonia before its namespace handling);
unescaped raw-text passthrough (`sanitize-html` `xmp` default,
[GHSA-rpr9-rxv7-x643](https://github.com/advisories/GHSA-rpr9-rxv7-x643); OWASP Java sanitizer
`style` with `allowTextIn`); wrong end-tag recognition (solidus after the end tag name,
[GHSA-jxwj-j7wr-gfrw](https://github.com/advisories/GHSA-jxwj-j7wr-gfrw); `--!>` ending a
comment, Typo3 CVE-2022-36020; CDATA in `math` read as a bogus comment, Typo3 CVE-2022-23499);
jsdom's raw-text parsing (DOMPurify 3.3.2 and 2.5.9, 2026); serializers that do not escape `<`
and `>` in attributes ([Nokogiri](https://github.com/advisories/GHSA-4p39-36wj-23h4),
[Loofah GHSA-h6v6-rg66-fqj4](https://github.com/advisories/GHSA-h6v6-rg66-fqj4), 2026).

Status: implementation bugs, so "not applicable" to the spec question. Still relevant: [#6362](https://github.com/whatwg/html/issues/6362) is
the normative statement that lets Nokogiri and Loofah call the attribute case a bug; and (d)
makes raw-text tokenization namespace-independent, which is what htmlparser2-style parsers
already do for these ten elements, so their remaining differences shrink to non-raw-text
foreign-content behavior (breakout elements, CDATA elsewhere, case adjustment).

### M16: `script` data escape states (residual of the proposal)

Mechanism: HTML `script` has escape and double-escape states (a comment opener followed by a
`script` start tag hides the end tag). Foreign `script` in the proposal is RCDATA with comment
nodes ended by the end tag. An HTML `script` whose text uses those states, reparsed as foreign
`script`, ends earlier and exposes the rest as markup. The repo README ruled this out for
sanitizer purposes because sanitizers drop `script`, and found one foreign case on real pages.

Status: not closed in (a) to (c) (it is the same today); in (d) the reverse direction (foreign
to HTML) looks stable by hand analysis, the forward direction does not, and I did not find any
published instance. Only matters if HTML `script` survives sanitizing, in which case the page
already has a simpler hole.

## Out of scope

- XML versus HTML parse differences (DOMParser XML documents then HTML, PIs from XML,
  `application/xhtml+xml` handling: e.g. DOMPurify 3.0.10, [GHSA-c6gr-qvv4-5v3f](https://github.com/advisories/GHSA-c6gr-qvv4-5v3f)).
- Encoding and charset confusion (UTF-7, ISO-2022-JP, meta charset flips).
- DOM clobbering (named elements shadowing `nodeName`, `parentNode`, `attributes`; DOMPurify wiki
  section 11).
- CSS-based issues (CSS strings, `@import`, `url()` in `style`, 2013 CSS escape classes as CSS bugs).
- URL scheme and SMIL attribute issues (`javascript:` in `href`, SMIL `animate`/`set`/`animateTransform`
  rewriting `href`: Mizu's SMIL post, Loofah GHSA-9wjq-cp2p-hrgf, sanitize-html SMIL advisories).
- Configuration and API misuse (permissive custom element patterns, prototype pollution,
  `ADD_TAGS` precedence, `SAFE_FOR_TEMPLATES` regex bugs).
- Server-side string concatenation that places sanitized output after unrelated markup.

## Classes that might survive

1. **Sink-context mismatch (M6).** Survives for HTML wrappers with comment, PI or literal-text
   carriers. Needs the application to put output in a different context. Not fixable in the parser.
2. **DOM-created nodes (M9) and `IN_PLACE`-style APIs.** Survives. The parser cannot produce
   these trees, so the serializer is the only lever; making the serializer escape unsafe
   text (for instance serialize raw text only when it cannot close the element) would be a spec
   change of a different kind. The README's "serializer mode" idea is the nearest candidate.
3. **Parse-time DOM generation (M10).** Survives; per-feature (`selectedcontent`, `template for`,
   declarative shadow DOM). Each new feature that generates nodes after parsing reopens it.
4. **Noscript with external parsers (M5).** After [#9426](https://github.com/whatwg/html/issues/9426), closed for browser-internal pairs, not for
   library parsers with their own flag and not for users with scripting disabled. Also depends on
   what [#9426](https://github.com/whatwg/html/issues/9426) specifies for `template` contents and for `DOMParser`; I did not read the final text.
5. **Structural pivots without published carriers (M7, M8, M11).** Survive as pivots. What I
   could not rule out: an element-identity flip (SVG `image` to HTML `img`, `a`, `title`) combined
   with attributes the sanitizer allows for the SVG identity; PIs and `<template for>`
   interacting with [#12118](https://github.com/whatwg/html/issues/12118) (PIs now parse in HTML; their serializer output and the PI
   terminator rules need a round-trip proof, and DOM or XML-created PIs can contain `>`);
   select/option content model changes (customizable select parsing, `selectedcontent`) as
   engine-version differentials during rollout; insertion-mode-dependent handling of raw-text
   start tags (select, frameset, table, head, template), where a start tag that parse 2 ignores
   would turn literal raw text into markup. I found no published case of the last one.
6. **Transition.** Everything in (d) applies only to updated engines. Stored or server-sanitized
   content, and sanitizers parsing with html5lib, ammonia, jsdom or Nokogiri before the browser
   ships, keep M1 to M4 for as long as old browsers exist (the README's transition section covers
   the sanitizer-side checklist).
7. **Residual M16 and PI/comment edge cases in the tokenizer.** Unsure; both need a fuzzer
   rather than a literature answer: round-trip every parser-created comment and PI through
   serialize and reparse under every pivot context, and compare against a model of the new
   tokenizer.

Overall: literature gives no published HTML-to-HTML mXSS that, after [#6362](https://github.com/whatwg/html/issues/6362) and [#9426](https://github.com/whatwg/html/issues/9426), is not
either (i) a foreign-versus-HTML raw-text tokenization difference (closed by the proposal), or
(ii) an application, DOM-API, implementation-bug or new-feature class (outside it). That is
evidence, not proof: Mizu and Kinugawa found new pivots roughly every few months from 2024 to
2026, and the DOMPurify wiki says "no known bypass" does not mean the search is over.

## Sources not accessed

The Bughunters post (Michał Bentkowski, June 2025): the fetch returned only the title; its content
here comes from search summaries and the Chrome blog. The securitum.com posts redirect now; I used
the local web.archive.org copies. Not read in full: Mizu part 2 (misconfigurations), Mizu's SMIL
and custom-element posts, the vovohelo and nsysean write-ups, Kinugawa's tweets, Heiderich's Hack
in Paris slides, and the Joplin/Typo3 advisory details (taken from the Sonar post and cheatsheet).
The 2013 paper was only partly readable (text extracted from the PDF with the spaces lost). No
mXSS advisories turned up for jsoup, and none for `sanitize-html` before 2026 beyond those cited.
Advisory dates after mid-2026 come straight from `gh api` and are not cross-checked.
