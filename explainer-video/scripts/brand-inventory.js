const fs = require('fs');
const path = require('path');

if (!process.argv[2]) { console.error('usage: node brand-inventory.js <project-root> > inventory.md'); process.exit(2); }
const ROOT = path.resolve(process.argv[2]);
const EXCLUDED = new Set(['node_modules', '.git', 'dist', 'build', '.next', '.nuxt', '.svelte-kit', '.output', 'coverage', 'out',
  '.turbo', 'vendor', '.cache', '.vercel', '.expo', 'android', 'ios', 'storybook-static', '__snapshots__', 'tmp', '.idea', '.vscode']);
const SOURCES = /\.(css|scss|sass|less|ts|tsx|js|jsx|mjs|cjs|vue|svelte|astro|html|json)$/i;
const files = [], images = [];

(function walk(dir, depth) {
  if (depth > 9) return;
  let entries = [];
  try { entries = fs.readdirSync(dir, { withFileTypes: true }); } catch (e) { return; }
  for (const e of entries) {
    if (e.name.startsWith('.') && e.name !== '.storybook') continue;
    const f = path.join(dir, e.name);
    if (e.isDirectory()) { if (!EXCLUDED.has(e.name)) walk(f, depth + 1); continue; }
    if (/\.(svg|png|webp|ico|woff2?|ttf|otf)$/i.test(e.name)) images.push(f);
    else if (SOURCES.test(e.name) && !/\.(min|map|lock)\./.test(e.name) && !/lock\.json$/.test(e.name)) {
      try { if (fs.statSync(f).size < 400 * 1024) files.push(f); } catch (e) {}
    }
  }
})(ROOT, 0);

const rel = (f) => path.relative(ROOT, f);
const read = (f) => { try { return fs.readFileSync(f, 'utf8'); } catch (e) { return ''; } };
const lineOf = (txt, i) => txt.slice(0, i).split('\n').length;
const out = [];
const heading = (t) => out.push('', '## ' + t, '');

const deps = {};
for (const f of files.filter(f => path.basename(f) === 'package.json')) {
  try { const p = JSON.parse(read(f)); Object.assign(deps, p.dependencies, p.devDependencies); } catch (e) {}
}
const STACKS = [['tailwindcss', 'Tailwind'], ['@mui/material', 'MUI'], ['@chakra-ui/react', 'Chakra'], ['@mantine/core', 'Mantine'],
  ['styled-components', 'styled-components'], ['@emotion/react', 'Emotion'], ['vuetify', 'Vuetify'], ['bootstrap', 'Bootstrap'],
  ['@radix-ui/themes', 'Radix Themes'], ['daisyui', 'daisyUI'], ['nativewind', 'NativeWind'], ['react-native', 'React Native'],
  ['next', 'Next.js'], ['astro', 'Astro'], ['@sveltejs/kit', 'SvelteKit'], ['nuxt', 'Nuxt'], ['vite', 'Vite']];
out.push('# Brand inventory: ' + path.basename(ROOT), '', 'Root: `' + ROOT + '`');
heading('UI stack');
out.push(STACKS.filter(([d]) => deps[d]).map(([d, n]) => `- ${n} (\`${d}\` ${deps[d]})`).join('\n') || '- no known UI library');
if (files.some(f => path.basename(f) === 'components.json')) out.push('- shadcn/ui (`components.json`): colors in the CSS variables `--primary`, `--background`...');

heading('Theme files to read first');
const THEME = /(tailwind\.config|theme|tokens?|palette|colors?|design-system|variables|globals?|app|index|main|styles?)\.(ts|js|mjs|cjs|json|css|scss)$/i;
const themes = files.filter(f => THEME.test(path.basename(f)) && /(theme|token|palette|color|tailwind|design|variables|global|style)/i.test(rel(f)));
out.push(themes.slice(0, 30).map(f => '- `' + rel(f) + '`').join('\n') || '- no obvious theme file: look for `createTheme`, `:root`, `@theme` below');

