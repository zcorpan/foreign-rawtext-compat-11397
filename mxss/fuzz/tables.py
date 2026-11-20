"""Print RESULTS tables (class level, no payloads): per label cases, tested, and findings by mechanism bucket.
usage: tables.py   (reads mxss/private/runs/*)"""
import collections, glob, json, os
HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = os.path.join(HERE, "..", "private", "runs")
src = open(os.path.join(HERE, "bucket.py")).read().split("for label in sys.argv")[0]
ns = {"__file__": os.path.join(HERE, "bucket.py")}
exec(src, ns)
bucket = ns["bucket"]
ORDER = ["ff-m0-scratch", "ff-m2-scratch", "ff-m3-scratch", "ff-m4-scratch", "chrome-scratch", "ff-m0-seeded", "ff-m2-seeded", "ff-m3-seeded", "ff-m4-seeded", "chrome-seeded",
         "ff-m0-selfclose", "ff-m3-selfclose", "ff-m4-selfclose", "ff-m0-noscriptmix", "ff-m2-noscriptmix", "ff-m3-noscriptmix", "ff-m4-noscriptmix", "ff-m0-legacyser", "ff-m5-scratch", "ff-m5-seeded", "ff-m5-selfclose", "ff-m5-noscriptmix"]
allb = set(); rows = {}
for label in ORDER:
    sigb = {}
    t = collections.Counter(); crashes = 0
    files = glob.glob(os.path.join(RUNS, label, "w*.jsonl"))
    for f in files:
        for l in open(f):
            r = json.loads(l)
            if r["type"] == "finding": sigb[r["sig"]] = bucket(r)
            elif r["type"] == "crash": crashes += 1
    cases = collections.Counter(); sigs = collections.defaultdict(set)
    for f in files:
        for l in open(f):
            r = json.loads(l)
            if r["type"] == "batch":
                st = r["stats"]
                for k in ("cases", "discard", "noCanary"): t[k] += st[k]
                for s, v in st["sigs"].items():
                    b = sigb.get(s, "unminimized/" + s.split(":")[0]); cases[b] += v; sigs[b].add(s)
    rows[label] = (t, cases, sigs, crashes); allb |= set(cases)
cols = sorted(allb)
print("| configuration | cases | tested | crashes | " + " | ".join(cols) + " |")
print("|---|---|---|---|" + "---|" * len(cols))
for label, (t, cases, sigs, cr) in rows.items():
    print(f"| {label} | {t['cases']:,} | {t['cases']-t['discard']-t['noCanary']:,} | {cr} | " + " | ".join((f"{cases[c]:,} ({len(sigs[c])})" if cases[c] else "0") for c in cols) + " |")
