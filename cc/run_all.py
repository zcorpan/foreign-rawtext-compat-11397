"""Run analyze_warc.py on each picked WARC once its download has finished."""
import os, subprocess, sys, time

listfile, data, out = sys.argv[1:4]
for p in open(listfile).read().split():
    f = os.path.join(data, os.path.basename(p))
    while not os.path.exists(f):
        time.sleep(10)
    subprocess.run([sys.executable, "cc/analyze_warc.py", out, f], check=True)
