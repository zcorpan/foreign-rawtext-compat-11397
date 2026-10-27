"""Aggregate ha/classify.py output: pages per mode whose candidate blocks parse differently,
by element and cause. Pages whose differing elements all come from blocks that look like markup
inside a script string (escaped quotes or slashes) are counted separately as "js-string".

usage: summarize.py CLASSIFIED_DIR BLOCKS_DIR > summary.txt; also writes CLASSIFIED_DIR/../pages-<mode>.jsonl
"""
import collections, glob, json, os, re, sys

cdir, bdir = sys.argv[1:3]
JS = re.compile(r'\\"|<\\/|\\u003c', re.I)
blocks_js = {}
for f in sorted(glob.glob(os.path.join(bdir, "*.json"))):
    for r in json.load(open(f)):
        bl = r.get("risky_blocks") or []
        blocks_js[r["page"]] = bool(bl) and all(JS.search(b) for b in bl)
modes = ("raw", "rcdata", "rcdata-dc")
pages = {m: collections.Counter() for m in modes}
causes = {m: collections.Counter() for m in modes}
errors = 0
out = {m: open(os.path.join(os.path.dirname(cdir.rstrip("/")), f"pages-{m}.jsonl"), "w") for m in modes}
for f in sorted(glob.glob(os.path.join(cdir, "*.jsonl"))):
    for line in open(f):
        r = json.loads(line)
        if "error" in r:
            errors += 1
            continue
        for m in modes:
            d = r["blocks"][m]
            if not d:
                continue
            bucket = "js-string" if blocks_js.get(r["page"]) else "markup"
            pages[m][bucket] += 1
            kinds = set()
            for e in d:
                for w in e["why"] or ["other"]:
                    kinds.add((bucket, f'{e["ns"]}:{e["name"]}', w))
            for k in kinds:
                causes[m][k] += 1
            out[m].write(json.dumps({"page": r["page"], "rank": r["rank"], "bucket": bucket, "elements": d[:20]}) + "\n")
print("errors", errors)
for m in modes:
    print(f"\n== {m}: pages", dict(pages[m]))
    for k, v in sorted(causes[m].items(), key=lambda kv: -kv[1]):
        print(" ", v, *k)
