"""Bucket minimized findings of a label by mechanism (heuristic regexes on the private repro; prints counts only).
usage: bucket.py LABEL..."""
import collections, glob, json, os, re, sys
RUNS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "private", "runs")
BRK = r"(textarea|xmp|iframe|noembed|noframes|plaintext)"
def bucket(r):
    sp = r["spec"]; pc = r["sig"].split(":")[0]
    if pc in ("wrap", "dom", "rawctx"): return pc
    t = "".join(sp.get("tokens") or [])
    if re.search(r"<template[^>]*\sfor\b", t, re.I): return "template-for patch" + (" (with PI/marker)" if "<?" in t else "")
    if re.search(r"<\?(?!>)", t) and pc != "dom" and os.environ.get("PIBUCKET"): return "PI construct"
    if re.search(r"<!--\s*<script", t, re.I): return "script-double-escape vs foreign script"
    if re.search(r"<" + BRK + r"\b[^>]*/>", t, re.I): return "self-closed breakout element, reparsed as breakout"
    if re.search(r"<\?", t): return "PI-like"
    if r["sig"].split("|")[0].split(":", 1)[1].startswith(("attr@",)): return "attribute carrier"
    return "unclassified"
for label in sys.argv[1:]:
    c = collections.Counter(); sigs = collections.defaultdict(set)
    for f in glob.glob(os.path.join(RUNS, label, "w*.jsonl")):
        for l in open(f):
            r = json.loads(l)
            if r["type"] == "finding":
                b = bucket(r); sigs[b].add(r["sig"])
    print("##", label)
    for b, s in sorted(sigs.items(), key=lambda x: -len(x[1])): print(f"  {len(s):>5} signatures  {b}")
