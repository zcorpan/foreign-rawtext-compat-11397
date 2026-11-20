"""Reference parser for whatwg/html#11397 ("foreign RCDATA"), built on html5lib 1.1.

make_parser("old") returns an unmodified html5lib parser; make_parser("new")
returns a subclass that follows the new spec text for the states listed in
the module docstring of each class.  Nothing global is monkeypatched: the
installed html5lib is left alone and "old" mode never touches the new code.

Limitations (new mode):
 * <template> content is not modelled (html5lib 1.1 has no template support).
 * Fragment contexts "svg x"/"math x" are supported for tokenizer state and
   for the adjusted current node, but the insertion-mode reset for them is
   html5lib's "in body" fallback.
 * Tokenizer states are the spec's, written char by char, only for the states
   listed in NewTokenizer; all other states are html5lib 1.1's.
"""
import re
from collections import deque

from html5lib import html5parser, _tokenizer
from html5lib.constants import (tokenTypes, spaceCharacters, asciiLetters,
                                asciiUpper2Lower, EOF, namespaces,
                                htmlIntegrationPointElements)
from html5lib.treebuilders import base

TT = tokenTypes
LOWER = asciiUpper2Lower
HTML_NS = namespaces["html"]
FOREIGN_RCDATA_NAMES = ("title", "style", "script", "noscript")


# ---------------------------------------------------------------- tree

class PIData(str):
    """Comment-token payload that marks a processing instruction."""
    def __new__(cls, target, data):
        o = str.__new__(cls, target + " " + data)
        o.target = target
        o.pidata = data
        return o


class Node(base.Node):
    def __init__(self, name, namespace=None, kind="element"):
        base.Node.__init__(self, name)
        self.namespace = namespace
        self.kind = kind

    @property
    def nameTuple(self):
        return (self.namespace, self.name)

    def appendChild(self, node):
        node.parent = self
        self.childNodes.append(node)

    def insertText(self, data, insertBefore=None):
        if insertBefore is None:
            if self.childNodes and self.childNodes[-1].kind == "text":
                self.childNodes[-1].value += data
            else:
                self.appendChild(_text(data))
        else:
            i = self.childNodes.index(insertBefore)
            if i > 0 and self.childNodes[i - 1].kind == "text":
                self.childNodes[i - 1].value += data
            else:
                t = _text(data)
                t.parent = self
                self.childNodes.insert(i, t)

    def insertBefore(self, node, refNode):
        i = self.childNodes.index(refNode)
        node.parent = self
        self.childNodes.insert(i, node)

    def removeChild(self, node):
        self.childNodes.remove(node)
        node.parent = None

    def cloneNode(self):
        n = Node(self.name, self.namespace)
        n.attributes = dict(self.attributes)
        return n

    def hasContent(self):
        return bool(self.childNodes)


def _text(data):
    n = Node("#text", kind="text")
    n.value = data
    return n


class DocNode(Node):
    def __init__(self):
        Node.__init__(self, "#document", kind="document")


class FragNode(Node):
    def __init__(self):
        Node.__init__(self, "#document-fragment", kind="fragment")


class CommentNode(Node):
    def __init__(self, data):
        Node.__init__(self, "#comment",
                      kind="pi" if isinstance(data, PIData) else "comment")
        self.value = data


class DoctypeNode(Node):
    def __init__(self, name, publicId=None, systemId=None):
        Node.__init__(self, name, kind="doctype")
        self.publicId = publicId
        self.systemId = systemId


class TreeBuilder(base.TreeBuilder):
    documentClass = DocNode
    elementClass = Node
    commentClass = CommentNode
    doctypeClass = DoctypeNode
    fragmentClass = FragNode

    def testSerializer(self, node):
        raise NotImplementedError

    def getDocument(self):
        return self.document

    errorHook = None   # set by the "old1" parser: step 1 parse errors

    def insertComment(self, token, parent=None):
        if parent is None:
            parent = self.openElements[-1]
        d = token["data"]
        if (self.errorHook and parent.kind == "element" and parent.namespace != HTML_NS
                and parent.name in FOREIGN_RCDATA_NAMES):
            pi = isinstance(d, PIData)
            if has_end_tag(d.pidata if pi else d, parent.name):
                self.errorHook("step1-pi-contains-end-tag" if pi
                               else "step1-comment-contains-end-tag")
        parent.appendChild(CommentNode(d))

    def insertDoctype(self, token):
        d = DoctypeNode(token["name"], token["publicId"], token["systemId"])
        self.document.appendChild(d)


