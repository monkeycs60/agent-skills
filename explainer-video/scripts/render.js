const http = require('http');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { execFile } = require('child_process');
const { lancer, sleep } = require('./cdp');
const { trouverFfmpeg } = require('./outils');

const USAGE = `usage :
  node render.js <dossier-film> planche <t1,t2,...> [lang]
  node render.js <dossier-film> video [lang]
  node render.js <dossier-film> encoder [lang]
  node render.js <dossier-film> verifier [lang]
  node render.js <dossier-film> affiche <t> [lang]
  node render.js <dossier-film> miniature [lang]`;
const MODES = ['planche', 'video', 'encoder', 'verifier', 'affiche', 'miniature'];
if (process.argv.length < 4 || !MODES.includes(process.argv[3])) { console.error(USAGE); process.exit(2); }

const OUTILS = __dirname;
const FILM = path.resolve(process.argv[2]);
const MODE = process.argv[3];
const A4 = process.argv[4] || '', A5 = process.argv[5] || '';
const AVEC_INSTANTS = MODE === 'planche' || MODE === 'affiche';
const LANG = AVEC_INSTANTS ? (A5 || 'fr') : (A4 || 'fr');
const NOM = path.basename(FILM);
const TMP = path.resolve(process.env.FRAMES_DIR ? path.join(process.env.FRAMES_DIR, NOM + '-' + LANG) : path.join(os.tmpdir(), 'explainer-video-' + NOM + '-' + LANG));
const OUT = path.join(FILM, 'out');
const MP4 = `${NOM}-${LANG}.mp4`;
const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.png': 'image/png', '.jpg': 'image/jpeg',
  '.woff2': 'font/woff2', '.woff': 'font/woff', '.ttf': 'font/ttf', '.otf': 'font/otf', '.css': 'text/css', '.webp': 'image/webp',
  '.svg': 'image/svg+xml', '.json': 'application/json', '.mp4': 'video/mp4' };
const absents = new Set();
let BASE = '';
const secondes = (t0) => ((Date.now() - t0) / 1000).toFixed(1) + ' s';
const executer = (bin, args) => new Promise((ok, ko) => execFile(bin, args, { maxBuffer: 64 * 1024 * 1024 },
  (e, so, se) => e ? ko(new Error(path.basename(bin) + ' : ' + (se || e.message).trim().split('\n').slice(-3).join(' '))) : ok(so)));

function serveur() {
  return new Promise(ok => {
    const s = http.createServer((req, res) => {
      const u = new URL(req.url, 'http://x');
      if (req.method === 'POST' && u.pathname === '/save') {
        const flux = fs.createWriteStream(path.join(OUT, path.basename(u.searchParams.get('f') || 'sortie.bin')));
        req.pipe(flux); flux.on('finish', () => res.end('ok'));
        return;
      }
      let f;
      if (u.pathname.startsWith('/frames/')) f = path.join(TMP, path.basename(u.pathname));
      else if (u.pathname.startsWith('/_outils/')) f = path.join(OUTILS, path.basename(u.pathname));
      else f = path.join(FILM, decodeURIComponent(u.pathname));
      if (![FILM, TMP, OUTILS].some(r => f.startsWith(r))) { res.statusCode = 403; return res.end(); }
      fs.readFile(f, (e, d) => {
        if (e) {
          if (!u.pathname.startsWith('/frames/') && !/favicon/.test(u.pathname)) absents.add(decodeURIComponent(u.pathname));
          res.statusCode = 404; return res.end();
        }
        res.setHeader('Content-Type', TYPES[path.extname(f).toLowerCase()] || 'application/octet-stream');
        res.setHeader('Cache-Control', 'no-store');
        res.end(d);
      });
    });
    s.listen(0, '127.0.0.1', () => { BASE = 'http://127.0.0.1:' + s.address().port; ok(s); });
  });
}

let signale = false;
async function controlerChargement(p) {
  const r = await p.js(`({ images: [...document.images].filter(i => i.getAttribute('src') && !i.naturalWidth).map(i => i.getAttribute('src')),
    polices: [...document.fonts].filter(f => f.status === 'error').map(f => f.family) })`);
  if (signale) return;
  signale = true;
  const manque = [...new Set([...r.images, ...absents])];
  if (manque.length) console.warn('ATTENTION fichiers introuvables dans le film : ' + manque.join(', ') + (manque.some(m => /ecran-reel/.test(m)) ? ' (capture réelle à faire : capturer.js)' : ''));
  if (r.polices.length) console.warn('ATTENTION polices en échec : ' + [...new Set(r.polices)].join(', ') + ' (vérifier @font-face dans charte.css)');
}

