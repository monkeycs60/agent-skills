const { spawn } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const sleep = (ms) => new Promise(r => setTimeout(r, ms));
function withTimeout(promise, ms, message) {
  let timer;
  const timeout = new Promise((_, reject) => { timer = setTimeout(() => reject(new Error(message())), ms); });
  return Promise.race([promise, timeout]).finally(() => clearTimeout(timer));
}

function inPath(names) {
  const dirs = (process.env.PATH || '').split(path.delimiter).filter(Boolean);
  for (const n of names) for (const d of dirs) {
    const f = path.join(d, n);
    try { fs.accessSync(f, fs.constants.X_OK); if (fs.statSync(f).isFile()) return f; } catch (e) {}
  }
  return null;
}

function findChrome() {
  const env = process.env.CHROME_PATH;
  if (env) {
    if (!fs.existsSync(env)) throw new Error('CHROME_PATH points to no file: ' + env);
    return env;
  }
  const home = os.homedir();
  let fixed = [];
  if (process.platform === 'darwin') {
    const apps = ['Google Chrome.app/Contents/MacOS/Google Chrome', 'Chromium.app/Contents/MacOS/Chromium',
      'Microsoft Edge.app/Contents/MacOS/Microsoft Edge', 'Brave Browser.app/Contents/MacOS/Brave Browser'];
    fixed = apps.flatMap(a => ['/Applications/' + a, path.join(home, 'Applications', a)]);
  } else if (process.platform === 'win32') {
    const L = process.env.LOCALAPPDATA || '';
    fixed = ['C:/Program Files/Google/Chrome/Application/chrome.exe', 'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
      L && path.join(L, 'Google/Chrome/Application/chrome.exe'), 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'];
  } else {
    const p = inPath(['google-chrome-stable', 'google-chrome', 'chromium', 'chromium-browser', 'microsoft-edge-stable', 'microsoft-edge', 'brave-browser']);
    if (p) return p;
    fixed = ['/opt/google/chrome/chrome', '/usr/lib/chromium/chromium', '/snap/bin/chromium'];
  }
  const f = fixed.filter(Boolean).find(c => fs.existsSync(c));
  if (!f) throw new Error('Chrome or Chromium not found: install Google Chrome (or Chromium), or give the binary path in CHROME_PATH');
  return f;
}

class Tab {
  constructor(browser, sessionId) { this.browser = browser; this.sessionId = sessionId; this.listeners = []; }
  cmd(method, params = {}) { return this.browser.cmd(method, params, this.sessionId); }
  async js(expr) {
    const r = await this.cmd('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true });
    if (r.exceptionDetails) {
      const d = r.exceptionDetails;
      throw new Error((d.exception && d.exception.description) || d.text);
    }
    return r.result.value;
  }
  waitForEvent(name, ms = 30000) {
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => { this.listeners = this.listeners.filter(x => x !== f); reject(new Error('timed out waiting for ' + name)); }, ms);
      const f = (m) => { if (m.method === name) { clearTimeout(timer); this.listeners = this.listeners.filter(x => x !== f); resolve(m.params); } };
      this.listeners.push(f);
    });
  }
  async goto(url, ms = 30000) {
    const loaded = this.waitForEvent('Page.loadEventFired', ms);
    const r = await this.cmd('Page.navigate', { url });
    if (r.errorText) { loaded.catch(() => {}); throw new Error(`page unreachable (${r.errorText}): ${url}`); }
    await loaded;
  }
  async waitFor(expr, ms = 30000) {
    const end = Date.now() + ms;
    let last = '';
    while (Date.now() < end) {
      try { if (await this.js(expr)) return true; } catch (e) { last = e.message; }
      await sleep(200);
    }
    throw new Error('timed out: ' + expr.slice(0, 80) + (last ? ' (' + last.split('\n')[0] + ')' : ''));
  }
  async size(w, h, dsf = 1) {
    await this.cmd('Emulation.setDeviceMetricsOverride', { width: w, height: h, deviceScaleFactor: dsf, mobile: false });
  }
  async screenshot(file, opts = {}) {
    const r = await this.cmd('Page.captureScreenshot', {
      format: opts.format || 'png', quality: opts.quality, captureBeyondViewport: false, optimizeForSpeed: !!opts.fast
    });
    const buf = Buffer.from(r.data, 'base64');
    if (file) fs.writeFileSync(file, buf);
    return buf;
  }
}

