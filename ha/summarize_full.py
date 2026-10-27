"""Summarize full-page parses (ha/classify.py --full on the selected bodies).

Selected pages: every page whose blocks differ in rcdata or rcdata-dc ("rcdata"), plus a seeded
sample of 500 of the pages whose blocks differ in raw only ("raw-sample"; extrapolated to
RAW_ONLY pages). For rcdata-dc, an element whose child text content is unchanged (only comment
nodes are gone) is counted as "dom-only".

usage: summarize_full.py CLASSIFIED_FULL_DIR SELECTED.csv RAW_ONLY_TOTAL
"""
import collections, csv, glob, json, os, re, sys

cdir, selected, raw_only_total = sys.argv[1], sys.argv[2], int(sys.argv[3])
why = {r[0]: r[1] for r in csv.reader(open(selected))}
WIX = re.compile(r'#comp-[\w-]+ svg \[data-color=&quot;')


def label(e, mode):
    t = e.get("new_text", "")
    if mode != "rcdata-dc" or e.get("old_text") != t or "unterminated" in e["why"]:
        pass
    else:
        return f'{e["ns"]}:{e["name"]} dom-only'
    if mode == "raw" and WIX.search(t):
        return "svg:style charrefs (Wix data-color)"
    w = [x for x in e["why"] if x not in ("cdata-markers",)] or e["why"] or ["other"]
    return f'{e["ns"]}:{e["name"]} {",".join(w)}'


res = {m: collections.Counter() for m in ("raw", "rcdata", "rcdata-dc")}
pages = {m: collections.Counter() for m in res}
examples = {}
n = collections.Counter()
for f in sorted(glob.glob(os.path.join(cdir, "*.jsonl"))):
    for line in open(f):
        r = json.loads(line)
        grp = why.get(r["page"], "?")
        n[grp] += 1
        if "error" in r:
            n["error"] += 1
            continue
        for m in res:
            labels = {label(e, m) for e in r["full"][m]}
            real = {l for l in labels if not l.endswith("dom-only")}
            if labels:
                pages[m][(grp, "any")] += 1
            if real:
                pages[m][(grp, "text-changes")] += 1
            for l in labels:
                res[m][(grp, l)] += 1
                examples.setdefault((m, grp, l), r["page"])
print("pages parsed", dict(n))
for m in res:
    print(f"\n== {m}")
    for k, v in sorted(pages[m].items()):
        print("  pages", k, v)
    if m == "raw":
        s = pages[m][("raw-sample", "any")]
        print(f"  raw-only extrapolated: {s}/{n['raw-sample']} x {raw_only_total} = {round(s / max(n['raw-sample'], 1) * raw_only_total)}")
    for k, v in sorted(res[m].items(), key=lambda kv: -kv[1]):
        print("  ", v, *k, "e.g.", examples[(m, *k)][:70])