def has_end_tag(text, name):
    """text contains '</' + name (ASCII case-insensitive) + tab/LF/FF/space/'/'/'>'."""
    return re.search("</" + re.escape(name) + "[\t\n\f />]", text, re.I | re.A) is not None


def dump(root):
    """Dump in the .dat '#document' format (without the '#document' line)."""
    prefixes = {namespaces["svg"]: "svg ", namespaces["mathml"]: "math "}
    lines = []

    def children(node):
        out = []
        for c in node.childNodes:
            if c.kind == "text" and out and out[-1].kind == "text":
                merged = _text(out[-1].value + c.value)
                out[-1] = merged
            else:
                out.append(c)
        return [c for c in out if not (c.kind == "text" and c.value == "")]

    def walk(node, depth):
        pad = " " * (2 * depth - 1) if depth > 0 else ""
        inner = " " * (2 * depth + 1)
        k = node.kind
        if k == "doctype":
            if node.publicId or node.systemId:
                lines.append('|%s<!DOCTYPE %s "%s" "%s">' % (
                    pad, node.name or "", node.publicId or "", node.systemId or ""))
            else:
                lines.append("|%s<!DOCTYPE %s>" % (pad, node.name or ""))
        elif k == "comment":
            lines.append("|%s<!-- %s -->" % (pad, node.value))
        elif k == "pi":
            lines.append("|%s<?%s %s?>" % (pad, node.value.target, node.value.pidata))
        elif k == "text":
            lines.append('|%s"%s"' % (pad, node.value))
        elif k == "element":
            lines.append("|%s<%s%s>" % (pad, prefixes.get(node.namespace, ""), node.name))
            attrs = []
            for key, val in node.attributes.items():
                if isinstance(key, tuple):
                    n = (key[0] + " " + key[1]) if key[0] else key[1]
                else:
                    n = key
                attrs.append((n, val))
            attrs.sort(key=lambda a: a[0].encode("utf-16-be"))
            for n, val in attrs:
                lines.append('|%s%s="%s"' % (inner, n, val))
        for c in children(node):
            walk(c, depth + 1)

    for c in children(root):
        walk(c, 1)
    return "\n".join(lines)


# ------------------------------------------------------------ tokenizer

class _EOFStream:
    """Stands in for the input stream for one step: next input char is EOF."""
    def __init__(self, real):
        self._real = real

    def char(self):
        return EOF

    def charsUntil(self, *a, **k):
        return ""

    def unget(self, c):
        pass

    def __getattr__(self, n):
        return getattr(self._real, n)


