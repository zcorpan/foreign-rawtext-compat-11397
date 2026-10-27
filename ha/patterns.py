"""Pages per pattern behind the rcdata and rcdata-dc differences (full-page parses).
For rcdata-dc, elements whose child text content is unchanged (only comment nodes gone) are left
out. "unterminated" is split by whether the crawled body looks complete (ends with </body> or
</html>) or truncated.

usage: patterns.py CLASSIFIED_FULL_DIR BODIES_DIR"""
import collections, glob, json, os, re, sys

cdir, bdir = sys.argv[1:3]
complete = {}
for f in glob.glob(os.path.join(bdir, "*.json")):
    for r in json.load(open(f)):
        complete[r["page"]] = bool(re.search(r"</(?:html|body)\s*>", r["body"][-4000:], re.I))


def pat(e):
    t = e.get("new_text", "")
    if "unterminated" in e["why"]:
        return "unterminated"
    m = re.search(r"<!--(.{0,24}?)-->", t, re.S)
    if m:
        d = m.group(1)
        if d == "":
            return "comment: <!----> (Lit/Angular marker)"
        if d.strip() == "":
            return "comment: <!-- --> (React text separator)"
        if re.fullmatch(r"t\.[\d.]+", d):
            return "comment: <!--t.N.N.N.N--> (framework marker)"
        if d.startswith("ng"):
            return "comment: <!--ng...--> (Angular)"
        if d.startswith("/*"):
            return "comment: <!--/*--> (Drupal-style CDATA wrapper)"
        return "comment: other"
    if "<!--" in t:
        return "comment: other (long or unclosed)"
    if "<?" in t:
        return "pi"
    m = re.search(r"</?([A-Za-z][\w-]*)", t)
    if m:
        return "element: <" + re.sub(r"^ly-as-\d+$", "ly-as-N", m.group(1).lower()) + ">"
    return "other"


for mode in ("rcdata", "rcdata-dc"):
    c = collections.Counter()
    ex = {}
    for f in sorted(glob.glob(os.path.join(cdir, "*.jsonl"))):
        for line in open(f):
            r = json.loads(line)
            if "error" in r:
                continue
            ps = set()
            for e in r["full"][mode]:
                if mode == "rcdata-dc" and e.get("old_text") == e.get("new_text") and "unterminated" not in e["why"]:
                    continue
                p = f'{e["name"]}: {pat(e)}'
                if p.endswith("unterminated"):
                    p += " (complete body)" if complete.get(r["page"]) else " (truncated body)"
                ps.add(p)
            for p in ps:
                c[p] += 1
                ex.setdefault(p, r["page"])
    print(f"== {mode}: pages per pattern")
    for p, v in c.most_common():
        print(f"  {v:5d} {p}   e.g. {ex[p][:60]}")
