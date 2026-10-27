# Shared by compare.py and recheck.py: launches the before/after browsers and visits a page the
# way the HTTP Archive crawl does (desktop 1366x768; mobile 360x640, DPR 3, mobile UA, touch).
import asyncio, difflib, functools, http.server, os, re, threading
from PIL import Image, ImageChops
import change

MEASURE_JS = """
() => ({
  url: location.href,
  contentType: document.contentType,
  title: document.title,
  text: (document.body ? document.body.innerText : document.documentElement ? document.documentElement.textContent : '').slice(0, 3000),
  scrollWidth: document.documentElement ? document.documentElement.scrollWidth : 0,
  scrollHeight: document.documentElement ? document.documentElement.scrollHeight : 0,
})
"""


URL_QUERY = re.compile(r'([a-z][a-z0-9+.-]*://[^\s?#"\'<>]+)[?#][^\s"\'<>]*', re.I)
CC_HOST = re.compile(r'\b(google|bing|yahoo|amazon|facebook)\.(?:co\.)?(?!com\b|net\b|org\b)[a-z]{2}\b')
ORIGIN = re.compile(r'[a-z][a-z0-9+.-]*://[^/?#\s]*', re.I)


def scrub(s):
    """Drop query strings and fragments from URLs (any scheme) and mask country-specific hosts:
    live loads put tracking IDs, tokens and location hints there, and run output gets published."""
    return CC_HOST.sub(r'\1.<cc>', URL_QUERY.sub(r'\1', s)) if isinstance(s, str) else s


def scrub_record(rec):
    """Call on each result before writing it, after the text ratios are computed: drops page text,
    titles and final URLs (geo-targeted content and geo redirects identify the tester) and cuts
    frame URLs to their origin."""
    for v in [rec] + [rec.get(t) for t in ('A', 'A2', 'B')]:
        if not isinstance(v, dict):
            continue
        for k in ('text', 'title', 'url'):
            v.pop(k, None)
        for fr in v.get('frames', []):
            fr.pop('text', None)
            fr.pop('title', None)
            m = ORIGIN.match(fr.get('url') or '')
            fr['url'] = m.group(0) if m else None
    return rec


async def launch(p, executable, setup):
    args = change.BEFORE_ARGS if setup == 'before' else change.AFTER_ARGS
    return await p.chromium.launch(executable_path=executable, args=args)


async def measure(frame):
    m = await frame.evaluate(MEASURE_JS)
    m['url'] = scrub(m['url'])
    if change.EXTRA_MEASURE_JS:
        m['extra'] = await frame.evaluate(change.EXTRA_MEASURE_JS)
    return m


async def visit(browser, url, client, setup, shot=None, wait=3000, full_page=True):
    mobile = client == 'mobile'
    major = browser.version.split('.')[0]
    ctx = await browser.new_context(
        viewport={'width': 360, 'height': 640} if mobile else {'width': 1366, 'height': 768},
        device_scale_factor=3 if mobile else 1, is_mobile=mobile, has_touch=mobile,
        user_agent=('Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) '
                    f'Chrome/{major}.0.0.0 Mobile Safari/537.36') if mobile else None,
        ignore_https_errors=True)
    for js in (change.INIT_JS, change.AFTER_INIT_JS if setup == 'after' else None):
        if js:
            await ctx.add_init_script(js)
    page = await ctx.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(scrub(str(e))[:300]))
    rec = {}
    try:
        resp = await page.goto(url, wait_until='load', timeout=30000)
        rec['status'] = resp.status if resp else None
        await page.wait_for_timeout(wait)
        if setup == 'after' and change.AFTER_LOAD_JS:
            await page.evaluate(change.AFTER_LOAD_JS)
            await page.wait_for_timeout(wait)
        rec.update(await measure(page))
        frames = []
        for fr in page.frames[1:20]:
            try:
                fm = await measure(fr)
                frames.append(fm | {'text': fm['text'][:200]})
            except Exception as e:
                frames.append({'url': scrub(fr.url), 'error': scrub(str(e))[:100]})
        rec['frames'] = frames
        if shot:
            await page.screenshot(path=shot, full_page=full_page, scale='css', timeout=20000)
            img = Image.open(shot)
            if img.height > 4000:
                img.crop((0, 0, img.width, 4000)).save(shot)
            rec['shot'] = shot
    except Exception as e:
        rec['error'] = scrub(str(e).splitlines()[0])[:300]
    rec['pageErrors'] = errors[:10]
    await ctx.close()
    return rec


async def guarded(coro, seconds=90):
    # page.evaluate and context.close have no timeout of their own; one hung page would stall the run.
    try:
        return await asyncio.wait_for(coro, seconds)
    except asyncio.TimeoutError:
        return {'error': f'visit timed out after {seconds}s', 'pageErrors': []}


def serve(directory):
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Quiet, directory=directory))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return f'http://127.0.0.1:{server.server_port}/'


def text_ratio(a, b):
    return round(difflib.SequenceMatcher(None, a.get('text', ''), b.get('text', '')).ratio(), 3)


def pixel_diff(a, b):
    """Fraction of pixels in the top 2000px that differ noticeably, or None without both shots."""
    try:
        ia, ib = Image.open(a).convert('RGB'), Image.open(b).convert('RGB')
    except Exception:
        return None
    w, h = min(ia.width, ib.width), min(ia.height, ib.height, 2000)
    if not w * h:
        return None
    hist = ImageChops.difference(ia.crop((0, 0, w, h)), ib.crop((0, 0, w, h))).convert('L').histogram()
    return round(sum(hist[17:]) / (w * h), 4)


def here(*parts):
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), *parts)