class NewTokenizer(_tokenizer.HTMLTokenizer):
    """Spec-faithful (whatwg/html#11397) states: foreign RCDATA (+ less-than
    sign), tag open, end tag open, markup declaration open, bogus comment,
    comment (all states), CDATA section (3 states), processing instruction
    (5 states), plus the foreign RCDATA flag rule."""

    def __init__(self, *a, **k):
        _tokenizer.HTMLTokenizer.__init__(self, *a, **k)
        self.foreignFlag = False
        self.lastStartTag = None
        self.returnState = self.dataState
        self.tempBuffer = ""
        self._sim = False
        self._real = None

    # -- driver
    def __iter__(self):
        self.tokenQueue = deque([])
        real = self.stream
        self._real = real
        while True:
            self._sim = False
            if self.foreignFlag and self.lastStartTag and self._flagMatches():
                self._sim = True
                self.stream = _EOFStream(real)
            try:
                cont = self.state()
            finally:
                self.stream = real
            if not cont:
                break
            while self.stream.errors:
                yield {"type": TT["ParseError"], "data": self.stream.errors.pop(0)}
            while self.tokenQueue:
                yield self.tokenQueue.popleft()
        # tokenization ended: flush anything queued by the last step
        while self.stream.errors:
            yield {"type": TT["ParseError"], "data": self.stream.errors.pop(0)}
        while self.tokenQueue:
            yield self.tokenQueue.popleft()

    # -- helpers
    def peek(self, n):
        s = self.stream
        cs = [s.char() for _ in range(n)]
        for c in reversed(cs):
            s.unget(c)
        return cs

    def consume(self, n):
        for _ in range(n):
            self._real.char() if self._sim else self.stream.char()

    def _flagMatches(self):
        name = self.lastStartTag
        n = len(name)
        s = self.peek(n + 3)
        if EOF in s:
            return False
        s = "".join(s)
        return (s[:2] == "</" and s[2:2 + n].translate(LOWER) == name
                and s[2 + n] in "\t\n\f />")

    def err(self, code):
        self.tokenQueue.append({"type": TT["ParseError"], "data": code})

    def emitChar(self, c):
        t = TT["SpaceCharacters"] if c in spaceCharacters else TT["Characters"]
        self.tokenQueue.append({"type": t, "data": c})

    def emitComment(self):
        self.tokenQueue.append(self.currentToken)

    def newComment(self, data=""):
        self.currentToken = {"type": TT["Comment"], "data": data}

    def eof(self):
        """'Emit an end-of-file token' (with the foreign RCDATA flag rule)."""
        if self._sim:
            name = self.lastStartTag
            self.foreignFlag = False
            self.consume(2 + len(name))
            self.currentToken = {"type": TT["EndTag"], "name": name,
                                 "data": [], "selfClosing": False}
            self.state = self.tagNameState
            return True
        return False

    def adjustedIsHTML(self):
        p = self.parser
        node = p.adjustedCurrentNode() if p is not None else None
        return node is None or node.namespace == p.tree.defaultNamespace

    def emitCurrentToken(self):
        t = self.currentToken
        _tokenizer.HTMLTokenizer.emitCurrentToken(self)
        if t["type"] == TT["StartTag"]:
            self.lastStartTag = t["name"]

    # -- foreign RCDATA
    def foreignRcdataState(self):
        c = self.stream.char()
        if c == "&":
            self.returnState = self.foreignRcdataState
            self.consumeEntity()      # character reference state
            self.state = self.foreignRcdataState
        elif c == "<":
            self.state = self.foreignRcdataLessThanState
        elif c == "\u0000":
            self.err("unexpected-null-character")
            self.emitChar("�")
        elif c is EOF:
            return self.eof()
        else:
            self.emitChar(c)
        return True

    def foreignRcdataLessThanState(self):
        c = self.stream.char()
        if c == "!":
            self.returnState = self.foreignRcdataState
            if self.foreignFlag or "".join(c for c in self.peek(7) if c is not EOF) == "[CDATA[":
                self.state = self.markupDeclarationOpenState
            else:
                self.emitChar("<")
                self.stream.unget(c)
                self.state = self.foreignRcdataState
        elif c == "?" and self.foreignFlag:
            self.returnState = self.foreignRcdataState
            self.tempBuffer = ""
            self.state = self.piOpenState
        else:
            self.emitChar("<")
            self.stream.unget(c)
            self.state = self.foreignRcdataState
        return True

    # -- tag open / end tag open
    def tagOpenState(self):
        c = self.stream.char()
        if c == "!":
            self.returnState = self.dataState
            self.state = self.markupDeclarationOpenState
        elif c == "/":
            self.state = self.closeTagOpenState
        elif c is not EOF and c in asciiLetters:
            self.currentToken = {"type": TT["StartTag"], "name": c, "data": [],
                                 "selfClosing": False,
                                 "selfClosingAcknowledged": False}
            self.state = self.tagNameState
        elif c == "?":
            self.returnState = self.dataState
            self.tempBuffer = ""
            self.state = self.piOpenState
        elif c is EOF:
            self.err("eof-before-tag-name")
            self.emitChar("<")
            return self.eof()
        else:
            self.err("invalid-first-character-of-tag-name")
            self.emitChar("<")
            self.stream.unget(c)
            self.state = self.dataState
        return True

    def closeTagOpenState(self):
        c = self.stream.char()
        if c is not EOF and c in asciiLetters:
            self.currentToken = {"type": TT["EndTag"], "name": c, "data": [],
                                 "selfClosing": False}
            self.state = self.tagNameState
        elif c == ">":
            self.err("missing-end-tag-name")
            self.state = self.dataState
        elif c is EOF:
            self.err("eof-before-tag-name")
            self.emitChar("<")
            self.emitChar("/")
            return self.eof()
        else:
            self.err("invalid-first-character-of-tag-name")
            self.returnState = self.dataState
            self.newComment()
            self.stream.unget(c)
            self.state = self.bogusCommentState
        return True

    # -- bogus comment, markup declaration open
    def bogusCommentState(self):
        c = self.stream.char()
        if c == ">":
            self.state = self.returnState
            self.emitComment()
        elif c is EOF:
            self.emitComment()
            return self.eof()
        elif c == "\u0000":
            self.err("unexpected-null-character")
            self.currentToken["data"] += "�"
        else:
            self.currentToken["data"] += c
        return True

    def markupDeclarationOpenState(self):
        s = "".join(c for c in self.peek(7) if c is not EOF)
        if s[:2] == "--":
            self.consume(2)
            self.newComment()
            self.state = self.commentStartState
        elif (len(s) == 7 and s.translate(LOWER) == "doctype"
              and self.returnState != self.foreignRcdataState):
            self.consume(7)
            self.currentToken = {"type": TT["Doctype"], "name": "",
                                 "publicId": None, "systemId": None,
                                 "correct": True}
            self.state = self.doctypeState
        elif s == "[CDATA[" and (
                self.foreignCdataAllowed()):
            self.consume(7)
            self.state = self.cdataSectionState
        elif s == "[CDATA[":
            self.consume(7)
            self.err("cdata-in-html-content")
            self.newComment("[CDATA[")
            self.state = self.bogusCommentState
        else:
            self.err("incorrectly-opened-comment")
            self.newComment()
            self.state = self.bogusCommentState
        return True

    def foreignCdataAllowed(self):
        return not self.adjustedIsHTML()

    # -- comment states
    def commentStartState(self):
        c = self.stream.char()
        if c == "-":
            self.state = self.commentStartDashState
        elif c == ">":
            self.err("abrupt-closing-of-empty-comment")
            self.state = self.returnState
            self.emitComment()
        else:
            self.stream.unget(c)
            self.state = self.commentState
        return True

    def commentStartDashState(self):
        c = self.stream.char()
        if c == "-":
            self.state = self.commentEndState
        elif c == ">":
            self.err("abrupt-closing-of-empty-comment")
            self.state = self.returnState
            self.emitComment()
        elif c is EOF:
            self.err("eof-in-comment")
            self.emitComment()
            return self.eof()
        else:
            self.currentToken["data"] += "-"
            self.stream.unget(c)
            self.state = self.commentState
        return True

    def commentState(self):
        c = self.stream.char()
        if c == "<":
            self.currentToken["data"] += c
            self.state = self.commentLessThanSignState
        elif c == "-":
            self.state = self.commentEndDashState
        elif c == "\u0000":
            self.err("unexpected-null-character")
            self.currentToken["data"] += "�"
        elif c is EOF:
            self.err("eof-in-comment")
            self.emitComment()
            return self.eof()
        else:
            self.currentToken["data"] += c
        return True

    def commentLessThanSignState(self):
        c = self.stream.char()
        if c == "!":
            self.currentToken["data"] += c
            self.state = self.commentLessThanSignBangState
        elif c == "<":
            self.currentToken["data"] += c
        else:
            self.stream.unget(c)
            self.state = self.commentState
        return True

    def commentLessThanSignBangState(self):
        c = self.stream.char()
        if c == "-":
            self.state = self.commentLessThanSignBangDashState
        else:
            self.stream.unget(c)
            self.state = self.commentState
        return True

    def commentLessThanSignBangDashState(self):
        c = self.stream.char()
        if c == "-":
            self.state = self.commentLessThanSignBangDashDashState
        else:
            self.stream.unget(c)
            self.state = self.commentEndDashState
        return True

    def commentLessThanSignBangDashDashState(self):
        c = self.stream.char()
        if c != ">" and c is not EOF:
            self.err("nested-comment")
        self.stream.unget(c)
        self.state = self.commentEndState
        return True

    def commentEndDashState(self):
        c = self.stream.char()
        if c == "-":
            self.state = self.commentEndState
        elif c is EOF:
            self.err("eof-in-comment")
            self.emitComment()
            return self.eof()
        else:
            self.currentToken["data"] += "-"
            self.stream.unget(c)
            self.state = self.commentState
        return True

    def commentEndState(self):
        c = self.stream.char()
        if c == ">":
            self.state = self.returnState
            self.emitComment()
        elif c == "!":
            self.state = self.commentEndBangState
        elif c == "-":
            self.currentToken["data"] += "-"
        elif c is EOF:
            self.err("eof-in-comment")
            self.emitComment()
            return self.eof()
        else:
            self.currentToken["data"] += "--"
            self.stream.unget(c)
            self.state = self.commentState
        return True

    def commentEndBangState(self):
        c = self.stream.char()
        if c == "-":
            self.currentToken["data"] += "--!"
            self.state = self.commentEndDashState
        elif c == ">":
            self.err("incorrectly-closed-comment")
            self.state = self.returnState
            self.emitComment()
        elif c is EOF:
            self.err("eof-in-comment")
            self.emitComment()
            return self.eof()
        else:
            self.currentToken["data"] += "--!"
            self.stream.unget(c)
            self.state = self.commentState
        return True

    # -- CDATA
    def cdataSectionState(self):
        c = self.stream.char()
        if c == "]":
            self.state = self.cdataSectionBracketState
        elif c is EOF:
            self.err("eof-in-cdata")
            return self.eof()
        elif c == "\u0000":
            self.err("unexpected-null-character")
            self.emitChar("�")
        else:
            self.emitChar(c)
        return True

    def cdataSectionBracketState(self):
        c = self.stream.char()
        if c == "]":
            self.state = self.cdataSectionEndState
        else:
            self.emitChar("]")
            self.stream.unget(c)
            self.state = self.cdataSectionState
        return True

    def cdataSectionEndState(self):
        c = self.stream.char()
        if c == "]":
            self.emitChar("]")
        elif c == ">":
            self.state = self.returnState
        else:
            self.emitChar("]")
            self.emitChar("]")
            self.stream.unget(c)
            self.state = self.cdataSectionState
        return True

    # -- processing instructions
    def convertBufferToComment(self):
        self.newComment("?" + self.tempBuffer)

    def piOpenState(self):
        c = self.stream.char()
        if c is not EOF and (c in asciiLetters or c == "_"):
            self.stream.unget(c)
            self.state = self.piTargetState
        elif c is EOF:
            self.err("eof-in-processing-instruction")
            return self.eof()
        else:
            self.err("invalid-first-character-of-processing-instruction-target")
            self.convertBufferToComment()
            self.stream.unget(c)
            self.state = self.bogusCommentState
        return True

    def piTargetState(self):
        c = self.stream.char()
        if c is not EOF and (c in "\t\n\f\r ?>"):
            target = self.tempBuffer
            if target.translate(LOWER) in ("xml", "xml-stylesheet"):
                self.err("disallowed-processing-instruction-target")
                self.convertBufferToComment()
                self.stream.unget(c)
                self.state = self.bogusCommentState
            else:
                self.piTarget = target
                self.piData = ""
                self.stream.unget(c)
                self.state = self.piAfterTargetState
        elif c is not EOF and (c in asciiLetters or c.isascii() and c.isdigit()
                               or c in "-_"):
            self.tempBuffer += c
        elif c is EOF:
            self.err("eof-in-processing-instruction")
            return self.eof()
        else:
            self.err("invalid-processing-instruction-target")
            self.convertBufferToComment()
            self.stream.unget(c)
            self.state = self.bogusCommentState
        return True

    def piAfterTargetState(self):
        c = self.stream.char()
        if c is not EOF and c in "\t\n\f\r ":
            pass
        else:
            self.stream.unget(c)
            self.state = self.piDataState
        return True

    def _emitPI(self):
        self.tokenQueue.append({"type": TT["Comment"],
                                "data": PIData(self.piTarget, self.piData)})

    def piDataState(self):
        c = self.stream.char()
        if c == "?":
            self.state = self.piQuestionableState
        elif c == ">":
            self.state = self.returnState
            self._emitPI()
        elif c is EOF:
            self.err("eof-in-processing-instruction")
            return self.eof()
        else:
            self.piData += c
        return True

    def piQuestionableState(self):
        c = self.stream.char()
        if c == ">":
            self.state = self.returnState
            self._emitPI()
        elif c is EOF:
            self.err("eof-in-processing-instruction")
            return self.eof()
        else:
            self.piData += "?"
            self.stream.unget(c)
            self.state = self.piDataState
        return True


