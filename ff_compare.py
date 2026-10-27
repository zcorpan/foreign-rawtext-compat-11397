"""Load each sampled page in a Firefox build with different `dom.parser.foreign_rawtext.mode`
values (A and A2: 0, today's parsing; B: the proposed mode) and record what changed.

usage: ff_compare.py FIREFOX_BINARY SAMPLE.jsonl OUT_DIR B_MODE [--limit N]

One JSON line per page in OUT_DIR/results.jsonl (resumable). Full-page screenshots in
OUT_DIR/shots/ (gitignored). Scrubbed at capture like harness.py.
"""
import concurrent.futures, json, os, sys, time, traceback

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service

from harness import scrub

GECKODRIVER = os.path.expanduser("~/git/web-platform-tests/wpt/_venv3/bin/geckodriver")
WAIT = 5
PAGE_TIMEOUT = 45

EXTRA_JS = r"""
const NAMES = new Set(['style','script','title','textarea','xmp','iframe','noembed','noframes','noscript','plaintext']);
const out = [];
for (const e of document.querySelectorAll('*')) {
  if (!NAMES.has(e.localName) || e.namespaceURI === 'http://www.w3.org/1999/xhtml') continue;
  const kinds = [...e.childNodes].map(n => n.nodeType === 1 ? 'E:' + n.localName : n.nodeType === 8 ? '#comment' : '#text');
  let rules = null;
  try { rules = e.sheet ? e.sheet.cssRules.length : null; } catch (err) { rules = 'err'; }
  const svg = e.closest('svg');
  out.push({ns: e.namespaceURI.includes('svg') ? 'svg' : 'math', name: e.localName,
            kinds: kinds.slice(0, 10), text: e.textContent.slice(0, 300), rules,
            svgBox: svg ? [Math.round(svg.getBoundingClientRect().width), Math.round(svg.getBoundingClientRect().height)] : null});
}
return {els: out.slice(0, 200), nEls: out.length,
        scrollWidth: document.documentElement ? document.documentElement.scrollWidth : 0,
        scrollHeight: document.documentElement ? document.documentElement.scrollHeight : 0,
        elementCount: document.getElementsByTagName('*').length};
"""


def make_driver(binary, mode):
    opts = Options()
    opts.binary_location = binary
    opts.add_argument("-headless")
    opts.set_preference("dom.parser.foreign_rawtext.mode", mode)
    opts.set_preference("browser.shell.checkDefaultBrowser", False)
    opts.set_preference("media.autoplay.default", 5)
    opts.enable_bidi = True
    d = webdriver.Firefox(options=opts, service=Service(GECKODRIVER))
    d.set_window_size(1366, 768)
    d.set_page_load_timeout(PAGE_TIMEOUT)
    d.set_script_timeout(20)
    errors = []
    d.script.add_javascript_error_handler(lambda e: errors.append(scrub(getattr(e, "text", str(e)))[:300]))
    d._fr_errors = errors
    return d


def visit(d, url, shot):
    d._fr_errors.clear()
    rec = {}
    try:
        d.get(url)
    except Exception as e:  # timeouts still leave a page to measure
        rec["load_error"] = type(e).__name__
    time.sleep(WAIT)
    rec.update(d.execute_script(EXTRA_JS))
    d.save_full_page_screenshot(shot)
    rec["errors"] = sorted(set(d._fr_errors))[:30]
    return rec


def main():
    binary, sample, out_dir, b_mode = sys.argv[1:5]
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
    os.makedirs(os.path.join(out_dir, "shots"), exist_ok=True)
    res_path = os.path.join(out_dir, "results.jsonl")
    done = set()
    if os.path.exists(res_path):
        done = {json.loads(l)["id"] for l in open(res_path)}
    items = [json.loads(l) for l in open(sample)]
    if limit:
        items = items[:limit]
    setups = [("A", 0), ("A2", 0), ("B", int(b_mode))]
    drivers = {label: make_driver(binary, mode) for label, mode in setups}
    pool = concurrent.futures.ThreadPoolExecutor(1)
    try:
        with open(res_path, "a") as out:
            for item in items:
                if item["id"] in done:
                    continue
                rec = {"id": item["id"], "url": scrub(item["url"])}
                for label, _ in setups:
                    shot = os.path.join(out_dir, "shots", f'{item["id"]}-{label}.png')
                    fut = pool.submit(visit, drivers[label], item["url"], shot)
                    try:
                        rec[label] = fut.result(timeout=PAGE_TIMEOUT + 60)
                    except concurrent.futures.TimeoutError:
                        rec[label] = {"error": "timeout"}
                        try:
                            drivers[label].quit()
                        except Exception:
                            pass
                        pool = concurrent.futures.ThreadPoolExecutor(1)
                        drivers[label] = make_driver(binary, dict(setups)[label])
                    except Exception as e:
                        rec[label] = {"error": scrub(repr(e))[:300]}
                out.write(json.dumps(rec) + "\n")
                out.flush()
                print(item["id"], flush=True)
    finally:
        for d in drivers.values():
            try:
                d.quit()
            except Exception:
                pass


if __name__ == "__main__":
    main()
