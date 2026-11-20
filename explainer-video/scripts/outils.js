const fs = require('fs');
const path = require('path');
const http = require('http');
const { execFile } = require('child_process');
const { dansLePath } = require('./cdp');

const sortie = (bin, args) => new Promise(ok => execFile(bin, args, { maxBuffer: 8 * 1024 * 1024 }, (e, so, se) => ok(e ? null : so + se)));

let memo;
async function trouverFfmpeg({ libx264 = true } = {}) {
  if (memo === undefined) {
    const ff = process.env.FFMPEG_PATH || dansLePath(['ffmpeg']) || ['/opt/homebrew/bin/ffmpeg', '/usr/local/bin/ffmpeg'].find(f => fs.existsSync(f));
    if (!ff) memo = null;
    else {
      const enc = await sortie(ff, ['-hide_banner', '-encoders']);
      const voisin = path.join(path.dirname(ff), process.platform === 'win32' ? 'ffprobe.exe' : 'ffprobe');
      const probe = process.env.FFPROBE_PATH || (fs.existsSync(voisin) ? voisin : dansLePath(['ffprobe']));
      memo = enc === null ? null : { ffmpeg: ff, ffprobe: probe || null, libx264: /\blibx264\b/.test(enc) };
    }
  }
  if (!memo || (libx264 && !memo.libx264)) return null;
  return memo;
}

async function diagnostic() {
  const lignes = [], bloquants = [];
  const ok = (b, texte, aide) => { lignes.push(`  ${b ? '✓' : '✗'} ${texte}` + (!b && aide ? `\n      ${aide}` : '')); return b; };
  const majeur = +process.versions.node.split('.')[0];
  if (!ok(majeur >= 20, `Node ${process.versions.node} (20 ou plus requis)`, 'installer Node 20 ou plus : https://nodejs.org')) bloquants.push('Node');
  let webcodecs = false;
  try {
    const { lancer } = require('./cdp');
    const srv = http.createServer((q, r) => { r.setHeader('content-type', 'text/html'); r.end('<!doctype html><title>diagnostic</title>'); });
    await new Promise(r => srv.listen(0, '127.0.0.1', r));
    const { nav, onglet: p, fermer } = await lancer();
    try {
      ok(true, `navigateur : ${nav.chemin} (${nav.version}), lancement sans interface OK`);
      await p.aller('http://127.0.0.1:' + srv.address().port + '/');
      webcodecs = await p.js(`(async () => { try { return (await VideoEncoder.isConfigSupported({ codec: 'avc1.640028', width: 1920, height: 1080,
        bitrate: 6e6, framerate: 60, avc: { format: 'avc' } })).supported; } catch (e) { return false; } })()`);
    } finally { await fermer(); srv.close(); }
  } catch (e) {
    ok(false, 'navigateur : ' + e.message.split('\n')[0],
      'Linux : installer Google Chrome ou Chromium (apt install chromium) ; macOS : installer Google Chrome ; ou CHROME_PATH=/chemin/du/binaire');
    bloquants.push('navigateur');
  }
  const ff = await trouverFfmpeg({ libx264: false });
  if (ff && ff.libx264) ok(true, `ffmpeg : ${ff.ffmpeg} (libx264) : encodage rapide et vérification image par image`);
  else ok(false, ff ? `ffmpeg : ${ff.ffmpeg} sans libx264, ignoré pour l'encodage` : 'ffmpeg : absent (facultatif)',
    'facultatif mais recommandé : apt install ffmpeg, ou brew install ffmpeg ; sinon FFMPEG_PATH=/chemin/de/ffmpeg');
  if (ff) ok(!!ff.ffprobe, `ffprobe : ${ff.ffprobe || 'absent'}`, 'livré avec ffmpeg, sert au contrôle de durée et de cadence');
  if (!bloquants.includes('navigateur')) {
    ok(webcodecs, `encodage H.264 dans le navigateur (WebCodecs) : ${webcodecs ? 'disponible' : 'indisponible'}`,
      ff && ff.libx264 ? 'sans importance : ffmpeg encode' : 'installer ffmpeg, ou Google Chrome qui encode le H.264');
    if (!webcodecs && !(ff && ff.libx264)) bloquants.push('encodeur H.264');
  }
  console.log('explainer-video : outils\n' + lignes.join('\n'));
  if (bloquants.length) { console.log(`\nManque : ${bloquants.join(', ')}. Aucune vidéo possible tant que ce n'est pas réglé.`); return false; }
  const encodeur = ff && ff.libx264 ? 'ffmpeg' : 'le navigateur (WebCodecs)';
  console.log(`\nPrêt : encodage par ${encodeur}. Film d'exemple complet : node ${path.join(__dirname, 'exemple.js')}`);
  return true;
}

if (require.main === module) diagnostic().then(b => process.exit(b ? 0 : 1)).catch(e => { console.error('ECHEC ' + e.message); process.exit(1); });

module.exports = { trouverFfmpeg };
