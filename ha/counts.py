"""Pages that parse differently per mode (full-page parses), excluding pages whose only
differences come from a truncated crawled body (an element left open at the end of a body that
doesn't end with </body> or </html>). usage: counts.py CLASSIFIED_FULL_DIR BODIES_DIR"""
import glob, json, os, re, sys

cdir, bdir = sys.argv[1:3]
complete = {}
for f in glob.glob(os.path.join(bdir, "*.json")):
    for r in json.load(open(f)):
        complete[r["page"]] = bool(re.search(r"</(?:html|body)\s*>", r["body"][-4000:], re.I))
for mode in ("rcdata", "rcdata-dc"):
    any_, text, trunc_only, unclosed = 0, 0, 0, 0
    for f in glob.glob(os.path.join(cdir, "*.jsonl")):
        for line in open(f):
            r = json.loads(line)
            if "error" in r:
                continue
            d = r["full"][mode]
            if not d:
                continue
            truncated = not complete.get(r["page"])
            real = [e for e in d if not ("unterminated" in e["why"] and truncated)]
            if not real:
                trunc_only += 1
                continue
            any_ += 1
            if any(not (mode == "rcdata-dc" and e.get("old_text") == e.get("new_text") and "unterminated" not in e["why"]) for e in real):
                text += 1
            if any("unterminated" in e["why"] for e in real):
                unclosed += 1
    print(f"{mode}: differ {any_} (text changes {text}, genuinely unclosed {unclosed}); truncated-body-only {trunc_only}")