heading('CSS variables (light / dark)');
const vars = [];
for (const f of files.filter(f => /\.(css|scss|sass|less|vue|svelte|astro)$/i.test(f))) {
  const t = read(f);
  const re = /([^{}]+)\{([^{}]*--[\w-]+\s*:[^{}]*)\}/g; let m;
  while ((m = re.exec(t))) {
    const sel = m[1].trim().split('\n').pop().trim().slice(0, 60);
    const ctx = /dark|\.night|theme=.?dark/i.test(sel) ? 'dark' : 'light';
    for (const v of m[2].matchAll(/(--[\w-]+)\s*:\s*([^;]+);/g)) vars.push({ f: rel(f), l: lineOf(t, m.index), sel, ctx, k: v[1], v: v[2].trim() });
  }
}
const relevant = (k, v) => /color|brand|primary|secondary|accent|background|foreground|surface|muted|border|ring|radius|font|success|warning|danger|destructive|error|bg|text|ink/i.test(k)
  || /^(#|rgb|hsl|oklch|oklab|lab|color\()/i.test(v) || /^\d+(\.\d+)?%?\s+\d/.test(v);
const vs = vars.filter(x => relevant(x.k, x.v));
if (!vs.length) out.push('- none');
for (const ctx of ['light', 'dark']) {
  const l = vs.filter(x => x.ctx === ctx);
  if (!l.length) continue;
  out.push(`**${ctx[0].toUpperCase() + ctx.slice(1)} theme** (${l.length} variables)`, '', '| Variable | Value | Selector | File |', '|---|---|---|---|');
  l.slice(0, 80).forEach(x => out.push(`| \`${x.k}\` | \`${x.v.replace(/\|/g, '\\|').slice(0, 70)}\` | \`${x.sel.replace(/\|/g, '\\|')}\` | ${x.f}:${x.l} |`));
  if (l.length > 80) out.push(`| ... | ${l.length - 80} more | | |`);
  out.push('');
}
const defined = new Set(vars.map(x => x.k)), orphans = new Map();
for (const f of files.filter(f => !/\.json$/i.test(f))) for (const m of read(f).matchAll(/var\(\s*(--[\w-]+)/g)) if (!defined.has(m[1])) orphans.set(m[1], (orphans.get(m[1]) || 0) + 1);
if (orphans.size) out.push('> Variables used but defined outside this folder (shared monorepo package, dependency, JS injection): '
  + [...orphans].sort((a, b) => b[1] - a[1]).slice(0, 12).map(([k]) => '`' + k + '`').join(', ') + '. Run the inventory again at the repository root.', '');
if (vs.some(x => /^\d+(\.\d+)?\s+\d+(\.\d+)?%\s+\d/.test(x.v))) out.push('> Values like `262 83% 58%`: HSL components without `hsl()` (shadcn convention). Write `hsl(262 83% 58%)` in brand.css.');

heading('Themes declared in code (MUI, Chakra, Tailwind v3, tokens)');
let nJs = 0;
for (const f of files.filter(f => /\.(ts|tsx|js|jsx|mjs|cjs)$/i.test(f))) {
  const t = read(f);
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
if (!nJs) out.push('- none');

heading('Fonts');
const fonts = new Map();
const note = (name, where) => { name = name.replace(/["']/g, '').trim(); if (name && !/^(inherit|initial|var\()/.test(name)) { if (!fonts.has(name)) fonts.set(name, new Set()); fonts.get(name).add(where); } };
for (const f of files) {
  const t = read(f);
  for (const m of t.matchAll(/@font-face\s*\{[^}]*font-family\s*:\s*([^;]+);/g)) note(m[1], '@font-face ' + rel(f));
  for (const m of t.matchAll(/fonts\.googleapis\.com\/css2?\?family=([^"'&)\s]+)/g)) decodeURIComponent(m[1]).split('|').forEach(x => note(x.split(':')[0].replace(/\+/g, ' '), 'Google Fonts ' + rel(f)));
  for (const m of t.matchAll(/import\s*\{([^}]+)\}\s*from\s*['"]next\/font\/google['"]/g)) m[1].split(',').forEach(x => note(x.trim().replace(/_/g, ' '), 'next/font ' + rel(f)));
  for (const m of t.matchAll(/@fontsource(?:-variable)?\/([\w-]+)/g)) note(m[1], '@fontsource ' + rel(f));
  for (const m of t.matchAll(/font-?[fF]amily['"]?\s*:\s*\[?\s*['"]?([A-Z][\w ]+?)['",;\]]/g)) note(m[1], 'font-family ' + rel(f));
}
out.push([...fonts].slice(0, 20).map(([n, s]) => `- **${n}**: ${[...s].slice(0, 3).join(', ')}`).join('\n') || '- no declared font: system font');
const fontFiles = images.filter(f => /\.(woff2?|ttf|otf)$/i.test(f));
if (fontFiles.length) out.push('', 'Font files (check the license before copying them into the film):', ...fontFiles.slice(0, 15).map(f => '- `' + rel(f) + '`'));

heading('Logos and brand icons');
const logos = images.filter(f => /logo|brand|wordmark|marque|favicon|icon[-_]?(512|192)|apple-touch|og-image/i.test(rel(f)) && !/\.(woff2?|ttf|otf)$/i.test(f));
out.push(logos.slice(0, 25).map(f => '- `' + rel(f) + '` (' + Math.round(fs.statSync(f).size / 1024) + ' KB)').join('\n') || '- no logo file: use `--name` (the name in the title font)');

heading('Most used colors in the code');
const freq = new Map();
for (const f of files.filter(f => !/\.json$/i.test(f))) for (const m of read(f).matchAll(/#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b/g)) {
  let h = m[0].toUpperCase(); if (h.length === 4) h = '#' + [...h.slice(1)].map(c => c + c).join('');
  freq.set(h, (freq.get(h) || 0) + 1);
}
const top = [...freq].sort((a, b) => b[1] - a[1]).slice(0, 24);
out.push(top.length ? '| Color | Occurrences |\n|---|---|\n' + top.map(([h, n]) => `| \`${h}\` | ${n} |`).join('\n') : '- no hexadecimal color');
const tw = new Map();
for (const f of files.filter(f => /\.(tsx|jsx|vue|svelte|astro|html)$/i.test(f))) for (const m of read(f).matchAll(/\b(?:bg|text|border|ring|from|to)-((?:primary|secondary|accent|brand|muted|destructive|[a-z]+-\d{2,3}))\b/g)) tw.set(m[1], (tw.get(m[1]) || 0) + 1);
if (tw.size) out.push('', 'Most used Tailwind color classes: ' + [...tw].sort((a, b) => b[1] - a[1]).slice(0, 16).map(([k, n]) => `\`${k}\` (${n})`).join(', '));

heading('Next');
out.push('1. Read the theme files above: the value in the code beats frequency.',
  '2. Measure on the running app (primary button, background, active item): `capture.js` with `styles`.',
  '3. Fill in the film\'s `brand.css`, one source comment per value (references/brand.md).');
console.log(out.join('\n'));