async function ouvrirFilm(p) {
  await p.taille(1920, 1080, 1);
  await p.aller(`${BASE}/film.html?render&lang=${LANG}`);
  await p.attendre('window.READY && true');
  await p.js('window.READY');
  await controlerChargement(p);
}

async function photoA(p, t, fichier, qualite = 93) {
  await p.js(`window.seek(${t.toFixed(6)})`);
  await p.photo(fichier, { format: 'jpeg', quality: qualite });
}

async function planche(p, temps) {
  if (!temps.length || temps.some(t => !Number.isFinite(t))) throw new Error('instants invalides : ' + A4 + ' (exemple : 2,6.5,12)');
  fs.mkdirSync(TMP, { recursive: true });
  await ouvrirFilm(p);
  const noms = [];
  for (const t of temps) {
    const n = `still-${String(Math.round(t * 100)).padStart(5, '0')}.jpg`;
    await photoA(p, t, path.join(TMP, n), 90);
    noms.push([n, t]);
  }
  const cols = Math.min(4, noms.length), w = 470, h = Math.round(w * 9 / 16), rangs = Math.ceil(noms.length / cols);
  const html = `<body style="margin:0;background:#141418;font:600 15px sans-serif;color:#ddd">
    <div style="display:grid;grid-template-columns:repeat(${cols},${w}px);gap:10px;padding:10px">
    ${noms.map(([n, t]) => `<div><img src="/frames/${n}" style="width:${w}px;height:${h}px;display:block;border-radius:4px"><div style="padding:4px 2px">${t.toFixed(2)} s</div></div>`).join('')}
    </div></body>`;
  fs.writeFileSync(path.join(TMP, 'planche.html'), html);
  await p.taille(cols * (w + 10) + 10, rangs * (h + 34) + 14, 1);
  await p.aller(`${BASE}/frames/planche.html`);
  await p.js('Promise.all([...document.images].map(i => i.decode()))');
  await p.photo(path.join(OUT, `planche-${LANG}.png`));
  console.log(`planche : ${noms.length} images -> out/planche-${LANG}.png (pleine taille dans ${TMP})`);
}

const X264 = (fps) => ['-vf', 'colorspace=ispace=bt470bg:iprimaries=bt709:itrc=bt709:irange=pc:space=bt709:primaries=bt709:trc=bt709:range=tv:format=yuv420p',
  '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-tune', 'animation', '-g', String(fps * 2),
  '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709', '-color_range', 'tv', '-movflags', '+faststart', path.join(OUT, MP4)];

async function choisirEncodeur() {
  const choix = (process.env.ENCODEUR || '').toLowerCase();
  const ff = choix === 'chrome' ? null : await trouverFfmpeg();
  if (choix === 'ffmpeg' && !ff) throw new Error('ENCODEUR=ffmpeg mais ffmpeg avec libx264 est introuvable');
  return ff;
}

async function images(nav, p) {
  fs.rmSync(TMP, { recursive: true, force: true });
  fs.mkdirSync(TMP, { recursive: true });
  await ouvrirFilm(p);
  const dur = await p.js('window.DURATION'), fps = await p.js('window.FPS');
  const n = Math.round(dur * fps), t0 = Date.now();
  const voulu = +process.env.WORKERS || Math.max(1, Math.min(4, Math.floor(os.cpus().length / 2)));
  const onglets = [p];
  for (let k = 1; k < Math.min(voulu, n); k++) { const o = await nav.onglet({ isole: true }); await ouvrirFilm(o); onglets.push(o); }
  let suivant = 0, faites = 0, palier = 0;
  await Promise.all(onglets.map(async (o) => {
    for (let i = suivant++; i < n; i = suivant++) {
      await photoA(o, i / fps, path.join(TMP, `f${String(i).padStart(5, '0')}.jpg`));
      faites++;
      if (faites >= palier) { console.log(`  image ${faites}/${n}  (${secondes(t0)})`); palier += 600; }
    }
  }));
  console.log(`images : ${n} en ${secondes(t0)} (${onglets.length} onglets en parallèle)`);
  return fps;
}

