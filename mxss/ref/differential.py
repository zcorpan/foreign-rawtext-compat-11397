#!/usr/bin/env python3
"""Differential check for whatwg/html step 1 (parse errors added to today's parsing).

For every input and context, parse with "old1" (today's spec plus `step1-*`
parse errors) and "new" (foreign RCDATA).  A = trees differ.  B = old1 reported
at least one `step1-*` error.  The invariant is A implies B.

usage: differential.py [--n N] [--seed S] [--dat DIR] [--examples K]
"""
import argparse
import collections
import glob
import os
import random
import re
import signal
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import frnew  # noqa: E402
import run_dat  # noqa: E402

CONTEXTS = [None, "div", "svg", "math", "svg title", "svg style", "svg script",
            "svg noscript", "math title", "svg desc", "svg foreignObject"]
NAMES = ["title", "style", "script", "noscript", "textarea", "xmp", "iframe",
         "noembed", "noframes", "plaintext"]
RCD = NAMES[:4]


# tokenizer errors that mean the input ended inside a construct (old1 parse)
EOF_RE = re.compile(r"^(eof-|unexpected-EOF|expected-tag-name-but-got-eof)")


class Timeout(Exception):
    pass


def _alarm(*_):
    raise Timeout()


signal.signal(signal.SIGALRM, _alarm)


def run(mode, data, ctx):
    signal.setitimer(signal.ITIMER_REAL, 2)
    try:
        return frnew.parse(mode, data, ctx)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


def evaluate(data, ctx):
    """Return ('crash', which) or (A, B, step1 codes)."""
    try:
        t1, e1 = run("old1", data, ctx)
    except Exception as e:  # noqa: BLE001
        return ("crash", "old1 " + type(e).__name__)
    try:
        t2, _ = run("new", data, ctx)
    except Exception as e:  # noqa: BLE001
        return ("crash", "new " + type(e).__name__)
    s1 = [c for c in e1 if c.startswith("step1-")]
    trunc = any(EOF_RE.match(c) for c in e1)
    return (t1 != t2, bool(s1), s1, trunc, [c for c in e1 if not c.startswith("step1-")])


# ---------------------------------------------------------------- corpus

def dat_inputs(d):
    out = []
    for f in sorted(glob.glob(os.path.join(d, "*.dat"))):
        with open(f, encoding="utf-8", newline="") as fh:
            for t in run_dat.parse_dat(fh.read()):
                out.append((t["data"], t["fragment"]))
    return out


def gen(n, seed):
    r = random.Random(seed)
    openers = ["", "<svg>", "<math>", "<svg><foreignObject>", "<svg><desc>", "<svg><title>",
               "<math><mtext>", "<math><annotation-xml encoding=text/html>", "<svg><g>",
               "<math><mi>", "<p><svg>", "<table><svg>", "<select><svg>"]
    others = ["b", "p", "div", "rect", "svg", "math", "mi", "table", "tr", "td", "font color=x",
              "br", "img", "a", "li", "template"]
    texts = ["x", " ", "a b", "&amp;", "&lt;", "&", "&#", "&#x41;", "<", "<<", "\u0000", "]", "]]", "--", "-"]
    comm_open = ["<!--", "<!---", "<!--->", "<!", "<!-", "<![CDATA[", "<![CDATA", "<?", "<?x", "<?x ", "</", "</ ", "<!DOCTYPE html>", "<!doctype x"]
    comm_close = ["-->", "--!>", ">", "?>", "]]>", "]]", "--", "]", "?", ""]
    delims = [">", " >", "/>", "\n>", "\t>", " x=1>", "x>", "", " ", "/", "\f>", "\r>"]

    def name():
        return r.choice(NAMES if r.random() < 0.7 else others)

    def case(nm):
        c = r.random()
        return nm.upper() if c < 0.15 else (nm.capitalize() if c < 0.25 else nm)

    def atom(cur):
        k = r.random()
        nm = cur if (cur and r.random() < 0.6) else name()
        if k < 0.20:
            return "<" + case(nm) + r.choice([">", ">", "/>", " a=b>", " >"])
        if k < 0.38:
            return "</" + case(nm) + r.choice(delims)
        if k < 0.52:
            return r.choice(comm_open)
        if k < 0.64:
            return r.choice(comm_close)
        if k < 0.80:
            return r.choice(texts)
        if k < 0.88:
            return "<" + r.choice(others) + ">"
        if k < 0.94:
            return "</" + r.choice(others) + ">"
        # end tag name inside a comment / PI / CDATA / bogus comment
        o = r.choice(["<!--", "<?x ", "<![CDATA[", "<!", "</ ", "<?"])
        c = {"<!--": "-->", "<?x ": "?>", "<![CDATA[": "]]>", "<!": ">", "</ ": ">", "<?": ">"}[o]
        return o + r.choice(["", " "]) + "</" + case(nm) + r.choice(delims) + r.choice(["", "x"]) + r.choice([c, ""])

    seen = set()
    while len(seen) < n:
        o = r.choice(openers)
        if r.random() < 0.7:
            cur = name() if r.random() < 0.8 else None
            head = o + (("<" + case(cur) + r.choice([">", ">", "/>", " a>"])) if cur else "")
        else:
            cur, head = None, o
        s = head + "".join(atom(cur) for _ in range(r.randint(1, 7)))
        if r.random() < 0.3:
            s += "</" + case(cur or name()) + ">"
        seen.add(s)
    return sorted(seen)


