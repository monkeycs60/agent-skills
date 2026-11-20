const fs = require('fs');
const path = require('path');

if (!process.argv[2]) { console.error('usage : node inventaire-charte.js <racine-du-projet> > inventaire.md'); process.exit(2); }
const RACINE = path.resolve(process.argv[2]);
const EXCLUS = new Set(['node_modules', '.git', 'dist', 'build', '.next', '.nuxt', '.svelte-kit', '.output', 'coverage', 'out',
  '.turbo', 'vendor', '.cache', '.vercel', '.expo', 'android', 'ios', 'storybook-static', '__snapshots__', 'tmp', '.idea', '.vscode']);
const SOURCES = /\.(css|scss|sass|less|ts|tsx|js|jsx|mjs|cjs|vue|svelte|astro|html|json)$/i;
const fichiers = [], images = [];

(function parcourir(dir, prof) {
  if (prof > 9) return;
  let entrees = [];
  try { entrees = fs.readdirSync(dir, { withFileTypes: true }); } catch (e) { return; }
  for (const e of entrees) {
    if (e.name.startsWith('.') && e.name !== '.storybook') continue;
    const f = path.join(dir, e.name);
    if (e.isDirectory()) { if (!EXCLUS.has(e.name)) parcourir(f, prof + 1); continue; }
    if (/\.(svg|png|webp|ico|woff2?|ttf|otf)$/i.test(e.name)) images.push(f);
    else if (SOURCES.test(e.name) && !/\.(min|map|lock)\./.test(e.name) && !/lock\.json$/.test(e.name)) {
      try { if (fs.statSync(f).size < 400 * 1024) fichiers.push(f); } catch (e) {}
    }
  }
})(RACINE, 0);

const rel = (f) => path.relative(RACINE, f);
const lire = (f) => { try { return fs.readFileSync(f, 'utf8'); } catch (e) { return ''; } };
const ligne = (txt, i) => txt.slice(0, i).split('\n').length;
const out = [];
const titre = (t) => out.push('', '## ' + t, '');

const deps = {};
for (const f of fichiers.filter(f => path.basename(f) === 'package.json')) {
  try { const p = JSON.parse(lire(f)); Object.assign(deps, p.dependencies, p.devDependencies); } catch (e) {}
}
const PILES = [['tailwindcss', 'Tailwind'], ['@mui/material', 'MUI'], ['@chakra-ui/react', 'Chakra'], ['@mantine/core', 'Mantine'],
  ['styled-components', 'styled-components'], ['@emotion/react', 'Emotion'], ['vuetify', 'Vuetify'], ['bootstrap', 'Bootstrap'],
  ['@radix-ui/themes', 'Radix Themes'], ['daisyui', 'daisyUI'], ['nativewind', 'NativeWind'], ['react-native', 'React Native'],
  ['next', 'Next.js'], ['astro', 'Astro'], ['@sveltejs/kit', 'SvelteKit'], ['nuxt', 'Nuxt'], ['vite', 'Vite']];
out.push('# Inventaire de charte : ' + path.basename(RACINE), '', 'Racine : `' + RACINE + '`');
titre('Pile UI');
out.push(PILES.filter(([d]) => deps[d]).map(([d, n]) => `- ${n} (\`${d}\` ${deps[d]})`).join('\n') || '- aucune bibliotheque UI reconnue');
if (fichiers.some(f => path.basename(f) === 'components.json')) out.push('- shadcn/ui (`components.json`) : couleurs dans les variables CSS `--primary`, `--background`...');

titre('Fichiers de theme a lire en premier');
const THEME = /(tailwind\.config|theme|tokens?|palette|colors?|design-system|variables|globals?|app|index|main|styles?)\.(ts|js|mjs|cjs|json|css|scss)$/i;
const themes = fichiers.filter(f => THEME.test(path.basename(f)) && /(theme|token|palette|color|tailwind|design|variables|global|style)/i.test(rel(f)));
out.push(themes.slice(0, 30).map(f => '- `' + rel(f) + '`').join('\n') || '- aucun fichier de theme evident : chercher `createTheme`, `:root`, `@theme` ci-dessous');

