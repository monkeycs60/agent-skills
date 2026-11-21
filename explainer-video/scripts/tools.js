const fs = require('fs');
const path = require('path');
const http = require('http');
const { execFile } = require('child_process');
const { inPath } = require('./cdp');

const output = (bin, args) => new Promise(ok => execFile(bin, args, { maxBuffer: 8 * 1024 * 1024 }, (e, so, se) => ok(e ? null : so + se)));

let memo;
async function findFfmpeg({ libx264 = true } = {}) {
  if (memo === undefined) {
    const ff = process.env.FFMPEG_PATH || inPath(['ffmpeg']) || ['/opt/homebrew/bin/ffmpeg', '/usr/local/bin/ffmpeg'].find(f => fs.existsSync(f));
    if (!ff) memo = null;
    else {
      const enc = await output(ff, ['-hide_banner', '-encoders']);
      const sibling = path.join(path.dirname(ff), process.platform === 'win32' ? 'ffprobe.exe' : 'ffprobe');
      const probe = process.env.FFPROBE_PATH || (fs.existsSync(sibling) ? sibling : inPath(['ffprobe']));
      memo = enc === null ? null : { ffmpeg: ff, ffprobe: probe || null, libx264: /\blibx264\b/.test(enc) };
    }
  }
  if (!memo || (libx264 && !memo.libx264)) return null;
  return memo;
}

async function diagnose() {
  const lines = [], blockers = [];
  const ok = (b, text, help) => { lines.push(`  ${b ? '✓' : '✗'} ${text}` + (!b && help ? `\n      ${help}` : '')); return b; };
  const major = +process.versions.node.split('.')[0];
  if (!ok(major >= 20, `Node ${process.versions.node} (20 or later required)`, 'install Node 20 or later: https://nodejs.org')) blockers.push('Node');
  let webcodecs = false;
  try {
    const { launch } = require('./cdp');
    const srv = http.createServer((q, r) => { r.setHeader('content-type', 'text/html'); r.end('<!doctype html><title>diagnostic</title>'); });
    await new Promise(r => srv.listen(0, '127.0.0.1', r));
    const { browser, tab: p, close } = await launch();
    try {
      ok(true, `browser: ${browser.path} (${browser.version}), headless launch OK`);
      await p.goto('http://127.0.0.1:' + srv.address().port + '/');
      webcodecs = await p.js(`(async () => { try { return (await VideoEncoder.isConfigSupported({ codec: 'avc1.640028', width: 1920, height: 1080,
        bitrate: 6e6, framerate: 60, avc: { format: 'avc' } })).supported; } catch (e) { return false; } })()`);
    } finally { await close(); srv.close(); }
  } catch (e) {
    ok(false, 'browser: ' + e.message.split('\n')[0],
      'Linux: install Google Chrome or Chromium (apt install chromium); macOS: install Google Chrome; or CHROME_PATH=/path/to/binary');
    blockers.push('browser');
  }
  const ff = await findFfmpeg({ libx264: false });
  if (ff && ff.libx264) ok(true, `ffmpeg: ${ff.ffmpeg} (libx264): fast encoding and frame-by-frame verification`);
  else ok(false, ff ? `ffmpeg: ${ff.ffmpeg} without libx264, not used for encoding` : 'ffmpeg: missing (optional)',
    'optional but recommended: apt install ffmpeg, or brew install ffmpeg; otherwise FFMPEG_PATH=/path/to/ffmpeg');
  if (ff) ok(!!ff.ffprobe, `ffprobe: ${ff.ffprobe || 'missing'}`, 'ships with ffmpeg, checks duration and frame rate');
  if (!blockers.includes('browser')) {
    ok(webcodecs, `H.264 encoding in the browser (WebCodecs): ${webcodecs ? 'available' : 'unavailable'}`,
      ff && ff.libx264 ? 'does not matter: ffmpeg encodes' : 'install ffmpeg, or Google Chrome, which encodes H.264');
    if (!webcodecs && !(ff && ff.libx264)) blockers.push('H.264 encoder');
  }
  console.log('explainer-video: tools\n' + lines.join('\n'));
  if (blockers.length) { console.log(`\nMissing: ${blockers.join(', ')}. No video is possible until this is fixed.`); return false; }
  const encoder = ff && ff.libx264 ? 'ffmpeg' : 'the browser (WebCodecs)';
  console.log(`\nReady: encoding with ${encoder}. Full example film: node ${path.join(__dirname, 'example.js')}`);
  return true;
}

if (require.main === module) diagnose().then(b => process.exit(b ? 0 : 1)).catch(e => { console.error('FAILED ' + e.message); process.exit(1); });

module.exports = { findFfmpeg };