# ------------------------------------------------------------ parser

NEW_BREAKOUT_EXTRA = frozenset(["textarea", "xmp", "iframe", "noembed",
                                "noframes", "plaintext"])
NEW_HIP = frozenset(htmlIntegrationPointElements) - {(namespaces["svg"], "title")}


def _make_foreign_phase(base_cls, old1=False):
    class NewForeignContent(base_cls):
        breakoutElements = (base_cls.breakoutElements if old1
                            else base_cls.breakoutElements | NEW_BREAKOUT_EXTRA)

        def processStartTag(self, token):
            parser = self.parser
            currentNode = parser.adjustedCurrentNode()
            if (token["name"] in self.breakoutElements or
                (token["name"] == "font" and
                 set(token["data"].keys()) & {"color", "face", "size"})):
                parser.parseError("unexpected-html-element-in-foreign-content",
                                  {"name": token["name"]})
                oe = self.tree.openElements
                while (oe[-1].namespace != self.tree.defaultNamespace and
                       not parser.isHTMLIntegrationPoint(oe[-1]) and
                       not parser.isMathMLTextIntegrationPoint(oe[-1])):
                    oe.pop()
                # "Reprocess the token according to the rules given in the section
                # corresponding to the current insertion mode in HTML content."
                return parser.phase.processStartTag(token)
            if currentNode.namespace == namespaces["mathml"]:
                parser.adjustMathMLAttributes(token)
            elif currentNode.namespace == namespaces["svg"]:
                self.adjustSVGTagNames(token)
                parser.adjustSVGAttributes(token)
            parser.adjustForeignAttributes(token)
            token["namespace"] = currentNode.namespace
            if old1 and token["name"] in NEW_BREAKOUT_EXTRA:
                parser.parseError("step1-foreign-start-tag-html-rawtext", {})
            self.tree.insertElement(token)
            if token["selfClosing"]:
                self.tree.openElements.pop()
                token["selfClosingAcknowledged"] = True
            elif (not old1) and self.tree.openElements[-1].name in FOREIGN_RCDATA_NAMES:
                parser.tokenizer.state = parser.tokenizer.foreignRcdataState
                parser.tokenizer.foreignFlag = True

        def processEndTag(self, token):
            parser = self.parser
            oe = self.tree.openElements
            if token["name"] in ("br", "p"):
                parser.parseError("unexpected-end-tag", {"name": token["name"]})
                while (oe[-1].namespace != self.tree.defaultNamespace and
                       not parser.isHTMLIntegrationPoint(oe[-1]) and
                       not parser.isMathMLTextIntegrationPoint(oe[-1])):
                    oe.pop()
                return parser.phase.processEndTag(token)
            nodeIndex = len(oe) - 1
            node = oe[-1]
            if node.name.translate(LOWER) != token["name"]:
                parser.parseError("unexpected-end-tag", {"name": token["name"]})
            while True:
                if nodeIndex == 0:          # topmost element: fragment case
                    return None
                if node.name.translate(LOWER) == token["name"]:
                    if parser.phase == parser.phases["inTableText"]:
                        parser.phase.flushCharacters()
                        parser.phase = parser.phase.originalPhase
                    while oe.pop() != node:
                        pass
                    return None
                nodeIndex -= 1
                node = oe[nodeIndex]
                if node.namespace != self.tree.defaultNamespace:
                    continue
                return parser.phase.processEndTag(token)
    return NewForeignContent


