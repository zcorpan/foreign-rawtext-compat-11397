"""Systematic PI round trips in Chrome Canary: PI shapes in different containers, parse, serialize, reparse. Payload-free; prints a table."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import driver
JS = r"""
const shapes = ['<?x>', '<?x ?>', '<?x?>', '<??>', '<?>', '<? x?>', '<?foo bar?>', '<?x y>?>d', '<?x\ny?>', '<?x/>', '<?xml version="1.0"?>', '<?x a="b" ?>', '<?x ??>', '<?x ???>', '<?X Y?>', '<?-x y?>', '<?1 y?>', '<?x:y z?>', '<?xé y?>', '<?x &amp; <b>?>', '<?x -->?>', '<?x ]]>?>', '<?x \u0000y?>', '<?x\ty?>', '<?x\ry?>', '<?x?', '<?x ?', '<?x  y  ?>', '<?marker name=m?>'];
const containers = {div: s => '<div>' + s + '</div>', svg: s => '<svg>' + s + '</svg>', math: s => '<math>' + s + '</math>', 'svg-title': s => '<svg><title>' + s + '</title></svg>', 'svg-style': s => '<svg><style>' + s + '</style></svg>', 'svg-script': s => '<svg><script>' + s + '</script></svg>', 'html-title': s => '<title>' + s + '</title>', 'html-style': s => '<style>' + s + '</style>', textarea: s => '<textarea>' + s + '</textarea>', select: s => '<select>' + s + '</select>', table: s => '<table>' + s + '</table>', tr: s => '<table><tr>' + s + '</tr></table>', template: s => '<template>' + s + '</template>', head: s => s, frameset: s => '<frameset>' + s + '</frameset>', p: s => '<p>' + s + '</p>'};
const desc = (n) => { const o = []; const w = (x) => { for (const c of x.childNodes) { if (c.nodeType === 7) o.push('PI(' + c.target + '|' + c.data + ')'); else if (c.nodeType === 8) o.push('C(' + c.data + ')'); else if (c.nodeType === 3) o.push('T(' + c.data + ')'); else { o.push(c.localName); if (c.content) w(c.content); w(c); } } }; w(n); return o.join(' '); };
const res = [];
for (const [cn, f] of Object.entries(containers)) for (const sh of shapes) {
  const d1 = new DOMParser().parseFromString(f(sh), 'text/html');
  const root1 = cn === 'head' ? d1 : d1.body;
  const S = d1.body.innerHTML + (cn === 'head' ? '' : '');
  const d2 = new DOMParser().parseFromString(cn === 'head' ? d1.documentElement.outerHTML : S, 'text/html');
  const a = desc(cn === 'head' ? d1.documentElement : d1.body), b = desc(cn === 'head' ? d2.documentElement : d2.body);
  const hasPI = a.includes('PI(');
  res.push({cn, sh, hasPI, same: a === b, a, b});
}
return res;
"""
d = driver.make("chrome")
rows = d.execute_script(JS)
driver.quit_quietly(d)
import collections
tab = collections.defaultdict(list)
for r in rows:
    if r["hasPI"] and not r["same"]: tab[r["cn"]].append(r["sh"])
nopi = collections.defaultdict(list)
for r in rows:
    if not r["hasPI"]: nopi[r["cn"]].append(r["sh"])
print("PI present in T1 but T1!=T2 (shape lists by container):")
for k, v in tab.items(): print(" ", k, len(v), "of", sum(1 for r in rows if r["cn"] == k and r["hasPI"]), v[:12])
print("containers where no PI node is created for a shape (PI text/comment instead):")
for k, v in nopi.items(): print(" ", k, len(v), "shapes")
json.dump(rows, open(os.path.join(HERE, "..", "private", "runs", "pi-roundtrip.json"), "w"))
