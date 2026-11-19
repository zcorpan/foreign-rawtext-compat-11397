"""Selenium helpers: start a browser, load the fuzz page, run batches.

Engines: firefox (binary + pref dom.parser.foreign_rawtext.mode), chrome, safari.
"""
import os, signal, subprocess, sys, time

from selenium import webdriver
from selenium.webdriver.firefox.options import Options as FxOptions
from selenium.webdriver.firefox.service import Service as FxService
from selenium.webdriver.chrome.options import Options as CrOptions
from selenium.webdriver.chrome.service import Service as CrService

HERE = os.path.dirname(os.path.abspath(__file__))
PAGE = "file://" + os.path.join(HERE, "page.html")
GECKODRIVER = os.path.expanduser("~/git/web-platform-tests/wpt/_venv3/bin/geckodriver")
CANARY = "/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary"
CHROMEDRIVER_GLOB = os.path.expanduser("~/.cache/selenium/chromedriver/mac-arm64/")


def chromedriver():
    vs = sorted(os.listdir(CHROMEDRIVER_GLOB), key=lambda v: [int(x) for x in v.split(".")])
    return os.path.join(CHROMEDRIVER_GLOB, vs[-1], "chromedriver")


def make(engine, binary=None, mode=0, script_timeout=120, profile_root=None):
    if engine == "firefox":
        o = FxOptions()
        o.binary_location = binary
        o.add_argument("-headless")
        o.set_preference("dom.parser.foreign_rawtext.mode", int(mode))
        o.set_preference("browser.shell.checkDefaultBrowser", False)
        o.set_preference("dom.max_script_run_time", 0)
        o.set_preference("dom.max_chrome_script_run_time", 0)
        args = []
        env = dict(os.environ)
        if profile_root:
            os.makedirs(profile_root, exist_ok=True)
            args = ["--profile-root", profile_root]
            env["TMPDIR"] = profile_root
        d = webdriver.Firefox(options=o, service=FxService(GECKODRIVER, service_args=args, env=env))
    elif engine == "chrome":
        o = CrOptions()
        o.binary_location = binary or CANARY
        o.add_argument("--headless=new")
        o.add_argument("--no-sandbox")
        d = webdriver.Chrome(options=o, service=CrService(chromedriver()))
    elif engine == "safari":
        d = webdriver.Safari()
    else:
        raise SystemExit("unknown engine " + engine)
    d.set_script_timeout(script_timeout)
    try:
        d.command_executor.set_timeout(script_timeout + 60)
    except Exception:
        pass
    d.set_page_load_timeout(60)
    d.get(PAGE)
    return d


RUN_JS = "const cb=arguments[arguments.length-1]; try { cb(FZ.run(arguments[0])); } catch(e) { cb({error:String(e)}); }"
MIN_JS = "const cb=arguments[arguments.length-1]; try { cb(FZ.minimize(arguments[0], arguments[1])); } catch(e) { cb({error:String(e)}); }"


def run_batch(d, opts):
    return d.execute_async_script(RUN_JS, opts)


def minimize(d, spec, ms=20000):
    return d.execute_async_script(MIN_JS, spec, ms)


def _descendants(pid):
    out = subprocess.run(["ps", "-axo", "pid=,ppid="], capture_output=True, text=True).stdout
    kids = {}
    for line in out.splitlines():
        a, b = line.split()
        kids.setdefault(int(b), []).append(int(a))
    res, stack = [], [pid]
    while stack:
        for c in kids.get(stack.pop(), []):
            res.append(c)
            stack.append(c)
    return res


def quit_quietly(d):
    """Quit the driver and make sure geckodriver/chromedriver and every browser process under it are gone."""
    if d is None:
        return
    pid = None
    try:
        pid = d.service.process.pid
        victims = _descendants(pid) + [pid]
    except Exception:
        victims = []
    try:
        d.quit()
    except Exception:
        pass
    for v in victims:
        try:
            os.kill(v, signal.SIGKILL)
        except Exception:
            pass