async function encoderFfmpeg(ff, fps) {
  const t0 = Date.now();
  await executer(ff, ['-hide_banner', '-loglevel', 'error', '-y', '-framerate', String(fps), '-i', path.join(TMP, 'f%05d.jpg'), ...X264(fps)]);
  const mo = fs.statSync(path.join(OUT, MP4)).size / 1e6;
  console.log(`encodage : ffmpeg libx264 en ${secondes(t0)} -> out/${MP4} (${mo.toFixed(1)} Mo)`);
}

async function encoderChrome(p, fps) {
  const n = fs.readdirSync(TMP).filter(f => /^f\d{5}\.jpg$/.test(f)).length;
  const t0 = Date.now();
  await p.aller(`${BASE}/_outils/encoder.html?n=${n}&fps=${fps}&out=${MP4}`);
  const r = await p.js('window.ENCODE');
  if (!r.ok) throw new Error('encodage dans le navigateur en échec : ' + r.err + ' (installer ffmpeg, ou prendre Google Chrome)');
  console.log(`encodage : WebCodecs ${r.codec} en ${secondes(t0)} -> out/${MP4} (${r.moSec} Mo)`);
}

async function encoder(p, fps) {
  const n = fs.existsSync(TMP) ? fs.readdirSync(TMP).filter(f => /^f\d{5}\.jpg$/.test(f)).length : 0;
  if (!n) throw new Error('aucune image à encoder dans ' + TMP + ' : lancer le mode video');
  const ff = await choisirEncodeur();
  if (ff) await encoderFfmpeg(ff.ffmpeg, fps);
  else await encoderChrome(p, fps);
}

async function sonde(ff, mp4) {
  if (!ff || !ff.ffprobe) return null;
  const j = JSON.parse(await executer(ff.ffprobe, ['-v', 'error', '-select_streams', 'v:0', '-count_packets',
    '-show_entries', 'stream=codec_name,width,height,r_frame_rate,nb_read_packets,pix_fmt,color_space:format=duration', '-of', 'json', mp4]));
  const s = j.streams[0], [a, b] = s.r_frame_rate.split('/').map(Number);
  return { codec: s.codec_name, largeur: s.width, hauteur: s.height, fps: +(a / b).toFixed(3), images: +s.nb_read_packets,
    duree: +(+j.format.duration).toFixed(3), pixels: s.pix_fmt, matrice: s.color_space };
}

async function verifier(p) {
  const mp4 = path.join(OUT, MP4);
  if (!fs.existsSync(mp4)) throw new Error('vidéo introuvable : out/' + MP4 + ' (lancer le mode video)');
  fs.mkdirSync(TMP, { recursive: true });
  await ouvrirFilm(p);
  const dur = await p.js('window.DURATION'), fps = await p.js('window.FPS'), n = Math.round(dur * fps);
  const ff = await trouverFfmpeg({ libx264: false });
  const info = await sonde(ff, mp4);
  const indices = [.08, .25, .42, .58, .75, .92].map(k => Math.min(n - 1, Math.round(k * n)));
  const paires = [];
  for (const i of indices) {
    const ref = `verif-ref-${String(i).padStart(5, '0')}.jpg`;
    await photoA(p, i / fps, path.join(TMP, ref));
    let dec = null;
    if (ff) {
      dec = `verif-dec-${String(i).padStart(5, '0')}.png`;
      await executer(ff.ffmpeg, ['-v', 'error', '-y', '-ss', ((i - 0.5) / fps).toFixed(4), '-i', mp4, '-frames:v', '1',
        '-vf', 'scale=in_color_matrix=bt709:in_range=tv:flags=accurate_rnd+full_chroma_int', path.join(TMP, dec)]);
    }
    paires.push({ i, t: +(i / fps).toFixed(3), ref: '/frames/' + ref, dec: dec && '/frames/' + dec });
  }
  await p.taille(1280, 560, 1);
  await p.aller(`${BASE}/_outils/verifier.html`);
  const r = await p.js(`verifier(${JSON.stringify({ paires, video: ff ? null : '/out/' + MP4, fps })})`);
  if (r.erreur) throw new Error('vérification impossible : ' + r.erreur);
  await p.photo(path.join(OUT, `verification-${LANG}.png`));
  const largeur = info ? info.largeur : r.largeur, hauteur = info ? info.hauteur : r.hauteur, duree = info ? info.duree : r.duree;
  const pbs = [];
  if (largeur !== 1920 || hauteur !== 1080) pbs.push(`taille ${largeur} x ${hauteur} au lieu de 1920 x 1080`);
  if (Math.abs(duree - n / fps) > 2 / fps) pbs.push(`durée ${duree} s au lieu de ${(n / fps).toFixed(3)} s`);
  if (info && Math.abs(info.fps - fps) > 0.01) pbs.push(`${info.fps} images par seconde au lieu de ${fps}`);
  if (info && info.images !== n) pbs.push(`${info.images} images au lieu de ${n}`);
  const seuil = ff ? 3 : 5;
  for (const q of r.points) {
    if (q.noire) pbs.push(`image noire ou vide à ${q.t} s`);
    if (q.ecartMoyen > seuil) pbs.push(`écart moyen de ${q.ecartMoyen} à ${q.t} s (attendu sous ${seuil})`);
  }
  if (!r.toutesDifferentes) pbs.push('deux images échantillonnées identiques : le film semble figé');
  console.log('vérification : ' + JSON.stringify({ ffprobe: info, decodeur: ff ? 'ffmpeg' : 'navigateur',
    points: r.points.map(q => ({ t: q.t, ecartMoyen: q.ecartMoyen, ecartMax: q.ecartMax, luminance: q.luminance })) }));
  console.log(`vérification : out/verification-${LANG}.png, image décodée pleine taille dans out/`);
  if (pbs.length) throw new Error('vérification en échec : ' + pbs.join(' ; '));
  console.log(`vérification OK : ${largeur} x ${hauteur}, ${duree} s, ${info ? info.fps + ' i/s, ' + info.images + ' images, ' : ''}écart moyen max ${Math.max(...r.points.map(q => q.ecartMoyen))}`);
}