# ---------------------------------------------------------- minimization

def ddmin(data, ctx, pred):
    s = data
    n = 2
    while len(s) >= 2:
        chunk = max(1, len(s) // n)
        reduced = False
        for i in range(0, len(s), chunk):
            cand = s[:i] + s[i + chunk:]
            if cand and pred(cand, ctx):
                s, n, reduced = cand, max(n - 1, 2), True
                break
        if not reduced:
            if chunk == 1:
                break
            n = min(len(s), n * 2)
    return s


def ctxkind(ctx):
    if ctx in ("svg title", "svg style", "svg script", "svg noscript", "math title"):
        return "fragment, foreign title/style/script/noscript context"
    return "document or other context"


def coarse(s):
    if "<![CDATA[" in s:
        return "CDATA section"
    if "<?" in s:
        return "processing instruction (or bogus comment from <?)"
    if "<!--" in s:
        return "comment"
    if "<!" in s or "</" in s and re.search(r"</[^A-Za-z>]", s):
        return "bogus comment"
    if "&" in s:
        return "character reference"
    if re.search(r"<[A-Za-z]", s) and not re.search(r"</", s):
        return "start tag only"
    if "</" in s:
        return "end tag / text"
    return "other"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20000, help="generated inputs")
    ap.add_argument("--seed", type=int, default=11397)
    ap.add_argument("--dat", default=os.path.expanduser(
        "~/git/web-platform-tests/wpt-foreign-rcdata/html/syntax/parsing/resources"))
    ap.add_argument("--examples", type=int, default=10)
    ap.add_argument("--max-min", type=int, default=500, help="max cases to minimize per kind")
    a = ap.parse_args()
    t0 = time.process_time()

    inputs = dat_inputs(a.dat)
    ndat = len({d for d, _ in inputs})
    corpus = {}
    for d, f in inputs:
        corpus.setdefault(d, set()).add(f)
    for d in gen(a.n, a.seed):
        corpus.setdefault(d, set())

    cnt = collections.Counter()
    crashes = collections.Counter()
    bad = []      # A and not B
    over = []     # B and not A
    s1codes = collections.Counter()
    for d in sorted(corpus):
        for ctx in dict.fromkeys(CONTEXTS + sorted(c for c in corpus[d] if c)):
            cnt["cases"] += 1
            r = evaluate(d, ctx)
            if r[0] == "crash":
                cnt["crash"] += 1
                crashes[r[1]] += 1
                continue
            A, B, codes, trunc, _ = r
            cnt["A"] += A
            cnt["B"] += B
            cnt["A&B"] += A and B
            if A and not B:
                bad.append((d, ctx))
                cnt["A-not-B truncated"] += trunc
            if B and not A:
                over.append((d, ctx))
                for c in set(codes):
                    s1codes[c] += 1
    print("inputs: %d (%d from .dat, %d generated), contexts: %d, cases: %d"
          % (len(corpus), ndat, a.n, len(CONTEXTS), cnt["cases"]))
    print("crashes (skipped): %d %s" % (cnt["crash"], dict(crashes)))
    print("A (tree differs): %d   B (step1 error): %d   A&B: %d   A-not-B: %d   B-not-A: %d"
          % (cnt["A"], cnt["B"], cnt["A&B"], len(bad), len(over)))
    print("invariant A => B %s" % ("HOLDS" if not bad else "VIOLATED"))
    print("elapsed CPU so far: %.0fs" % (time.process_time() - t0))

    def pred_bad(s, ctx, trunc=None):
        r = evaluate(s, ctx)
        return (r[0] != "crash" and r[0] and not r[1]
                and (trunc is None or r[3] == trunc))

    def pred_bad_trunc(s, ctx):
        return pred_bad(s, ctx, True)

    def pred_bad_full(s, ctx):
        return pred_bad(s, ctx, False)

    def pred_over(s, ctx):
        r = evaluate(s, ctx)
        return r[0] != "crash" and r[1] and not r[0]

    def report(title, cases, pred, key, show_codes=False):
        print("\n## " + title)
        bysig = {}
        pool = sorted(cases, key=lambda x: (x[0], x[1] or ""))
        rnd = random.Random(a.seed)
        if len(pool) > a.max_min:
            pool = rnd.sample(pool, a.max_min)
        for d, ctx in pool:
            m = ddmin(d, ctx, pred)
            bysig.setdefault((m, ctx), None)
        groups = collections.defaultdict(list)
        for m, ctx in bysig:
            groups[key(m, ctx)].append((m, ctx))
        for g, items in sorted(groups.items(), key=lambda kv: -len(kv[1])):
            print("\n### %s  (%d distinct minimized)" % (g, len(items)))
            for m, ctx in sorted(items, key=lambda x: (len(x[0]), x[0], x[1] or ""))[:a.examples]:
                extra = ""
                if show_codes:
                    extra = "   old1 errors: " + ",".join(
                        c for c in evaluate(m, ctx)[4] if not c.startswith("expected-doctype"))
                print("  ctx=%-18s %r%s" % (ctx or "document", m, extra))

    by = collections.Counter(ctxkind(c) for _, c in bad)
    print("A-not-B by context kind:", dict(by))
    by = collections.Counter(ctxkind(c) for _, c in over)
    print("B-not-A by context kind:", dict(by))
    def other(r):
        return [c for c in r[4] if not c.startswith("expected-doctype")]

    def pred_e(s, ctx):
        r = evaluate(s, ctx)
        return r[0] != "crash" and r[0] and not r[1] and not other(r)

    def pred_ob(s, ctx):
        r = evaluate(s, ctx)
        return r[0] != "crash" and r[0] and not r[1] and bool(other(r))

    evals = [(x, evaluate(*x)) for x in bad]
    e_cases = [x for x, r in evals if not other(r)]
    ob_cases = [x for x, r in evals if other(r)]
    print("A-not-B with NO other parse error in old1 (besides missing doctype): %d" % len(e_cases))
    print("A-not-B but old1 already reports an ordinary parse error: %d" % len(ob_cases))
    print("  no-other-error gaps by context kind:",
          dict(collections.Counter(ctxkind(c) for _, c in e_cases)))
    print("  gaps by context:", dict(collections.Counter(c or "document" for _, c in e_cases)))
    if e_cases:
        report("A without any parse error in old1 (real gaps)", e_cases, pred_e,
               lambda m, c: ctxkind(c) + " / " + coarse(m), True)
    if ob_cases:
        def key2(m, c):
            r = evaluate(m, c)
            noise = ("expected-closing-tag-but-got-eof", "eof-in-table", "unexpected-start-tag-implies-table-voodoo")
            return ctxkind(c) + " / old1 ordinary errors: " + ",".join(
                sorted({x for x in other(r) if x not in noise}))
        report("A without step1 error, but old1 already reports an ordinary parse error",
               ob_cases, pred_ob, key2)
    if over:
        def okey(m, ctx):
            r = evaluate(m, ctx)
            return ctxkind(ctx) + " / " + (",".join(sorted(set(r[2]))) if r[0] != "crash" else "crash")
        report("B without A (step 1 error, same tree)", over, pred_over, okey)
    print("\nstep1 codes in B-without-A cases:", dict(s1codes))
    print("total CPU: %.0fs" % (time.process_time() - t0))


if __name__ == "__main__":
    main()
