"""Known-bypass calibration: evaluate every seed in mxss/private/seeds.jsonl with the oracle.

usage: calibrate.py --engine firefox --binary B --mode M --label L
Canary substitution: handler values (alert(...), xss(), 1) become the marker; seeds without a
handler get one on their `img`/`script`. Seeds that are structural-only (no script payload) are
flagged when the T1->T2 element multiset differs in the same context ("struct").
Writes mxss/private/runs/calibration-LABEL.jsonl (per seed: class, flagged, via) and prints a
class-level table (no markup).
"""
import argparse, json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import driver

PRIV = os.path.join(HERE, "..", "private")


def canary(html):
    h = re.sub(r"alert\([^)]*\)|xss\(\)|(?<=onerror=)1\b", "X7Q0", html)
    if "X7Q0" not in h:
        h = re.sub(r"<script>[^<]*</script>", "<script>X7Q0</script>", h)
    if "X7Q0" not in h:
        h = re.sub(r"<img([^>]*?)>", lambda m: "<img%s onerror=X7Q0>" % m.group(1), h, count=1)
    return h


JS = """
const html = arguments[0]; const out = {flag: null, struct: null};
const T2 = ['doc','h:div','s:svg','m:math','h:template','h:table','h:tbody','h:tr','h:td','h:select','s:foreignObject','m:mtext','m:annotation-xml;text/html','s:title','h:body'].concat(['xmp','iframe','noembed','noframes','noscript','style','textarea','title','select','table','svg','math','template','plaintext'].map(w => 'w:' + w));
const NS = false;  // calibration lifts the noscript restriction (pre-#9426 scripting differential)
const names = [...new Set((html.match(/<\\/?[a-zA-Z][a-zA-Z0-9-]*/g) || []).map(x => x.replace(/^<\\/?/, '').toLowerCase()))];
const stripped = html.replace(/^\\s*<(svg|math)[^>]*>/i, '').replace(/<\\/(svg|math)>\\s*$/i, '');
const inputs = [html, '<p>' + html]; if (stripped !== html) inputs.push(stripped);
const prunes = [null]; for (const n of names) for (const mode of ['unwrap', 'drop']) prunes.push({deny: [n], names: [], ns: false, attrs: null, mode, comments: true});
for (const inp of inputs) for (const t1 of (NS ? ['doc'] : ['doc','h:div','h:template','h:td','h:select','s:svg','m:math'])) {
  if (inp === stripped && stripped !== html && !/^[sm]:/.test(t1)) continue;
  if (inp === '<p>' + html && t1 !== 'doc') continue;
  for (const ser of [undefined, 'legacy']) for (const prune of prunes) for (const deep of [[], ['h:div'], ['doc']]) {
    const spec = {tokens:[inp], t1, t2: NS ? ['doc'] : T2, deep: NS ? deep.map(()=>'doc') : deep, keepAll: true, prune, ser};
    const r = FZ.evalSpec(spec, false);
    if (r.findings && r.findings.length) { out.flag = {ser: ser || 'native', t1, depth: r.findings[0].depth, prune: prune ? prune.mode + ':' + prune.deny[0] : null, sig: r.findings[0].sig}; return out; }
    if (r.struct && !out.struct) out.struct = r.struct;
  }
}
return out;
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", default="firefox"); ap.add_argument("--binary"); ap.add_argument("--mode", default="0"); ap.add_argument("--label", required=True)
    ap.add_argument("--seeds", default=os.path.join(PRIV, "seeds.jsonl"))
    a = ap.parse_args()
    d = driver.make(a.engine, a.binary, a.mode)
    rows = []
    for i, l in enumerate(open(a.seeds)):
        x = json.loads(l)
        r = d.execute_script(JS, canary(x["html"]))
        rows.append({"i": i, "class": x["class"], "flagged": bool(r["flag"]), "struct": r["struct"] is not None, "via": r["flag"]})
    driver.quit_quietly(d)
    os.makedirs(os.path.join(PRIV, "runs"), exist_ok=True)
    with open(os.path.join(PRIV, "runs", "calibration-%s.jsonl" % a.label), "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    by = {}
    for r in rows:
        c = by.setdefault(r["class"], [0, 0, 0]); c[0] += 1; c[1] += r["flagged"]; c[2] += (r["struct"] and not r["flagged"])
    print("== %s (%s mode %s): flagged %d/%d" % (a.label, a.engine, a.mode, sum(r["flagged"] for r in rows), len(rows)))
    for k in sorted(by, key=lambda s: int(s[1:])):
        print("  %-4s flagged %d/%d (+%d struct-only)" % (k, by[k][1], by[k][0], by[k][2]))


main()
