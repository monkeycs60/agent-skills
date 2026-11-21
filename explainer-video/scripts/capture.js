const fs = require('fs');
const path = require('path');
const { pathToFileURL } = require('url');
const { launch, sleep } = require('./cdp');

if (!process.argv[2]) { console.error('usage: node capture.js recipe.json   (format: references/capture.md)'); process.exit(2); }
const FILE = path.resolve(process.argv[2]);
const DIR = path.dirname(FILE);
const R = JSON.parse(fs.readFileSync(FILE, 'utf8'));
if (!R.url || !R.output) { console.error('FAILED the recipe must give "url" and "output"'); process.exit(2); }
const [VW, VH] = R.viewport || [1440, 900];
const DSF = R.dsf || 2;
const LOCAL = !/^[a-z][a-z0-9+.-]*:/i.test(R.url);
const PAGE_URL = LOCAL ? (() => { const [f, q] = R.url.split(/\?(.*)/s); return pathToFileURL(path.resolve(DIR, f)).href + (q ? '?' + q : ''); })() : R.url;
const OUTPUT = path.resolve(DIR, R.output);
const WAIT = R.wait !== undefined ? R.wait : (PAGE_URL.startsWith('file:') ? 0 : 1500);

const HELPERS = `
  const leaf = (re) => [...document.querySelectorAll('body *:not(script):not(style):not(svg *)')].find(e => e.children.length === 0 && re.test(e.textContent.trim()));
  const ancestorWithBg = (el, bg) => { while (el && getComputedStyle(el).backgroundColor !== bg) el = el.parentElement; return el; };
  const minWidth = (el, w) => { while (el && el.getBoundingClientRect().width < w) el = el.parentElement; return el; };
  const frame = (e) => { if (!e) return null; const b = e.getBoundingClientRect(); return { x: +b.x.toFixed(1), y: +b.y.toFixed(1), w: +b.width.toFixed(1), h: +b.height.toFixed(1) }; };
  const style = (e) => { if (!e) return null; const s = getComputedStyle(e); return { background: s.backgroundColor, color: s.color, border: s.borderColor,
    radius: s.borderRadius, font: s.fontFamily, weight: s.fontWeight, size: s.fontSize, shadow: s.boxShadow }; };`;
const DISMISS = (re) => `(() => {
  const re = new RegExp(${JSON.stringify(re)}, 'i');
  const b = [...document.querySelectorAll('button, [role=button], a')].find(x => x.offsetParent && re.test(x.innerText.trim()));
  if (b) { b.click(); return true; }
  return false; })()`;
const CLICK = (target) => `(() => {
  const c = ${JSON.stringify(target)};
  let el;
  if (c.startsWith('css:')) el = document.querySelector(c.slice(4));
  else { const re = c.startsWith('/') ? new RegExp(c.slice(1, c.lastIndexOf('/')), c.slice(c.lastIndexOf('/') + 1)) : null;
    el = [...document.querySelectorAll('button, a, [role=button], [role=menuitem], [role=tab], label')]
      .find(x => x.offsetParent && (re ? re.test(x.innerText.trim()) : x.innerText.trim() === c)); }
  if (!el) throw new Error('not found: ' + c);
  el.scrollIntoView({ block: 'center' }); el.click(); return true; })()`;
const STABLE = `(async () => { await document.fonts.ready; await Promise.all([...document.images].map(i => i.decode().catch(() => {}))); return true; })()`;

async function tidy(p) { if (!R.dismiss) return; for (let i = 0; i < 8; i++) { if (!(await p.js(DISMISS(R.dismiss)))) break; await sleep(600); } }

(async () => {
  const { tab: p, close } = await launch({ width: VW, height: VH });
  try {
    await p.size(VW, VH, DSF);
    await p.cmd('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-color-scheme', value: R.theme || 'light' }, { name: 'prefers-reduced-motion', value: 'reduce' }] });
    if (R.lang) await p.cmd('Emulation.setLocaleOverride', { locale: R.lang }).catch(() => {});
    if (R.cookies) { await p.cmd('Network.enable'); for (const c of R.cookies) await p.cmd('Network.setCookie', { path: '/', ...c }); }
    await p.goto(PAGE_URL);
    if (R.localStorage) {
      await p.js(`(() => { const o = ${JSON.stringify(R.localStorage)}; for (const k in o) localStorage.setItem(k, o[k]); })()`);
      await p.goto(PAGE_URL);
    }
    await p.js(STABLE); await sleep(WAIT); await tidy(p);
    for (const e of R.steps || []) {
      if (e.type) {
        await p.js(`(() => { const el = document.querySelector(${JSON.stringify(e.type.selector)}); if (!el) throw new Error('field not found: ' + ${JSON.stringify(e.type.selector)}); el.focus(); el.select && el.select(); })()`);
        await p.cmd('Input.insertText', { text: e.type.text });
      } else if (e.click) await p.js(CLICK(e.click));
      else if (e.waitFor) await p.waitFor(e.waitFor, 25000);
      else if (e.goto) await p.goto(e.goto);
      else if (e.pause) await sleep(e.pause);
      else if (e.hide) await p.js(`document.querySelectorAll(${JSON.stringify(e.hide)}).forEach(x => x.style.visibility = 'hidden')`);
      else if (e.js) await p.js(e.js);
      await sleep(e.pause ? 0 : 700); await tidy(p);
    }
    if ((R.steps || []).length) { await sleep(1200); await tidy(p); }
    await p.cmd('Input.dispatchMouseEvent', { type: 'mouseMoved', x: VW - 5, y: VH - 5 });
    await p.js(STABLE); await sleep(150);
    const boxes = {}, styles = {};
    for (const [k, expr] of Object.entries(R.boxes || {})) boxes[k] = await p.js(`(() => { ${HELPERS} return frame(${expr}); })()`);
    for (const [k, expr] of Object.entries(R.styles || {})) styles[k] = await p.js(`(() => { ${HELPERS} return style(${expr}); })()`);
    const empty = Object.keys(boxes).filter(k => !boxes[k]).concat(Object.keys(styles).filter(k => !styles[k]));
    fs.mkdirSync(path.dirname(OUTPUT), { recursive: true });
    await p.screenshot(OUTPUT);
    const meta = { url: await p.js('location.href'), viewport: [VW, VH], dsf: DSF, boxes, styles, capturedAt: new Date().toISOString() };
    fs.writeFileSync(OUTPUT.replace(/\.png$/i, '') + '.json', JSON.stringify(meta, null, 2));
    console.log('capture: ' + OUTPUT + '\n' + JSON.stringify({ boxes, styles }, null, 2));
    if (empty.length) console.warn('WARNING element not found for: ' + empty.join(', '));
  } finally { await close(); }
})().catch(e => { console.error('FAILED ' + e.message); process.exit(1); });
