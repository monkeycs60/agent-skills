const fs = require('fs');
const path = require('path');
const { execFile } = require('child_process');
const { findFfmpeg } = require('./tools');
if (!process.argv[2]) { console.error('usage: node kit.js <film-folder> [lang]'); process.exit(2); }
const FILM = path.resolve(process.argv[2] || '.');
const LANG = process.argv[3] || 'en';
const NAME = path.basename(FILM);
const OUT = path.join(FILM, 'out');
const FK = path.join(FILM, `youtube-${LANG}.json`);
if (!fs.existsSync(FK)) { console.error(`FAILED ${FK} not found: copy template/youtube-en.json and fill it in (references/youtube.md)`); process.exit(1); }
const K = JSON.parse(fs.readFileSync(FK, 'utf8'));
const RESERVED = /^https?:\/\/([^/]+\.)?(example\.(com|org|net)|[^/]+\.(example|test|invalid))(\/|$)/i;
const UI = LANG === 'fr' ? 'fr' : 'en';
const LANGUAGE = (() => { try { return new Intl.DisplayNames([UI], { type: 'language' }).of(LANG); } catch (e) { return LANG; } })();
const JPG = `${NAME}-${LANG}-thumbnail.jpg`, PNG = `${NAME}-${LANG}-thumbnail.png`, MP4 = `${NAME}-${LANG}.mp4`;
const CH = fs.existsSync(path.join(FILM, 'brand.css')) ? fs.readFileSync(path.join(FILM, 'brand.css'), 'utf8') : '';
const PROJECT_NAME = (CH.match(/--name:\s*["']([^"']+)/) || [])[1] || '';
const LOGO = ((CH.match(/--logo-dark:\s*url\(\s*["']?([^"')]+)/) || [])[1] || '').replace(/^(?=.)(?!https?:|data:|\/)/, '../');
const CHANNEL = K.channel || PROJECT_NAME;
const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const L = {
  en: {
    kit: 'YouTube kit', intro: (d, l) => `${d} video, ${l}. Everything is ready to paste into YouTube Studio.`,
    thumb: 'Thumbnail', thumbNote: (f) => `1280 x 720, file to upload: <b>${f}</b> (in the same folder as this kit).`,
    search: 'Search results', home: 'Home, on a phone', next: '“Up next” column',
    title: 'Title', titleCount: (n) => `${n} characters out of 100`, copyTitle: 'Copy title',
    desc: 'Description', descCount: (n) => `${n} characters out of 5,000. Highlighted: what shows before “more”.`, copyDesc: 'Copy description',
    tags: 'Tags', tagsCount: (n, c) => `${n} tags, ${c} characters out of 500`, copyTags: 'Copy tags',
    settings: 'Settings in YouTube Studio', checks: 'Automatic checks', files: 'Files', video: 'Video', copied: 'Copied', colon: ': '
  },
  fr: {
    kit: 'Kit YouTube', intro: (d, l) => `Vidéo de ${d}, ${l}. Tout est prêt à copier dans YouTube Studio.`,
    thumb: 'Miniature', thumbNote: (f) => `1280 x 720, fichier à téléverser : <b>${f}</b> (dans le même dossier que ce kit).`,
    search: 'Résultats de recherche', home: 'Accueil, sur téléphone', next: 'Colonne « à suivre »',
    title: 'Titre', titleCount: (n) => `${n} caractères sur 100`, copyTitle: 'Copier le titre',
    desc: 'Description', descCount: (n) => `${n} caractères sur 5 000. Surligné : ce qui s'affiche avant « plus ».`, copyDesc: 'Copier la description',
    tags: 'Tags', tagsCount: (n, c) => `${n} tags, ${c} caractères sur 500`, copyTags: 'Copier les tags',
    settings: 'Réglages dans YouTube Studio', checks: 'Contrôles automatiques', files: 'Fichiers', video: 'Vidéo', copied: 'Copié', colon: ' : '
  }
}[UI];

(async () => {
  const C = [];
  const ok = (cond, text, detail = '') => C.push({ ok: !!cond, text, detail });
  const tl = [...K.title].length;
  ok(tl <= 100, `Title of ${tl} characters`, 'YouTube cuts at 100. Ideal: 70 at most, since phones show about 60.');
  ok(tl <= 70, 'Title fully readable on desktop', tl > 60 ? 'Beyond 60 characters, the end may be cut on phones.' : 'Fully visible on phones too.');
  const dl = [...K.description].length;
  ok(dl <= 5000, `Description of ${dl} characters`, 'YouTube limit: 5,000.');
  const chap = K.description.split('\n').map(l => l.match(/^(\d{1,2}):(\d{2})\s+(.+)/)).filter(Boolean).map(m => ({ s: +m[1] * 60 + +m[2], t: m[3] }));
  const gaps = chap.slice(1).map((c, i) => c.s - chap[i].s).concat(chap.length ? [K.duration - chap[chap.length - 1].s] : []);
  ok(chap.length >= 3 && chap[0].s === 0 && gaps.every(e => e >= 10), `${chap.length} chapters`,
     'YouTube requires: the first at 00:00, at least three, each at least 10 s long. Lengths: ' + gaps.map(e => Math.round(e) + ' s').join(', ') + '.');
  const tagsLen = K.tags.join(',').length;
  ok(tagsLen <= 500, `Tags: ${K.tags.length} tags, ${tagsLen} characters`, 'YouTube limit: 500 characters in total.');
  const hashtags = (K.description.match(/#[\p{L}\p{N}_]+/gu) || []);
  ok(hashtags.length > 0 && hashtags.length <= 15, `${hashtags.length} hashtags`, 'The first three show above the title. Beyond 15, YouTube ignores them all.');
  const all = K.title + K.description + K.tags.join(' ');
  ok(!/[–—]/.test(all), 'No em dash or en dash');
  const links = K.description.match(/https?:\/\/\S+/g) || [];
  for (const u of links) {
    if (RESERVED.test(u)) { ok(true, `Example link not checked: ${u.replace(/^https?:\/\//, '')}`, 'Domain reserved for examples: replace it with the real docs before publishing.'); continue; }
    let code = 0;
    try { code = (await fetch(u, { method: 'GET', redirect: 'follow', signal: AbortSignal.timeout(10000) })).status; } catch (e) {}
    ok(code === 200, `Link ${code || 'unreachable'}: ${u.replace(/^https?:\/\//, '')}`);
  }
  const fMp4 = path.join(OUT, MP4), ff = await findFfmpeg({ libx264: false });
  if (fs.existsSync(fMp4) && ff && ff.ffprobe) {
    const d = await new Promise(r => execFile(ff.ffprobe, ['-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', fMp4], (e, so) => r(e ? NaN : +so)));
    ok(Math.abs(d - K.duration) < 0.1, `Stated duration ${K.duration} s, video of ${d.toFixed(2)} s`, 'Set "duration" in the JSON to the real duration: the chapters depend on it.');
  }
  const fJpg = path.join(OUT, JPG), fPng = path.join(OUT, PNG);
  const exists = fs.existsSync(fJpg);
  ok(exists && fs.statSync(fJpg).size < 2 * 1024 * 1024, 'Thumbnail JPG under 2 MB', exists ? Math.round(fs.statSync(fJpg).size / 1024) + ' KB' : 'not found: run render.js thumbnail');
  if (fs.existsSync(fPng)) { const b = fs.readFileSync(fPng); ok(b.readUInt32BE(16) === 1280 && b.readUInt32BE(20) === 720, `Thumbnail at ${b.readUInt32BE(16)} x ${b.readUInt32BE(20)}`, 'Format expected by YouTube: 1280 x 720, 16:9.'); }
  const start = [...K.description].slice(0, 150).join('');
  const durText = Math.floor(K.duration / 60) + ':' + String(Math.round(K.duration % 60)).padStart(2, '0');

  const card = (w, cls) => `<div class="yt" style="width:${w}px"><div class="vig"><img src="${JPG}" alt=""><span class="dur">${durText}</span></div>
    <div class="yt-t ${cls}">${esc(K.title)}</div><div class="yt-c">${esc(CHANNEL)}</div></div>`;
  const html = `<!doctype html><html lang="${UI}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>${L.kit}, ${esc(K.film)}</title>
<link rel="stylesheet" href="../brand.css">
<style>
:root { --v:var(--brand); --lav:var(--tint); --g:var(--muted); }
* { box-sizing: border-box; } body { margin: 0; background: var(--bg); color: var(--ink); font: 400 16px/1.55 var(--font-body); }
.w { max-width: 1080px; margin: 0 auto; padding: 0 20px 80px; }
header { background: var(--v); color: #fff; padding: 34px 0 30px; margin-bottom: 26px; }
header .w { padding-bottom: 0; } header img { height: 30px; display: block; margin-bottom: 18px; }
h1 { font: 900 38px/1.1 var(--font-title); letter-spacing: -.03em; margin: 0; } header p { margin: 8px 0 0; color: var(--on-brand-soft); } header .name { font: 900 30px var(--font-title); margin-bottom: 18px; }
h2 { font: 800 24px/1.2 var(--font-title); letter-spacing: -.02em; margin: 0 0 14px; }
.card { background: #fff; border: 1px solid var(--line); border-radius: 22px; padding: 24px; margin-bottom: 20px; box-shadow: 0 1px 2px rgba(30,20,60,.04), 0 14px 40px rgba(30,20,60,.06); }
.big { width: 100%; max-width: 760px; border-radius: 14px; display: block; box-shadow: 0 10px 30px rgba(30,20,60,.15); }
.row { display: flex; flex-wrap: wrap; gap: 22px; row-gap: 22px; align-items: flex-start; margin-top: 18px; }
.yt .vig { position: relative; } .yt img { width: 100%; display: block; border-radius: 10px; }
.dur { position: absolute; right: 6px; bottom: 6px; background: rgba(0,0,0,.8); color: #fff; font: 600 12px Arial, sans-serif; padding: 1px 5px; border-radius: 4px; }
.yt-t { font: 600 15px/1.3 Arial, sans-serif; margin-top: 8px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.yt-t.s { font-size: 13px; } .yt-c { font: 400 12.5px Arial, sans-serif; color: #606060; margin-top: 3px; }
.leg { font-size: 12.5px; color: var(--g); margin-top: 6px; }
.field { background: var(--bg); border: 1px solid var(--line); border-radius: 14px; padding: 16px 18px; white-space: pre-wrap; word-break: break-word; font-size: 15.5px; }
.title { font: 800 22px/1.3 var(--font-title); letter-spacing: -.01em; }
.bar { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; justify-content: space-between; margin-bottom: 10px; }
button { background: var(--v); color: #fff; border: 0; border-radius: 22px; padding: 9px 18px; font: 700 14px var(--font-body); cursor: pointer; }
button.done { background: #00A63E; }
.cpt { font-size: 13px; color: var(--g); }
.fold { background: #FFF6D6; border-radius: 6px; }
.tags { display: flex; flex-wrap: wrap; gap: 8px; } .tag { background: var(--lav); color: var(--v); border-radius: 16px; padding: 4px 12px; font-size: 14px; font-weight: 600; }
table { width: 100%; border-collapse: collapse; font-size: 15px; } td { padding: 9px 8px; border-bottom: 1px solid var(--line); vertical-align: top; } tr:last-child td { border-bottom: 0; }
td:first-child { width: 34px; font-weight: 800; } .v { color: #00A63E; } .x { color: #E7000B; }
.files code { background: var(--bg); padding: 2px 8px; border-radius: 6px; font-size: 13.5px; word-break: break-all; }
</style></head><body>
<header><div class="w">${LOGO ? `<img src="${esc(LOGO)}" alt="${esc(PROJECT_NAME)}">` : `<div class="name">${esc(PROJECT_NAME)}</div>`}
<h1>${L.kit}, ${esc(K.film)}</h1><p>${L.intro(durText, esc(LANGUAGE))}</p></div></header>
<div class="w">

<div class="card"><h2>${L.thumb}</h2>
<img class="big" src="${JPG}" alt="${L.thumb}">
<div class="leg">${L.thumbNote(JPG)}</div>
<div class="row">
  <div>${card(360, '')}<div class="leg">${L.search}</div></div>
  <div>${card(246, 's')}<div class="leg">${L.home}</div></div>
  <div>${card(168, 's')}<div class="leg">${L.next}</div></div>
</div></div>

<div class="card"><h2>${L.title}</h2>
<div class="bar"><span class="cpt">${L.titleCount(tl)}</span><button data-c="title">${L.copyTitle}</button></div>
<div class="field title" id="title">${esc(K.title)}</div></div>

<div class="card"><h2>${L.desc}</h2>
<div class="bar"><span class="cpt">${L.descCount(dl)}</span><button data-c="desc">${L.copyDesc}</button></div>
<div class="field" id="desc"><span class="fold">${esc(start)}</span>${esc([...K.description].slice(150).join(''))}</div></div>

<div class="card"><h2>${L.tags}</h2>
<div class="bar"><span class="cpt">${L.tagsCount(K.tags.length, tagsLen)}</span><button data-c="tags">${L.copyTags}</button></div>
<div class="tags">${K.tags.map(t => `<span class="tag">${esc(t)}</span>`).join('')}</div>
<div id="tags" style="display:none">${esc(K.tags.join(', '))}</div></div>

<div class="card"><h2>${L.settings}</h2><table>
${Object.entries(K.settings || {}).map(([k, v]) => `<tr><td>•</td><td><b>${esc(k)}</b>${L.colon}${esc(v)}</td></tr>`).join('')}
</table></div>

<div class="card"><h2>${L.checks}</h2><table>
${C.map(c => `<tr><td class="${c.ok ? 'v' : 'x'}">${c.ok ? '✓' : '✗'}</td><td><b>${esc(c.text)}</b>${c.detail ? '<br><span class="cpt">' + esc(c.detail) + '</span>' : ''}</td></tr>`).join('')}
</table></div>

<div class="card files"><h2>${L.files}</h2>
<p>${L.video}${L.colon}<code>out/${MP4}</code><br>${L.thumb}${L.colon}<code>out/${JPG}</code></p></div>
</div>
<script>
document.querySelectorAll('button[data-c]').forEach(b => b.onclick = async () => {
  const txt = document.getElementById(b.dataset.c).textContent;
  try { await navigator.clipboard.writeText(txt); }
  catch (e) { const t = document.createElement('textarea'); t.value = txt; document.body.appendChild(t); t.select(); document.execCommand('copy'); t.remove(); }
  const l = b.textContent; b.textContent = ${JSON.stringify(L.copied)}; b.classList.add('done'); setTimeout(() => { b.textContent = l; b.classList.remove('done'); }, 1600);
});
</script></body></html>`;
  const output = path.join(OUT, `youtube-kit-${LANG}.html`);
  fs.writeFileSync(output, html);
  console.log('kit: ' + output);
  C.forEach(c => console.log('  ' + (c.ok ? 'ok   ' : 'FAIL ') + c.text + (c.ok ? '' : '  ' + c.detail)));
  const failed = C.filter(c => !c.ok).length;
  console.log(failed ? `kit: ${failed} check(s) failed, fix before publishing` : 'kit: all checks passed');
  if (failed) process.exitCode = 1;
})().catch(e => { console.error('FAILED ' + e.message); process.exit(1); });
