"""Foreign (SVG/MathML) textarea, xmp, iframe, noembed, noframes, noscript and plaintext elements in
the downloaded HTTP Archive bodies (today's parse): what they contain and what follows them
inside the same <svg>/<math>, i.e. what a breakout would push out of the foreign subtree.

usage: breakout_check.py BODIES_DIR"""
import collections, glob, json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "cc"))
import frparse

NAMES = {"textarea", "xmp", "iframe", "noembed", "noframes", "noscript", "plaintext"}
SVG, MATH = "{http://www.w3.org/2000/svg}", "{http://www.w3.org/1998/Math/MathML}"
c = collections.Counter(); ex = collections.defaultdict(list)
for f in sorted(glob.glob(os.path.join(sys.argv[1], "*.json"))):
    for r in json.load(open(f)):
        _, info = frparse.parse(r["body"], "old")
        for e in info["elements"]:
            if e["name"] not in NAMES or e.get("etree") is None:
                continue
            el = e["etree"]
            kids = [k.tag.split("}")[-1] if isinstance(k.tag, str) else "#comment" for k in el][:5]
            k = (e["ns"], e["name"])
            c[k] += 1
            if len(ex[k]) < 5:
                ex[k].append((r["page"], kids, (el.text or "")[:60]))
print(json.dumps({f"{a}:{b}": v for (a, b), v in sorted(c.items())}))
for k, v in sorted(ex.items()):
    print(k)
    for x in v:
        print("   ", x[0][:55], "children:", x[1], "text:", json.dumps(x[2]))

# What comes after each such element inside its <svg> (siblings and the rest of the ancestors' children):
# a breakout would close the <svg> there and push that content out of the SVG subtree.
def following_in_svg(root, target):
    parent = {c: p for p in root.iter() for c in p}
    out = []
    node = target
    while node in parent:
        p = parent[node]
        kids = list(p)
        out += [k for k in kids[kids.index(node) + 1:] if isinstance(k.tag, str)]
        if isinstance(p.tag, str) and p.tag == SVG + "svg" and p not in parent.get(p, []) and not (parent.get(p) is not None and parent[p].tag.startswith(SVG)):
            break
        node = p
    return out

after = collections.Counter(); ex2 = []
for f in sorted(glob.glob(os.path.join(sys.argv[1], "*.json"))):
    for r in json.load(open(f)):
        doc, info = frparse.parse(r["body"], "old")
        for e in info["elements"]:
            if e["name"] not in NAMES or e.get("etree") is None:
                continue
            fol = following_in_svg(doc, e["etree"])
            svg_fol = [k for k in fol if k.tag.startswith(SVG)]
            key = "svg content after it" if svg_fol else "nothing SVG after it"
            after[(e["name"], key)] += 1
            if len(ex2) < 12:
                ex2.append((r["page"][:50], e["name"], [k.tag.split("}")[-1] for k in svg_fol][:6]))
print(dict(after))
for x in ex2:
    print("  ", x)

# Is each foreign iframe inside a foreign noscript (the GTM snippet)?
inside = collections.Counter(); standalone = []
for f in sorted(glob.glob(os.path.join(sys.argv[1], "*.json"))):
    for r in json.load(open(f)):
        doc, info = frparse.parse(r["body"], "old")
        parent = {c: p for p in doc.iter() for c in p}
        for e in info["elements"]:
            if e["name"] != "iframe" or e.get("etree") is None:
                continue
            p = parent.get(e["etree"])
            k = "inside svg:noscript" if p is not None and p.tag == SVG + "noscript" else "standalone"
            inside[k] += 1
            if k == "standalone":
                standalone.append((r["page"][:50], e["etree"].get("src", "")[:60]))
print("svg:iframe:", dict(inside))
for x in standalone:
    print("  ", x)
