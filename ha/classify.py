"""Exact classification of HTTP Archive candidates (queries/candidates.sql output).

Reads JSON rows {page, rank, risky_blocks: [...], body?} (bq --format=json output, one array) and
parses each candidate block standalone (in <body>) today's way and in each variant, with
cc/frparse.py. With --full, also parses the full body (when present) to confirm in context.
Writes one JSON line per page with the per-mode differing elements.

usage: classify.py OUT_DIR ROWS.json... [--full]   (one OUT_DIR/<name>.jsonl per input; skips done)
"""
import json, multiprocessing as mp, os, signal, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "cc"))
import analyze_warc, frparse

MODES = ("raw", "rcdata", "rcdata-dc")


def diff(html):
    _, old = frparse.parse(html, "old")
    out = {}
    for m in MODES:
        _, new = frparse.parse(html, m)
        out[m] = [e for e in analyze_warc.compare(old["elements"], new["elements"])["elements"] if e["verdict"] != "same"]
    out["n_old"] = len(old["elements"])
    return out


def work(args):
    row, full = args
    signal.signal(signal.SIGALRM, analyze_warc._alarm)
    signal.alarm(120)
    try:
        res = {"page": row["page"], "rank": row.get("rank"), "blocks": {m: [] for m in MODES}}
        for blk in row.get("risky_blocks") or []:
            d = diff("<!DOCTYPE html><body>" + blk)
            for m in MODES:
                res["blocks"][m].extend(d[m])
        if full and row.get("body"):
            d = diff(row["body"])
            res["full"] = {m: d[m] for m in MODES}
        return res
    except analyze_warc.Timeout:
        return {"page": row["page"], "error": "timeout"}
    except Exception as e:
        return {"page": row["page"], "error": repr(e)[:200]}
    finally:
        signal.alarm(0)


def rows(path):
    with open(path) as f:
        data = json.load(f)
    for r in data:
        yield r


if __name__ == "__main__":
    out_dir = sys.argv[1]
    full = "--full" in sys.argv
    os.makedirs(out_dir, exist_ok=True)
    with mp.Pool(int(os.environ.get("NPROC", "8"))) as pool:
        for src in [a for a in sys.argv[2:] if not a.startswith("--")]:
            dst = os.path.join(out_dir, os.path.basename(src).replace(".json", ".jsonl"))
            if os.path.exists(dst):
                continue
            with open(dst + ".part", "w") as out:
                for res in pool.imap_unordered(work, ((r, full) for r in rows(src)), chunksize=4):
                    out.write(json.dumps(res) + "\n")
            os.rename(dst + ".part", dst)
            print(dst, flush=True)
