"""Sequential campaign over configurations (resumable: finished steps are skipped via private/runs/campaign.done).

usage: campaign.py [--only LABEL...] [--m4 BINARY]
Steps are (label, engine, binary, mode, seeds, workers, cases_per_worker, cfg). Re-running continues each label
from its worker logs; a step is only marked done when run.py returns normally.
"""
import json, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
PRIV = os.path.join(HERE, "..", "private")
PY = os.path.join(HERE, "..", "..", ".venv", "bin", "python")
FX = os.path.expanduser("~/src/firefox-foreign-rawtext/obj-aarch64-apple-darwin27.0.0/dist/Nightly.app/Contents/MacOS/firefox")
SEEDS = os.path.join(PRIV, "seeds-all.jsonl")
steps = []
def add(label, engine, binary, mode, seeds, workers, cases, cfg=None, seconds=3000):
    steps.append(dict(label=label, engine=engine, binary=binary, mode=mode, seeds=seeds, workers=workers, cases=cases, cfg=cfg, seconds=seconds))
M4 = os.path.expanduser("~/src/m4-fuzz/Nightly.app/Contents/MacOS/firefox")
SD = {"pSeed": 0.5, "pMutate": 0.3}
# (label, engine, binary, mode) in priority order; budgets are cases per worker
add("ff-m0-scratch", "firefox", FX, 0, None, 4, 3_000_000)
add("ff-m4-scratch", "firefox", M4, 4, None, 4, 3_000_000)
add("ff-m4-noscriptmix", "firefox", M4, 4, None, 2, 150_000, cfg={"allowNoscriptFrag": True})
add("ff-m0-noscriptmix", "firefox", FX, 0, None, 2, 150_000, cfg={"allowNoscriptFrag": True})
add("ff-m4-seeded", "firefox", M4, 4, SEEDS, 4, 500_000, cfg=SD)
add("ff-m0-seeded", "firefox", FX, 0, SEEDS, 4, 500_000, cfg=SD)
add("ff-m3-scratch", "firefox", FX, 3, None, 4, 1_000_000)
add("ff-m2-scratch", "firefox", FX, 2, None, 4, 1_000_000)
add("chrome-scratch", "chrome", None, 0, None, 2, 1_000_000)
add("ff-m3-seeded", "firefox", FX, 3, SEEDS, 4, 250_000, cfg=SD)
add("ff-m2-seeded", "firefox", FX, 2, SEEDS, 4, 250_000, cfg=SD)
add("chrome-seeded", "chrome", None, 0, SEEDS, 2, 250_000, cfg=SD)
add("ff-m3-noscriptmix", "firefox", FX, 3, None, 2, 100_000, cfg={"allowNoscriptFrag": True})
add("ff-m2-noscriptmix", "firefox", FX, 2, None, 2, 100_000, cfg={"allowNoscriptFrag": True})
SC = {"tk": "selfclose", "pSeed": 0, "pMutate": 0.2}
for label, eng, b, m in (("ff-m4-selfclose", "firefox", M4, 4), ("ff-m0-selfclose", "firefox", FX, 0), ("ff-m3-selfclose", "firefox", FX, 3)):
    add(label, eng, b, m, None, 2, 1_500_000, cfg=SC)
only = sys.argv[sys.argv.index("--only") + 1:] if "--only" in sys.argv else None
done_f = os.path.join(PRIV, "runs", "campaign.done")
done = set(open(done_f).read().split()) if os.path.exists(done_f) else set()
for s in steps:
    if s["label"] in done or (only and s["label"] not in only):
        continue
    cmd = [PY, os.path.join(HERE, "run.py"), "--engine", s["engine"], "--mode", str(s["mode"]), "--label", s["label"], "--workers", str(s["workers"]), "--cases", str(s["cases"]), "--seconds", str(s["seconds"])]
    if s["binary"]: cmd += ["--binary", s["binary"]]
    if s["seeds"]: cmd += ["--seeds", s["seeds"]]
    if s["cfg"]: cmd += ["--cfg", json.dumps(s["cfg"])]
    print("RUN", s["label"], flush=True)
    r = subprocess.run(cmd)
    if r.returncode == 0:
        open(done_f, "a").write(s["label"] + "\n")