async function miniature(p) {
  if (!fs.existsSync(path.join(FILM, 'miniature.html'))) throw new Error('miniature.html introuvable dans ' + FILM);
  await p.taille(1280, 720, 1);
  await p.aller(`${BASE}/miniature.html?lang=${LANG}`);
  await p.attendre('window.READY && true');
  await p.js('window.READY');
  await controlerChargement(p);
  const jpg = path.join(OUT, `${NOM}-${LANG}-miniature.jpg`);
  await p.photo(jpg, { format: 'jpeg', quality: 92 });
  await p.photo(path.join(OUT, `${NOM}-${LANG}-miniature.png`));
  console.log(`miniature : out/${NOM}-${LANG}-miniature.jpg (${Math.round(fs.statSync(jpg).size / 1024)} Ko, limite YouTube 2 Mo) et .png`);
}

(async () => {
  if (!fs.existsSync(path.join(FILM, 'film.html'))) throw new Error('film.html introuvable dans ' + FILM);
  const CHARTE = path.join(FILM, 'charte.css');
  if (!fs.existsSync(CHARTE)) throw new Error('charte.css introuvable dans ' + FILM + ' : copier modele/charte.css et la remplir (references/charte.md)');
  if (fs.readFileSync(CHARTE, 'utf8').includes('CHARTE-NON-REMPLIE')) throw new Error('charte.css est encore le gabarit : relever la charte du projet (references/charte.md), puis retirer la ligne CHARTE-NON-REMPLIE');
  fs.mkdirSync(OUT, { recursive: true });
  const t0 = Date.now();
  const srv = await serveur();
  const { nav, onglet: p, fermer } = await lancer();
  try {
    if (MODE === 'planche') await planche(p, A4.split(',').filter(Boolean).map(Number));
    else if (MODE === 'video') { const fps = await images(nav, p); await encoder(p, fps); }
    else if (MODE === 'encoder') { await ouvrirFilm(p); await encoder(p, await p.js('window.FPS')); }
    else if (MODE === 'verifier') await verifier(p);
    else if (MODE === 'affiche') {
      if (!Number.isFinite(parseFloat(A4))) throw new Error('instant manquant : node render.js <dossier> affiche <t> [lang]');
      await ouvrirFilm(p);
      await photoA(p, +A4, path.join(OUT, `${NOM}-${LANG}-affiche.jpg`), 90);
      console.log(`affiche : out/${NOM}-${LANG}-affiche.jpg (t = ${A4} s)`);
    } else if (MODE === 'miniature') await miniature(p);
  } finally { await fermer(); srv.close(); }
  console.log(`${MODE} terminé en ${secondes(t0)}`);
})().catch(e => { console.error('ECHEC ' + e.message); process.exit(1); });
