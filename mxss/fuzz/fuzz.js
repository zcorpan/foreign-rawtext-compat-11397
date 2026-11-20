// In-page differential mXSS fuzzer (see README.md). Exposes window.FZ.
// Everything (generator, oracle, minimizer) runs here; the driver only starts batches.
(function () {
'use strict';
const NS = {h: 'http://www.w3.org/1999/xhtml', s: 'http://www.w3.org/2000/svg', m: 'http://www.w3.org/1998/Math/MathML'};
const NSKEY = new Map([[NS.h, 'h'], [NS.s, 's'], [NS.m, 'm']]);
const MARK = 'X7Q';
const LIVE = {img: ['onerror'], video: ['onerror'], audio: ['onerror'], source: ['onerror'], input: ['onerror'], link: ['onerror', 'onload'], svg: ['onload'], body: ['onload'], iframe: ['onload']};
const HD = document.implementation.createHTMLDocument(''); // scripting-disabled doc owning context elements

// ---------- PRNG ----------
function mulberry32(a) { return function () { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
function hash2(a, b) { let h = (2166136261 ^ a) >>> 0; h = Math.imul(h ^ (b >>> 0), 16777619); h ^= h >>> 15; h = Math.imul(h, 0x85ebca6b); h ^= h >>> 13; return h >>> 0; }
const R = (rng, a) => a[Math.floor(rng() * a.length)];
const chance = (rng, p) => rng() < p;

// ---------- vocab ----------
const FORMATTING = ['a', 'b', 'big', 'code', 'em', 'font', 'i', 'nobr', 's', 'small', 'strike', 'strong', 'tt', 'u'];
const TABLE = ['table', 'caption', 'colgroup', 'col', 'tbody', 'thead', 'tfoot', 'tr', 'td', 'th'];
const BLOCK = ['p', 'li', 'dd', 'dt', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'button', 'marquee', 'object', 'applet', 'div', 'ul', 'ol', 'dl', 'pre', 'listing', 'address', 'center', 'blockquote', 'span', 'label', 'details', 'summary', 'fieldset', 'article', 'menu', 'dir'];
const RAW = ['style', 'script', 'xmp', 'iframe', 'noembed', 'noframes', 'noscript', 'plaintext', 'textarea', 'title'];
const VOIDISH = ['br', 'hr', 'image', 'input', 'img', 'wbr', 'embed', 'area', 'base', 'link', 'meta', 'param', 'source', 'track', 'keygen', 'basefont', 'bgsound', 'frame'];
const MISC = ['form', 'select', 'option', 'optgroup', 'template', 'frameset', 'ruby', 'rb', 'rt', 'rtc', 'rp', 'html', 'head', 'body', 'plaintext', 'sub', 'sup', 'var', 'custom-el', 'x-foo', 'datalist', 'search'];
const FOREIGN = ['svg', 'math', 'mi', 'mo', 'mn', 'ms', 'mtext', 'mglyph', 'malignmark', 'annotation-xml', 'semantics', 'mrow', 'foreignObject', 'desc', 'title', 'g', 'path', 'circle', 'text', 'tspan', 'use', 'defs', 'symbol', 'a', 'switch'];
const NAMES_ALL = [...new Set([...FORMATTING, ...TABLE, ...BLOCK, ...RAW, ...VOIDISH, ...MISC, ...FOREIGN])];
const WEIGHTED = [];
for (const [list, w] of [[FORMATTING, 2], [TABLE, 3], [BLOCK, 2], [RAW, 5], [VOIDISH, 1], [MISC, 3], [FOREIGN, 8]]) for (const n of list) for (let i = 0; i < w; i++) WEIGHTED.push(n);
for (const n of ['svg', 'math', 'form', 'select', 'template', 'mtext', 'mglyph', 'annotation-xml', 'foreignObject', 'style', 'noscript', 'table', 'p', 'a']) for (let i = 0; i < 6; i++) WEIGHTED.push(n);
const ATTRS = ['is', 'encoding', 'definitionurl', 'xlink:href', 'color', 'face', 'size', 'class', 'id', 'title', 'style', 'href', 'src', 'data-x', 'xmlns', 'xmlns:xlink', 'name', 'type', 'value', 'alt', 'lang', 'viewBox', 'onload'];
const ATTR_VALS = ['', 'x', 'text/html', 'application/xhtml+xml', 'TEXT/HTML', 'a', '1', '&lt;', '&gt;', '&quot;', '&amp;', '&#34;', '&#x3c;', '<', '>', '<>', '</', '--', '<!--', '-->', ']]>', 'foo bar'];
const CLOSERS = ['style', 'title', 'textarea', 'xmp', 'iframe', 'noembed', 'noframes', 'noscript', 'script', 'plaintext', 'svg', 'math', 'template', 'select', 'table', 'p', 'a', 'mtext', 'annotation-xml', 'foreignObject', 'desc', 'form', 'div', 'span', 'option', 'td', 'tr', 'body', 'html'];
const CHARREFS = ['&lt;', '&gt;', '&amp;', '&quot;', '&apos;', '&#x3c;', '&#60;', '&#0;', '&#x80;', '&#xD800;', '&amp', '&notit;', '&NotAnEntity;', '&#x26;lt;', '&nbsp;', '&#10;', '&#13;', '&lt', '&#', '&#x', '&'];
const SPECIAL = ['\0', '\r', '\r\n', '\f', '\t', '\n', ' ', ' ', ' ', '�', '﻿', '\u0085'];
const WS = [' ', ' ', ' ', '\n', '\t', '\f', '\r', '  ', '/', ' /'];
const WORDS = ['a', 'foo', 'x', 'bar', 'hello', '1', '{}', 'a{b:c}', '/*', '*/', '"', "'", '`', '=', ';'];
const DOCTYPES = ['<!DOCTYPE html>', '<!doctype html>', '<!DOCTYPE>', '<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01//EN">', '<!DOCTYPE html SYSTEM "x">'];
const CMT_END = ['-->', '-->', '-->', '--!>', '--!>', '--->', '->', '-', '', '>', '--', '<!-->'];
const CMT_START = ['<!--', '<!--', '<!--', '<!-->', '<!--->', '<!-', '<!---', '<!- -'];

// ---------- payloads ----------
function payload(rng, avoid) {
  const cores = [`<img src=x onerror=${MARK}>`, `<img src=x onerror=${MARK}>`, `<img src=x onerror=${MARK}>`, `<img/src=x onerror="${MARK}">`, `<svg onload=${MARK}>`, `<script>${MARK}</script>`, `<iframe onload=${MARK}>`.replace('iframe', 'body')];
  for (let tries = 0; tries < 8; tries++) {
    const k = rng();
    let pre;
    if (k < 0.3) pre = '';
    else if (k < 0.55) pre = '</' + caseVar(rng, R(rng, CLOSERS)) + R(rng, ['>', '>', ' >', '/>', ' x>', '\n>']);
    else pre = R(rng, ['">', "'>", '>', '-->', '--!>', ']]>', '?>', '"/>', '"><', "'/><", '</', '</ ', '"\n>', '`>']);
    let core = R(rng, cores);
    if (chance(rng, 0.2)) core = '<' + R(rng, ['svg', 'math', 'form', 'select', 'table', 'p', 'b']) + '>' + core;
    const s = pre + core;
    if (!avoid || !s.includes(avoid)) return s;
  }
  return '<img src=x onerror=' + MARK + '>';
}
function caseVar(rng, n) {
  const r = rng();
  if (r < 0.82) return n;
  if (r < 0.9) return n.toUpperCase();
  let o = ''; for (const c of n) o += chance(rng, 0.5) ? c.toUpperCase() : c; return o;
}

// ---------- generator (flat token arrays; tokens are the mutation unit) ----------
function attrVal(rng, q) {
  const r = rng();
  if (r < 0.28) return payload(rng, q);
  if (r < 0.35) return ATTR_VALS[Math.floor(rng() * ATTR_VALS.length)] + payload(rng, q);
  return R(rng, ATTR_VALS);
}
function attrs(rng) {
  let s = ''; const n = chance(rng, 0.45) ? 0 : 1 + Math.floor(rng() * 2.4);
  for (let i = 0; i < n; i++) {
    const name = caseVar(rng, R(rng, ATTRS)); s += R(rng, WS.slice(0, 5));
    const r = rng();
    if (r < 0.1) s += name;
    else if (r < 0.15) s += name + '=' + R(rng, ['x', '1', 'text/html']);
    else if (r < 0.7) s += name + R(rng, ['=', ' = ', '=\n']) + '"' + attrVal(rng, '"') + '"';
    else s += name + '=' + "'" + attrVal(rng, "'") + "'";
  }
  return s;
}
function startTag(rng, name) {
  const r = rng();
  const nm = caseVar(rng, name);
  if (r < 0.03) return '<' + nm + attrs(rng); // unterminated
  const sc = chance(rng, 0.07) ? R(rng, ['/', ' /']) : '';
  return '<' + nm + attrs(rng) + sc + '>';
}
function endTag(rng, name) { return '</' + caseVar(rng, name) + R(rng, ['>', '>', '>', ' >', '\n>', ' x="y">', '/>']); }
function pickName(rng) { return R(rng, WEIGHTED); }
function carrier(rng, out) {
  const k = rng(); const pl = chance(rng, 0.8);
  const pay = () => payload(rng);
  if (k < 0.35) { out.push(R(rng, CMT_START)); if (pl) out.push(pay()); else out.push(R(rng, WORDS)); out.push(R(rng, CMT_END)); }
  else if (k < 0.5) { out.push('<?' + R(rng, ['x', 'php', 'xml', '']) + ' '); if (pl) out.push(pay()); out.push(R(rng, ['?>', '>', '?', ''])); }
  else if (k < 0.65) { out.push('<![CDATA['); if (pl) out.push(pay()); out.push(R(rng, [']]>', ']]>', ']]', '>', ''])); }
  else if (k < 0.8) { out.push(R(rng, ['<!', '<!x ', '</', '</ ', '</3', '<!ELEMENT ', '<![if ', '<!--[if IE]>', '</?'])); if (pl) out.push(pay()); out.push('>'); }
  else if (k < 0.9) { out.push(R(rng, DOCTYPES)); }
  else { out.push(R(rng, CMT_START)); out.push(R(rng, ['--', '<!--', '<!-', '<', '--!'])); if (pl) out.push(pay()); out.push(R(rng, CMT_END)); }
}
function textTok(rng) {
  const r = rng();
  if (r < 0.2) return payload(rng);
  if (r < 0.4) return R(rng, CHARREFS);
  if (r < 0.5) return R(rng, SPECIAL);
  if (r < 0.6) return '</' + R(rng, CLOSERS) + '>';
  return R(rng, WORDS);
}
function genNodes(rng, depth, out) {
  const n = 1 + Math.floor(rng() * 3.6);
  for (let i = 0; i < n; i++) genItem(rng, depth, out);
}
function genItem(rng, depth, out) {
  const r = rng();
  if (r < 0.5 && depth > 0) {
    const name = pickName(rng);
    out.push(startTag(rng, name));
    if (RAW.includes(name) && chance(rng, 0.5)) { out.push(textTok(rng)); if (chance(rng, 0.3)) carrier(rng, out); }
    if (!VOIDISH.includes(name) || chance(rng, 0.1)) genNodes(rng, depth - 1, out);
    if (chance(rng, 0.72)) out.push(endTag(rng, chance(rng, 0.85) ? name : pickName(rng)));
  } else if (r < 0.6) out.push(endTag(rng, pickName(rng)));
  else if (r < 0.78) carrier(rng, out);
  else out.push(textTok(rng));
}
function genGrammar(rng) {
  const out = [];
  if (chance(rng, 0.1)) out.push(R(rng, DOCTYPES));
  const top = 1 + Math.floor(rng() * 2.5);
  for (let i = 0; i < top; i++) genItem(rng, 3 + Math.floor(rng() * 2), out);
  return out;
}
function fragment(rng) { const o = []; if (chance(rng, 0.6)) genItem(rng, 1, o); else if (chance(rng, 0.5)) carrier(rng, o); else o.push(textTok(rng)); return o; }
function ensurePayload(rng, toks) {
  if (toks.some(t => t.includes(MARK))) return toks;
  const i = Math.floor(rng() * (toks.length + 1)); const o = [];
  if (chance(rng, 0.5)) carrier(rng, o); else o.push(payload(rng));
  if (!o.some(t => t.includes(MARK))) o.splice(1, 0, payload(rng));
  toks.splice(i, 0, ...o); return toks;
}
function mutate(rng, base, corpus, seeds) {
  let t = base.slice();
  const n = 1 + Math.floor(rng() * 3);
  for (let k = 0; k < n; k++) {
    const r = rng(); const i = Math.floor(rng() * (t.length + 1));
    if (r < 0.15 && t.length > 1) t.splice(Math.min(i, t.length - 1), 1);
    else if (r < 0.3 && t.length) { const j = Math.min(i, t.length - 1); t.splice(j, 0, t[j]); }
    else if (r < 0.42 && t.length > 1) { const a = Math.min(i, t.length - 1), b = Math.floor(rng() * t.length); [t[a], t[b]] = [t[b], t[a]]; }
    else if (r < 0.6 && corpus.length) { const o = R(rng, corpus); const a = Math.floor(rng() * o.length); t.splice(i, 0, ...o.slice(a, a + 1 + Math.floor(rng() * 4))); }
    else if (r < 0.7 && seeds.length) { const o = R(rng, seeds); const a = Math.floor(rng() * o.length); t.splice(i, 0, ...o.slice(a, a + 1 + Math.floor(rng() * 6))); }
    else if (r < 0.85) t.splice(i, 0, ...fragment(rng));
    else if (t.length) { const j = Math.min(i, t.length - 1); t.splice(j, 1, ...fragment(rng)); }
  }
  if (t.length > 120) t = t.slice(0, 120);
  return t;
}
// seed text -> tokens with canaries injected into attribute values, comments and text nodes
function seedTokens(rng, text) {
  const pieces = text.match(/<!--[\s\S]*?-->|<[^>]*>|[^<]+|</g) || [];
  const t = pieces.slice();
  const n = 1 + Math.floor(rng() * 2);
  for (let k = 0; k < n; k++) {
    const i = Math.floor(rng() * t.length); const p = t[i]; const r = rng();
    if (!p) continue;
    if (p[0] === '<' && p.length > 2 && p[1] !== '!' && p[1] !== '/' && p.endsWith('>') && r < 0.5) {
      t[i] = p.replace(/>$/, ` title="${payload(rng, '"')}">`);
    } else if (p.startsWith('<!--') && r < 0.8) {
      t[i] = '<!--' + payload(rng) + p.slice(4);
    } else if (p[0] !== '<') t[i] = p + payload(rng);
    else t.splice(i, 0, R(rng, ['<!--', '<?x ', '<![CDATA[']) + payload(rng) + R(rng, ['-->', '>', ']]>']));
  }
  return t;
}

// ---------- prune model ----------
function nsKey(e) { return NSKEY.get(e.namespaceURI) || 'o'; }
function genPrune(rng) {
  const useNs = chance(rng, 0.3), q = R(rng, [0.5, 0.7, 0.85, 0.95]);
  const pool = [];
  for (const n of NAMES_ALL) { if (useNs) { for (const k of ['h', 's', 'm']) pool.push(k + ':' + n); } else pool.push(n); }
  const names = pool.filter(n => chance(rng, q));
  for (const n of ['svg', 'math', 'style', 'title', 'p', 'a', 'b', 'div', 'span', 'img', 'table', 'form', 'mtext', 'mglyph']) if (chance(rng, 0.6)) names.push(useNs ? R(rng, ['h', 's', 'm']) + ':' + n : n);
  const attrs = chance(rng, 0.5) ? null : ATTRS.concat(['alt', 'src', 'width', 'height']).filter(() => chance(rng, 0.75));
  return {names, ns: useNs, attrs, mode: R(rng, ['drop', 'unwrap', 'unwrap']), comments: chance(rng, 0.5), pis: chance(rng, 0.4)};
}
function applyPrune(root, p) {
  const allowN = new Set(p.names), denyN = p.deny ? new Set(p.deny) : null, allowA = p.attrs ? new Set(p.attrs) : null;
  const proc = (parent) => {
    for (let c = parent.firstChild; c;) {
      const next = c.nextSibling;
      if (c.nodeType === 8) { if (!p.comments) parent.removeChild(c); }
      else if (c.nodeType === 7) { if (!p.pis) parent.removeChild(c); }
      else if (c.nodeType === 1) {
        const tc = (c.localName === 'template' && c.namespaceURI === NS.h && c.content) ? c.content : null;
        proc(c); if (tc) proc(tc);
        const key = p.ns ? nsKey(c) + ':' + c.localName : c.localName;
        if (denyN ? denyN.has(key) : !allowN.has(key)) {
          if (p.mode !== 'drop') { while (c.firstChild) parent.insertBefore(c.firstChild, c); if (tc) while (tc.firstChild) parent.insertBefore(tc.firstChild, c); }
          parent.removeChild(c);
        } else if (allowA) { for (const a of Array.from(c.attributes)) if (!allowA.has(a.name)) c.removeAttribute(a.name); }
      }
      c = next;
    }
  };
  proc(root);
}


// ---------- JS serializer (spec algorithm; options: escape < > in attributes, scripting flag) ----------
const VOID = new Set(['area', 'base', 'basefont', 'bgsound', 'br', 'col', 'embed', 'frame', 'hr', 'img', 'input', 'keygen', 'link', 'meta', 'param', 'source', 'track', 'wbr']);
const RAWTXT = new Set(['style', 'script', 'xmp', 'iframe', 'noembed', 'noframes', 'plaintext']);
let SEROPT = {angle: true, scripting: false};
function escText(t) { return t.replace(/&/g, '&amp;').replace(/\u00a0/g, '&nbsp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }
function escAttr(t) { t = t.replace(/&/g, '&amp;').replace(/\u00a0/g, '&nbsp;').replace(/"/g, '&quot;'); return SEROPT.angle ? t.replace(/</g, '&lt;').replace(/>/g, '&gt;') : t; }
function attrName(a) {
  const ns = a.namespaceURI;
  if (ns === null) return a.localName;
  if (ns === 'http://www.w3.org/XML/1998/namespace') return 'xml:' + a.localName;
  if (ns === 'http://www.w3.org/2000/xmlns/') return a.localName === 'xmlns' ? 'xmlns' : 'xmlns:' + a.localName;
  if (ns === 'http://www.w3.org/1999/xlink') return 'xlink:' + a.localName;
  return a.name;
}
function serKids(node, out) {
  const kids = (node.localName === 'template' && node.namespaceURI === NS.h && node.content) ? node.content : node;
  for (let c = kids.firstChild; c; c = c.nextSibling) serNode(c, out);
}
function serNode(n, out) {
  switch (n.nodeType) {
    case 1: {
      const name = n.namespaceURI === NS.h || n.namespaceURI === NS.s || n.namespaceURI === NS.m ? n.localName : n.tagName;
      out.push('<' + name);
      for (const a of n.attributes) out.push(' ' + attrName(a) + '="' + escAttr(a.value) + '"');
      out.push('>');
      if (n.namespaceURI === NS.h && VOID.has(n.localName)) return;
      serKids(n, out);
      out.push('</' + name + '>');
      return;
    }
    case 3: {
      const p = n.parentNode;
      if (p && p.nodeType === 1 && p.namespaceURI === NS.h && (RAWTXT.has(p.localName) || (p.localName === 'noscript' && SEROPT.scripting))) out.push(n.data);
      else out.push(escText(n.data));
      return;
    }
    case 8: out.push('<!--' + n.data + '-->'); return;
    case 7: out.push('<?' + n.target + ' ' + n.data + '>'); return;
    case 10: out.push('<!DOCTYPE ' + n.name + '>'); return;
  }
}
function jsSer(node) { const out = []; serKids(node, out); return out.join(''); }

// ---------- parse / serialize / scan ----------
function mkCtx(spec) {
  const [q, enc] = spec.split(';'); const [k, name] = q.split(':');
  const el = HD.createElementNS(NS[k], name);
  if (enc) el.setAttribute('encoding', enc);
  return el;
}
const WRAP = ['xmp', 'iframe', 'noembed', 'noframes', 'noscript', 'style', 'textarea', 'title', 'select', 'table', 'svg', 'math', 'template', 'plaintext'];
let parseIn = function (ctx, s) {
  if (ctx === 'u:doc') { const d = Document.parseHTMLUnsafe(s); return {root: d, pruneRoot: d.body, ser: () => d.body ? (SEROPT.js ? jsSer(d.body) : d.body.innerHTML) : ''}; }
  if (ctx === 'u:h:div') { const el = mkCtx('h:div'); el.setHTMLUnsafe(s); return {root: el, pruneRoot: el, ser: () => SEROPT.js ? jsSer(el) : el.innerHTML}; }
  if (ctx === 'dw') { const d = document.implementation.createHTMLDocument(''); d.open(); d.write(s); d.close(); return {root: d, pruneRoot: d.body, ser: () => d.body ? (SEROPT.js ? jsSer(d.body) : d.body.innerHTML) : ''}; }
  if (ctx.startsWith('w:')) {
    const nm = ctx.slice(2), el = mkCtx('h:div');
    el.innerHTML = '<' + nm + '>' + s + (nm === 'plaintext' ? '' : '</' + nm + '>');
    return {root: el, pruneRoot: el, ser: () => SEROPT.js ? jsSer(el) : el.innerHTML};
  }
  if (ctx === 'doc') {
    const d = new DOMParser().parseFromString(s, 'text/html');
    return {root: d, pruneRoot: d.body, ser: () => d.body ? (SEROPT.js ? jsSer(d.body) : d.body.innerHTML) : ''};
  }
  const el = mkCtx(ctx); el.innerHTML = s;
  const tpl = el.localName === 'template' && el.namespaceURI === NS.h;
  return {root: el, pruneRoot: tpl ? el.content : el, ser: () => SEROPT.js ? jsSer(el) : el.innerHTML};
};

function scan(root, names, live, pis) {
  const stack = [root];
  while (stack.length) {
    const n = stack.pop();
    if (names) { if (n.nodeType === 7) { names.set('#pi', (names.get('#pi') || 0) + 1); if (pis) pis.push(n.target + '\u0001' + n.data); } else if (n.nodeType === 8) names.set('#cmt', (names.get('#cmt') || 0) + 1); }
    if (n.nodeType === 1) {
      const key = nsKey(n) + ':' + n.localName;
      let isLive = false;
      if (n !== root && LIVE[n.localName]) for (let i = 0, a = n.attributes; i < a.length; i++) if (a[i].value.includes(MARK) && LIVE[n.localName].includes(a[i].name.toLowerCase())) isLive = true;
      if (!isLive && n !== root && n.localName === 'script' && /^\s*X7Q\d+\s*$/.test(n.textContent)) isLive = true;
      if (isLive) { if (live) live.push(n); } else if (names && n !== root) names.set(key, (names.get(key) || 0) + 1);
      if (n.localName === 'template' && n.namespaceURI === NS.h && n.content) stack.push(n.content);
    }
    for (let c = n.lastChild; c; c = c.previousSibling) stack.push(c);
  }
}
function diffNames(a, b) {
  const d = [];
  for (const [k, v] of a) { const w = b.get(k) || 0; if (v !== w) d.push((w > v ? '+' : '-') + k); }
  for (const [k, v] of b) if (!a.has(k)) d.push('+' + k);
  return d.sort();
}
function parentKey(n) { const p = n.parentNode; if (!p) return '^'; if (p.nodeType === 1) return nsKey(p) + ':' + p.localName; if (p.nodeType === 11) return 'frag'; return 'doc'; }
function carrierOf(root, id) {
  const re = new RegExp(id + '(?!\\d)');
  const stack = [root];
  while (stack.length) {
    const n = stack.pop();
    if (n.nodeType === 8 && re.test(n.data)) { const d = n.data; return {kind: d[0] === '?' ? 'pi' : d.startsWith('[CDATA[') ? 'cdata' : 'comment', el: n.parentNode}; }
    if (n.nodeType === 7 && re.test(n.data)) return {kind: 'pi', el: n.parentNode};
    if (n.nodeType === 3 && re.test(n.data)) return {kind: 'text', el: n.parentNode};
    if (n.nodeType === 1) {
      for (let i = 0, a = n.attributes; i < a.length; i++) if (re.test(a[i].value)) return {kind: 'attr', el: n};
      if (n.localName === 'template' && n.namespaceURI === NS.h && n.content) stack.push(n.content);
    }
    for (let c = n.lastChild; c; c = c.previousSibling) stack.push(c);
  }
  return {kind: 'none', el: null};
}
const KNOWN = new Set(NAMES_ALL.map(x => x.toLowerCase()).concat(['html', 'head', 'body', 'foreignobject', 'annotation-xml', 'mglyph', 'tbody', 'thead', 'tfoot', 'colgroup', 'font', 'image', 'frameset', 'frame', 'marquee', 'object', 'applet', 'ruby', 'rb', 'rtc', 'rp', 'rt', 'selectedcontent']));
function nm(l) { return KNOWN.has(l.toLowerCase()) ? l : (l.includes('-') ? 'custom' : 'other'); }
function elKey(n) { return n && n.nodeType === 1 ? nsKey(n) + ':' + nm(n.localName) : (n ? (n.nodeType === 11 ? 'frag' : 'doc') : '^'); }
function nsSet(root, local) { const m = new Set(); const st = [root]; while (st.length) { const n = st.pop(); if (n.nodeType === 1) { if (n.localName === local) m.add(nsKey(n)); if (n.localName === 'template' && n.namespaceURI === NS.h && n.content) st.push(n.content); } for (let c = n.lastChild; c; c = c.previousSibling) st.push(c); } return Array.from(m).sort().join(''); }
function piCause(root1, p2, root2) {
  const rest = p2.slice(); let cause = null; const st = [root1];
  while (st.length && !cause) { const n = st.pop();
    if (n.nodeType === 7) { const key = n.target + '\u0001' + n.data; const i = rest.indexOf(key); if (i >= 0) rest.splice(i, 1); else cause = 'lost/changed in ' + parentKey(n) + (/\?$/.test(n.data) ? ' (data ends with ?)' : '') + (n.target.toLowerCase() === 'marker' ? ' marker' : ''); }
    if (n.nodeType === 1 && n.localName === 'template' && n.namespaceURI === NS.h && n.content) st.push(n.content);
    for (let c = n.lastChild; c; c = c.previousSibling) st.push(c); }
  if (cause) return cause;
  const rest1 = []; const q = [root1]; { const tmp = []; scan(root1, new Map(), null, tmp); rest1.push(...tmp); }
  const s2 = [root2]; const used = rest1.slice();
  while (s2.length) { const n = s2.pop();
    if (n.nodeType === 7) { const key = n.target + '\u0001' + n.data; const i = used.indexOf(key); if (i >= 0) used.splice(i, 1); else return 'gained in ' + parentKey(n); }
    if (n.nodeType === 1 && n.localName === 'template' && n.namespaceURI === NS.h && n.content) s2.push(n.content);
    for (let c = n.lastChild; c; c = c.previousSibling) s2.push(c); }
  return 'other';
}
function lens(root) { const m = new Map(); scan(root, m, null); return m; }


// ---------- targeted generators (enumeration.md corners) ----------
const PIVOTS = ['<form>', '<math>', '<svg>', '<mtext>', '<mi>', '<mglyph>', '<malignmark>', '<annotation-xml encoding="text/html">', '<annotation-xml encoding="application/xhtml+xml">', '<foreignObject>', '<desc>', '<title>', '<table>', '<select>', '<template>', '<a>', '<p>', '<b>', '<noscript>', '<button>', '</form>', '</p>', '</table>', '</math>', '</svg>', '</mtext>', '</template>', '</b>', '</a>', '</select>'];
function genSelfClose(rng) {
  const out = [], BRK = ['textarea', 'xmp', 'iframe', 'noembed', 'noframes', 'plaintext'];
  const MID = ['<math>', '<svg>', '<foreignObject>', '<desc>', '<mtext>', '<mi>', '<annotation-xml encoding="text/html">', '<noscript>', '<title>', '<style>', '<script>', '<plaintext>', '<textarea>', '<xmp>', '<mglyph>', '<form>', '<table>', '<p>', '<a>', '<b>'];
  out.push(R(rng, ['<svg>', '<math>', '<svg>', '<math><mtext>', '<svg><foreignObject>', '<math><annotation-xml encoding="text/html">']));
  const n = 1 + Math.floor(rng() * 2);
  for (let i = 0; i < n; i++) out.push('<' + caseVar(rng, R(rng, BRK)) + R(rng, ['/>', ' />', ' x=y/>']));
  const m = Math.floor(rng() * 4);
  for (let i = 0; i < m; i++) out.push(R(rng, MID));
  const nm = R(rng, RAW);
  out.push('<' + nm + '>');
  if (chance(rng, 0.6)) out.push(R(rng, ['<plaintext>', '<xmp>', '<style>', '<textarea>', '<script>', '<!--', '<?x ', '<![CDATA[']));
  out.push('</' + caseVar(rng, nm) + '>' + payload(rng));
  if (chance(rng, 0.4)) out.push(R(rng, PIVOTS));
  return out;
}
function genTargeted(rng, force) {
  if (force === 'selfclose') return genSelfClose(rng);
  if (force === 'desync') return genDesync(rng);
  const out = []; const raw = R(rng, RAW);
  const k = rng();
  if (!force && k > 0.9) return genSelfClose(rng);
  if (!force && k > 0.82) return genDesync(rng);
  const nPiv = Math.floor(rng() * 4);
  for (let i = 0; i < nPiv; i++) out.push(R(rng, PIVOTS));
  if (chance(rng, 0.4)) out.push(R(rng, ['<svg>', '<math>', '<svg>']));
  if (k < 0.2) { // HTML script double escape
    out.push(startTag(rng, 'script')); out.push(R(rng, ['<!--', '<!--', '<!--->', '<!---->']));
    out.push(R(rng, ['<script>', '<SCRIPT >', '<script/>', '<script x>']));
    out.push(payload(rng)); if (chance(rng, 0.7)) out.push('</script>'); out.push(R(rng, ['-->', '', '--!>']));
    if (chance(rng, 0.6)) out.push('</script>');
  } else {
    out.push(startTag(rng, raw));
    const nk = 1 + Math.floor(rng() * 3);
    for (let i = 0; i < nk; i++) {
      const r = rng();
      const pl = '</' + caseVar(rng, raw) + R(rng, ['>', ' >', '/>', ' x>']) + (chance(rng, 0.7) ? payload(rng) : '');
      if (r < 0.3) out.push(R(rng, CMT_START), pl, R(rng, CMT_END));
      else if (r < 0.55) out.push('<?' + R(rng, ['x', 'php', 'xml', 'x ', '']) + ' ', pl, R(rng, ['?>', '>', '?>', '']));
      else if (r < 0.7) out.push('<![CDATA[', pl, R(rng, [']]>', ']]>', '']));
      else if (r < 0.8) out.push(R(rng, ['<!', '</', '<!x ']), pl, '>');
      else if (r < 0.9) out.push(startTag(rng, pickName(rng)), pl);
      else out.push(pl);
    }
    if (chance(rng, 0.7)) out.push(endTag(rng, chance(rng, 0.8) ? raw : pickName(rng)));
  }
  const tail = Math.floor(rng() * 3);
  for (let i = 0; i < tail; i++) out.push(R(rng, PIVOTS));
  if (chance(rng, 0.3)) genItem(rng, 1, out);
  return out;
}

// ---------- PI and `template for` generators (Chrome: PIs parse as nodes, template for patches) ----------
const PI_SHAPES = ['<?x>', '<?x ?>', '<?x?>', '<??>', '<?>', '<? x?>', '<?foo bar?>', '<?x y>?>d', '<?x\ny?>', '<?x/>', '<?xml version="1.0"?>', '<?x a="b" ?>', '<?x ??>', '<?x ???>', '<?X Y?>', '<?-x y?>', '<?1 y?>', '<?x:y z?>', '<?xé y?>', '<?x \u0000y?>'];
const MARK_NAMES = ['m', 'm', 'm', 'M', 'm ', 'a', 'x y'];
function piWithPayload(rng) {
  const P = () => payload(rng);
  const r = rng();
  if (r < 0.12) return '<?x ' + P() + '?>';
  if (r < 0.24) return '<?x ' + P() + '>';
  if (r < 0.34) return '<?x>' + P();
  if (r < 0.42) return '<?x ?>' + P();
  if (r < 0.5) return '<?' + P() + '?>';
  if (r < 0.58) return '<?x a="' + P() + '"?>';
  if (r < 0.66) return '<?x ?' + P() + '>';
  if (r < 0.74) return '<?x>' + R(rng, ['?>', '-->', ']]>']) + P();
  if (r < 0.82) return '<?' + R(rng, ['marker', 'start', 'end', 'x']) + ' name="' + P() + '"?>';
  if (r < 0.9) return '<?marker name=m ' + P() + '?>';
  return R(rng, PI_SHAPES) + P();
}
function markerPi(rng) {
  const nm = R(rng, MARK_NAMES), r = rng();
  const q = R(rng, ['"', "'", '']);
  const tgt = chance(rng, 0.85) ? 'marker' : R(rng, ['MARKER', 'Marker', 'start', 'end']);
  const body = tgt.toLowerCase() === 'end' ? '' : ' name=' + q + nm.trim() + q;
  return '<?' + tgt + body + R(rng, ['?>', '?>', '>', ' ?>']);
}
function rangeMarkers(rng) { return ['<?start name=m?>', R(rng, ['stuff', '<b>', '<!--x-->', payload(rng)]), R(rng, ['<?end?>', '<?end>', '<?start name=m?><?end?><?end?>', ''])]; }
function tfContent(rng, host, out) {
  const n = 1 + Math.floor(rng() * 3);
  for (let i = 0; i < n; i++) {
    const r = rng(), closer = '</' + caseVar(rng, host) + R(rng, ['>', ' >', '/>']);
    if (r < 0.2) out.push(R(rng, CMT_START), closer + (chance(rng, 0.8) ? payload(rng) : ''), R(rng, CMT_END));
    else if (r < 0.35) out.push(piWithPayload(rng));
    else if (r < 0.5) out.push(startTag(rng, pickName(rng)), chance(rng, 0.5) ? payload(rng) : 'x', endTag(rng, pickName(rng)));
    else if (r < 0.6) out.push(closer + payload(rng));
    else if (r < 0.7) out.push(startTag(rng, R(rng, RAW)), closer, payload(rng));
    else if (r < 0.78) out.push('<template for=m>', R(rng, ['x', '<b>']), '</template>');
    else if (r < 0.86) out.push('<template>', payload(rng), '</template>');
    else genItem(rng, 1, out);
  }
}
const TF_HOSTS = ['title', 'style', 'script', 'noscript', 'textarea', 'xmp', 'iframe', 'noembed', 'noframes', 'select', 'table', 'tr', 'tbody', 'colgroup', 'div', 'p', 'desc', 'foreignObject', 'mtext', 'annotation-xml', 'template', 'svg', 'math', 'option', 'plaintext', 'a', 'b'];
function genPiTf(rng) {
  const out = [];
  const nPiv = Math.floor(rng() * 3);
  for (let i = 0; i < nPiv; i++) out.push(R(rng, PIVOTS));
  const wrap = R(rng, ['', '', 'svg', 'math', 'svg', 'math']);
  if (wrap) out.push('<' + wrap + '>');
  const host = R(rng, TF_HOSTS);
  if (chance(rng, 0.7)) out.push(startTag(rng, host));
  const k = rng();
  if (k < 0.55) out.push(markerPi(rng));
  else if (k < 0.7) out.push(...rangeMarkers(rng));
  else if (k < 0.85) out.push(piWithPayload(rng));
  else out.push(R(rng, PI_SHAPES));
  if (chance(rng, 0.3)) out.push(piWithPayload(rng));
  if (chance(rng, 0.5)) out.push(endTag(rng, host));
  if (chance(rng, 0.4)) genItem(rng, 1, out);
  const nt = chance(rng, 0.1) ? 0 : 1 + Math.floor(rng() * 2.3);
  for (let t = 0; t < nt; t++) {
    const attrsx = R(rng, ['', '', ' shadowrootmode=open', ' id=t', ' x']);
    out.push('<template for=' + R(rng, ['"m"', 'm', "'m'", '"M"', '"m "', '""', 'm']) + attrsx + '>');
    tfContent(rng, host, out);
    if (chance(rng, 0.9)) out.push('</template>');
    if (t === 0 && chance(rng, 0.15)) out.push(markerPi(rng)); // marker after the template
  }
  if (chance(rng, 0.4)) out.push(payload(rng));
  return out;
}


// ---------- desync generator: formatting-list / reconstruction triggers around foreign RCDATA elements ----------
const DS_FMT = ['<b>', '<a>', '<i>', '<strong>', '<em>', '<font>', '<nobr>', '<u>', '<code>', '<s>', '<big>', '<small>', '<tt>', '<a href=x>', '<b><i>', '<a><b>', '<p><b>', '<p><a>', '<p><i><b>', '<b><p>', '<a><table>', '<table><b>', '<table><tr><td><b>', '<select><b>', '<template><b>', '<button><b>', '<li><b>', '<h1><b>', '<div><b>'];
const DS_CLOSE = ['</p>', '</b>', '</a>', '</i>', '</div>', '</table>', '</td>', '</select>', '</template>', '</li>', '</h1>', '</button>', '</nobr>', '<p>', '<br>', '</span>', ''];
const DS_IP = ['', '', '<foreignObject>', '<desc>', '<mtext>', '<mi>', '<annotation-xml encoding="text/html">', '<svg>', '<math>', '<svg><foreignObject>', '<math><mtext>', '<svg><desc>', '<svg><title>', '<g>', '<mrow>'];
function genDesync(rng) {
  const out = [];
  const nf = 1 + Math.floor(rng() * 2);
  for (let i = 0; i < nf; i++) { out.push(R(rng, DS_FMT)); if (chance(rng, 0.4)) out.push(R(rng, ['x', '<!--c-->', ''])); }
  if (chance(rng, 0.85)) out.push(R(rng, DS_CLOSE));
  if (chance(rng, 0.5)) out.push(R(rng, DS_IP));
  const raw = R(rng, ['title', 'title', 'style', 'script', 'noscript', 'title', 'textarea', 'xmp']);
  const nm = caseVar(rng, raw);
  out.push('<' + nm + R(rng, ['', '', ' id=t']) + '>');
  const k = Math.floor(rng() * 3);
  for (let i = 0; i < k; i++) out.push(R(rng, ['x', '<b>', '</b>', '<!--c-->', '&amp;', '<a>', '</p>', textTok(rng)]));
  out.push('</' + nm + R(rng, ['>', ' >', '/>', ' x>']));
  const tail = 1 + Math.floor(rng() * 3);
  for (let i = 0; i < tail; i++) {
    const r = rng();
    if (r < 0.35) out.push(R(rng, CMT_START), '</' + caseVar(rng, raw) + R(rng, ['>', ' >', '/>']) + (chance(rng, 0.7) ? payload(rng) : ''), R(rng, CMT_END));
    else if (r < 0.5) out.push(piWithPayload(rng));
    else if (r < 0.6) out.push('<![CDATA[', '</' + raw + '>' + payload(rng), ']]>');
    else if (r < 0.7) out.push(R(rng, ['<!', '</']), '</' + raw + '>' + payload(rng), '>');
    else if (r < 0.8) out.push(R(rng, DS_FMT));
    else if (r < 0.9) out.push(textTok(rng));
    else out.push(payload(rng));
  }
  return out;
}
const DESYNC_T1 = ['s:svg', 'm:math', 's:g', 'm:mrow', 's:foreignObject', 's:desc', 'm:mtext', 'm:annotation-xml;text/html', 'doc', 'doc', 'h:div', 'h:template', 'h:td', 'h:select', 's:title', 'm:mi'];

const DOMRAW = ['title', 'style', 'script', 'noscript', 'textarea', 'xmp', 'iframe', 'noembed', 'noframes', 'plaintext', 'svg', 'math', 'div'];
function genDom(rng) {
  const ns = R(rng, ['h', 's', 'm']), name = R(rng, DOMRAW), kids = [];
  const n = 1 + Math.floor(rng() * 3);
  for (let i = 0; i < n; i++) {
    const pre = chance(rng, 0.7) ? '</' + name + '>' : '';
    kids.push({k: R(rng, ['c', 'c', 'p', 't', 'e', 't', 'ec']), v: pre + payload(rng)});
  }
  return {ns, name, kids, wrap: R(rng, ['', '', 'svg', 'math'])};
}
function buildDom(d) {
  const root = HD.createElement('div');
  let top = root;
  if (d.wrap) { top = HD.createElementNS(NS[d.wrap === 'svg' ? 's' : 'm'], d.wrap); root.appendChild(top); }
  const el = HD.createElementNS(NS[d.ns], d.name); top.appendChild(el);
  for (const k of d.kids) {
    try {
      if (k.k === 'c') el.appendChild(HD.createComment(k.v));
      else if (k.k === 'p') el.appendChild(HD.createProcessingInstruction('x', k.v.replace(/\?>/g, '? >')));
      else if (k.k === 't') el.appendChild(HD.createTextNode(k.v));
      else if (k.k === 'e') { const b = HD.createElementNS(NS[d.ns], 'b'); b.appendChild(HD.createTextNode(k.v)); el.appendChild(b); }
      else { const b = HD.createElementNS(NS.h, 'b'); b.appendChild(HD.createComment(k.v)); el.appendChild(b); }
    } catch (e) { /* DOM rejected the node */ }
  }
  return {root, pruneRoot: root, ser: () => SEROPT.js ? jsSer(root) : root.innerHTML};
}
const RAWCTX_RE = /^[hsm]:(style|script|title|textarea|xmp|iframe|noembed|noframes|noscript|plaintext)$/;


// ---------- direct invariants (no round trip): foreign title/style/script/noscript hold only text/comment/PI (I1), comment/PI data never
// holds the element's end tag (I2), no foreign textarea/xmp/iframe/noembed/noframes/plaintext (I3)
const INV_RC = new Set(['title', 'style', 'script', 'noscript']);
const INV_BRK = new Set(['textarea', 'xmp', 'iframe', 'noembed', 'noframes', 'plaintext']);
let INV = {on: false, n: 0, keys: new Set()};
function invariants(root, tag, out) {
  const stack = [root];
  while (stack.length) {
    const n = stack.pop();
    if (n.nodeType === 1) {
      const k = nsKey(n);
      if (k === 's' || k === 'm') {
        const ln = n.localName.toLowerCase();
        if (INV_BRK.has(ln) && n !== root) out.add(tag + '|I3:' + k + ':' + ln);
        if (INV_RC.has(ln)) {
          const re = new RegExp('</' + ln + '[\\s/>]', 'i');
          for (let c = n.firstChild; c; c = c.nextSibling) {
            if (c.nodeType === 1) out.add(tag + '|I1:' + k + ':' + ln + ':element');
            else if ((c.nodeType === 8 || c.nodeType === 7) && re.test(c.data)) out.add(tag + '|I2:' + k + ':' + ln + ':' + (c.nodeType === 8 ? 'comment' : 'pi'));
          }
        }
      }
      if (n.localName === 'template' && n.namespaceURI === NS.h && n.content) stack.push(n.content);
    }
    for (let c = n.lastChild; c; c = c.previousSibling) stack.push(c);
  }
}
const parseIn0 = parseIn;
parseIn = function (ctx, s) {
  const r = parseIn0(ctx, s);
  if (INV.on) { INV.n++; try { invariants(r.root, (INV.n === 1 ? 'T1@' : 'T2@') + ctx, INV.keys); } catch (e) { /* ignore */ } }
  return r;
};

// ---------- oracle ----------
const DEFAULT_T1 = ['doc', 'doc', 'h:div', 'h:div', 's:svg', 'm:math', 'h:template', 'h:td', 'h:select', 'h:table', 's:style', 's:title', 's:script', 'm:style', 's:noscript', 's:textarea', 'h:style', 'h:title', 's:g', 'm:mrow', 's:foreignObject', 's:desc', 'm:mtext', 'm:annotation-xml;text/html'];
const DEFAULT_T2 = ['doc', 'h:div', 's:svg', 'm:math', 'h:template', 'h:table', 'h:tbody', 'h:tr', 'h:td', 'h:select', 's:foreignObject', 'm:mtext', 'm:annotation-xml;text/html', 's:title', 'h:body'].concat(['s:style', 's:title', 's:script', 'm:title', 's:noscript', 's:xmp', 's:textarea'], WRAP.map(w => 'w:' + w));
// Returns {discard} | {findings:[...], struct: key|null}
function evalSpec0(spec, wantAll) {
  SEROPT = spec.ser === 'legacy' ? {js: true, angle: false, scripting: false} : spec.ser === 'js' ? {js: true, angle: true, scripting: false} : {js: false};
  let t1;
  if (spec.dom) t1 = buildDom(spec.dom);
  else { const input = spec.tokens.join(''); if (input.length > 6000) return {discard: 1}; t1 = parseIn(spec.t1, input); }
  const live1 = []; scan(t1.root, null, live1);
  if (live1.length) return {discard: 1};
  if (spec.prune) {
    if (!t1.pruneRoot) return {discard: 1};
    applyPrune(t1.pruneRoot, spec.prune);
    scan(t1.root, null, live1); if (live1.length) return {discard: 1};
  }
  const S = t1.ser();
  if (S.length > 20000) return {discard: 1};
  if (!S.includes(MARK) && !spec.keepAll) return {noCanary: 1, S};
  let tfNote = null;
  if (spec.tokens && spec.tokens.length) { const inp = spec.tokens.join(''); const tin = (inp.match(/<template[^>]*\sfor\b/gi) || []).length; if (tin) { const q = t1.root.querySelectorAll ? t1.root.querySelectorAll('template[for]').length : 0; tfNote = tin > q ? 'patched' : 'unpatched'; } }
  const pis1 = []; const names1 = new Map(); scan(t1.root, names1, null, pis1);
  const res = {findings: [], struct: null, S, tfNote};
  const paths = spec.path ? [spec.path] : null;
  const t2list = paths ? [paths[0][0]] : (spec.t2 || []);
  let carrier = null;
  const HTMLISH = ['doc', 'h:div', 'h:body'];
  const mkFinding = (path, T2root, live, depth, Sx) => {
    let id = MARK + '0';
    for (let i = 0, a = live[0].attributes; i < a.length; i++) { const m = /X7Q\d+/.exec(a[i].value); if (m) id = m[0]; }
    { const m = /X7Q\d+/.exec(live[0].textContent); if (m && live[0].localName === 'script') id = m[0]; }
    carrier = carrierOf(t1.root, id);
    const last = path[path.length - 1];
    const pc = spec.dom ? 'dom' : RAWCTX_RE.test(spec.t1) ? 'rawctx' : (last === spec.t1 || (HTMLISH.includes(last) && HTMLISH.includes(spec.t1))) ? 'same' : (last.startsWith('w:') ? 'wrap' : /^[sm]:/.test(last) ? 'toForeign' : 'toHtml');
    const cname = carrier.el && carrier.el.nodeType === 1 ? carrier.el.localName : null; const cn = cname && nm(cname);
    const piv = cname ? cn + ':' + nsSet(t1.root, cname) + '>' + nsSet(T2root, cname) : '-';
    const sig = pc + ':' + carrier.kind + '@' + elKey(carrier.el) + '|' + piv + '';
    return {sig, depth, path, t1: spec.t1, S: Sx};
  };
  for (const c2 of t2list) {
    const t2 = parseIn(c2, S);
    const live = []; const n2 = new Map(); scan(t2.root, n2, live);
    if (live.length) { res.findings.push(mkFinding([c2], t2.root, live, 1, S)); if (!wantAll) return res; continue; }
    if (c2 === spec.t1 && !spec.prune && !spec.dom && res.struct === null) {
      const d = diffNames(names1, n2);
      if (d.length) res.struct = d.slice(0, 3).join(',');
      if (names1.get('#pi')) { const p2 = []; scan(t2.root, new Map(), null, p2); res.piCause = null; if (p2.slice().sort().join('\u0002') !== pis1.slice().sort().join('\u0002')) res.piCause = piCause(t1.root, p2, t2.root); const a = pis1.slice().sort().join('\u0002'), b = p2.sort().join('\u0002'); if (a !== b) res.piRT = pis1.length !== p2.length ? 'count ' + pis1.length + '>' + p2.length : 'data-changed'; }
    }
    const deep = paths ? paths[0].slice(1) : (spec.deep || []);
    if (deep.length) {
      let cur = t2, S2 = t2.ser(), prevS = S, ctxs = [c2];
      for (const c3 of deep) {
        if (S2 === prevS || S2.length > 20000) break;
        const t3 = parseIn(c3, S2); ctxs = ctxs.concat([c3]);
        const lv = []; scan(t3.root, null, lv);
        if (lv.length) { res.findings.push(mkFinding(ctxs, t3.root, lv, ctxs.length, S2)); break; }
        prevS = S2; S2 = t3.ser();
      }
      if (res.findings.length && !wantAll) return res;
    }
  }
  return res;
}

function evalSpec(spec, wantAll) {
  if (spec.invKind) spec = Object.assign({}, spec, {keepAll: true});
  INV = {on: true, n: 0, keys: new Set()};
  let r;
  try { r = evalSpec0(spec, wantAll); } finally { INV.on = false; }
  const keys = Array.from(INV.keys).sort();
  if (spec.invKind) {
    const want = spec.sig ? spec.sig.slice(4) : null;
    const k = want && INV.keys.has(want) ? want : keys[0];
    return {findings: k ? [{sig: 'inv:' + k, depth: 0, path: [spec.t1]}] : [], inv: keys};
  }
  r.inv = keys;
  return r;
}
// ---------- minimizer ----------
function ddmin(arr, test, deadline) {
  let n = 2, cur = arr.slice();
  while (cur.length >= 2) {
    if (Date.now() > deadline) break;
    const chunk = Math.ceil(cur.length / n); let reduced = false;
    for (let i = 0; i < cur.length; i += chunk) {
      const cand = cur.slice(0, i).concat(cur.slice(i + chunk));
      if (cand.length && test(cand)) { cur = cand; n = Math.max(n - 1, 2); reduced = true; break; }
    }
    if (!reduced) { if (n >= cur.length) break; n = Math.min(cur.length, n * 2); }
  }
  return cur;
}
function minimize(spec, timeMs) {
  const deadline = Date.now() + (timeMs || 20000);
  const base = Object.assign({}, spec, {keepAll: true});
  const target = spec.sig;
  const ok = (sp) => { try { const r = evalSpec(sp); return !r.discard && r.findings.length && r.findings[0].sig === target; } catch (e) { return false; } };
  if (!ok(base)) return {ok: false, spec};
  if (base.dom) { const kids = ddmin(base.dom.kids, (c) => ok(Object.assign({}, base, {dom: Object.assign({}, base.dom, {kids: c})})), deadline); const o = Object.assign({}, base, {dom: Object.assign({}, base.dom, {kids})}); return {ok: true, spec: o}; }
  let toks = ddmin(base.tokens, (c) => ok(Object.assign({}, base, {tokens: c})), deadline);
  // character level within the joined string
  let chars = Array.from(toks.join(''));
  chars = ddmin(chars, (c) => ok(Object.assign({}, base, {tokens: [c.join('')]})), deadline);
  const out = Object.assign({}, base, {tokens: [chars.join('')]});
  // shrink prune allowlist (names/attrs) greedily
  if (out.prune) {
    const names = ddmin(out.prune.names, (c) => ok(Object.assign({}, out, {prune: Object.assign({}, out.prune, {names: c})})), deadline);
    out.prune = Object.assign({}, out.prune, {names});
  }
  return {ok: true, spec: out, input: out.tokens[0]};
}

// ---------- driver entry ----------
function probeNoscript() { // does fragment parsing (innerHTML) treat noscript as scripting-disabled?
  const e = HD.createElement('div'); e.innerHTML = '<noscript><b>x</b></noscript>';
  return !(e.firstChild && e.firstChild.firstChild && e.firstChild.firstChild.nodeType === 1);
}
const state = {fragNoscriptBad: probeNoscript(), corpus: [], seeds: [], seedToks: [], structSeen: new Set(), cfg: null};
function pickT2(rng, cfg, t1) {
  if (!cfg.t2sample || cfg.t2.length <= cfg.t2sample) return cfg.t2;
  const pool = cfg.t2.filter(c => c !== t1), pick = [];
  while (pick.length < cfg.t2sample - 1 && pool.length) pick.push(pool.splice(Math.floor(rng() * pool.length), 1)[0]);
  return pick.concat([t1]);
}
function genSpec(rng, cfg) {
  let toks, kind;
  const r = rng();
  if (rng() < cfg.pDom) {
    const spec = {dom: genDom(rng), tokens: [], t1: 'dom', kind: 'dom', ser: cfg.ser};
    spec.t2 = pickT2(rng, cfg, 'dom');
    { let k = 0; const f = (v) => v.replace(/X7Q\d*/g, () => MARK + (k++)); for (const kd of spec.dom.kids) kd.v = f(kd.v); }
    if (chance(rng, cfg.pDeep)) spec.deep = [R(rng, spec.t2)];
    return spec;
  }
  if (state.seeds.length && r < cfg.pSeed) { kind = 'seed'; toks = seedTokens(rng, R(rng, state.seeds)); }
  else if (state.corpus.length > 20 && r < cfg.pSeed + cfg.pMutate) { kind = 'mutate'; toks = mutate(rng, R(rng, state.corpus), state.corpus, state.seedToks); }
  else if (!cfg.noPitf && rng() < cfg.pPitf) { kind = 'pitf'; toks = genPiTf(rng); }
  else if (cfg.tk || rng() < cfg.pTarget) { kind = 'target'; toks = genTargeted(rng, cfg.tk); }
  else { kind = 'grammar'; toks = genGrammar(rng); }
  if (cfg.noPitf) toks = toks.filter(t => !/<\?/.test(t) && !/<template[^>]*\sfor\b/i.test(t));
  if (kind !== 'grammar' && chance(rng, 0.5) && !toks.some(t => t.includes(MARK))) ensurePayload(rng, toks);
  if (kind === 'grammar' || kind === 'target' || kind === 'pitf') ensurePayload(rng, toks);
  { let k = 0; toks = toks.map(t => t.replace(/X7Q\d*/g, () => MARK + (k++))); }
  const spec = {tokens: toks, t1: (cfg.tk === 'desync' && chance(rng, 0.8)) ? R(rng, DESYNC_T1) : R(rng, cfg.t1), t2: cfg.t2, kind, ser: cfg.ser};
  if (cfg.t2sample && cfg.t2.length > cfg.t2sample) {
    const pool = cfg.t2.filter(c => c !== spec.t1), pick = [];
    while (pick.length < cfg.t2sample - 1 && pool.length) pick.push(pool.splice(Math.floor(rng() * pool.length), 1)[0]);
    spec.t2 = pick.concat([spec.t1]);
  }
  if (state.fragNoscriptBad && !cfg.allowNoscriptFrag && /noscript/i.test(toks.join(''))) { spec.t1 = 'doc'; spec.t2 = ['doc']; }
  if (chance(rng, cfg.pPrune)) spec.prune = genPrune(rng);
  const rd = rng();
  if (rd < cfg.pDeep) { const n = rd < cfg.pDeep / 3 ? 2 : 1; spec.deep = []; for (let i = 0; i < n; i++) spec.deep.push(R(rng, spec.t2)); }
  return spec;
}
const FZ = {
  gen(base, i) { return genGrammar(mulberry32(hash2(base, i))); },
  evalSpec, minimize, MARK, state, jsSer, invCheck(html, ctx) { const o = new Set(); const hd2 = document.implementation.createHTMLDocument(''); INV = {on: false, n: 0, keys: o}; const r = parseIn0(ctx, html); invariants(r.root, 'T1', o); return Array.from(o); }, setSer(o) { SEROPT = o; },
  getCorpus() { return state.corpus; },
  setCorpus(c, seen) { state.corpus = c; state.structSeen = new Set(seen || []); },
  getSeen() { return Array.from(state.structSeen).slice(0, 20000); },
  setSeeds(list) { state.seeds = list; state.seedToks = list.slice(0, 500).map(s => (s.match(/<!--[\s\S]*?-->|<[^>]*>|[^<]+|</g) || [])); },
  // opts: base, start, n, timeMs, skip (array of sigs not to sample), maxSamples
  run(opts) {
    const cfg0 = {t1: DEFAULT_T1, t2: DEFAULT_T2, pSeed: 0.15, pMutate: 0.35, pPrune: 0.25, pDeep: 0.3, t2sample: 8, pTarget: 0.25, pDom: 0.04, pPitf: 0, noPitf: false, t2extra: []}; const cfg = Object.assign(cfg0, opts.cfg || {}); if (cfg.t2extra.length) cfg.t2 = cfg.t2.concat(cfg.t2extra);
    if (!state.seeds.length) cfg.pSeed = 0;
    const skip = new Set(opts.skip || []);
    const st = {cases: 0, discard: 0, noCanary: 0, findingCases: 0, struct: {}, sigs: {}, t1: {}, depth: {}, kinds: {}, errors: 0};
    const samples = [];
    const t0 = Date.now();
    let i = opts.start;
    for (; i < opts.start + opts.n; i++) {
      if ((i & 15) === 0 && Date.now() - t0 > opts.timeMs) break;
      const rng = mulberry32(hash2(opts.base, i));
      let spec;
      try { spec = genSpec(rng, cfg); } catch (e) { st.errors++; st.lastError = 'gen ' + String(e).slice(0, 200); continue; }
      if (opts.stopAt === i) return {done: i - opts.start, stopSpec: spec, stats: st, samples, ms: Date.now() - t0};
      if (opts.trace) { const x = new XMLHttpRequest(); x.open('POST', opts.trace, false); try { x.send(String(i)); } catch (e) { /* ignore */ } }
      let r;
      try { r = evalSpec(spec); } catch (e) { st.errors++; st.lastError = String(e).slice(0, 200); continue; }
      st.cases++;
      st.kinds[spec.kind] = (st.kinds[spec.kind] || 0) + 1;
      if (r.inv && r.inv.length) {
        st.inv = st.inv || {};
        for (const k of r.inv) {
          st.inv[k] = (st.inv[k] || 0) + 1;
          if (!skip.has('inv:' + k) && samples.filter(x => x.sig === 'inv:' + k).length < 1) {
            const m = /^T2@(.*?)\|/.exec(k);
            samples.push({sig: 'inv:' + k, spec: Object.assign({}, spec, {invKind: true, sig: 'inv:' + k, path: m ? [m[1]] : undefined, t2: undefined, deep: undefined}), idx: i});
          }
        }
      }
      if (r.discard) { st.discard++; continue; }
      if (r.noCanary) { st.noCanary++; continue; }
      st.t1[spec.t1] = (st.t1[spec.t1] || 0) + 1;
      if (r.tfNote) { st.tf = st.tf || {}; st.tf[r.tfNote] = (st.tf[r.tfNote] || 0) + 1; }
      if (r.piCause && opts.piSamples) { st.piS = st.piS || {}; if (!st.piS[r.piCause]) st.piS[r.piCause] = {spec, k: r.piCause}; }
      if (r.piCause) { st.piCause = st.piCause || {}; const kk = r.piCause + ' | t1=' + spec.t1; st.piCause[kk] = (st.piCause[kk] || 0) + 1; }
      if (r.piRT) { st.piRT = st.piRT || {}; st.piRT[r.piRT] = (st.piRT[r.piRT] || 0) + 1; }
      if (r.struct) {
        st.struct[r.struct] = (st.struct[r.struct] || 0) + 1;
        if (!state.structSeen.has(r.struct) || (chance(rng, 0.02) && state.corpus.length < 3000)) {
          state.structSeen.add(r.struct);
          if (state.corpus.length < 3000) state.corpus.push(spec.tokens); else state.corpus[Math.floor(rng() * 3000)] = spec.tokens;
        }
      }
      if (r.findings.length) {
        st.findingCases++;
        const f = r.findings[0];
        st.sigs[f.sig] = (st.sigs[f.sig] || 0) + 1;
        st.depth[f.depth] = (st.depth[f.depth] || 0) + 1;
        { const pr = spec.t1 + '>' + f.path[0]; st.pairs = st.pairs || {}; st.pairs[pr] = (st.pairs[pr] || 0) + 1; }
        if (!skip.has(f.sig) && samples.filter(s => s.sig === f.sig).length < (opts.maxSamples || 2)) {
          samples.push({sig: f.sig, spec: Object.assign({}, spec, {path: f.path, sig: f.sig, t2: undefined, deep: undefined}), idx: i});
          if (state.corpus.length < 3000) state.corpus.push(spec.tokens);
        }
      }
    }
    return {done: i - opts.start, stats: st, samples, ms: Date.now() - t0};
  },
};
window.FZ = FZ;
})();
