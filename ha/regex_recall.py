"""Recall of queries/candidates.sql's candidate test, measured on the Common Crawl pages whose
exact parse differs (out-cc/differs.jsonl): would the BigQuery regex logic have flagged them?
Mirrors the SQL (RE2 semantics are close enough here): blocks, element regex with a 40-char
tail, classify, page is a candidate if any element isn't plain/self-closing.

usage: regex_recall.py DATA_DIR(with the WARCs)"""
import collections, glob, json, os, re, sys
sys.path.insert(0, os.path.expanduser("~/.claude/skills/web-platform-skills/skills/httparchive/template"))
import cc

BLOCK = re.compile(r"(?is)(<(?:svg|math)[\s/>][\s\S]*?(?:</(?:svg|math)\s*>|<\\/(?:svg|math)|$))")
NAMES = r"(?:style|script|xmp|iframe|noembed|noframes|noscript|plaintext|title|textarea)"
HAS = re.compile(r"(?i)<" + NAMES + r"\b")
EL = re.compile(r"(?i)(<" + NAMES + r"\b[^>]*>[^<&]*(?:[<&][\s\S]{0,40})?)")


def kind(el):
    name = re.match(r"<([A-Za-z]+)", el).group(1).lower()
    tag = re.match(r"(<[^>]*>)", el).group(1)
    rest = re.match(r"<[^>]*>[^<]*([\s\S]*)$" if name in ("title", "textarea") else r"<[^>]*>[^<&]*([\s\S]*)$", el).group(1)
    if re.search(r"/\s*>$", tag): return "self-closing"
    if rest == "": return "unterminated"
    if re.match(r"</" + name + r"[\s/>]", rest.lower()): return "plain"
    return "risky"


def candidate(html):
    for b in BLOCK.findall(html):
        if not HAS.search(b):
            continue
        for el in EL.findall(b):
            if kind(el) not in ("plain", "self-closing"):
                return True
    return False


want = {}
for line in open("out-cc/differs.jsonl"):
    r = json.loads(line)
    if "totals" in r:
        continue
    want[r["url"]] = ("rcdata" if r["rcdata"] else "raw-only")
found = collections.Counter(); total = collections.Counter(); missed = []
for p in sorted(glob.glob(os.path.join(os.path.expanduser(sys.argv[1]), "*.warc.gz"))):
    for url, html in cc.html_responses(p):
        if url in want:
            g = want.pop(url)
            total[g] += 1
            if candidate(html):
                found[g] += 1
            else:
                missed.append((g, url))
for g in total:
    print(f"{g}: regex flags {found[g]} of {total[g]} pages that differ")
for m in missed[:15]:
    print("  missed", m)
