"""Download the picked WARC files (sequentially, resumable) into a data directory."""
import os, subprocess, sys

listfile, outdir = sys.argv[1], sys.argv[2]
for p in open(listfile).read().split():
    dest = os.path.join(outdir, os.path.basename(p))
    if os.path.exists(dest):
        continue
    subprocess.run(["curl", "-sS", "--retry", "5", "-o", dest + ".part",
                    "https://data.commoncrawl.org/" + p], check=True)
    os.rename(dest + ".part", dest)
    print("done", dest, flush=True)
