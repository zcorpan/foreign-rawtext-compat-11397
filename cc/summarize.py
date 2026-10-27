"""Summarize analyze_warc.py output per mode: pages and elements by element name and cause."""
import collections, glob, json, sys

files = sys.argv[1:] or sorted(glob.glob("out-cc/*.jsonl"))
tot = collections.Counter()
for mode in ("raw", "rcdata"):
    pages = collections.Counter()
    els = collections.Counter()
    page_why = collections.Counter()
    for f in files:
        for line in open(f):
            r = json.loads(line)
            if "totals" in r:
                if mode == "raw":
                    for k, v in r["totals"].items():
                        if k != "warc":
                            tot[k] += v
                continue
            if r["status"] != "ok":
                continue
            pages["with-foreign-element"] += 1
            names, dnames, pw = set(), set(), set()
            for e in r[mode]["elements"]:
                key = f'{e["ns"]}:{e["name"]}'
                names.add(key)
                els[(key, e["verdict"])] += 1
                if e["verdict"] == "differs":
                    dnames.add(key)
                    for w in e["why"]:
                        pw.add((key, w))
                elif e["verdict"] == "unaligned":
                    pw.add((key, e["why"][0]))
            for n in names:
                pages["has " + n] += 1
            for n in dnames:
                pages["differs " + n] += 1
            if dnames:
                pages["differs any"] += 1
            for k in pw:
                page_why[k] += 1
    if mode == "raw":
        print("totals", dict(tot))
    print(f"\n== mode {mode}")
    for k, v in sorted(pages.items()):
        print(f"pages {k}: {v}")
    for k, v in sorted(els.items()):
        print("elements", k, v)
    for k, v in sorted(page_why.items(), key=lambda kv: -kv[1]):
        print("pages-with-cause", k, v)
