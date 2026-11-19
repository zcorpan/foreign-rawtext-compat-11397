"""Class-level report over run labels (no payloads): python report.py LABEL...

Per label: cases, tested (non-discarded, canary survived), finding cases, signatures grouped by
pair class (same / toHtml / toForeign / wrap) and by carrier kind + carrier element + namespace
pivot, plus structural non-round-trip groups.
"""
import collections, glob, json, os, sys
RUNS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "private", "runs")
for label in ([] if "--classes" in sys.argv else sys.argv[1:]):
    tot = collections.Counter(); sigs = collections.Counter(); struct = collections.Counter(); n_find = 0; pairs = collections.Counter()
    for f in glob.glob(os.path.join(RUNS, label, "w*.jsonl")):
        for l in open(f):
            r = json.loads(l)
            if r["type"] == "batch":
                st = r["stats"]
                for k in ("cases", "discard", "noCanary", "findingCases"): tot[k] += st[k]
                for k, v in st["sigs"].items(): sigs[k] += v
                for k, v in st["struct"].items(): struct[k] += v
                for k, v in st.get("pairs", {}).items(): pairs[k] += v
            elif r["type"] == "finding": n_find += 1
    print(f"## {label}: cases={tot['cases']:,} tested={tot['cases']-tot['discard']-tot['noCanary']:,} findingCases={tot['findingCases']:,} sigs={len(sigs)} minimized={n_find}")
    by = collections.defaultdict(collections.Counter)
    for k, v in sigs.items(): by[k.split(":")[0]][k] += v
    for pc in ("same", "toHtml", "toForeign", "wrap"):
        print(f"  [{pc}] sigs={len(by[pc])} cases={sum(by[pc].values()):,}")
        for k, v in by[pc].most_common(int(os.environ.get("TOP", "12"))): print(f"     {v:>8,}  {k}")
    def fam(c):
        if c == 'dom': return 'dom'
        if c.startswith('w:'): return 'wrap-sink'
        if c.startswith(('s:', 'm:')): return 'foreign-ctx'
        return 'html-ctx'
    fp = collections.Counter()
    for k, v in pairs.items():
        a, b = k.split('>', 1); fp[fam(a) + ' -> ' + fam(b)] += v
    print('  finding cases by context family (first finding path):', dict(fp.most_common()))
    print(f"  struct non-roundtrip: classes={len(struct)} cases={sum(struct.values()):,}")
    for k, v in struct.most_common(8): print(f"     {v:>8,}  {k}")


# ---- class mapping (heuristic, by signature) used by RESULTS tables
RAWN = ("style", "script", "xmp", "iframe", "noembed", "noframes", "plaintext", "noscript", "textarea", "title")
def mclass(sig):
    pc, rest = sig.split(":", 1)
    kind = rest.split("@")[0]
    el = rest.split("@", 1)[1].split("|")[0]
    ns, _, name = el.partition(":")
    if pc == "dom": return "M9 DOM-built"
    if pc == "wrap": return "M6 sink wrapper"
    if pc == "rawctx": return "row19/22 raw or foreign-raw fragment context"
    if name == "noscript": return "M5 noscript"
    if kind == "attr": return "M2/M3 attribute carrier"
    if kind in ("comment", "pi", "cdata") and ns in ("s", "m") and name in RAWN: return "M4 foreign comment/PI/CDATA holds end tag"
    if kind in ("comment", "pi", "cdata"): return "M3/M7 comment/PI carrier via structure"
    if kind == "text" and ns == "h" and name in RAWN: return "M1 raw text becomes markup (namespace/context pivot)"
    if kind == "text" and ns in ("s", "m"): return "M1b foreign raw text"
    return "other: " + kind + "@" + el


def by_mclass(label):
    out = collections.Counter(); samples = {}
    for f in glob.glob(os.path.join(RUNS, label, "w*.jsonl")):
        for l in open(f):
            r = json.loads(l)
            if r["type"] == "batch":
                for k, v in r["stats"]["sigs"].items():
                    pc = k.split(":")[0]
                    out[(pc, mclass(k))] += v
    return out


if "--classes" in sys.argv:
    for label in [a for a in sys.argv[1:] if not a.startswith("--")]:
        print("##", label)
        for (pc, mc), v in sorted(by_mclass(label).items(), key=lambda x: (x[0][0], -x[1])): print(f"  {pc:10} {v:>10,}  {mc}")
