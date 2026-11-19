import subprocess, sys, time, os
# wait for any running campaign to finish, then run the m4 steps
while subprocess.run(["pgrep", "-f", "fuzz/campaign.py"], capture_output=True).stdout.strip():
    time.sleep(20)
here = os.path.dirname(os.path.abspath(__file__))
subprocess.run([sys.executable, os.path.join(here, "campaign.py"), "--m4", os.path.expanduser("~/src/m4-fuzz/Nightly.app/Contents/MacOS/firefox"), "--only", "ff-m4-scratch", "ff-m4-seeded", "ff-m4-noscriptmix"])
