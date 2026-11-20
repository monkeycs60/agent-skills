const fs = require('fs');
const path = require('path');
const { pathToFileURL } = require('url');
const { lancer, sleep } = require('./cdp');

if (!process.argv[2]) { console.error('usage : node capturer.js recette.json   (format : references/capture.md)'); process.exit(2); }
const FICHIER = path.resolve(process.argv[2]);
const DOSSIER = path.dirname(FICHIER);
const R = JSON.parse(fs.readFileSync(FICHIER, 'utf8'));
if (!R.url || !R.sortie) { console.error('ECHEC la recette doit donner "url" et "sortie"'); process.exit(2); }
const [VW, VH] = R.viewport || [1440, 900];
const DSF = R.dsf || 2;
const LOCAL = !/^[a-z][a-z0-9+.-]*:/i.test(R.url);
const URL_PAGE = LOCAL ? (() => { const [f, q] = R.url.split(/\?(.*)/s); return pathToFileURL(path.resolve(DOSSIER, f)).href + (q ? '?' + q : ''); })() : R.url;
const SORTIE = path.resolve(DOSSIER, R.sortie);
const ATTENTE = R.attente !== undefined ? R.attente : (URL_PAGE.startsWith('file:') ? 0 : 1500);

const AIDES = `
  const feuille = (re) => [...document.querySelectorAll('body *:not(script):not(style):not(svg *)')].find(e => e.children.length === 0 && re.test(e.textContent.trim()));
  const ancetreFond = (el, bg) => { while (el && getComputedStyle(el).backgroundColor !== bg) el = el.parentElement; return el; };
  const largeurMin = (el, w) => { while (el && el.getBoundingClientRect().width < w) el = el.parentElement; return el; };
  const cadre = (e) => { if (!e) return null; const b = e.getBoundingClientRect(); return { x: +b.x.toFixed(1), y: +b.y.toFixed(1), w: +b.width.toFixed(1), h: +b.height.toFixed(1) }; };
  const style = (e) => { if (!e) return null; const s = getComputedStyle(e); return { fond: s.backgroundColor, texte: s.color, bordure: s.borderColor,
    rayon: s.borderRadius, police: s.fontFamily, graisse: s.fontWeight, taille: s.fontSize, ombre: s.boxShadow }; };`;
const FERMER = (re) => `(() => {
  const re = new RegExp(${JSON.stringify(re)}, 'i');
  const b = [...document.querySelectorAll('button, [role=button], a')].find(x => x.offsetParent && re.test(x.innerText.trim()));
  if (b) { b.click(); return true; }
  return false; })()`;
const CLIQUER = (cible) => `(() => {
  const c = ${JSON.stringify(cible)};
  let el;
  if (c.startsWith('css:')) el = document.querySelector(c.slice(4));
  else { const re = c.startsWith('/') ? new RegExp(c.slice(1, c.lastIndexOf('/')), c.slice(c.lastIndexOf('/') + 1)) : null;
    el = [...document.querySelectorAll('button, a, [role=button], [role=menuitem], [role=tab], label')]
      .find(x => x.offsetParent && (re ? re.test(x.innerText.trim()) : x.innerText.trim() === c)); }
  if (!el) throw new Error('introuvable : ' + c);
  el.scrollIntoView({ block: 'center' }); el.click(); return true; })()`;
const STABLE = `(async () => { await document.fonts.ready; await Promise.all([...document.images].map(i => i.decode().catch(() => {}))); return true; })()`;

async function nettoyer(p) { if (!R.fermer) return; for (let i = 0; i < 8; i++) { if (!(await p.js(FERMER(R.fermer)))) break; await sleep(600); } }

(async () => {
  const { onglet: p, fermer } = await lancer({ largeur: VW, hauteur: VH });
  try {
    await p.taille(VW, VH, DSF);
    await p.cmd('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-color-scheme', value: R.theme || 'light' }, { name: 'prefers-reduced-motion', value: 'reduce' }] });
    if (R.lang) await p.cmd('Emulation.setLocaleOverride', { locale: R.lang }).catch(() => {});
    if (R.cookies) { await p.cmd('Network.enable'); for (const c of R.cookies) await p.cmd('Network.setCookie', { path: '/', ...c }); }
    await p.aller(URL_PAGE);
    if (R.localStorage) {
      await p.js(`(() => { const o = ${JSON.stringify(R.localStorage)}; for (const k in o) localStorage.setItem(k, o[k]); })()`);
      await p.aller(URL_PAGE);
    }
    await p.js(STABLE); await sleep(ATTENTE); await nettoyer(p);
    for (const e of R.etapes || []) {
      if (e.saisir) {
        await p.js(`(() => { const el = document.querySelector(${JSON.stringify(e.saisir.selecteur)}); if (!el) throw new Error('champ introuvable : ' + ${JSON.stringify(e.saisir.selecteur)}); el.focus(); el.select && el.select(); })()`);
        await p.cmd('Input.insertText', { text: e.saisir.texte });
      } else if (e.cliquer) await p.js(CLIQUER(e.cliquer));
      else if (e.attendre) await p.attendre(e.attendre, 25000);
      else if (e.aller) await p.aller(e.aller);
      else if (e.pause) await sleep(e.pause);
      else if (e.masquer) await p.js(`document.querySelectorAll(${JSON.stringify(e.masquer)}).forEach(x => x.style.visibility = 'hidden')`);
      else if (e.js) await p.js(e.js);
      await sleep(e.pause ? 0 : 700); await nettoyer(p);
    }
    if ((R.etapes || []).length) { await sleep(1200); await nettoyer(p); }
    await p.cmd('Input.dispatchMouseEvent', { type: 'mouseMoved', x: VW - 5, y: VH - 5 });
    await p.js(STABLE); await sleep(150);
    const boites = {}, styles = {};
    for (const [k, expr] of Object.entries(R.boites || {})) boites[k] = await p.js(`(() => { ${AIDES} return cadre(${expr}); })()`);
    for (const [k, expr] of Object.entries(R.styles || {})) styles[k] = await p.js(`(() => { ${AIDES} return style(${expr}); })()`);
    const vides = Object.keys(boites).filter(k => !boites[k]).concat(Object.keys(styles).filter(k => !styles[k]));
    fs.mkdirSync(path.dirname(SORTIE), { recursive: true });
    await p.photo(SORTIE);
    const meta = { url: await p.js('location.href'), viewport: [VW, VH], dsf: DSF, boites, styles, capture: new Date().toISOString() };
    fs.writeFileSync(SORTIE.replace(/\.png$/i, '') + '.json', JSON.stringify(meta, null, 2));
    console.log('capture : ' + SORTIE + '\n' + JSON.stringify({ boites, styles }, null, 2));
    if (vides.length) console.warn('ATTENTION élément introuvable pour : ' + vides.join(', '));
  } finally { await fermer(); }
})().catch(e => { console.error('ECHEC ' + e.message); process.exit(1); });
