"""Fetch the breakout-candidate pages live (queries/breakout-candidates.json) and, with today's
parse, find SVG/MathML textarea, xmp, iframe, noembed, noframes and plaintext elements: are they
inside an SVG noscript, and is there SVG/MathML content after them in the same foreign subtree
(which a breakout would push out of SVG)?

usage: breakout_live.py CANDIDATES.json OUT.jsonl"""
import concurrent.futures, json, os, subprocess, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "cc"))

NAMES = {"textarea", "xmp", "iframe", "noembed", "noframes", "plaintext"}
UA = "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Mobile Safari/537.36"
FOREIGN = ("{http://www.w3.org/2000/svg}", "{http://www.w3.org/1998/Math/MathML}")


def fetch(url):
    p = subprocess.run(["curl", "-sL", "--compressed", "--max-time", "25", "--max-filesize", "8000000",
                        "-A", UA, url], capture_output=True)
    return p.stdout.decode("utf-8", "replace") if p.returncode == 0 else None


def analyze(url):
    import frparse
    html = fetch(url)
    if html is None:
        return {"page": url, "status": "fetch-error"}
    doc, info = frparse.parse(html, "old")
    parent = {c: p for p in doc.iter() for c in p}
    found = []
    for e in info["elements"]:
        if e["name"] not in NAMES or e.get("etree") is None:
            continue
        el = e["etree"]
        p = parent.get(el)
        in_noscript = p is not None and isinstance(p.tag, str) and p.tag.endswith("}noscript")
        after = []
        node = el
        while node in parent and isinstance(parent[node].tag, str) and parent[node].tag.startswith(FOREIGN):
            sib = list(parent[node])
            after += [k.tag.split("}")[-1] for k in sib[sib.index(node) + 1:] if isinstance(k.tag, str) and k.tag.startswith(FOREIGN)]
            node = parent[node]
        found.append({"ns": e["ns"], "name": e["name"], "self_closing": e["self_closing"], "in_noscript": in_noscript,
                      "foreign_after": len(after), "after_sample": after[:5],
                      "children": [k.tag.split("}")[-1] if isinstance(k.tag, str) else "#comment" for k in el][:4],
                      "text": "".join(el.itertext())[:80], "attrs": {k: v[:80] for k, v in el.attrib.items() if isinstance(k, str)}})
    return {"page": url, "status": "ok", "elements": found}


if __name__ == "__main__":
    src, dst = sys.argv[1:3]
    rows = json.load(open(src))
    done = set()
    if os.path.exists(dst):
        done = {json.loads(l)["page"] for l in open(dst)}
    todo = [r["page"] for r in rows if r["page"] not in done]
    with open(dst, "a") as out, concurrent.futures.ProcessPoolExecutor(12) as ex:
        futs = {ex.submit(analyze, u): u for u in todo}
        for fu in concurrent.futures.as_completed(futs):
            try:
                res = fu.result(timeout=300)
            except Exception as e:
                res = {"page": futs[fu], "status": "error", "error": repr(e)[:200]}
            out.write(json.dumps(res) + "\n")
            out.flush()
