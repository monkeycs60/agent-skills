const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawnSync } = require('child_process');

const SKILL = path.resolve(__dirname, '..');
const args = process.argv.slice(2);
const noVideo = args.includes('--no-video');
const pos = args.filter(a => !a.startsWith('--'));
const LANG = pos[1] || 'en';
if (!['fr', 'en'].includes(LANG)) { console.error('usage: node example.js [folder] [en|fr] [--no-video]'); process.exit(2); }
const ROOT = process.env.EXPLAINER_VIDEO_DIR || path.join(os.homedir(), 'explainer-videos');
const FILM = path.resolve(pos[0] || path.join(ROOT, 'coche', 'invite-team'));
const SHEET = '1.9,4.6,7.4,10.3,13.9,16.6,19.6,22.5,26.9,31.3,33.2,35.5';

const times = [];
function step(name, script, ...a) {
  const t0 = Date.now();
  console.log(`\n== ${name}`);
  const r = spawnSync(process.execPath, [path.join(__dirname, script), ...a], { stdio: 'inherit' });
  const s = (Date.now() - t0) / 1000;
  times.push([name, s]);
  if (r.status !== 0) { console.error(`\nFAILED at step "${name}" (${s.toFixed(1)} s). Tool diagnostic: node ${path.join(__dirname, 'tools.js')}`); process.exit(1); }
}

fs.mkdirSync(FILM, { recursive: true });
fs.cpSync(path.join(SKILL, 'template'), FILM, { recursive: true });
fs.copyFileSync(path.join(SKILL, 'example', 'brand.css'), path.join(FILM, 'brand.css'));
const recipe = {
  url: path.join(SKILL, 'example', 'mockup.html') + '?lang=' + LANG,
  viewport: [1440, 900], dsf: 2, lang: LANG === 'fr' ? 'fr-FR' : 'en-US',
  output: `assets/real-screen-${LANG}.png`,
  boxes: { linkArea: "document.querySelector('#link')", menuItem: "document.querySelector('[data-item=invite]')" },
  styles: { primaryButton: "document.querySelector('.button')", activeItem: "document.querySelector('.item.active')", page: 'document.body' }
};
fs.writeFileSync(path.join(FILM, `recipe-${LANG}.json`), JSON.stringify(recipe, null, 2) + '\n');
console.log(`Example film (fictional product "Coche") in ${FILM}`);

step('real screen capture', 'capture.js', path.join(FILM, `recipe-${LANG}.json`));
step('key-frame contact sheet', 'render.js', FILM, 'contact-sheet', SHEET, LANG);
if (!noVideo) {
  step('video', 'render.js', FILM, 'video', LANG);
  step('verification', 'render.js', FILM, 'verify', LANG);
}
step('poster', 'render.js', FILM, 'poster', '22', LANG);
step('thumbnail', 'render.js', FILM, 'thumbnail', LANG);
step('YouTube kit', 'kit.js', FILM, LANG);

console.log('\nTime per step:');
for (const [n, s] of times) console.log(`  ${n.padEnd(28)} ${s.toFixed(1)} s`);
console.log(`  ${'total'.padEnd(28)} ${times.reduce((a, b) => a + b[1], 0).toFixed(1)} s`);
console.log(`\nOpen: ${path.join(FILM, 'film.html')}, ${path.join(FILM, 'out')}`);
