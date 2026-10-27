"""Rerun the pages that differ in rcdata mode with the rcdata-dc mode (RCDATA plus dropping
comments). Only those pages can differ in rcdata-dc mode: it differs from rcdata only where the
input has "<!--" inside a foreign RCDATA element, which today is a comment child.

usage: recheck_dc.py OUT_DIR WARC_DIR > OUT_DIR/dc.jsonl
"""
import glob, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import analyze_warc, frparse
from warcio.archiveiterator import ArchiveIterator

out_dir, warc_dir = sys.argv[1:3]
for f in sorted(glob.glob(os.path.join(out_dir, "CC-*.jsonl"))):
    want = set()
    for line in open(f):
        r = json.loads(line)
        if r.get("status") == "ok" and any(e["verdict"] != "same" for e in r["rcdata"]["elements"]):
            want.add(r["url"])
    if not want:
        continue
    warc = os.path.join(warc_dir, os.path.basename(f).replace(".jsonl", ".warc.gz"))
    with open(warc, "rb") as fh:
        for rec in ArchiveIterator(fh):
            if rec.rec_type != "response":
                continue
            url = rec.rec_headers.get_header("WARC-Target-URI")
            if url not in want:
                continue
            want.discard(url)
            html = analyze_warc.decode(rec.content_stream().read(), rec.http_headers.get_header("Content-Type"))
            _, old = frparse.parse(html, "old")
            _, new = frparse.parse(html, "rcdata-dc")
            print(json.dumps({"url": url, "rcdata-dc": analyze_warc.compare(old["elements"], new["elements"])}), flush=True)
