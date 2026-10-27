"""Would SVG/MathML <script> parse differently with the HTML script data states (plus character
references) than with plain RCDATA? Only if its content has "<!--" followed by "<script" before
the end tag (the escape states then let a </script> through). Checks the fully parsed pages:
every foreign script that differs from today, its RCDATA text, and the raw body.

usage: script_states.py CLASSIFIED_FULL_DIR BODIES_DIR"""
import glob, json, os, re, sys

cdir, bdir = sys.argv[1:3]
complete = {}
bodies = {}
for f in glob.glob(os.path.join(bdir, "*.json")):
    for r in json.load(open(f)):
        complete[r["page"]] = bool(re.search(r"</(?:html|body)\s*>", r["body"][-4000:], re.I))
        bodies[r["page"]] = r["body"]
scripts = pages = escape = 0
ex = []
for f in sorted(glob.glob(os.path.join(cdir, "*.jsonl"))):
    for line in open(f):
        r = json.loads(line)
        if "error" in r:
            continue
        found = False
        for e in r["full"]["rcdata"]:
            if e["name"] != "script":
                continue
            scripts += 1
            found = True
            t = e.get("new_text", "") + e.get("new_text_tail", "")
            if re.search(r"<!--[\s\S]*<script", t, re.I):
                escape += 1
                ex.append((r["page"], complete.get(r["page"])))
        pages += found
print(f"foreign scripts that differ from today (rcdata mode): {scripts} on {pages} pages")
print(f"  ... whose content has <!-- followed by <script: {escape}")
for p, c in ex:
    b = bodies.get(p, "")
    m = re.search(r"<svg\b[^>]*>(?:(?!</svg)[\s\S]){0,200}?<script\b[^>]*>", b, re.I)
    print(f"  {p} (complete body: {c}); SVG script starts: {json.dumps(b[m.end():m.end() + 80]) if m else None}")

# Script data (raw mode, character references then decoded) vs RCDATA: same text?
import html
same = diff = 0
for f in sorted(glob.glob(os.path.join(cdir, "*.jsonl"))):
    for line in open(f):
        r = json.loads(line)
        if "error" in r:
            continue
        raw = [e for e in r["full"]["raw"] if e["name"] == "script"]
        rc = [e for e in r["full"]["rcdata"] if e["name"] == "script"]
        for a, b in zip(raw, rc):
            ta = (html.unescape(a.get("new_text", "")), html.unescape(a.get("new_text_tail", "")))
            tb = (b.get("new_text", ""), b.get("new_text_tail", ""))
            if ta == tb:
                same += 1
            else:
                diff += 1
                body = bodies.get(r["page"], "")
                i = body.lower().find("<script", body.lower().find("<svg"))
                seg = body[i:body.lower().find("</script", i)] if i >= 0 else ""
                print(f"  differs: {r['page']} (complete body: {complete.get(r['page'])}; "
                      f"<!-- in it: {'<!--' in seg}; named refs: {sorted(set(re.findall(r'&[a-zA-Z]+;', seg)))[:4]})")
print(f"script data + decoded refs vs RCDATA: {same} same, {diff} differ")
