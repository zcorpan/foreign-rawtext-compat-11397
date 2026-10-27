"""Analyze ff_compare.py output: element-level changes (A vs B), new JS errors in B, and pixel
diffs (A vs A2 is noise; A vs B is the change). Writes OUT_DIR/analysis.jsonl and side-by-side
review crops (A left, B right) in OUT_DIR/review/ for pages whose A-vs-B diff isn't noise.

usage: ff_analyze.py OUT_DIR
"""
import json, os, sys
from PIL import Image, ImageChops

out_dir = sys.argv[1]
os.makedirs(os.path.join(out_dir, "review"), exist_ok=True)
Image.MAX_IMAGE_PIXELS = None


def load(rid, label):
    p = os.path.join(out_dir, "shots", f"{rid}-{label}.png")
    return Image.open(p).convert("RGB") if os.path.exists(p) else None


def diff_bbox(a, b):
    w, h = min(a.width, b.width), min(a.height, b.height)
    d = ImageChops.difference(a.crop((0, 0, w, h)), b.crop((0, 0, w, h))).convert("L").point(lambda v: 255 if v > 24 else 0)
    box = d.getbbox()
    frac = sum(d.histogram()[255:]) / (w * h) if w * h else 0
    return box, frac, (a.size != b.size)


def key(e):
    return (e["ns"], e["name"])


res = []
for line in open(os.path.join(out_dir, "results.jsonl")):
    r = json.loads(line)
    A, A2, B = r.get("A", {}), r.get("A2", {}), r.get("B", {})
    out = {"id": r["id"], "url": r["url"]}
    if any("error" in x for x in (A, A2, B)):
        out["status"] = "error"
        res.append(out)
        continue
    ea, eb = A.get("els", []), B.get("els", [])
    changed = []
    for i, (x, y) in enumerate(zip(ea, eb)):
        if key(x) != key(y):
            changed.append({"i": i, "A": key(x), "B": key(y)})
            break
        if x["text"] != y["text"] or x["kinds"] != y["kinds"] or x["rules"] != y["rules"]:
            changed.append({"i": i, "name": x["name"], "A_text": x["text"][:160], "B_text": y["text"][:160],
                            "A_kinds": x["kinds"][:4], "B_kinds": y["kinds"][:4], "A_rules": x["rules"], "B_rules": y["rules"]})
    out["n_els"] = [A.get("nEls"), B.get("nEls")]
    out["el_changes"] = changed[:10]
    out["n_el_changes"] = len(changed)
    out["elementCount"] = [A.get("elementCount"), A2.get("elementCount"), B.get("elementCount")]
    out["scroll"] = [[A.get("scrollWidth"), A.get("scrollHeight")], [B.get("scrollWidth"), B.get("scrollHeight")]]
    base = set(A.get("errors", [])) | set(A2.get("errors", []))
    out["new_errors"] = [e for e in B.get("errors", []) if e not in base][:10]
    ia, ia2, ib = load(r["id"], "A"), load(r["id"], "A2"), load(r["id"], "B")
    if ia and ia2 and ib:
        nbox, nfrac, nsize = diff_bbox(ia, ia2)
        cbox, cfrac, csize = diff_bbox(ia, ib)
        out["noise"] = {"box": nbox, "frac": round(nfrac, 5), "size_changed": nsize}
        out["change"] = {"box": cbox, "frac": round(cfrac, 5), "size_changed": csize}
        if cbox and (cbox != nbox or cfrac > nfrac * 1.5):
            x0, y0, x1, y1 = cbox
            pad = 120
            box = (max(0, x0 - pad), max(0, y0 - pad), min(ia.width, x1 + pad), min(ia.height, y1 + pad, y0 + 1600))
            ca, cb = ia.crop(box), ib.crop(box)
            img = Image.new("RGB", (ca.width * 2 + 12, ca.height), "red")
            img.paste(ca, (0, 0))
            img.paste(cb, (ca.width + 12, 0))
            if img.width > 2400:
                img = img.resize((2400, int(img.height * 2400 / img.width)))
            path = os.path.join(out_dir, "review", f'{r["id"]}.png')
            img.save(path)
            out["review"] = path
    res.append(out)

with open(os.path.join(out_dir, "analysis.jsonl"), "w") as f:
    for o in res:
        f.write(json.dumps(o) + "\n")
for o in res:
    print(o["id"], o.get("status", ""), "elchg", o.get("n_el_changes"), "newerr", len(o.get("new_errors", [])),
          "noise", (o.get("noise") or {}).get("frac"), "chg", (o.get("change") or {}).get("frac"), o.get("review", ""))