class NewParser(html5parser.HTMLParser):
    old1 = False      # True: today's spec plus step 1 parse errors ("step1-*")
    tokenizerClass = None   # set below

    def __init__(self, *a, **k):
        html5parser.HTMLParser.__init__(self, *a, **k)
        old = self.phases["inForeignContent"]
        self.phases["inForeignContent"] = _make_foreign_phase(type(old), self.old1)(self, self.tree)
        self.fragmentContextNode = None
        if self.old1:
            self.tree.errorHook = lambda code: self.parseError(code, {})

    def preDispatch(self, token, cur):
        """Step 1 dispatcher paragraph (old1 only)."""
        if (self.old1 and token["type"] == TT["StartTag"] and cur is not None
                and cur.namespace != HTML_NS and cur.name in FOREIGN_RCDATA_NAMES):
            self.parseError("step1-start-tag-in-foreign-rcdata-element", {})
        elif (self.old1 and self.innerHTMLMode and self.fragmentContextNode is not None
                and token["type"] in (TT["EndTag"], TT["Comment"])
                and self.fragmentContextNode.namespace != HTML_NS
                and self.fragmentContextNode.name in FOREIGN_RCDATA_NAMES
                and len(self.tree.openElements) == 1):
            self.parseError("step1-fragment-context-non-start-tag", {})

    def isHTMLIntegrationPoint(self, element):
        if self.old1:
            return html5parser.HTMLParser.isHTMLIntegrationPoint(self, element)
        return self._hip(element)

    def _parse(self, stream, innerHTML=False, container="div", scripting=False, **kw):
        self.innerHTMLMode = innerHTML
        self.container = container
        self.scripting = scripting
        self.tokenizer = self.tokenizerClass(stream, parser=self, **kw)
        self.reset()
        try:
            self.mainLoop()
        except html5parser._ReparseException:
            self.reset()
            self.mainLoop()

    def reset(self):
        self.fragmentContextNode = None
        foreign = None
        if self.innerHTMLMode:
            m = re.match(r"(svg|math) (.+)\Z", self.container, re.S)
            if m:
                foreign = (namespaces["svg" if m.group(1) == "svg" else "mathml"],
                           m.group(2))
                self.fragmentContextNode = Node(foreign[1], foreign[0])
            else:
                self.fragmentContextNode = Node(self.container.lower(), HTML_NS)
        html5parser.HTMLParser.reset(self)
        if foreign and foreign[1] in FOREIGN_RCDATA_NAMES and not self.old1:
            # spec: foreign RCDATA state, foreign RCDATA flag not set
            self.tokenizer.state = self.tokenizer.foreignRcdataState

    def adjustedCurrentNode(self):
        oe = self.tree.openElements
        if self.innerHTMLMode and len(oe) == 1 and self.fragmentContextNode:
            return self.fragmentContextNode
        return oe[-1] if oe else None

    def _hip(self, element):
        if (element.name == "annotation-xml" and
                element.namespace == namespaces["mathml"]):
            return ("encoding" in element.attributes and
                    element.attributes["encoding"].translate(LOWER) in
                    ("text/html", "application/xhtml+xml"))
        return (element.namespace, element.name) in NEW_HIP

    def mainLoop(self):
        Chars, Space, Start, End, Comment, Doctype, PErr = (
            TT["Characters"], TT["SpaceCharacters"], TT["StartTag"],
            TT["EndTag"], TT["Comment"], TT["Doctype"], TT["ParseError"])
        for token in self.tokenizer:
            prev = None
            new = token
            first = True
            while new is not None:
                prev = new
                cur = self.adjustedCurrentNode()
                curNS = cur.namespace if cur else None
                curName = cur.name if cur else None
                typ = new["type"]
                if typ == PErr:
                    self.parseError(new["data"], new.get("datavars", {}))
                    new = None
                    continue
                if first:
                    self.preDispatch(new, cur)
                    first = False
                if (cur is None or curNS == self.tree.defaultNamespace or
                    (self.isMathMLTextIntegrationPoint(cur) and
                     ((typ == Start and new["name"] not in ("mglyph", "malignmark"))
                      or typ in (Chars, Space))) or
                    (curNS == namespaces["mathml"] and curName == "annotation-xml"
                     and typ == Start and new["name"] == "svg") or
                    (self.isHTMLIntegrationPoint(cur) and typ in (Start, Chars, Space))):
                    phase = self.phase
                else:
                    phase = self.phases["inForeignContent"]
                if typ == Chars:
                    new = phase.processCharacters(new)
                elif typ == Space:
                    new = phase.processSpaceCharacters(new)
                elif typ == Start:
                    new = phase.processStartTag(new)
                elif typ == End:
                    new = phase.processEndTag(new)
                elif typ == Comment:
                    new = phase.processComment(new)
                elif typ == Doctype:
                    new = phase.processDoctype(new)
            if (token["type"] == Start and prev["selfClosing"] and
                    not prev["selfClosingAcknowledged"]):
                self.parseError("non-void-element-with-trailing-solidus",
                                {"name": prev["name"]})
        reprocess = True
        phases = []
        while reprocess:
            phases.append(self.phase)
            reprocess = self.phase.processEOF()
            if reprocess:
                assert self.phase not in phases


