"""Kill orphaned browsers started by this fuzzer (parent gone, profile dir under mxss/private/profiles).
usage: reap.py [--loop SECONDS]; prints how many it killed."""
import os, signal, subprocess, sys, time
MARK = "private/profiles"
def once():
    out = subprocess.run(["ps", "-axo", "pid=,ppid=,command="], capture_output=True, text=True).stdout
    n = 0
    for line in out.splitlines():
        parts = line.split(None, 2)
        if len(parts) < 3: continue
        pid, ppid, cmd = int(parts[0]), int(parts[1]), parts[2]
        if ppid == 1 and MARK in cmd and ("firefox" in cmd or "chrome" in cmd.lower()):
            try: os.kill(pid, signal.SIGKILL); n += 1
            except Exception: pass
    return n
if "--loop" in sys.argv:
    iv = int(sys.argv[sys.argv.index("--loop") + 1])
    while True:
        k = once()
        if k: print(time.strftime("%H:%M:%S"), "reaped", k, flush=True)
        time.sleep(iv)
else:
    print(once())
