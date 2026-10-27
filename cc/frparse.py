"""html5lib, patched to optionally implement the proposed parsing change (whatwg/html#11397).

New mode: in foreign content, a non-self-closing start tag for style, xmp, iframe, noembed,
noframes, noscript (RAWTEXT), script (script data), title, textarea (RCDATA) or plaintext
(PLAINTEXT) creates the SVG/MathML element as today but switches the tokenizer like the HTML
element would ("raw" mode), or to RCDATA for all of them except plaintext ("rcdata" mode). In those states, when the current node is foreign, `<![CDATA[` is dropped and
sets a flag; while the flag is set, the next `]]>` is dropped and clears it.

parse(html, mode) (mode: "old", "raw" or "rcdata") returns (document, info) where info records each foreign element of interest.
"""
import html5lib
from html5lib import _tokenizer, html5parser
from html5lib.constants import EOF, namespaces, spaceCharacters, tokenTypes

HTML_NS = namespaces["html"]
RAWTEXT = {"style", "xmp", "iframe", "noembed", "noframes", "noscript"}
RCDATA = {"title", "textarea"}
NAMES = RAWTEXT | RCDATA | {"script", "plaintext"}

T = _tokenizer.HTMLTokenizer


def _foreign(tok):
    oe = tok.parser.tree.openElements
    return bool(oe) and oe[-1].namespace not in (None, HTML_NS)


def _new(tok):
    return getattr(tok.parser, "_fr_new", False)


def _cdata_close(tok):
    """Called with ']' consumed and the flag set. Returns True if ']]>' was consumed."""
    c2 = tok.stream.char()
    if c2 == "]":
        c3 = tok.stream.char()
        if c3 == ">":
            tok._fr_cdata = False
            tok.parser._fr_info["cdata_close"] += 1
            return True
        tok.stream.unget(c3)
    tok.stream.unget(c2)
    return False


def _make_text_state(orig, stop, has_amp):
    def state(self):
        if not getattr(self, "_fr_cdata", False):
            return orig(self)
        data = self.stream.char()
        if data == "]":
            if not _cdata_close(self):
                self.tokenQueue.append({"type": tokenTypes["Characters"], "data": "]"})
            return True
        # The original states consume runs past "]" only in their catch-all branch (and, in
        # RAWTEXT and script data, for spaces), so delegate everything else to them. Between
        # CDATA markers, "&" is plain text, as in a CDATA section today.
        if data in ("<", "\u0000", EOF) or (has_amp and data in spaceCharacters):
            self.stream.unget(data)
            return orig(self)
        chars = self.stream.charsUntil(tuple(c for c in stop if c != "&") + ("]",))
        self.tokenQueue.append({"type": tokenTypes["Characters"], "data": data + chars})
        return True
    return state


T.rawtextState = _make_text_state(T.rawtextState, ("<", "\u0000"), False)
T.scriptDataState = _make_text_state(T.scriptDataState, ("<", "\u0000"), False)
T.rcdataState = _make_text_state(T.rcdataState, ("&", "<", "\u0000"), True)


def _make_lt_state(orig, base_name):
    def state(self):
        if _new(self) and _foreign(self):
            data = self.stream.char()
            if data == "!":
                want = "[CDATA["
                got = []
                for ch in want:
                    c = self.stream.char()
                    got.append(c)
                    if c != ch:
                        break
                if "".join(got) == want:
                    self._fr_cdata = True
                    self.parser._fr_info["cdata_open"] += 1
                    self.state = getattr(self, base_name)
                    return True
                for c in reversed(got):
                    self.stream.unget(c)
            self.stream.unget(data)
        return orig(self)
    return state


T.rawtextLessThanSignState = _make_lt_state(T.rawtextLessThanSignState, "rawtextState")
T.rcdataLessThanSignState = _make_lt_state(T.rcdataLessThanSignState, "rcdataState")
T.scriptDataLessThanSignState = _make_lt_state(T.scriptDataLessThanSignState, "scriptDataState")


class Parser(html5lib.HTMLParser):
    def __init__(self, mode):
        super().__init__(tree=html5lib.getTreeBuilder("etree"), namespaceHTMLElements=True)
        assert mode in ("old", "raw", "rcdata")
        self._fr_mode = mode
        self._fr_new = mode != "old"

    def reset(self):
        super().reset()
        self._fr_info = {"elements": [], "cdata_open": 0, "cdata_close": 0}


def _patched_start_tag(orig):
    def processStartTag(self, token):
        parser = self.parser
        name = token["name"]
        before = len(parser.tree.openElements)
        ret = orig(self, token)
        if ret is None and name in NAMES and hasattr(parser, "_fr_info"):
            node = parser.tree.openElements[-1] if len(parser.tree.openElements) > before else None
            rec = {"name": name, "self_closing": bool(token["selfClosing"]), "switched": False,
                   "cdata_before": parser._fr_info["cdata_open"]}
            if node is not None and node.name == name and node.namespace != HTML_NS:
                rec["ns"] = "svg" if node.namespace == namespaces["svg"] else "math"
                rec["node"] = node
                if parser._fr_new:
                    tok = parser.tokenizer
                    tok._fr_cdata = False
                    if parser._fr_mode == "rcdata" and name != "plaintext":
                        tok.state = tok.rcdataState
                    elif name in RAWTEXT:
                        tok.state = tok.rawtextState
                    elif name in RCDATA:
                        tok.state = tok.rcdataState
                    elif name == "script":
                        tok.state = tok.scriptDataState
                    else:
                        tok.state = tok.plaintextState
                    rec["switched"] = True
            else:
                # Self-closing: the element was pushed and popped; it's the last child.
                cur = parser.tree.openElements[-1]
                kids = list(cur._element)
                rec["ns"] = "svg" if cur.namespace == namespaces["svg"] else "math"
                rec["etree"] = kids[-1] if kids else None
            parser._fr_info["elements"].append(rec)
        return ret
    return processStartTag


_fc = type(Parser("old").phases["inForeignContent"])
_fc.processStartTag = _patched_start_tag(_fc.processStartTag)


def parse(html, mode):
    p = Parser(mode)
    doc = p.parse(html)
    info = p._fr_info
    tok = p.tokenizer
    info["eof_state"] = tok.state.__name__ if hasattr(tok.state, "__name__") else str(tok.state)
    info["eof_cdata_open"] = bool(getattr(tok, "_fr_cdata", False))
    oe = p.tree.openElements
    info["eof_current"] = (oe[-1].name, oe[-1].namespace) if oe else None
    els = info["elements"]
    for i, rec in enumerate(els):
        node = rec.pop("node", None)
        rec["open_at_eof"] = node is not None and node in oe
        if node is not None:
            rec["etree"] = node._element
        after = els[i + 1]["cdata_before"] if i + 1 < len(els) else info["cdata_open"]
        rec["cdata_markers"] = after - rec["cdata_before"]
    return doc, info
