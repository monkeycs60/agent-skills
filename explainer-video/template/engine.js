const P = { snap:{w:34,z:.74}, ui:{w:24,z:.8}, def:{w:15,z:.86}, heavy:{w:10.5,z:1}, play:{w:19,z:.5}, cam:{w:5.4,z:1}, soft:{w:8,z:1} };
function S(t, p) {
  if (t <= 0) return 0;
  const w = p.w, z = p.z;
  if (z < 1) { const wd = w * Math.sqrt(1 - z*z); return 1 - Math.exp(-z*w*t) * (Math.cos(wd*t) + (z*w/wd) * Math.sin(wd*t)); }
  return 1 - Math.exp(-w*t) * (1 + w*t);
}
const sp = (t, t0, p = 'ui') => S(t - t0, P[p]);
const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
function tr(t, v0, keys) { let v = v0, prev = v0; for (const [ti, vi, p] of keys) { v += (vi - prev) * S(t - ti, P[p || 'def']); prev = vi; } return v; }
function trA(t, a0, keys) { return a0.map((c, i) => tr(t, c, keys.map(k => [k[0], k[1][i], k[2]]))); }
const io = (t, a, b, pa = 'ui', pb = 'ui') => clamp(sp(t, a, pa)) * (1 - clamp(sp(t, b, pb)));
const imp = (t, t0, amp, k = 9, w = 24) => { const d = t - t0; return d > 0 ? amp * Math.exp(-k*d) * Math.sin(w*d) : 0; };
const rgba = (c) => `rgba(${Math.round(clamp(c[0],0,255))},${Math.round(clamp(c[1],0,255))},${Math.round(clamp(c[2],0,255))},${clamp(c[3] === undefined ? 1 : c[3]).toFixed(3)})`;
const $ = (id) => document.getElementById(id);

function put(el, o) {
  const x = o.x || 0, y = o.y || 0, s = o.s === undefined ? 1 : o.s, r = o.r || 0;
  el.style.transform = `translate(${x.toFixed(2)}px,${y.toFixed(2)}px) scale(${s.toFixed(4)}) rotate(${r.toFixed(2)}deg)`;
  el.style.opacity = clamp(o.o === undefined ? 1 : o.o).toFixed(3);
  const b = o.blur || 0; el.style.filter = b > .05 ? `blur(${b.toFixed(2)}px)` : 'none';
  el.style.visibility = (o.o !== undefined && o.o <= 0.001) ? 'hidden' : 'visible';
}
function enter(t, tin, tout, o = {}) {
  const a = sp(t, tin, o.pin || 'def'), b = sp(t, tout, o.pout || 'ui');
  const dy = o.dy === undefined ? 40 : o.dy, dyo = o.dyo === undefined ? -24 : o.dyo;
  const dx = o.dx || 0, dxo = o.dxo || 0;
  return { x: dx * (1 - a) + dxo * b, y: dy * (1 - a) + dyo * b, s: (o.s0 || .94) + (1 - (o.s0 || .94)) * a - (1 - (o.so || .97)) * b,
           o: clamp(a) * (1 - clamp(b)), blur: 8 * (1 - clamp(a)) + 10 * clamp(b) };
}
function words(el) {
  const txt = el.textContent; el.textContent = '';
  txt.split(' ').forEach((w, i, arr) => {
    const o = document.createElement('span'); o.className = 'w';
    const n = document.createElement('span'); n.textContent = w; o.appendChild(n); el.appendChild(o);
    if (i < arr.length - 1) el.appendChild(document.createTextNode(' '));
  });
  return [...el.querySelectorAll('.w > span')];
}

const brandVar = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const _pix = Object.assign(document.createElement('canvas'), { width: 1, height: 1 }).getContext('2d', { willReadFrequently: true });
function color(v, a = 1) {
  const d = document.createElement('i'); d.style.color = `var(${v})`; document.documentElement.appendChild(d);
  const c = getComputedStyle(d).color; d.remove();
  _pix.clearRect(0, 0, 1, 1); _pix.fillStyle = c; _pix.fillRect(0, 0, 1, 1);
  const p = _pix.getImageData(0, 0, 1, 1).data;
  return [p[0], p[1], p[2], a];
}
const alpha = (c, a) => rgba([c[0], c[1], c[2], a]);
function logos() {
  document.querySelectorAll('img[data-logo]').forEach(img => {
    const m = brandVar('--logo-' + img.dataset.logo).match(/url\(\s*["']?([^"')]+)/);
    if (m) { img.src = m[1]; return; }
    const s = document.createElement('div'), h = parseFloat(img.style.height) || 44;
    s.className = img.className; s.id = img.id; s.style.cssText = img.style.cssText;
    Object.assign(s.style, { height: 'auto', fontFamily: 'var(--font-title)', fontWeight: 900, fontSize: (h * .9) + 'px', lineHeight: h + 'px',
      letterSpacing: '-.03em', whiteSpace: 'nowrap', color: img.dataset.logo === 'dark' ? '#fff' : 'var(--ink)' });
    s.textContent = brandVar('--name').replace(/^["']|["']$/g, '');
    img.replaceWith(s);
  });
}
const brandFonts = () => { const t = brandVar('--font-title'), b = brandVar('--font-body');
  return [`900 60px ${t}`, `800 60px ${t}`, `700 60px ${t}`, `500 30px ${b}`, `700 30px ${b}`]; };

function startFilm({ duration, fps = 60, init, paint, fonts = [], waitFor = [] }) {
  const q = new URLSearchParams(location.search);
  const RENDER = q.has('render');
  if (RENDER) document.body.classList.add('render');
  window.DURATION = duration; window.FPS = fps;
  // wait two frames: without them, the screenshot shows the styles of the previous frame
  window.seek = (t) => { paint(t); return new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))); };
  window.READY = (async () => {
    await Promise.all(fonts.map(f => document.fonts.load(f)));
    await document.fonts.ready;
    await Promise.all([...document.images].map(i => i.decode().catch(() => {})));
    await Promise.all(waitFor);
    init(); paint(0);
    return true;
  })();
  if (RENDER) return;
  const st = $('stage'), sc = $('scrub'), tc = $('tc'), pp = $('pp');
  sc.max = duration;
  const fit = () => {
    const k = Math.min(innerWidth / 1920, (innerHeight - 56) / 1080);
    st.style.transform = `scale(${k})`;
    st.style.left = ((innerWidth - 1920 * k) / 2) + 'px'; st.style.top = ((innerHeight - 56 - 1080 * k) / 2) + 'px';
  };
  addEventListener('resize', fit); fit();
  const PLAY = q.get('lang') === 'fr' ? 'Lecture' : 'Play';
  let playing = true, t0 = performance.now(), tNow = +(q.get('t') || 0);
  if (tNow) { playing = false; pp.textContent = PLAY; }
  pp.onclick = () => { playing = !playing; pp.textContent = playing ? 'Pause' : PLAY; t0 = performance.now() - tNow * 1000; };
  sc.oninput = () => { tNow = +sc.value; t0 = performance.now() - tNow * 1000; paint(tNow); tc.textContent = tNow.toFixed(2) + ' s'; };
  window.READY.then(() => {
    t0 = performance.now() - tNow * 1000;
    const loop = (now) => {
      if (playing) { tNow = ((now - t0) / 1000) % duration; paint(tNow); sc.value = tNow; tc.textContent = tNow.toFixed(2) + ' s'; }
      requestAnimationFrame(loop);
    };
    paint(tNow); requestAnimationFrame(loop);
  });
}
