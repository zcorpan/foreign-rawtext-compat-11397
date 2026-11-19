import subprocess, sys, time, os
while subprocess.run(["pgrep", "-f", "fuzz/chain.py"], capture_output=True).stdout.strip():
    time.sleep(20)
here = os.path.dirname(os.path.abspath(__file__))
subprocess.run([sys.executable, os.path.join(here, "campaign.py")])