class Browser {
  constructor(proc, profile) {
    this.proc = proc; this.profile = profile; this.id = 0; this.pending = new Map(); this.tabs = new Map();
    this.log = ''; this.stopped = false;
    proc.stderr.on('data', (d) => { this.log = (this.log + d.toString()).slice(-3000); });
    let chunks = [];
    proc.stdio[4].on('data', (buf) => {
      let start = 0, i;
      while ((i = buf.indexOf(0, start)) !== -1) {
        chunks.push(buf.subarray(start, i));
        const m = JSON.parse(Buffer.concat(chunks).toString('utf8'));
        chunks = []; start = i + 1;
        this.receive(m);
      }
      if (start < buf.length) chunks.push(buf.subarray(start));
    });
    proc.stdio[3].on('error', () => {});
    proc.on('exit', (code, signal) => {
      this.stopped = true;
      const e = new Error(`the browser stopped (${signal || 'code ' + code})` + this.tail());
      for (const { reject } of this.pending.values()) reject(e);
      this.pending.clear();
    });
  }
  tail() {
    const l = this.log.split('\n').filter(x => x.trim() && !/DevTools listening|dbus|Fontconfig/i.test(x)).slice(-4).join('\n');
    return l ? '\n' + l : '';
  }
  receive(m) {
    if (m.id !== undefined && this.pending.has(m.id)) {
      const { resolve, reject, method } = this.pending.get(m.id); this.pending.delete(m.id);
      m.error ? reject(new Error(method + ': ' + m.error.message)) : resolve(m.result);
    } else if (m.method && m.sessionId && this.tabs.has(m.sessionId)) {
      this.tabs.get(m.sessionId).listeners.forEach(f => f(m));
    }
  }
  cmd(method, params = {}, sessionId) {
    if (this.stopped) return Promise.reject(new Error('the browser is stopped' + this.tail()));
    const id = ++this.id;
    const msg = { id, method, params };
    if (sessionId) msg.sessionId = sessionId;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject, method });
      this.proc.stdio[3].write(JSON.stringify(msg) + '\0');
    });
  }
  async tab({ isolated = false } = {}) {
    const p = {};
    if (isolated) p.browserContextId = (await this.cmd('Target.createBrowserContext')).browserContextId;
    const { targetId } = await this.cmd('Target.createTarget', { url: 'about:blank', ...p });
    const { sessionId } = await this.cmd('Target.attachToTarget', { targetId, flatten: true });
    const t = new Tab(this, sessionId);
    this.tabs.set(sessionId, t);
    await t.cmd('Page.enable');
    await t.cmd('Runtime.enable');
    return t;
  }
  async close() {
    if (!this.stopped) {
      const exited = new Promise(r => this.proc.once('exit', r));
      this.cmd('Browser.close').catch(() => {});
      await withTimeout(exited, 3000, () => '').catch(() => {});
      if (!this.stopped) { this.proc.kill('SIGKILL'); await withTimeout(exited, 1000, () => '').catch(() => {}); }
    }
    for (let i = 0; i < 5; i++) {
      try { fs.rmSync(this.profile, { recursive: true, force: true }); break; } catch (e) { await sleep(300); }
    }
  }
}

const running = new Set();
let guarded = false;
function guard() {
  if (guarded) return;
  guarded = true;
  process.on('exit', () => { for (const p of running) try { p.kill('SIGKILL'); } catch (e) {} });
  for (const s of ['SIGINT', 'SIGTERM', 'SIGHUP']) process.once(s, () => process.exit(130));
}

const ROOT = typeof process.getuid === 'function' && process.getuid() === 0;
async function launch({ width = 1920, height = 1080 } = {}, noSandbox = ROOT || process.env.CHROME_NO_SANDBOX === '1') {
  const bin = findChrome();
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'explainer-video-chrome-'));
  const args = [
    '--headless=new', '--remote-debugging-pipe', '--user-data-dir=' + profile,
    '--no-first-run', '--no-default-browser-check', '--disable-extensions', '--disable-component-update', '--disable-sync',
    '--disable-default-apps', '--password-store=basic', '--use-mock-keychain', '--disable-dev-shm-usage',
    '--hide-scrollbars', '--mute-audio', '--force-color-profile=srgb', '--font-render-hinting=none',
    '--disable-background-timer-throttling', '--disable-renderer-backgrounding', '--disable-backgrounding-occluded-windows',
    '--window-size=' + width + ',' + height
  ];
  if (noSandbox) args.push('--no-sandbox');
  const proc = spawn(bin, args, { stdio: ['ignore', 'ignore', 'pipe', 'pipe', 'pipe'] });
  const launchError = new Promise((_, reject) => proc.once('error', (e) => reject(new Error(`cannot launch ${bin}: ${e.message}`))));
  guard(); running.add(proc); proc.once('exit', () => running.delete(proc));
  const browser = new Browser(proc, profile);
  try {
    const v = await withTimeout(Promise.race([browser.cmd('Browser.getVersion'), launchError]), 30000,
      () => 'the browser did not answer within 30 s' + browser.tail());
    browser.version = v.product; browser.path = bin;
  } catch (e) {
    await browser.close();
    if (!noSandbox && /sandbox/i.test(browser.log)) {
      console.warn('WARNING browser sandbox unavailable (container?): retrying with --no-sandbox; CHROME_NO_SANDBOX=1 skips this detour');
      return launch({ width, height }, true);
    }
    throw e;
  }
  const tab = await browser.tab();
  return { browser, tab, close: () => browser.close() };
}

module.exports = { launch, sleep, findChrome, inPath };
