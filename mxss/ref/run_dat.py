#!/usr/bin/env python3
"""Run html5lib-tests style .dat files through frnew (old and/or new mode).

usage: run_dat.py [--mode old|new|both] [--last N] [--show FILE:IDX]
                  [--codes] [--json OUT] PATH...
PATH is a .dat file or a directory of them.  Indices are 0-based entries in
the file (script-off entries are skipped, as in wpt's test.js).  A test
passes when the dumped tree is equal and the number of lines under
#errors + #new-errors equals the number of parse errors.
"""
import argparse
import glob
import json
import os
import signal
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import frnew  # noqa: E402

HEADINGS = {"data", "errors", "new-errors", "errors-new", "document-fragment",
            "script-on", "script-off", "document", "description"}


def parse_dat(text):
    """Port of wpt's resources/test.js parseDat."""
    if text.endswith("\n"):
        text = text[:-1]
    lines = text.split("\n")
    cases, data, key = [], None, None

    def heading(line):
        if not line.startswith("#"):
            return None
        h = line[1:].strip()
        return h if h in HEADINGS else None

    def normalise(d):
        return {k: (v[:-1] if v.endswith("\n") else v) for k, v in d.items()}

    for i, l in enumerate(lines):
        line = l + ("" if i == len(lines) - 1 else "\n")
        h = heading(line)
        if h:
            if data is not None and (h == "description" or (h == "data" and key != "description")):
                if key is not None and len(data[key]) > 0:
                    data[key] = data[key][:-1]
                cases.append(normalise(data))
                data = None
            if data is None:
                data = {}
            key = h
            data[key] = ""
        elif key is not None:
            data[key] += line
    if data is not None:
        cases.append(normalise(data))
    out = []
    for c in cases:
        e1 = [x for x in c.get("errors", "").split("\n") if x.strip()]
        e2 = [x for k in ("new-errors", "errors-new")
              for x in c.get(k, "").split("\n") if x.strip()]
        errs = {"max": e1 if len(e1) >= len(e2) else e2, "sum": e1 + e2,
                "errors": e1}[COUNT]
        out.append({"data": c.get("data", ""), "document": c.get("document", ""),
                    "fragment": c.get("document-fragment"),
                    "script_off": "script-off" in c, "errors": errs})
    return out


class Timeout(Exception):
    pass


def _alarm(*_):
    raise Timeout()


def run_one(mode, t):
    signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(5)
    try:
        tree, codes = frnew.parse(mode, t["data"], t["fragment"], scripting=True)
        return {"tree": tree, "codes": codes}
    except Timeout:
        return {"crash": "timeout"}
    except Exception as e:  # noqa: BLE001
        return {"crash": "%s: %s" % (type(e).__name__, e)}
    finally:
        signal.alarm(0)


COUNT = "sum"   # how to count #errors vs #new-errors: max | sum | errors


def judge(t, r):
    if "crash" in r:
        return "crash", r["crash"]
    why = []
    if r["tree"] != t["document"]:
        why.append("tree")
    if len(r["codes"]) != len(t["errors"]) and not t.get("tree_only"):
        why.append("errcount exp %d (%s) got %d (%s)" % (
            len(t["errors"]), ",".join(e.split(": ")[-1] for e in t["errors"]),
            len(r["codes"]), ",".join(r["codes"])))
    return ("fail", "; ".join(why)) if why else ("pass", "")


def collect(paths):
    files = []
    for p in paths:
        if os.path.isdir(p):
            files += sorted(glob.glob(os.path.join(p, "*.dat")))
        else:
            files.append(p)
    return files


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--mode", default="both", choices=["old", "old1", "new", "both"])
    ap.add_argument("--last", type=int)
    ap.add_argument("--show")
    ap.add_argument("--json")
    ap.add_argument("--quiet-fails", action="store_true",
                    help="only print per-file counts, not failing indices")
    ap.add_argument("--count", default="sum", choices=["max", "sum", "errors"],
                    help="expected error count: max(#errors,#new-errors) (default; the "
                    "files list the same errors in both), their sum, or #errors only")
    a = ap.parse_args()
    global COUNT
    COUNT = a.count
    modes = ["old", "new"] if a.mode == "both" else [a.mode]
    results = {}   # mode -> file -> idx -> (status, why, result)
    for f in collect(a.paths):
        name = os.path.basename(f)
        with open(f, encoding="utf-8", newline="") as fh:
            tests = parse_dat(fh.read())
        tree_only = not any(t["errors"] for t in tests)   # e.g. processing-instructions.dat
        for t in tests:
            t["tree_only"] = tree_only
        idxs = list(range(len(tests)))
        if a.last:
            idxs = idxs[-a.last:]
        for m in modes:
            d = results.setdefault(m, {}).setdefault(name, {})
            for i in idxs:
                t = tests[i]
                if t["script_off"]:
                    continue
                r = run_one(m, t)
                st, why = judge(t, r)
                d[i] = (st, why, r, t)
    if a.show:
        fn, idx = a.show.rsplit(":", 1)
        for m in modes:
            st, why, r, t = results[m][fn][int(idx)]
            print("== %s %s [%s] %s" % (m, a.show, st, why))
            print("data:", repr(t["data"]), "fragment:", t["fragment"])
            print("--expected\n" + t["document"] + "\n--actual\n" + r.get("tree", ""))
            print("errors exp:", t["errors"], "got:", r.get("codes"))
        return
    for m in modes:
        print("##", m)
        tp = tf = tt = 0
        for name, d in results[m].items():
            p = sum(1 for v in d.values() if v[0] == "pass")
            tok = sum(1 for v in d.values() if v[2].get("tree") == v[3]["document"])
            f_ = len(d) - p
            tp += p
            tf += f_
            tt += tok
            line = "%-45s pass %4d fail %4d (tree-ok %4d)" % (name, p, f_, tok)
            if f_ and not a.quiet_fails:
                line += "  fails: " + " ".join(
                    str(i) for i, v in d.items() if v[0] != "pass")
            print(line)
        print("TOTAL pass %d fail %d (tree-ok %d)" % (tp, tf, tt))
    if a.mode == "both":
        print("## differences old -> new (status or tree differ; count-only changes on tests "
              "that pass/fail the same way are omitted)")
        n = 0
        for name, d in results["new"].items():
            for i, v in d.items():
                o = results["old"][name][i]
                if o[0] != v[0] or o[2].get("tree") != v[2].get("tree"):
                    n += 1
                    print("%s:%d  %s -> %s  %r" % (name, i, o[0], v[0], v[3]["data"][:70]))
                    if v[0] != "pass":
                        print("      new: " + v[1])
        print("%d differing tests" % n)
    if a.json:
        out = {m: {n: {str(i): [v[0], v[1], v[2].get("tree"), v[2].get("codes")]
                       for i, v in d.items()} for n, d in fs.items()}
               for m, fs in results.items()}
        with open(a.json, "w") as fh:
            json.dump(out, fh, indent=1)


if __name__ == "__main__":
    main()
