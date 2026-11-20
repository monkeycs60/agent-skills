const fs = require('fs');
const path = require('path');
const { execFile } = require('child_process');
const { trouverFfmpeg } = require('./outils');
if (!process.argv[2]) { console.error('usage : node kit.js <dossier-film> [lang]'); process.exit(2); }
const FILM = path.resolve(process.argv[2] || '.');
const LANG = process.argv[3] || 'fr';
const NOM = path.basename(FILM);
const OUT = path.join(FILM, 'out');
const FK = path.join(FILM, `youtube-${LANG}.json`);
if (!fs.existsSync(FK)) { console.error(`ECHEC ${FK} introuvable : copier modele/youtube-fr.json et le remplir (references/youtube.md)`); process.exit(1); }
const K = JSON.parse(fs.readFileSync(FK, 'utf8'));
const RESERVE = /^https?:\/\/([^/]+\.)?(example\.(com|org|net)|[^/]+\.(example|test|invalid))(\/|$)/i;
const LANGUE = (() => { try { return new Intl.DisplayNames(['fr'], { type: 'language' }).of(LANG); } catch (e) { return LANG; } })();
const JPG = `${NOM}-${LANG}-miniature.jpg`, PNG = `${NOM}-${LANG}-miniature.png`, MP4 = `${NOM}-${LANG}.mp4`;
const CH = fs.existsSync(path.join(FILM, 'charte.css')) ? fs.readFileSync(path.join(FILM, 'charte.css'), 'utf8') : '';
const NOM_PROJET = (CH.match(/--nom:\s*["']([^"']+)/) || [])[1] || '';
const LOGO = ((CH.match(/--logo-fonce:\s*url\(\s*["']?([^"')]+)/) || [])[1] || '').replace(/^(?=.)(?!https?:|data:|\/)/, '../');
const CHAINE = K.chaine || NOM_PROJET;
const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

(async () => {
  const C = [];
  const ok = (cond, texte, detail = '') => C.push({ ok: !!cond, texte, detail });
  const tl = [...K.titre].length;
  ok(tl <= 100, `Titre de ${tl} caractères`, 'YouTube coupe à 100. Idéal : 70 au plus, car les téléphones en affichent environ 60.');
  ok(tl <= 70, 'Titre lisible en entier sur ordinateur', tl > 60 ? 'Au-delà de 60 caractères, la fin peut être coupée sur téléphone.' : 'Entièrement visible sur téléphone aussi.');
  const dl = [...K.description].length;
  ok(dl <= 5000, `Description de ${dl} caractères`, 'Limite YouTube : 5 000.');
  const chap = K.description.split('\n').map(l => l.match(/^(\d{1,2}):(\d{2})\s+(.+)/)).filter(Boolean).map(m => ({ s: +m[1] * 60 + +m[2], t: m[3] }));
  const ecarts = chap.slice(1).map((c, i) => c.s - chap[i].s).concat(chap.length ? [K.duree - chap[chap.length - 1].s] : []);
  ok(chap.length >= 3 && chap[0].s === 0 && ecarts.every(e => e >= 10), `${chap.length} chapitres`,
     'YouTube exige : le premier à 00:00, au moins trois, chacun de 10 s au moins. Durées : ' + ecarts.map(e => Math.round(e) + ' s').join(', ') + '.');
  const tagsLen = K.tags.join(',').length;
  ok(tagsLen <= 500, `Tags : ${K.tags.length} tags, ${tagsLen} caractères`, 'Limite YouTube : 500 caractères au total.');
  const hashtags = (K.description.match(/#[\p{L}\p{N}_]+/gu) || []);
  ok(hashtags.length > 0 && hashtags.length <= 15, `${hashtags.length} hashtags`, 'Les trois premiers s’affichent au-dessus du titre. Au-delà de 15, YouTube les ignore tous.');
  const tout = K.titre + K.description + K.tags.join(' ');
  ok(!/[–—]/.test(tout), 'Aucun tiret cadratin ni demi-cadratin');
  const liens = K.description.match(/https?:\/\/\S+/g) || [];
  for (const u of liens) {
    if (RESERVE.test(u)) { ok(true, `Lien d'exemple non vérifié : ${u.replace(/^https?:\/\//, '')}`, 'Domaine réservé aux exemples : remplacer par la vraie doc avant publication.'); continue; }
    let code = 0;
    try { code = (await fetch(u, { method: 'GET', redirect: 'follow', signal: AbortSignal.timeout(10000) })).status; } catch (e) {}
    ok(code === 200, `Lien ${code || 'injoignable'} : ${u.replace(/^https?:\/\//, '')}`);
  }
  const fMp4 = path.join(OUT, MP4), ff = await trouverFfmpeg({ libx264: false });
  if (fs.existsSync(fMp4) && ff && ff.ffprobe) {
    const d = await new Promise(r => execFile(ff.ffprobe, ['-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', fMp4], (e, so) => r(e ? NaN : +so)));
    ok(Math.abs(d - K.duree) < 0.1, `Durée annoncée ${K.duree} s, vidéo de ${d.toFixed(2)} s`, 'Mettre « duree » du JSON à la durée réelle : les chapitres en dépendent.');
  }
  const fJpg = path.join(OUT, JPG), fPng = path.join(OUT, PNG);
  const existe = fs.existsSync(fJpg);
  ok(existe && fs.statSync(fJpg).size < 2 * 1024 * 1024, 'Miniature JPG sous 2 Mo', existe ? Math.round(fs.statSync(fJpg).size / 1024) + ' Ko' : 'introuvable : lancer render.js miniature');
  if (fs.existsSync(fPng)) { const b = fs.readFileSync(fPng); ok(b.readUInt32BE(16) === 1280 && b.readUInt32BE(20) === 720, `Miniature en ${b.readUInt32BE(16)} x ${b.readUInt32BE(20)}`, 'Format attendu par YouTube : 1280 x 720, 16:9.'); }
  const debut = [...K.description].slice(0, 150).join('');
  const dureeTxt = Math.floor(K.duree / 60) + ':' + String(Math.round(K.duree % 60)).padStart(2, '0');

  const carte = (w, cls) => `<div class="yt" style="width:${w}px"><div class="vig"><img src="${JPG}" alt=""><span class="duree">${dureeTxt}</span></div>
    <div class="yt-t ${cls}">${esc(K.titre)}</div><div class="yt-c">${esc(CHAINE)}</div></div>`;
  const html = `<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Kit YouTube, ${esc(K.film)}</title>
<link rel="stylesheet" href="../charte.css">
<style>
:root { --v:var(--brand); --lav:var(--tint); --g:var(--muted); }
* { box-sizing: border-box; } body { margin: 0; background: var(--bg); color: var(--ink); font: 400 16px/1.55 var(--font-body); }
.w { max-width: 1080px; margin: 0 auto; padding: 0 20px 80px; }
header { background: var(--v); color: #fff; padding: 34px 0 30px; margin-bottom: 26px; }
header .w { padding-bottom: 0; } header img { height: 30px; display: block; margin-bottom: 18px; }
h1 { font: 900 38px/1.1 var(--font-title); letter-spacing: -.03em; margin: 0; } header p { margin: 8px 0 0; color: var(--on-brand-soft); } header .nom { font: 900 30px var(--font-title); margin-bottom: 18px; }
h2 { font: 800 24px/1.2 var(--font-title); letter-spacing: -.02em; margin: 0 0 14px; }
.card { background: #fff; border: 1px solid var(--line); border-radius: 22px; padding: 24px; margin-bottom: 20px; box-shadow: 0 1px 2px rgba(30,20,60,.04), 0 14px 40px rgba(30,20,60,.06); }
.big { width: 100%; max-width: 760px; border-radius: 14px; display: block; box-shadow: 0 10px 30px rgba(30,20,60,.15); }
.row { display: flex; flex-wrap: wrap; gap: 22px; row-gap: 22px; align-items: flex-start; margin-top: 18px; }
.yt .vig { position: relative; } .yt img { width: 100%; display: block; border-radius: 10px; }
.duree { position: absolute; right: 6px; bottom: 6px; background: rgba(0,0,0,.8); color: #fff; font: 600 12px Arial, sans-serif; padding: 1px 5px; border-radius: 4px; }
.yt-t { font: 600 15px/1.3 Arial, sans-serif; margin-top: 8px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.yt-t.s { font-size: 13px; } .yt-c { font: 400 12.5px Arial, sans-serif; color: #606060; margin-top: 3px; }
.leg { font-size: 12.5px; color: var(--g); margin-top: 6px; }
.champ { background: var(--bg); border: 1px solid var(--line); border-radius: 14px; padding: 16px 18px; white-space: pre-wrap; word-break: break-word; font-size: 15.5px; }
.titre { font: 800 22px/1.3 var(--font-title); letter-spacing: -.01em; }
.bar { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; justify-content: space-between; margin-bottom: 10px; }
button { background: var(--v); color: #fff; border: 0; border-radius: 22px; padding: 9px 18px; font: 700 14px var(--font-body); cursor: pointer; }
button.fait { background: #00A63E; }
.cpt { font-size: 13px; color: var(--g); }
.pli { background: #FFF6D6; border-radius: 6px; }
.tags { display: flex; flex-wrap: wrap; gap: 8px; } .tag { background: var(--lav); color: var(--v); border-radius: 16px; padding: 4px 12px; font-size: 14px; font-weight: 600; }
table { width: 100%; border-collapse: collapse; font-size: 15px; } td { padding: 9px 8px; border-bottom: 1px solid var(--line); vertical-align: top; } tr:last-child td { border-bottom: 0; }
td:first-child { width: 34px; font-weight: 800; } .v { color: #00A63E; } .x { color: #E7000B; }
.fic code { background: var(--bg); padding: 2px 8px; border-radius: 6px; font-size: 13.5px; word-break: break-all; }
</style></head><body>
<header><div class="w">${LOGO ? `<img src="${esc(LOGO)}" alt="${esc(NOM_PROJET)}">` : `<div class="nom">${esc(NOM_PROJET)}</div>`}
<h1>Kit YouTube, ${esc(K.film)}</h1><p>Vidéo de ${dureeTxt}, ${esc(LANGUE)}. Tout est prêt à copier dans YouTube Studio.</p></div></header>
<div class="w">

<div class="card"><h2>Miniature</h2>
<img class="big" src="${JPG}" alt="Miniature">
<div class="leg">1280 x 720, fichier à téléverser : <b>${JPG}</b> (dans le même dossier que ce kit).</div>
<div class="row">
  <div>${carte(360, '')}<div class="leg">Résultats de recherche</div></div>
  <div>${carte(246, 's')}<div class="leg">Accueil, sur téléphone</div></div>
  <div>${carte(168, 's')}<div class="leg">Colonne « à suivre »</div></div>
</div></div>

<div class="card"><h2>Titre</h2>
<div class="bar"><span class="cpt">${tl} caractères sur 100</span><button data-c="titre">Copier le titre</button></div>
<div class="champ titre" id="titre">${esc(K.titre)}</div></div>

<div class="card"><h2>Description</h2>
<div class="bar"><span class="cpt">${dl} caractères sur 5 000. Surligné : ce qui s'affiche avant « plus ».</span><button data-c="desc">Copier la description</button></div>
<div class="champ" id="desc"><span class="pli">${esc(debut)}</span>${esc([...K.description].slice(150).join(''))}</div></div>

<div class="card"><h2>Tags</h2>
<div class="bar"><span class="cpt">${K.tags.length} tags, ${tagsLen} caractères sur 500</span><button data-c="tags">Copier les tags</button></div>
<div class="tags">${K.tags.map(t => `<span class="tag">${esc(t)}</span>`).join('')}</div>
<div id="tags" style="display:none">${esc(K.tags.join(', '))}</div></div>

<div class="card"><h2>Réglages dans YouTube Studio</h2><table>
${Object.entries(K.reglages || {}).map(([k, v]) => `<tr><td>•</td><td><b>${esc(k)}</b> : ${esc(v)}</td></tr>`).join('')}
</table></div>

<div class="card"><h2>Contrôles automatiques</h2><table>
${C.map(c => `<tr><td class="${c.ok ? 'v' : 'x'}">${c.ok ? '✓' : '✗'}</td><td><b>${esc(c.texte)}</b>${c.detail ? '<br><span class="cpt">' + esc(c.detail) + '</span>' : ''}</td></tr>`).join('')}
</table></div>

<div class="card fic"><h2>Fichiers</h2>
<p>Vidéo : <code>out/${MP4}</code><br>Miniature : <code>out/${JPG}</code></p></div>
</div>
<script>
document.querySelectorAll('button[data-c]').forEach(b => b.onclick = async () => {
  const txt = document.getElementById(b.dataset.c).textContent;
  try { await navigator.clipboard.writeText(txt); }
  catch (e) { const t = document.createElement('textarea'); t.value = txt; document.body.appendChild(t); t.select(); document.execCommand('copy'); t.remove(); }
  const l = b.textContent; b.textContent = 'Copié'; b.classList.add('fait'); setTimeout(() => { b.textContent = l; b.classList.remove('fait'); }, 1600);
});
</script></body></html>`;
  const sortie = path.join(OUT, `kit-youtube-${LANG}.html`);
  fs.writeFileSync(sortie, html);
  console.log('kit : ' + sortie);
  C.forEach(c => console.log('  ' + (c.ok ? 'ok ' : 'KO ') + c.texte + (c.ok ? '' : '  ' + c.detail)));
  const ko = C.filter(c => !c.ok).length;
  console.log(ko ? `kit : ${ko} contrôle(s) en échec, à corriger avant publication` : 'kit : tous les contrôles sont au vert');
  if (ko) process.exitCode = 1;
})().catch(e => { console.error('ECHEC ' + e.message); process.exit(1); });
