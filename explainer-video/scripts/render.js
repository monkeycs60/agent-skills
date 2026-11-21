const http = require('http');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { execFile } = require('child_process');
const { launch, sleep } = require('./cdp');
const { findFfmpeg } = require('./tools');

const USAGE = `usage:
  node render.js <film-folder> contact-sheet <t1,t2,...> [lang]
  node render.js <film-folder> video [lang]
  node render.js <film-folder> encode [lang]
  node render.js <film-folder> verify [lang]
  node render.js <film-folder> poster <t> [lang]
  node render.js <film-folder> thumbnail [lang]`;
const MODES = ['contact-sheet', 'video', 'encode', 'verify', 'poster', 'thumbnail'];
if (process.argv.length < 4 || !MODES.includes(process.argv[3])) { console.error(USAGE); process.exit(2); }

const SCRIPTS = __dirname;
const FILM = path.resolve(process.argv[2]);
const MODE = process.argv[3];
const A4 = process.argv[4] || '', A5 = process.argv[5] || '';
const WITH_TIMES = MODE === 'contact-sheet' || MODE === 'poster';
const LANG = WITH_TIMES ? (A5 || 'en') : (A4 || 'en');
const NAME = path.basename(FILM);
const TMP = path.resolve(process.env.FRAMES_DIR ? path.join(process.env.FRAMES_DIR, NAME + '-' + LANG) : path.join(os.tmpdir(), 'explainer-video-' + NAME + '-' + LANG));
const OUT = path.join(FILM, 'out');
const MP4 = `${NAME}-${LANG}.mp4`;
const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.png': 'image/png', '.jpg': 'image/jpeg',
  '.woff2': 'font/woff2', '.woff': 'font/woff', '.ttf': 'font/ttf', '.otf': 'font/otf', '.css': 'text/css', '.webp': 'image/webp',
  '.svg': 'image/svg+xml', '.json': 'application/json', '.mp4': 'video/mp4' };
const missing = new Set();
let BASE = '';
const seconds = (t0) => ((Date.now() - t0) / 1000).toFixed(1) + ' s';
const run = (bin, args) => new Promise((ok, ko) => execFile(bin, args, { maxBuffer: 64 * 1024 * 1024 },
  (e, so, se) => e ? ko(new Error(path.basename(bin) + ': ' + (se || e.message).trim().split('\n').slice(-3).join(' '))) : ok(so)));

