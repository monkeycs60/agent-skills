const { spawn } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const sleep = (ms) => new Promise(r => setTimeout(r, ms));
function avecDelai(promesse, ms, message) {
  let minuteur;
  const delai = new Promise((_, ko) => { minuteur = setTimeout(() => ko(new Error(message())), ms); });
  return Promise.race([promesse, delai]).finally(() => clearTimeout(minuteur));
}

function dansLePath(noms) {
  const dossiers = (process.env.PATH || '').split(path.delimiter).filter(Boolean);
  for (const n of noms) for (const d of dossiers) {
    const f = path.join(d, n);
    try { fs.accessSync(f, fs.constants.X_OK); if (fs.statSync(f).isFile()) return f; } catch (e) {}
  }
  return null;
}

function trouverChrome() {
  const env = process.env.CHROME_PATH;
  if (env) {
    if (!fs.existsSync(env)) throw new Error('CHROME_PATH ne mène à aucun fichier : ' + env);
    return env;
  }
  const home = os.homedir();
  let fixes = [];
  if (process.platform === 'darwin') {
    const apps = ['Google Chrome.app/Contents/MacOS/Google Chrome', 'Chromium.app/Contents/MacOS/Chromium',
      'Microsoft Edge.app/Contents/MacOS/Microsoft Edge', 'Brave Browser.app/Contents/MacOS/Brave Browser'];
    fixes = apps.flatMap(a => ['/Applications/' + a, path.join(home, 'Applications', a)]);
  } else if (process.platform === 'win32') {
    const L = process.env.LOCALAPPDATA || '';
    fixes = ['C:/Program Files/Google/Chrome/Application/chrome.exe', 'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
      L && path.join(L, 'Google/Chrome/Application/chrome.exe'), 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'];
  } else {
    const p = dansLePath(['google-chrome-stable', 'google-chrome', 'chromium', 'chromium-browser', 'microsoft-edge-stable', 'microsoft-edge', 'brave-browser']);
    if (p) return p;
    fixes = ['/opt/google/chrome/chrome', '/usr/lib/chromium/chromium', '/snap/bin/chromium'];
  }
  const f = fixes.filter(Boolean).find(c => fs.existsSync(c));
  if (!f) throw new Error('Chrome ou Chromium introuvable : installer Google Chrome (ou Chromium), ou donner le chemin du binaire dans CHROME_PATH');
  return f;
}

class Onglet {
  constructor(nav, sessionId) { this.nav = nav; this.sessionId = sessionId; this.ecoutes = []; }
  cmd(method, params = {}) { return this.nav.cmd(method, params, this.sessionId); }
  async js(expr) {
    const r = await this.cmd('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true });
    if (r.exceptionDetails) {
      const d = r.exceptionDetails;
      throw new Error((d.exception && d.exception.description) || d.text);
    }
    return r.result.value;
  }
  attendreEvenement(nom, ms = 30000) {
    return new Promise((ok, ko) => {
      const minuteur = setTimeout(() => { this.ecoutes = this.ecoutes.filter(x => x !== f); ko(new Error('délai dépassé en attendant ' + nom)); }, ms);
      const f = (m) => { if (m.method === nom) { clearTimeout(minuteur); this.ecoutes = this.ecoutes.filter(x => x !== f); ok(m.params); } };
      this.ecoutes.push(f);
    });
  }
  async aller(url, ms = 30000) {
    const charge = this.attendreEvenement('Page.loadEventFired', ms);
    const r = await this.cmd('Page.navigate', { url });
    if (r.errorText) { charge.catch(() => {}); throw new Error(`page inaccessible (${r.errorText}) : ${url}`); }
    await charge;
  }
  async attendre(expr, ms = 30000) {
    const fin = Date.now() + ms;
    let derniere = '';
    while (Date.now() < fin) {
      try { if (await this.js(expr)) return true; } catch (e) { derniere = e.message; }
      await sleep(200);
    }
    throw new Error('délai dépassé : ' + expr.slice(0, 80) + (derniere ? ' (' + derniere.split('\n')[0] + ')' : ''));
  }
  async taille(w, h, dsf = 1) {
    await this.cmd('Emulation.setDeviceMetricsOverride', { width: w, height: h, deviceScaleFactor: dsf, mobile: false });
  }
  async photo(fichier, opts = {}) {
    const r = await this.cmd('Page.captureScreenshot', {
      format: opts.format || 'png', quality: opts.quality, captureBeyondViewport: false, optimizeForSpeed: !!opts.rapide
    });
    const buf = Buffer.from(r.data, 'base64');
    if (fichier) fs.writeFileSync(fichier, buf);
    return buf;
  }
}

class Navigateur {
  constructor(proc, profil) {
    this.proc = proc; this.profil = profil; this.id = 0; this.attente = new Map(); this.onglets = new Map();
    this.journal = ''; this.fini = false;
    proc.stderr.on('data', (d) => { this.journal = (this.journal + d.toString()).slice(-3000); });
    let morceaux = [];
    proc.stdio[4].on('data', (buf) => {
      let debut = 0, i;
      while ((i = buf.indexOf(0, debut)) !== -1) {
        morceaux.push(buf.subarray(debut, i));
        const m = JSON.parse(Buffer.concat(morceaux).toString('utf8'));
        morceaux = []; debut = i + 1;
        this.recevoir(m);
      }
      if (debut < buf.length) morceaux.push(buf.subarray(debut));
    });
    proc.stdio[3].on('error', () => {});
    proc.on('exit', (code, signal) => {
      this.fini = true;
      const e = new Error(`le navigateur s'est arrêté (${signal || 'code ' + code})` + this.fin());
      for (const { ko } of this.attente.values()) ko(e);
      this.attente.clear();
    });
  }
  fin() {
    const l = this.journal.split('\n').filter(x => x.trim() && !/DevTools listening|dbus|Fontconfig/i.test(x)).slice(-4).join('\n');
    return l ? '\n' + l : '';
  }
  recevoir(m) {
    if (m.id !== undefined && this.attente.has(m.id)) {
      const { ok, ko, method } = this.attente.get(m.id); this.attente.delete(m.id);
      m.error ? ko(new Error(method + ' : ' + m.error.message)) : ok(m.result);
    } else if (m.method && m.sessionId && this.onglets.has(m.sessionId)) {
      this.onglets.get(m.sessionId).ecoutes.forEach(f => f(m));
    }
  }
  cmd(method, params = {}, sessionId) {
    if (this.fini) return Promise.reject(new Error("le navigateur est arrêté" + this.fin()));
    const id = ++this.id;
    const msg = { id, method, params };
    if (sessionId) msg.sessionId = sessionId;
    return new Promise((ok, ko) => {
      this.attente.set(id, { ok, ko, method });
      this.proc.stdio[3].write(JSON.stringify(msg) + '\0');
    });
  }
  async onglet({ isole = false } = {}) {
    const p = {};
    if (isole) p.browserContextId = (await this.cmd('Target.createBrowserContext')).browserContextId;
    const { targetId } = await this.cmd('Target.createTarget', { url: 'about:blank', ...p });
    const { sessionId } = await this.cmd('Target.attachToTarget', { targetId, flatten: true });
    const o = new Onglet(this, sessionId);
    this.onglets.set(sessionId, o);
    await o.cmd('Page.enable');
    await o.cmd('Runtime.enable');
    return o;
  }
  async fermer() {
    if (!this.fini) {
      const sortie = new Promise(r => this.proc.once('exit', r));
      this.cmd('Browser.close').catch(() => {});
      await avecDelai(sortie, 3000, () => '').catch(() => {});
      if (!this.fini) { this.proc.kill('SIGKILL'); await avecDelai(sortie, 1000, () => '').catch(() => {}); }
    }
    for (let i = 0; i < 5; i++) {
      try { fs.rmSync(this.profil, { recursive: true, force: true }); break; } catch (e) { await sleep(300); }
    }
  }
}

const ouverts = new Set();
let gardes = false;
function garder() {
  if (gardes) return;
  gardes = true;
  process.on('exit', () => { for (const p of ouverts) try { p.kill('SIGKILL'); } catch (e) {} });
  for (const s of ['SIGINT', 'SIGTERM', 'SIGHUP']) process.once(s, () => process.exit(130));
}

const ROOT = typeof process.getuid === 'function' && process.getuid() === 0;
async function lancer({ largeur = 1920, hauteur = 1080 } = {}, sansBac = ROOT || process.env.CHROME_NO_SANDBOX === '1') {
  const bin = trouverChrome();
  const profil = fs.mkdtempSync(path.join(os.tmpdir(), 'explainer-video-chrome-'));
  const args = [
    '--headless=new', '--remote-debugging-pipe', '--user-data-dir=' + profil,
    '--no-first-run', '--no-default-browser-check', '--disable-extensions', '--disable-component-update', '--disable-sync',
    '--disable-default-apps', '--password-store=basic', '--use-mock-keychain', '--disable-dev-shm-usage',
    '--hide-scrollbars', '--mute-audio', '--force-color-profile=srgb', '--font-render-hinting=none',
    '--disable-background-timer-throttling', '--disable-renderer-backgrounding', '--disable-backgrounding-occluded-windows',
    '--window-size=' + largeur + ',' + hauteur
  ];
  if (sansBac) args.push('--no-sandbox');
  const proc = spawn(bin, args, { stdio: ['ignore', 'ignore', 'pipe', 'pipe', 'pipe'] });
  const erreurLancement = new Promise((_, ko) => proc.once('error', (e) => ko(new Error(`impossible de lancer ${bin} : ${e.message}`))));
  garder(); ouverts.add(proc); proc.once('exit', () => ouverts.delete(proc));
  const nav = new Navigateur(proc, profil);
  try {
    const v = await avecDelai(Promise.race([nav.cmd('Browser.getVersion'), erreurLancement]), 30000,
      () => 'le navigateur ne répond pas après 30 s' + nav.fin());
    nav.version = v.product; nav.chemin = bin;
  } catch (e) {
    await nav.fermer();
    if (!sansBac && /sandbox/i.test(nav.journal)) {
      console.warn('ATTENTION bac à sable du navigateur indisponible (conteneur ?) : relance avec --no-sandbox ; CHROME_NO_SANDBOX=1 évite ce détour');
      return lancer({ largeur, hauteur }, true);
    }
    throw e;
  }
  const onglet = await nav.onglet();
  return { nav, onglet, fermer: () => nav.fermer() };
}

module.exports = { lancer, sleep, trouverChrome, dansLePath };
