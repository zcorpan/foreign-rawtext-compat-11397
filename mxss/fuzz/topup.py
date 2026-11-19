import subprocess, sys, os
here = os.path.dirname(os.path.abspath(__file__))
py = sys.executable
fx = os.path.expanduser("~/src/firefox-foreign-rawtext/obj-aarch64-apple-darwin27.0.0/dist/Nightly.app/Contents/MacOS/firefox")
for m in (3, 2):
    subprocess.run([py, os.path.join(here, "run.py"), "--engine", "firefox", "--binary", fx, "--mode", str(m), "--label", f"ff-m{m}-scratch", "--workers", "4", "--cases", "2000000", "--seconds", "3000"])
