"""Class-level description of `template for` findings (those that need patching): marker parent, kinds of patched children,
T1 ancestors' namespaces. Prints aggregates, no markup."""
import collections, glob, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import driver
RUNS = os.path.join(HERE, "..", "private", "runs")
JS = r"""
const sp = arguments[0]; const t = sp.tokens.join('');
const un = t.replace(/(<template[^>]*?\s)for\b/gi, '$1data-for');
const NSK = {'http://www.w3.org/1999/xhtml': 'h', 'http://www.w3.org/2000/svg': 's', 'http://www.w3.org/1998/Math/MathML': 'm'};
const k = (e) => (NSK[e.namespaceURI] || 'o') + ':' + e.localName;
const d = sp.t1 === 'doc' ? new DOMParser().parseFromString(un, 'text/html') : null;
let root = d ? d : null; let el = null;
if (!d) { const [q] = sp.t1.split(';'); const [ns, nm] = q.split(':'); el = document.createElementNS({h: 'http://www.w3.org/1999/xhtml', s: 'http://www.w3.org/2000/svg', m: 'http://www.w3.org/1998/Math/MathML'}[ns], nm); el.innerHTML = un; root = el; }
const out = {markers: [], tpl: []};
const walk = (n) => { for (const c of n.childNodes) { if (c.nodeType === 7 && /^(marker|start)$/i.test(c.target)) out.markers.push(k(c.parentNode.nodeType === 1 ? c.parentNode : {namespaceURI: '', localName: 'frag'})); if (c.nodeType === 1) { if (c.localName === 'template' && c.content && c.hasAttribute('data-for')) out.tpl.push([...c.content.childNodes].map(x => x.nodeType === 1 ? k(x) : '#' + x.nodeType).join(' ')); walk(c); if (c.content) walk(c.content); } } };
walk(root);
return out;
"""
d = driver.make("chrome", profile_root=os.path.join(HERE, "..", "private", "profiles", "tfclass"))
nec = {}
for l in open(os.path.join(RUNS, "ablate.jsonl")):
    r = json.loads(l)
    if r["nec"].startswith("needs") and "template" in r["nec"]: nec[(r["label"], r["sig"])] = r
mp = collections.Counter(); kinds = collections.Counter(); n = 0
for (label, sig), a in nec.items():
    for f in glob.glob(os.path.join(RUNS, label, "w*.jsonl")):
        done = False
        for l in open(f):
            if '"type": "finding"' in l:
                r = json.loads(l)
                if r["sig"] == sig:
                    o = d.execute_script(JS, r["spec"]); n += 1
                    for m in set(o["markers"]): mp[m] += 1
                    for t in o["tpl"]:
                        for x in set(t.split()): kinds[x] += 1
                    done = True; break
        if done: break
driver.quit_quietly(d)
print("findings analysed:", n)
print("marker parent (ns:name):", dict(mp.most_common()))
print("kinds of nodes in template content (per finding):", dict(kinds.most_common(25)))
