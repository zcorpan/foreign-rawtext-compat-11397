"""Compare today's parse with rcdata, rcdata-dc and rcdata-c (RCDATA, comments kept as comment
nodes, an end tag inside a comment still ends the element) by the exact child nodes (type and
data) of each SVG/MathML element of interest. Pages whose only difference is an element left
open at the end of a truncated body are counted separately.

usage: mode_c.py HA_BODIES_DIR CC_DATA_DIR OUT.json"""
import collections, concurrent.futures, glob, json, os, re, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "cc"))
sys.path.insert(0, os.path.expanduser("~/.claude/skills/web-platform-skills/skills/httparchive/template"))

MODES = ("rcdata", "rcdata-dc", "rcdata-c")


def kids(e):
    out = []
    if e.text:
        out.append(("t", e.text))
    for k in e:
        out.append(("c", k.text or "") if not isinstance(k.tag, str) else ("e", k.tag))
        if k.tail:
            out.append(("t", k.tail))
    # Merge adjacent text nodes (the parser does too).
    merged = []
    for x in out:
        if merged and x[0] == "t" and merged[-1][0] == "t":
            merged[-1] = ("t", merged[-1][1] + x[1])
        else:
            merged.append(x)
    return merged


def page(html):
    import frparse
    complete = bool(re.search(r"</(?:html|body)\s*>", html[-4000:], re.I))
    _, old = frparse.parse(html, "old")
    res = {}
    for m in MODES:
        _, new = frparse.parse(html, m)
        diffs = []
        for a, b in zip(old["elements"], new["elements"]):
            if a["name"] != b["name"] or a.get("ns") != b.get("ns"):
                diffs.append("unaligned")
                break
            if a.get("etree") is None or b.get("etree") is None:
                continue
            if kids(a["etree"]) != kids(b["etree"]):
                diffs.append("unterminated-truncated" if b.get("open_at_eof") and not complete else
                             ("unterminated" if b.get("open_at_eof") else "differs"))
        if len(old["elements"]) != len(new["elements"]) and "unaligned" not in diffs:
            diffs.append("count")
        res[m] = sorted(set(diffs))
    return res


def ha_items(d):
    for f in sorted(glob.glob(os.path.join(d, "*.json"))):
        for r in json.load(open(f)):
            yield ("ha", r["page"], r["body"])


def cc_items(d):
    import cc
    want = {json.loads(l)["url"] for l in open("out-cc/differs.jsonl") if "totals" not in l}
    for p in sorted(glob.glob(os.path.join(d, "*.warc.gz"))):
        for url, html in cc.html_responses(p):
            if url in want:
                yield ("cc", url, html)


def work(item):
    src, url, html = item
    try:
        return src, url, page(html)
    except Exception as e:
        return src, url, {"error": repr(e)[:200]}


if __name__ == "__main__":
    ha_dir, cc_dir, out_path = sys.argv[1:4]
    results = {}
    with concurrent.futures.ProcessPoolExecutor(11) as ex:
        for gen in (ha_items(ha_dir), cc_items(os.path.expanduser(cc_dir))):
            for src, url, res in ex.map(work, gen, chunksize=4):
                results[f"{src} {url}"] = res
    json.dump(results, open(out_path, "w"))
    for src in ("ha", "cc"):
        c = collections.Counter()
        for k, v in results.items():
            if not k.startswith(src + " ") or "error" in v:
                continue
            for m in MODES:
                real = [d for d in v[m] if d != "unterminated-truncated"]
                c[(m, "differs" if real else ("truncated-only" if v[m] else "same"))] += 1
        print(src, {f"{m} {k}": n for (m, k), n in sorted(c.items())})
