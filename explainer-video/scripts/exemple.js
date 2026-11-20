const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawnSync } = require('child_process');

const SKILL = path.resolve(__dirname, '..');
const args = process.argv.slice(2);
const sansVideo = args.includes('--sans-video');
const pos = args.filter(a => !a.startsWith('--'));
const LANG = pos[1] || 'fr';
if (!['fr', 'en'].includes(LANG)) { console.error('usage : node exemple.js [dossier] [fr|en] [--sans-video]'); process.exit(2); }
const RACINE = process.env.EXPLAINER_VIDEO_DIR || path.join(os.homedir(), 'explainer-videos');
const FILM = path.resolve(pos[0] || path.join(RACINE, 'coche', 'inviter-equipe'));
const PLANCHE = '1.9,4.6,7.4,10.3,13.9,16.6,19.6,22.5,26.9,31.3,33.2,35.5';

const temps = [];
function etape(nom, script, ...a) {
  const t0 = Date.now();
  console.log(`\n== ${nom}`);
  const r = spawnSync(process.execPath, [path.join(__dirname, script), ...a], { stdio: 'inherit' });
  const s = (Date.now() - t0) / 1000;
  temps.push([nom, s]);
  if (r.status !== 0) { console.error(`\nECHEC à l'étape « ${nom} » (${s.toFixed(1)} s). Diagnostic des outils : node ${path.join(__dirname, 'outils.js')}`); process.exit(1); }
}

fs.mkdirSync(FILM, { recursive: true });
fs.cpSync(path.join(SKILL, 'modele'), FILM, { recursive: true });
fs.copyFileSync(path.join(SKILL, 'exemple', 'charte.css'), path.join(FILM, 'charte.css'));
const recette = {
  url: path.join(SKILL, 'exemple', 'maquette.html') + '?lang=' + LANG,
  viewport: [1440, 900], dsf: 2, lang: LANG === 'fr' ? 'fr-FR' : 'en-US',
  sortie: `assets/ecran-reel-${LANG}.png`,
  boites: { zoneLien: "document.querySelector('#lien')", itemMenu: "document.querySelector('[data-item=inviter]')" },
  styles: { boutonPrincipal: "document.querySelector('.bouton')", itemActif: "document.querySelector('.item.actif')", fond: 'document.body' }
};
fs.writeFileSync(path.join(FILM, `recette-${LANG}.json`), JSON.stringify(recette, null, 2) + '\n');
console.log(`Film d'exemple (produit fictif « Coche ») dans ${FILM}`);

etape('capture de l\'écran réel', 'capturer.js', path.join(FILM, `recette-${LANG}.json`));
etape('planche d\'images clés', 'render.js', FILM, 'planche', PLANCHE, LANG);
if (!sansVideo) {
  etape('vidéo', 'render.js', FILM, 'video', LANG);
  etape('vérification', 'render.js', FILM, 'verifier', LANG);
}
etape('affiche', 'render.js', FILM, 'affiche', '22', LANG);
etape('miniature', 'render.js', FILM, 'miniature', LANG);
etape('kit YouTube', 'kit.js', FILM, LANG);

console.log('\nTemps par étape :');
for (const [n, s] of temps) console.log(`  ${n.padEnd(28)} ${s.toFixed(1)} s`);
console.log(`  ${'total'.padEnd(28)} ${temps.reduce((a, b) => a + b[1], 0).toFixed(1)} s`);
console.log(`\nÀ ouvrir : ${path.join(FILM, 'film.html')}, ${path.join(FILM, 'out')}`);
