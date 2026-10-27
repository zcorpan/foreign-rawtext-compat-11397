"""Compare today's parsing with the proposed foreign raw text parsing for every HTML response in
the given WARC files. Writes one JSON line per page that has an SVG/MathML element of interest,
plus one totals line per WARC.

usage: analyze_warc.py OUT_DIR WARC...
"""
import html as htmlmod
import json
import multiprocessing as mp
import os
import re
import signal
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

MAX_BYTES = 3_000_000
PRE_FOREIGN = re.compile(rb"<(?:svg|math)[\s>/]", re.I)
PRE_NAMES = re.compile(rb"<(?:style|script|title|textarea|xmp|iframe|noembed|noframes|noscript|plaintext)[\s>/]", re.I)
META_CHARSET = re.compile(rb"""<meta[^>]+charset\s*=\s*["']?([\w-]+)""", re.I)
SNIP = 400


class Timeout(Exception):
    pass


def _alarm(signum, frame):
    raise Timeout()


def decode(body, content_type):
    cs = None
    m = re.search(r"charset=([\w-]+)", content_type or "", re.I)
    if m:
        cs = m.group(1)
    else:
        m = META_CHARSET.search(body[:4096])
        if m:
            cs = m.group(1).decode("ascii", "replace")
    for enc in (cs, "utf-8"):
        if not enc:
            continue
        try:
            return body.decode(enc, "replace")
        except LookupError:
            pass
    return body.decode("utf-8", "replace")


def child_info(e):
    """Kinds of children, the child text content (text node children only), and textContent."""
    kinds = set()
    texts = []
    if e.text:
        texts.append(e.text)
        kinds.add("text")
    for k in e:
        kinds.add("element" if isinstance(k.tag, str) else "comment")
        if k.tail:
            texts.append(k.tail)
            kinds.add("text")
    all_text = "".join(t for t in e.itertext()) if e is not None else ""
    return sorted(kinds), "".join(texts), all_text


def child_tags(e):
    return [k.tag.split("}")[-1] if isinstance(k.tag, str) else "#comment" for k in e][:20]


def classify(old, new):
    """Per-element comparison. old/new are records from frparse.parse."""
    name = new["name"]
    out = {"name": name, "ns": new.get("ns"), "self_closing": new["self_closing"],
           "attrs": {k if isinstance(k, str) else k[1]: v[:200] for k, v in
                     (new["etree"].attrib.items() if new.get("etree") is not None else [])}}
    if new["self_closing"] or not new["switched"]:
        out["verdict"] = "same"
        out["why"] = ["self-closing"] if new["self_closing"] else ["not-switched"]
        return out
    okinds, otext, oall = child_info(old["etree"]) if old.get("etree") is not None else ([], "", "")
    nkinds, ntext, _ = child_info(new["etree"])
    why = []
    if new["open_at_eof"]:
        why.append("unterminated")
    if "element" in okinds:
        why.append("old-element-children")
    if "comment" in okinds:
        why.append("old-comment-children")
    if new["cdata_markers"]:
        why.append("cdata-markers")
    if otext != ntext:
        if name not in ("title", "textarea") and htmlmod.unescape(ntext) == otext:
            why.append("charrefs")
        elif not new["open_at_eof"] and okinds in ([], ["text"]):
            why.append("text-differs-other")
    if old["open_at_eof"] and not new["open_at_eof"]:
        why.append("old-open-at-eof")
    changed = otext != ntext or okinds not in ([], ["text"]) or new["open_at_eof"]
    out["verdict"] = "differs" if changed else "same"
    out["why"] = why
    out["old_kinds"] = okinds
    out["new_len"] = len(ntext)
    if changed:
        out["old_children"] = child_tags(old["etree"]) if old.get("etree") is not None else []
        out["old_text"] = otext[:SNIP]
        out["old_text_all"] = oall[:SNIP]
        out["new_text"] = ntext[:SNIP]
        out["new_text_tail"] = ntext[-200:] if len(ntext) > SNIP else ""
    return out


def same_record(a, b):
    def attrs(r):
        e = r.get("etree")
        return dict(e.attrib) if e is not None else None
    return a["name"] == b["name"] and a.get("ns") == b.get("ns") and attrs(a) == attrs(b)


def analyze(html):
    import frparse
    _, oldinfo = frparse.parse(html, "old")
    if not oldinfo["elements"]:
        return None
    res = {"n_old": len(oldinfo["elements"])}
    for mode in ("raw", "rcdata"):
        _, newinfo = frparse.parse(html, mode)
        res[mode] = compare(oldinfo["elements"], newinfo["elements"])
    return res


def compare(olds, news):
    els = []
    aligned = True
    for i, n in enumerate(news):
        if not aligned or i >= len(olds) or not same_record(olds[i], n):
            aligned = False
            els.append({"name": n["name"], "ns": n.get("ns"), "verdict": "unaligned",
                        "why": ["unterminated-earlier"] if any(e.get("verdict") == "differs" and "unterminated" in e["why"] for e in els) else ["unaligned"]})
            continue
        els.append(classify(olds[i], n))
    return {"n_new": len(news), "elements": els}


def work(item):
    url, ctype, body = item
    signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(60)
    try:
        html = decode(body, ctype)
        res = analyze(html)
        if res is None:
            return {"url": url, "status": "no-foreign-elements"}
        res["url"] = url
        res["status"] = "ok"
        return res
    except Timeout:
        return {"url": url, "status": "timeout"}
    except Exception as e:  # noqa
        return {"url": url, "status": "error", "error": repr(e)[:300]}
    finally:
        signal.alarm(0)


def records(path, totals):
    from warcio.archiveiterator import ArchiveIterator
    with open(path, "rb") as f:
        for rec in ArchiveIterator(f):
            if rec.rec_type != "response":
                continue
            ctype = rec.http_headers.get_header("Content-Type") if rec.http_headers else ""
            if not ctype or "html" not in ctype.lower():
                continue
            status = rec.http_headers.get_statuscode()
            if status != "200":
                continue
            totals["html"] += 1
            body = rec.content_stream().read(MAX_BYTES + 1)
            if len(body) > MAX_BYTES:
                totals["too_big"] += 1
                continue
            if not PRE_FOREIGN.search(body):
                continue
            totals["has_svg_or_math_tag"] += 1
            if not PRE_NAMES.search(body[PRE_FOREIGN.search(body).start():]):
                continue
            totals["prefiltered"] += 1
            yield rec.rec_headers.get_header("WARC-Target-URI"), ctype, body


def main():
    out_dir = sys.argv[1]
    os.makedirs(out_dir, exist_ok=True)
    nproc = int(os.environ.get("NPROC", "6"))
    for path in sys.argv[2:]:
        base = os.path.basename(path).replace(".warc.gz", "")
        out_path = os.path.join(out_dir, base + ".jsonl")
        if os.path.exists(out_path):
            continue
        totals = {"warc": base, "html": 0, "too_big": 0, "has_svg_or_math_tag": 0, "prefiltered": 0}
        tmp = out_path + ".part"
        with mp.Pool(nproc) as pool, open(tmp, "w") as out:
            for res in pool.imap_unordered(work, records(path, totals), chunksize=4):
                status = res["status"]
                totals[status] = totals.get(status, 0) + 1
                if status != "no-foreign-elements":
                    out.write(json.dumps(res) + "\n")
            out.write(json.dumps({"totals": totals}) + "\n")
        os.rename(tmp, out_path)
        print(json.dumps(totals), flush=True)


if __name__ == "__main__":
    main()
