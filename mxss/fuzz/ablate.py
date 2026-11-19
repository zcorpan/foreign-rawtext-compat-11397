"""For each minimized finding of the given labels, test whether it needs PI parsing or `template for` (Chrome):
replace `<?` by `<!` (bogus comment) and/or `for=` by `data-for=`, re-evaluate on the same path, and bucket by what is necessary.
Prints counts per (pair class, necessity) and distinct signatures; repros stay in private/.
usage: ablate.py LABEL... [--out private/runs/ablate.jsonl]"""
import collections, glob, json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import driver
RUNS = os.path.join(HERE, "..", "private", "runs")
JS = """
const sp = arguments[0]; const out = {};
const ok = (tokens) => { try { const r = FZ.evalSpec(Object.assign({}, sp, {tokens, keepAll: true})); return !r.discard && r.findings && r.findings.length > 0; } catch (e) { return false; } };
const t = sp.tokens.join('');
out.orig = ok([t]);
out.noPI = ok([t.replace(/<\\?/g, '<!')]);
out.noTF = ok([t.replace(/(<template[^>]*?\\s)for\\b/gi, '$1data-for')]);
out.noBoth = ok([t.replace(/<\\?/g, '<!').replace(/(<template[^>]*?\\s)for\\b/gi, '$1data-for')]);
out.hasPI = /<\\?/.test(t); out.hasTF = /<template[^>]*\\sfor\\b/i.test(t);
return out;
"""
labels = [a for a in sys.argv[1:] if not a.startswith("--")]
outp = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else os.path.join(RUNS, "ablate.jsonl")
d = driver.make("chrome", profile_root=os.path.join(HERE, "..", "private", "profiles", "ablate"))
seen = {}
for label in labels:
    for f in glob.glob(os.path.join(RUNS, label, "w*.jsonl")):
        for l in open(f):
            r = json.loads(l)
            if r["type"] == "finding" and (label, r["sig"]) not in seen:
                seen[(label, r["sig"])] = r
res = collections.Counter(); per = collections.defaultdict(set)
with open(outp, "w") as o:
    for (label, sig), r in seen.items():
        a = d.execute_script(JS, r["spec"])
        if not a["orig"]:
            nec = "not reproducible"
        elif not a["hasPI"] and not a["hasTF"]:
            nec = "neither token present"
        elif not a["noBoth"]:
            nec = "needs " + ("PI" if a["hasPI"] and a["noPI"] is False and not (a["hasTF"] and a["noTF"] is False) else "") + ("+" if a["noPI"] is False and a["noTF"] is False else "") + ("template-for" if a["noTF"] is False else "")
            if nec == "needs ":
                nec = "needs PI or template-for (jointly)"
        else:
            nec = "still works without PI and template-for"
        pc = sig.split(":")[0]
        res[(label, pc, nec)] += 1; per[nec].add(sig)
        o.write(json.dumps({"label": label, "sig": sig, "nec": nec, "a": a}) + "\n")
driver.quit_quietly(d)
for (label, pc, nec), n in sorted(res.items()):
    print(f"{label:20} {pc:10} {n:5}  {nec}")
