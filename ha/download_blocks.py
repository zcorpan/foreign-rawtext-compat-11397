"""Page through a table (default test.fr11397_blocks; TABLE env var) with `bq head` (tabledata.list, not billed as a query) and
write one JSON file per batch into OUT_DIR. Resumable.

usage: download_blocks.py OUT_DIR [BATCH [WORKER NWORKERS]]
"""
import json, os, subprocess, sys

TABLE = os.environ.get("TABLE", "test.fr11397_blocks")

out_dir = sys.argv[1]
batch = int(sys.argv[2]) if len(sys.argv) > 2 else 2000
worker, nworkers = (int(sys.argv[3]), int(sys.argv[4])) if len(sys.argv) > 4 else (0, 1)
total = int(json.loads(subprocess.run(["bq", "show", "--format=json", TABLE],
                                       capture_output=True, text=True, check=True).stdout)["numRows"])
os.makedirs(out_dir, exist_ok=True)
for i, start in enumerate(range(0, total, batch)):
    if i % nworkers != worker:
        continue
    path = os.path.join(out_dir, f"{start:07d}.json")
    if os.path.exists(path):
        continue
    for attempt in range(5):
        p = subprocess.run(["bq", "head", "--format=json", f"--start_row={start}", f"--max_rows={batch}",
                            TABLE], capture_output=True, text=True)
        if p.returncode == 0 and p.stdout.strip().startswith("["):
            break
    else:
        sys.exit(f"failed at {start}: {p.stderr[:300]}")
    rows = json.loads(p.stdout)
    with open(path + ".part", "w") as f:
        json.dump(rows, f)
    os.rename(path + ".part", path)
    print(start, len(rows), flush=True)
