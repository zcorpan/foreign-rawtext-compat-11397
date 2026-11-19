"""Run the fuzzer for one configuration with N parallel browser workers (resumable).

usage: run.py --engine firefox --binary PATH --mode 0 --label ff-m0 [--workers 4] [--seconds 600]
              [--seeds seeds.jsonl] [--cases N] [--base 1] [--batch 50000] [--cfg JSON]

Logs: mxss/private/runs/LABEL/w<k>.jsonl (append-only). One 'batch' line per batch (case index
range [start, start+done), stats) and one 'finding' line per newly seen signature (minimized spec).
Case i of worker k derives from PRNG seed hash(base, i) with i in the worker's own index space
(start = k * 10**12 + n), so re-running with the same label continues where each worker stopped.
"""
import argparse, glob, http.server, json, multiprocessing as mp, os, sys, threading, time, traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import driver

RUNS = os.path.join(HERE, "..", "private", "runs")


def load_state(rundir, k):
    nxt = k * 10**12
    for l in open(os.path.join(rundir, f"w{k}.jsonl")) if os.path.exists(os.path.join(rundir, f"w{k}.jsonl")) else []:
        try:
            r = json.loads(l)
        except Exception:
            continue
        if r.get("type") == "batch":
            nxt = max(nxt, r["start"] + max(r["done"], 1))
    return nxt


def known_sigs(rundir):
    s = set()
    for f in glob.glob(os.path.join(rundir, "w*.jsonl")):
        for l in open(f):
            if '"type": "finding"' in l:
                try:
                    s.add(json.loads(l)["sig"])
                except Exception:
                    pass
    return s


class Trace(http.server.BaseHTTPRequestHandler):
    last = None
    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        Trace.last = self.rfile.read(n).decode()
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
    def do_OPTIONS(self):
        self.send_response(204)
        for h, v in (("Access-Control-Allow-Origin", "*"), ("Access-Control-Allow-Headers", "*"), ("Access-Control-Allow-Methods", "POST")):
            self.send_header(h, v)
        self.end_headers()
    def log_message(self, *a):
        pass


def worker(k, a, deadline):
    rundir = os.path.join(RUNS, a.label)
    log = open(os.path.join(rundir, f"w{k}.jsonl"), "a", buffering=1)
    seeds = [json.loads(l) for l in open(a.seeds)] if a.seeds and os.path.exists(a.seeds) else []
    seeds = [s if isinstance(s, str) else s.get("html", "") for s in seeds]
    start = load_state(rundir, k)
    base = a.base + k * 7919
    total = 0
    d = None
    snap = None  # (corpus, seen) at the start of the current batch
    cfg = json.loads(a.cfg) if a.cfg else {}
    prof = os.path.join(HERE, "..", "private", "profiles", f"{a.label}-w{k}")
    srv = http.server.HTTPServer(("127.0.0.1", 0), Trace)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    trace_url = f"http://127.0.0.1:{srv.server_address[1]}/"

    def fresh():
        nd = driver.make(a.engine, a.binary, a.mode, script_timeout=a.batch_ms // 1000 + 10, profile_root=prof)
        try:
            nd.command_executor.set_timeout(a.batch_ms // 1000 + 30)
        except Exception:
            pass
        if seeds:
            nd.execute_script("FZ.setSeeds(arguments[0])", seeds)
        if snap:
            nd.execute_script("FZ.setCorpus(arguments[0], arguments[1])", snap[0], snap[1])
        return nd

    while time.time() < deadline and (a.cases is None or total < a.cases):
        opts = None
        try:
            if d is None:
                d = fresh()
            snap = d.execute_script("return [FZ.getCorpus(), FZ.getSeen()]")
            skip = sorted(known_sigs(rundir))
            t = min(a.batch_ms, int((deadline - time.time()) * 1000))
            if t < 1000:
                break
            opts = {"base": base, "start": start, "n": a.batch, "timeMs": t, "skip": skip, "maxSamples": 1, "cfg": cfg}
            r = driver.run_batch(d, opts)
            if "error" in r:
                raise RuntimeError(r["error"])
            log.write(json.dumps({"type": "batch", "t": time.time(), "start": start, "done": r["done"], "ms": r["ms"], "stats": r["stats"], "engine": a.engine, "mode": a.mode, "seeded": bool(seeds)}) + "\n")
            start += max(r["done"], 1)
            total += r["done"]
            seen = set(skip)
            for s in r["samples"]:
                if s["sig"] in seen:
                    continue
                seen.add(s["sig"])
                m = driver.minimize(d, s["spec"], 10000)
                rec = {"type": "finding", "sig": s["sig"], "engine": a.engine, "mode": a.mode, "label": a.label, "worker": k, "idx": s["idx"], "min_ok": m.get("ok"), "spec": m.get("spec", s["spec"])}
                log.write(json.dumps(rec) + "\n")
        except Exception as e:
            log.write(json.dumps({"type": "error", "t": time.time(), "err": traceback.format_exc()[-300:], "start": start}) + "\n")
            driver.quit_quietly(d)
            d = None
            # replay the batch from its corpus snapshot with per-case tracing to find a crashing case
            try:
                if opts is None:
                    raise RuntimeError("no batch")
                Trace.last = None
                d = fresh()
                ropts = dict(opts, trace=trace_url, timeMs=a.batch_ms * 3)
                driver.run_batch(d, ropts)
                log.write(json.dumps({"type": "unreproduced", "start": start}) + "\n")
                start += a.batch
            except Exception:
                idx = int(Trace.last) if Trace.last else None
                driver.quit_quietly(d)
                d = None
                if idx is None:
                    start += a.batch
                else:
                    try:
                        d = fresh()
                        r2 = driver.run_batch(d, dict(opts, stopAt=idx))
                        log.write(json.dumps({"type": "crash", "t": time.time(), "idx": idx, "engine": a.engine, "mode": a.mode, "spec": r2.get("stopSpec")}) + "\n")
                    except Exception:
                        driver.quit_quietly(d)
                        d = None
                    start = idx + 1
            time.sleep(1)
    driver.quit_quietly(d)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", default="firefox")
    ap.add_argument("--binary")
    ap.add_argument("--mode", default="0")
    ap.add_argument("--label", required=True)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--seconds", type=int, default=600)
    ap.add_argument("--cases", type=int)
    ap.add_argument("--seeds")
    ap.add_argument("--base", type=int, default=1)
    ap.add_argument("--batch", type=int, default=100000)
    ap.add_argument("--batch-ms", dest="batch_ms", type=int, default=20000)
    ap.add_argument("--cfg")
    a = ap.parse_args()
    os.makedirs(os.path.join(RUNS, a.label), exist_ok=True)
    deadline = time.time() + a.seconds
    ps = [mp.Process(target=worker, args=(k, a, deadline)) for k in range(a.workers)]
    for p in ps:
        p.start()
    for p in ps:
        p.join()


if __name__ == "__main__":
    main()
