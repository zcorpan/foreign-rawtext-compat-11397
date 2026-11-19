"""Log summed RSS (MB) of all browser processes whose command line mentions mxss/private/profiles, every N seconds.
usage: memwatch.py OUTFILE [SECONDS]"""
import subprocess, sys, time
out, iv = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 15
while True:
    ps = subprocess.run(["ps", "-axo", "rss=,command="], capture_output=True, text=True).stdout
    tot = n = 0
    # child renderer processes don't carry the profile path; sum all Chrome Canary / Nightly processes
    for line in ps.splitlines():
        rss, _, cmd = line.strip().partition(" ")
        if "private/profiles" in cmd or "Google Chrome Canary" in cmd or "m4-fuzz/Nightly" in cmd:
            tot += int(rss); n += 1
    with open(out, "a") as f: f.write(f"{time.strftime('%H:%M:%S')} {tot/1024:.0f}MB {n}procs\n")
    time.sleep(iv)