function server() {
  return new Promise(ok => {
    const s = http.createServer((req, res) => {
      const u = new URL(req.url, 'http://x');
      if (req.method === 'POST' && u.pathname === '/save') {
        const stream = fs.createWriteStream(path.join(OUT, path.basename(u.searchParams.get('f') || 'output.bin')));
        req.pipe(stream); stream.on('finish', () => res.end('ok'));
        return;
      }
      let f;
      if (u.pathname.startsWith('/frames/')) f = path.join(TMP, path.basename(u.pathname));
      else if (u.pathname.startsWith('/_scripts/')) f = path.join(SCRIPTS, path.basename(u.pathname));
      else f = path.join(FILM, decodeURIComponent(u.pathname));
      if (![FILM, TMP, SCRIPTS].some(r => f.startsWith(r))) { res.statusCode = 403; return res.end(); }
      fs.readFile(f, (e, d) => {
        if (e) {
          if (!u.pathname.startsWith('/frames/') && !/favicon/.test(u.pathname)) missing.add(decodeURIComponent(u.pathname));
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

let reported = false;
async function checkLoading(p) {
  const r = await p.js(`({ images: [...document.images].filter(i => i.getAttribute('src') && !i.naturalWidth).map(i => i.getAttribute('src')),
    fonts: [...document.fonts].filter(f => f.status === 'error').map(f => f.family) })`);
  if (reported) return;
  reported = true;
  const absent = [...new Set([...r.images, ...missing])];
  if (absent.length) console.warn('WARNING files requested by the film but not found: ' + absent.join(', ') + (absent.some(m => /real-screen/.test(m)) ? ' (real screen capture still to do: capture.js)' : ''));
  if (r.fonts.length) console.warn('WARNING fonts failed to load: ' + [...new Set(r.fonts)].join(', ') + ' (check @font-face in brand.css)');
}

async function openFilm(p) {
  await p.size(1920, 1080, 1);
  await p.goto(`${BASE}/film.html?render&lang=${LANG}`);
  await p.waitFor('window.READY && true');
  await p.js('window.READY');
  await checkLoading(p);
}

async function shotAt(p, t, file, quality = 93) {
  await p.js(`window.seek(${t.toFixed(6)})`);
  await p.screenshot(file, { format: 'jpeg', quality });
}

async function contactSheet(p, times) {
  if (!times.length || times.some(t => !Number.isFinite(t))) throw new Error('invalid times: ' + A4 + ' (example: 2,6.5,12)');
  fs.mkdirSync(TMP, { recursive: true });
  await openFilm(p);
  const names = [];
  for (const t of times) {
    const n = `still-${String(Math.round(t * 100)).padStart(5, '0')}.jpg`;
    await shotAt(p, t, path.join(TMP, n), 90);
    names.push([n, t]);
  }
  const cols = Math.min(4, names.length), w = 470, h = Math.round(w * 9 / 16), rows = Math.ceil(names.length / cols);
  const html = `<body style="margin:0;background:#141418;font:600 15px sans-serif;color:#ddd">
    <div style="display:grid;grid-template-columns:repeat(${cols},${w}px);gap:10px;padding:10px">
    ${names.map(([n, t]) => `<div><img src="/frames/${n}" style="width:${w}px;height:${h}px;display:block;border-radius:4px"><div style="padding:4px 2px">${t.toFixed(2)} s</div></div>`).join('')}
    </div></body>`;
  fs.writeFileSync(path.join(TMP, 'contact-sheet.html'), html);
  await p.size(cols * (w + 10) + 10, rows * (h + 34) + 14, 1);
  await p.goto(`${BASE}/frames/contact-sheet.html`);
  await p.js('Promise.all([...document.images].map(i => i.decode()))');
  await p.screenshot(path.join(OUT, `contact-sheet-${LANG}.png`));
  console.log(`contact sheet: ${names.length} frames -> out/contact-sheet-${LANG}.png (full size in ${TMP})`);
}

const X264 = (fps) => ['-vf', 'colorspace=ispace=bt470bg:iprimaries=bt709:itrc=bt709:irange=pc:space=bt709:primaries=bt709:trc=bt709:range=tv:format=yuv420p',
  '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-tune', 'animation', '-g', String(fps * 2),
  '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709', '-color_range', 'tv', '-movflags', '+faststart', path.join(OUT, MP4)];

async function chooseEncoder() {
  const choice = (process.env.ENCODER || '').toLowerCase();
  const ff = choice === 'chrome' ? null : await findFfmpeg();
  if (choice === 'ffmpeg' && !ff) throw new Error('ENCODER=ffmpeg but no ffmpeg with libx264 was found');
  return ff;
}

async function renderFrames(browser, p) {
  fs.rmSync(TMP, { recursive: true, force: true });
  fs.mkdirSync(TMP, { recursive: true });
  await openFilm(p);
  const dur = await p.js('window.DURATION'), fps = await p.js('window.FPS');
  const n = Math.round(dur * fps), t0 = Date.now();
  const wanted = +process.env.WORKERS || Math.max(1, Math.min(4, Math.floor(os.cpus().length / 2)));
  const tabs = [p];
  for (let k = 1; k < Math.min(wanted, n); k++) { const o = await browser.tab({ isolated: true }); await openFilm(o); tabs.push(o); }
  let next = 0, done = 0, milestone = 0;
  await Promise.all(tabs.map(async (o) => {
    for (let i = next++; i < n; i = next++) {
      await shotAt(o, i / fps, path.join(TMP, `f${String(i).padStart(5, '0')}.jpg`));
      done++;
      if (done >= milestone) { console.log(`  frame ${done}/${n}  (${seconds(t0)})`); milestone += 600; }
    }
  }));
  console.log(`frames: ${n} in ${seconds(t0)} (${tabs.length} tabs in parallel)`);
  return fps;
}

async function encodeFfmpeg(ff, fps) {
  const t0 = Date.now();
  await run(ff, ['-hide_banner', '-loglevel', 'error', '-y', '-framerate', String(fps), '-i', path.join(TMP, 'f%05d.jpg'), ...X264(fps)]);
  const mb = fs.statSync(path.join(OUT, MP4)).size / 1e6;
  console.log(`encoding: ffmpeg libx264 in ${seconds(t0)} -> out/${MP4} (${mb.toFixed(1)} MB)`);
}

async function encodeChrome(p, fps) {
  const n = fs.readdirSync(TMP).filter(f => /^f\d{5}\.jpg$/.test(f)).length;
  const t0 = Date.now();
  await p.goto(`${BASE}/_scripts/encoder.html?n=${n}&fps=${fps}&out=${MP4}`);
  const r = await p.js('window.ENCODE');
  if (!r.ok) throw new Error('in-browser encoding failed: ' + r.err + ' (install ffmpeg, or use Google Chrome)');
  console.log(`encoding: WebCodecs ${r.codec} in ${seconds(t0)} -> out/${MP4} (${r.mb} MB)`);
}

async function encode(p, fps) {
  const n = fs.existsSync(TMP) ? fs.readdirSync(TMP).filter(f => /^f\d{5}\.jpg$/.test(f)).length : 0;
  if (!n) throw new Error('no frames to encode in ' + TMP + ': run the video mode');
  const ff = await chooseEncoder();
  if (ff) await encodeFfmpeg(ff.ffmpeg, fps);
  else await encodeChrome(p, fps);
}

async function probe(ff, mp4) {
  if (!ff || !ff.ffprobe) return null;
  const j = JSON.parse(await run(ff.ffprobe, ['-v', 'error', '-select_streams', 'v:0', '-count_packets',
    '-show_entries', 'stream=codec_name,width,height,r_frame_rate,nb_read_packets,pix_fmt,color_space:format=duration', '-of', 'json', mp4]));
  const s = j.streams[0], [a, b] = s.r_frame_rate.split('/').map(Number);
  return { codec: s.codec_name, width: s.width, height: s.height, fps: +(a / b).toFixed(3), frames: +s.nb_read_packets,
    duration: +(+j.format.duration).toFixed(3), pixels: s.pix_fmt, matrix: s.color_space };
}

async function verify(p) {
  const mp4 = path.join(OUT, MP4);
  if (!fs.existsSync(mp4)) throw new Error('video not found: out/' + MP4 + ' (run the video mode)');
  fs.mkdirSync(TMP, { recursive: true });
  await openFilm(p);
  const dur = await p.js('window.DURATION'), fps = await p.js('window.FPS'), n = Math.round(dur * fps);
  const ff = await findFfmpeg({ libx264: false });
  const info = await probe(ff, mp4);
  const indices = [.08, .25, .42, .58, .75, .92].map(k => Math.min(n - 1, Math.round(k * n)));
  const pairs = [];
  for (const i of indices) {
    const ref = `verify-ref-${String(i).padStart(5, '0')}.jpg`;
    await shotAt(p, i / fps, path.join(TMP, ref));
    let dec = null;
    if (ff) {
      dec = `verify-dec-${String(i).padStart(5, '0')}.png`;
      await run(ff.ffmpeg, ['-v', 'error', '-y', '-ss', ((i - 0.5) / fps).toFixed(4), '-i', mp4, '-frames:v', '1',
        '-vf', 'scale=in_color_matrix=bt709:in_range=tv:flags=accurate_rnd+full_chroma_int', path.join(TMP, dec)]);
    }
    pairs.push({ i, t: +(i / fps).toFixed(3), ref: '/frames/' + ref, dec: dec && '/frames/' + dec });
  }
  await p.size(1280, 560, 1);
  await p.goto(`${BASE}/_scripts/verify.html`);
  const r = await p.js(`verify(${JSON.stringify({ pairs, video: ff ? null : '/out/' + MP4, fps })})`);
  if (r.error) throw new Error('verification impossible: ' + r.error);
  await p.screenshot(path.join(OUT, `verification-${LANG}.png`));
  const width = info ? info.width : r.width, height = info ? info.height : r.height, duration = info ? info.duration : r.duration;
  const issues = [];
  if (width !== 1920 || height !== 1080) issues.push(`size ${width} x ${height} instead of 1920 x 1080`);
  if (Math.abs(duration - n / fps) > 2 / fps) issues.push(`duration ${duration} s instead of ${(n / fps).toFixed(3)} s`);
  if (info && Math.abs(info.fps - fps) > 0.01) issues.push(`${info.fps} frames per second instead of ${fps}`);
  if (info && info.frames !== n) issues.push(`${info.frames} frames instead of ${n}`);
  const threshold = ff ? 3 : 5;
  for (const q of r.points) {
    if (q.black) issues.push(`black or empty frame at ${q.t} s`);
    if (q.meanDiff > threshold) issues.push(`mean difference of ${q.meanDiff} at ${q.t} s (expected below ${threshold})`);
  }
  if (!r.allDifferent) issues.push('two sampled frames are identical: the film looks frozen');
  console.log('verification: ' + JSON.stringify({ ffprobe: info, decoder: ff ? 'ffmpeg' : 'browser',
    points: r.points.map(q => ({ t: q.t, meanDiff: q.meanDiff, maxDiff: q.maxDiff, luminance: q.luminance })) }));
  console.log(`verification: out/verification-${LANG}.png, full-size decoded frame in out/`);
  if (issues.length) throw new Error('verification failed: ' + issues.join('; '));
  console.log(`verification OK: ${width} x ${height}, ${duration} s, ${info ? info.fps + ' fps, ' + info.frames + ' frames, ' : ''}max mean difference ${Math.max(...r.points.map(q => q.meanDiff))}`);
}

async function thumbnail(p) {
  if (!fs.existsSync(path.join(FILM, 'thumbnail.html'))) throw new Error('thumbnail.html not found in ' + FILM);
  await p.size(1280, 720, 1);
  await p.goto(`${BASE}/thumbnail.html?lang=${LANG}`);
  await p.waitFor('window.READY && true');
  await p.js('window.READY');
  await checkLoading(p);
  const jpg = path.join(OUT, `${NAME}-${LANG}-thumbnail.jpg`);
  await p.screenshot(jpg, { format: 'jpeg', quality: 92 });
  await p.screenshot(path.join(OUT, `${NAME}-${LANG}-thumbnail.png`));
  console.log(`thumbnail: out/${NAME}-${LANG}-thumbnail.jpg (${Math.round(fs.statSync(jpg).size / 1024)} KB, YouTube limit 2 MB) and .png`);
}

(async () => {
  if (!fs.existsSync(path.join(FILM, 'film.html'))) throw new Error('film.html not found in ' + FILM);
  const BRAND = path.join(FILM, 'brand.css');
  if (!fs.existsSync(BRAND)) throw new Error('brand.css not found in ' + FILM + ': copy template/brand.css and fill it in (references/brand.md)');
  if (fs.readFileSync(BRAND, 'utf8').includes('BRAND-NOT-FILLED')) throw new Error('brand.css is still the template: extract the project brand (references/brand.md), then remove the BRAND-NOT-FILLED line');
  fs.mkdirSync(OUT, { recursive: true });
  const t0 = Date.now();
  const srv = await server();
  const { browser, tab: p, close } = await launch();
  try {
    if (MODE === 'contact-sheet') await contactSheet(p, A4.split(',').filter(Boolean).map(Number));
    else if (MODE === 'video') { const fps = await renderFrames(browser, p); await encode(p, fps); }
    else if (MODE === 'encode') { await openFilm(p); await encode(p, await p.js('window.FPS')); }
    else if (MODE === 'verify') await verify(p);
    else if (MODE === 'poster') {
      if (!Number.isFinite(parseFloat(A4))) throw new Error('missing time: node render.js <folder> poster <t> [lang]');
      await openFilm(p);
      await shotAt(p, +A4, path.join(OUT, `${NAME}-${LANG}-poster.jpg`), 90);
      console.log(`poster: out/${NAME}-${LANG}-poster.jpg (t = ${A4} s)`);
    } else if (MODE === 'thumbnail') await thumbnail(p);
  } finally { await close(); srv.close(); }
  console.log(`${MODE} done in ${seconds(t0)}`);
})().catch(e => { console.error('FAILED ' + e.message); process.exit(1); });
