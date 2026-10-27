"""Pages with an HTML <plaintext> element (real parse), and whether </plaintext> appears in its
text (the only case where ending it at </plaintext> would change anything)."""
import glob, json, multiprocessing as mp, os, re, sys
sys.path.insert(0, os.path.expanduser("~/.claude/skills/web-platform-skills/skills/httparchive/template"))
import cc, html5lib

PRE = re.compile(r"<plaintext[\s/>]", re.I)

def work(item):
    url, text = item
    doc = html5lib.parse(text, treebuilder="etree", namespaceHTMLElements=True)
    els = [e for e in doc.iter("{http://www.w3.org/1999/xhtml}plaintext")]
    if not els:
        return {"url": url, "parsed": False}
    t = "".join(els[0].itertext())
    m = re.search(r"</plaintext\s*>", t, re.I)
    return {"url": url, "parsed": True, "len": len(t), "end_tag_inside": bool(m),
            "after_end_tag": t[m.end():m.end() + 200] if m else "", "start": t[:120]}

def items(paths, tot):
    for p in paths:
        for url, text in cc.html_responses(p):
            tot["html"] += 1
            if PRE.search(text):
                tot["regex"] += 1
                yield url, text

if __name__ == "__main__":
    paths = sorted(glob.glob(os.path.expanduser("~/git/commoncrawl/cc-data/CC-MAIN-2026-39/*.warc.gz")))
    tot = {"html": 0, "regex": 0}
    with mp.Pool(10) as pool, open(sys.argv[1] if len(sys.argv) > 1 else "out-cc/plaintext.jsonl", "w") as out:
        for r in pool.imap_unordered(work, items(paths, tot), chunksize=1):
            out.write(json.dumps(r) + "\n")
    print(json.dumps(tot))
