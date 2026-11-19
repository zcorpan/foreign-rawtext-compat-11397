"""Summarize runs: python summarize.py LABEL... -> cases, discard rate, signatures (class level, no payloads)."""
import glob, json, os, sys, collections
RUNS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "private", "runs")
for label in sys.argv[1:]:
    cases = disc = nocan = fc = errs = 0
    sigs = collections.Counter(); first = {}; struct = collections.Counter(); pairs = collections.Counter(); depth = collections.Counter(); ms = 0
    nfind = 0
    for f in glob.glob(os.path.join(RUNS, label, "w*.jsonl")):
        for l in open(f):
            r = json.loads(l)
            if r["type"] == "batch":
                st = r["stats"]; cases += st["cases"]; disc += st["discard"]; nocan += st["noCanary"]; fc += st["findingCases"]; ms += r["ms"]
                for k, v in st["sigs"].items(): sigs[k] += v
                for k, v in st["struct"].items(): struct[k] += v
                for k, v in st.get("pairs", {}).items(): pairs[k] += v
                for k, v in st["depth"].items(): depth[k] += v
            elif r["type"] == "finding": nfind += 1
            elif r["type"] == "error": errs += 1
    print(f"== {label}: cases={cases} discarded={disc} noCanary={nocan} findingCases={fc} uniqueSigs={len(sigs)} structClasses={len(struct)} structCases={sum(struct.values())} errors={errs} cpu_s={ms/1000:.0f}")
    print("   depth", dict(depth))
    if "-v" in sys.argv: pass
