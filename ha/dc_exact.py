"""rcdata-dc: pages whose foreign elements' content changes beyond losing comment nodes (exact,
untruncated comparison of child nodes with comments removed). Truncated-body-only pages separate.
usage: dc_exact.py HA_BODIES_DIR"""
import collections, concurrent.futures, glob, json, os, re, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "cc"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mode_c import kids


def strip(ks):
    out = []
    for k in ks:
        if k[0] == "c":
            continue
        if out and k[0] == "t" and out[-1][0] == "t":
            out[-1] = ("t", out[-1][1] + k[1])
        else:
            out.append(k)
    return out


def work(r):
    import frparse
    html = r["body"]
    complete = bool(re.search(r"</(?:html|body)\s*>", html[-4000:], re.I))
    _, a = frparse.parse(html, "old"); _, b = frparse.parse(html, "rcdata-dc")
    kinds = set()
    for x, y in zip(a["elements"], b["elements"]):
        if x["name"] != y["name"]:
            kinds.add("unaligned"); break
        if x.get("etree") is None or y.get("etree") is None:
            continue
        kx, ky = kids(x["etree"]), kids(y["etree"])
        if kx == ky:
            continue
        if y.get("open_at_eof") and not complete:
            kinds.add("truncated")
        elif strip(kx) == strip(ky):
            kinds.add("comment-only")
        else:
            kinds.add("text")
    return r["page"], sorted(kinds)


def safe(r):
    try:
        return work(r)
    except Exception as e:
        return r["page"], ["error"]


def results():
    import multiprocessing as mp
    # One batch file at a time, recycling workers, so memory stays bounded.
    with mp.Pool(10, maxtasksperchild=25) as pool:
        for f in sorted(glob.glob(os.path.join(sys.argv[1], "*.json"))):
            yield from pool.imap_unordered(safe, json.load(open(f)), chunksize=2)


if __name__ == "__main__":
    c = collections.Counter()
    for page, kinds in results():
        if "error" in kinds:
            c["error"] += 1
        elif not kinds:
            c["same"] += 1
        elif "text" in kinds or "unaligned" in kinds:
            c["text changes"] += 1
        elif "comment-only" in kinds:
            c["comment nodes only"] += 1
        else:
            c["truncated only"] += 1
    print(dict(c))