class Old1Tokenizer(NewTokenizer):
    """Today's spec tokenizer (never enters foreign RCDATA) plus the step 1
    end-tag-in-cdata-section parse error."""

    def cdataSectionState(self):
        c = self.stream.char()
        if c == "<":
            node = self.parser.adjustedCurrentNode() if self.parser else None
            if (node is not None and node.namespace != HTML_NS
                    and node.name in FOREIGN_RCDATA_NAMES):
                n = len(node.name)
                s = self.peek(n + 2)
                if EOF not in s:
                    s = "".join(s)
                    if (s[0] == "/" and s[1:1 + n].translate(LOWER) == node.name
                            and s[1 + n] in "\t\n\f />"):
                        self.err("step1-end-tag-in-cdata-section")
            self.emitChar(c)
            return True
        self.stream.unget(c)
        return NewTokenizer.cdataSectionState(self)


class Old1Parser(NewParser):
    old1 = True


NewParser.tokenizerClass = NewTokenizer
Old1Parser.tokenizerClass = Old1Tokenizer
_CACHE = {}


def make_parser(mode):
    """Parsers are cached per mode (building one is slow); parse() resets them."""
    if mode not in _CACHE:
        _CACHE[mode] = _make_parser(mode)
    return _CACHE[mode]


def _make_parser(mode):
    if mode == "old1":
        return Old1Parser(tree=TreeBuilder, namespaceHTMLElements=True)
    if mode == "old":
        return html5parser.HTMLParser(tree=TreeBuilder, namespaceHTMLElements=True)
    if mode == "new":
        return NewParser(tree=TreeBuilder, namespaceHTMLElements=True)
    raise ValueError(mode)


def parse(mode, data, fragment=None, scripting=True):
    """Return (dump string, list of error codes)."""
    p = make_parser(mode)
    if fragment is None:
        root = p.parse(data, scripting=scripting)
    else:
        root = p.parseFragment(data, container=fragment, scripting=scripting)
    return dump(root), [e[1] for e in p.errors]
