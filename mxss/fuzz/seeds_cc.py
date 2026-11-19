"""Extract SVG/MathML blocks (plus a little surrounding markup) from Common Crawl WARCs as fuzz seeds.

usage: seeds_cc.py OUT.jsonl [N_WARCS] [MAX_BLOCKS]   (output belongs in mxss/private/)
Needs warcio (in the repo venv) and cc.py from the httparchive skill template.
"""
import glob, json, os, random, re, sys
sys.path.insert(0, os.path.expanduser("~/git/zcorpan/web-platform-skills/plugins/httparchive/skills/httparchive/template"))
import cc

out, nw, maxb = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 3, int(sys.argv[3]) if len(sys.argv) > 3 else 4000
warcs = sorted(glob.glob(os.path.expanduser("~/git/commoncrawl/cc-data/CC-MAIN-2026-39/*.warc.gz")))[:nw]
INTEREST = re.compile(r"<(style|script|title|textarea|xmp|iframe|noembed|noframes|noscript|plaintext|foreignObject|annotation-xml|mglyph)\b|<!--|<!\[CDATA\[|<\?", re.I)
rnd = random.Random(11397)
n = 0
with open(out, "w") as f:
    for w in warcs:
        per = 0
        for url, html in cc.html_responses(w):
            for m in re.finditer(r"<(svg|math)\b", html, re.I):
                blk = html[max(0, m.start() - 80):m.start() + 1500]
                end = re.search(r"</(svg|math)>", blk[80:], re.I)
                if end:
                    blk = blk[:80 + end.end()]
                if INTEREST.search(blk) and rnd.random() < 0.5:
                    f.write(json.dumps({"html": blk}) + "\n"); n += 1; per += 1
                    break
            if per >= maxb // nw:
                break
print(n, "blocks")