titre('Variables CSS (clair / sombre)');
const vars = [];
for (const f of fichiers.filter(f => /\.(css|scss|sass|less|vue|svelte|astro)$/i.test(f))) {
  const t = lire(f);
  const re = /([^{}]+)\{([^{}]*--[\w-]+\s*:[^{}]*)\}/g; let m;
  while ((m = re.exec(t))) {
    const sel = m[1].trim().split('\n').pop().trim().slice(0, 60);
    const ctx = /dark|\.night|theme=.?dark/i.test(sel) ? 'sombre' : 'clair';
    for (const v of m[2].matchAll(/(--[\w-]+)\s*:\s*([^;]+);/g)) vars.push({ f: rel(f), l: ligne(t, m.index), sel, ctx, k: v[1], v: v[2].trim() });
  }
}
const interessant = (k, v) => /color|brand|primary|secondary|accent|background|foreground|surface|muted|border|ring|radius|font|success|warning|danger|destructive|error|bg|text|ink/i.test(k)
  || /^(#|rgb|hsl|oklch|oklab|lab|color\()/i.test(v) || /^\d+(\.\d+)?%?\s+\d/.test(v);
const vs = vars.filter(x => interessant(x.k, x.v));
if (!vs.length) out.push('- aucune');
for (const ctx of ['clair', 'sombre']) {
  const l = vs.filter(x => x.ctx === ctx);
  if (!l.length) continue;
  out.push(`**Theme ${ctx}** (${l.length} variables)`, '', '| Variable | Valeur | Selecteur | Fichier |', '|---|---|---|---|');
  l.slice(0, 80).forEach(x => out.push(`| \`${x.k}\` | \`${x.v.replace(/\|/g, '\\|').slice(0, 70)}\` | \`${x.sel.replace(/\|/g, '\\|')}\` | ${x.f}:${x.l} |`));
  if (l.length > 80) out.push(`| ... | ${l.length - 80} de plus | | |`);
  out.push('');
}
const definies = new Set(vars.map(x => x.k)), orphelines = new Map();
for (const f of fichiers.filter(f => !/\.json$/i.test(f))) for (const m of lire(f).matchAll(/var\(\s*(--[\w-]+)/g)) if (!definies.has(m[1])) orphelines.set(m[1], (orphelines.get(m[1]) || 0) + 1);
if (orphelines.size) out.push('> Variables employees mais definies hors de ce dossier (paquet partage du monorepo, dependance, injection JS) : '
  + [...orphelines].sort((a, b) => b[1] - a[1]).slice(0, 12).map(([k]) => '`' + k + '`').join(', ') + '. Relancer l\'inventaire a la racine du depot.', '');
if (vs.some(x => /^\d+(\.\d+)?\s+\d+(\.\d+)?%\s+\d/.test(x.v))) out.push('> Valeurs du type `262 83% 58%` : composantes HSL sans `hsl()` (convention shadcn). Ecrire `hsl(262 83% 58%)` dans charte.css.');

titre('Themes declares en code (MUI, Chakra, Tailwind v3, tokens)');
let nJs = 0;
for (const f of fichiers.filter(f => /\.(ts|tsx|js|jsx|mjs|cjs)$/i.test(f))) {
  const t = lire(f);
  if (!/createTheme|extendTheme|createStitches|defineConfig\(|theme\s*:\s*\{|palette\s*:|colors\s*:\s*\{|fontFamily\s*:/.test(t)) continue;
  if (!/(primary|brand|main|fontFamily|colors)\b/.test(t)) continue;
  const hits = [];
  t.split('\n').forEach((l, i) => {
    if (/(primary|secondary|brand|accent|main|light|dark|background|paper|default|text|success|warning|error|fontFamily|borderRadius|radius)\b\s*:/.test(l) && /['"#\d]/.test(l)) hits.push(`${i + 1}: ${l.trim().slice(0, 110)}`);
  });
  if (!hits.length) continue;
  if (++nJs > 12) break;
  out.push('`' + rel(f) + '`', '```', ...hits.slice(0, 25), '```');
}
if (!nJs) out.push('- aucun');

titre('Polices');
const polices = new Map();
const note = (nom, ou) => { nom = nom.replace(/["']/g, '').trim(); if (nom && !/^(inherit|initial|var\()/.test(nom)) { if (!polices.has(nom)) polices.set(nom, new Set()); polices.get(nom).add(ou); } };
for (const f of fichiers) {
  const t = lire(f);
  for (const m of t.matchAll(/@font-face\s*\{[^}]*font-family\s*:\s*([^;]+);/g)) note(m[1], '@font-face ' + rel(f));
  for (const m of t.matchAll(/fonts\.googleapis\.com\/css2?\?family=([^"'&)\s]+)/g)) decodeURIComponent(m[1]).split('|').forEach(x => note(x.split(':')[0].replace(/\+/g, ' '), 'Google Fonts ' + rel(f)));
  for (const m of t.matchAll(/import\s*\{([^}]+)\}\s*from\s*['"]next\/font\/google['"]/g)) m[1].split(',').forEach(x => note(x.trim().replace(/_/g, ' '), 'next/font ' + rel(f)));
  for (const m of t.matchAll(/@fontsource(?:-variable)?\/([\w-]+)/g)) note(m[1], '@fontsource ' + rel(f));
  for (const m of t.matchAll(/font-?[fF]amily['"]?\s*:\s*\[?\s*['"]?([A-Z][\w ]+?)['",;\]]/g)) note(m[1], 'font-family ' + rel(f));
}
out.push([...polices].slice(0, 20).map(([n, s]) => `- **${n}** : ${[...s].slice(0, 3).join(', ')}`).join('\n') || '- aucune police declaree : police systeme');
const fontes = images.filter(f => /\.(woff2?|ttf|otf)$/i.test(f));
if (fontes.length) out.push('', 'Fichiers de police (verifier la licence avant de les copier dans le film) :', ...fontes.slice(0, 15).map(f => '- `' + rel(f) + '`'));

titre('Logos et icones de marque');
const logos = images.filter(f => /logo|brand|wordmark|marque|favicon|icon[-_]?(512|192)|apple-touch|og-image/i.test(rel(f)) && !/\.(woff2?|ttf|otf)$/i.test(f));
out.push(logos.slice(0, 25).map(f => '- `' + rel(f) + '` (' + Math.round(fs.statSync(f).size / 1024) + ' Ko)').join('\n') || '- aucun fichier de logo : utiliser `--nom` (le nom en police de titre)');

titre('Couleurs les plus employees dans le code');
const freq = new Map();
for (const f of fichiers.filter(f => !/\.json$/i.test(f))) for (const m of lire(f).matchAll(/#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b/g)) {
  let h = m[0].toUpperCase(); if (h.length === 4) h = '#' + [...h.slice(1)].map(c => c + c).join('');
  freq.set(h, (freq.get(h) || 0) + 1);
}
const top = [...freq].sort((a, b) => b[1] - a[1]).slice(0, 24);
out.push(top.length ? '| Couleur | Occurrences |\n|---|---|\n' + top.map(([h, n]) => `| \`${h}\` | ${n} |`).join('\n') : '- aucune couleur hexadecimale');
const tw = new Map();
for (const f of fichiers.filter(f => /\.(tsx|jsx|vue|svelte|astro|html)$/i.test(f))) for (const m of lire(f).matchAll(/\b(?:bg|text|border|ring|from|to)-((?:primary|secondary|accent|brand|muted|destructive|[a-z]+-\d{2,3}))\b/g)) tw.set(m[1], (tw.get(m[1]) || 0) + 1);
if (tw.size) out.push('', 'Classes Tailwind de couleur les plus employees : ' + [...tw].sort((a, b) => b[1] - a[1]).slice(0, 16).map(([k, n]) => `\`${k}\` (${n})`).join(', '));

titre('Suite');
out.push('1. Lire les fichiers de theme ci-dessus : la valeur du code prime sur la frequence.',
  '2. Mesurer sur l\'app qui tourne (bouton principal, fond, item actif) : `capturer.js` avec `styles`.',
  '3. Remplir `charte.css` du film, une source en commentaire par valeur (references/charte.md).');
console.log(out.join('\n'));
