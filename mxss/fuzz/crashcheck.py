"""Replay logged crashing cases (private/crash-specs.json) in each mode, one fresh browser each. Prints counts only."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import driver
FX = os.path.expanduser("~/src/firefox-foreign-rawtext/obj-aarch64-apple-darwin27.0.0/dist/Nightly.app/Contents/MacOS/firefox")
M4 = os.path.expanduser("~/src/m4-fuzz/Nightly.app/Contents/MacOS/firefox")
specs = json.load(open(os.path.join(HERE, "..", "private", "crash-specs.json")))
JS = "const cb=arguments[arguments.length-1]; try { FZ.evalSpec(arguments[0]); cb('ok'); } catch(e) { cb('js-error'); }"
res = {}
for mode, b in ((0, FX), (2, FX), (3, FX), (4, M4)):
    n = crashed = 0
    for found_mode, sp in specs:
        n += 1
        d = None
        try:
            d = driver.make("firefox", b, mode, script_timeout=15, profile_root=os.path.join(HERE, "..", "private", "profiles", "crashcheck"))
            d.command_executor.set_timeout(30)
            d.execute_async_script(JS, sp)
        except Exception:
            crashed += 1
        finally:
            driver.quit_quietly(d)
    res[mode] = (crashed, n)
    print("mode", mode, "crashed", crashed, "of", n, flush=True)
