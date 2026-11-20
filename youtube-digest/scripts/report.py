#!/usr/bin/env python3
import argparse
import base64
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
import urllib.request
from pathlib import Path

DATA = Path.home() / ".local" / "share" / "youtube"
CACHE = Path.home() / ".cache" / "youtube-skill"
MERMAID = CACHE / "mermaid.min.js"
CHROME_NAMES = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome")
CHROME_APPS = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
)
MERMAID_CDN = "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"
VERDICTS = {"regarder": ("À regarder", "go"), "survoler": ("À survoler", "mid"), "passer": ("À passer", "stop")}
COMMENT_KINDS = {
    "correction": "Correction", "alerte": "Mise en garde", "alternative": "Alternative",
    "question": "Question ouverte", "avis": "Avis",
}


def esc(text):
    return html.escape(str(text or ""), quote=True)


def inline(text):
    out = esc(text)
    out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
    out = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"(?<![\w*])\*([^*\s][^*]*)\*(?![\w*])", r"<em>\1</em>", out)
    return re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2" target="_blank" rel="noopener">\1</a>', out)


def linkify(text):
    return re.sub(r"(https?://[^\s<]+)", r'<a href="\1" target="_blank" rel="noopener">\1</a>', esc(text))


def clock(s):
    s = int(s)
    h, m, sec = s // 3600, s % 3600 // 60, s % 60
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m:02d}:{sec:02d}"


def slug(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "video"


def parse_transcript(path):
    doc = {"title": "", "meta": "", "link": "", "source": "", "links": [], "description": "",
           "blocks": [], "comments": []}
    section = None
    desc = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# ") and not doc["title"]:
            doc["title"] = line[2:].strip()
        elif line.startswith("- Chaîne : ") and section is None:
            doc["meta"] = line[2:].strip()
        elif line.startswith("- Lien : ") and section is None:
            doc["link"] = line[9:].strip()
        elif line.startswith("- Texte : ") and section is None:
            doc["source"] = line[10:].strip()
        elif line.startswith("## "):
            section = line[3:].split(" (")[0].strip()
        elif section == "Liens utiles" and line.startswith("- "):
            kind, _, url = line[2:].partition(" : ")
            doc["links"].append((kind, url.strip()))
        elif section == "Description":
            desc.append(line)
        elif section == "Transcription":
            m = re.match(r"^(###|\*\*)\s*\[(\d[\d:]*)\]\(https?://\S+?t=(\d+)\)(?:\*\*)?\s*(.*)$", line)
            if m:
                doc["blocks"].append(("h" if m.group(1) == "###" else "p", int(m.group(3)), m.group(4)))
        elif section == "Commentaires les plus appréciés" and line.startswith("- **"):
            m = re.match(r"^- \*\*(.+?)\*\* \((.*?)\) : (.*)$", line)
            if m:
                doc["comments"].append(m.groups())
    doc["description"] = "\n".join(desc).strip()
    return doc


def find_chrome():
    if os.environ.get("CHROME_PATH") and Path(os.environ["CHROME_PATH"]).exists():
        return os.environ["CHROME_PATH"]
    for name in CHROME_NAMES:
        if shutil.which(name):
            return shutil.which(name)
    for app in CHROME_APPS:
        for base in ("", str(Path.home())):
            if Path(base + app).exists():
                return base + app
    return None


def open_in_browser(path):
    chrome = find_chrome()
    if chrome:
        cmd = [chrome, str(path)]
    elif sys.platform == "darwin":
        cmd = ["open", str(path)]
    elif shutil.which("xdg-open"):
        cmd = ["xdg-open", str(path)]
    else:
        return False
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    return True


def ensure_mermaid():
    if MERMAID.exists():
        return True
    CACHE.mkdir(parents=True, exist_ok=True)
    try:
        MERMAID.write_bytes(urllib.request.urlopen(MERMAID_CDN, timeout=30).read())
        return True
    except Exception as e:
        print(f"Mermaid indisponible ({e}) : schémas laissés en source.", file=sys.stderr)
        return False


def render_mermaid(sources):
    chrome = find_chrome()
    if not sources or not chrome or not ensure_mermaid():
        return [None] * len(sources)
    payload = json.dumps(sources).replace("<", "\\u003c")
    page = f"""<!doctype html><html><body><div id="out"></div>
<script src="{MERMAID.as_uri()}"></script>
<script>
mermaid.initialize({{ startOnLoad: false, securityLevel: 'strict', theme: 'base', fontFamily: 'system-ui, sans-serif',
  themeVariables: {{ primaryColor: '#efeaff', primaryBorderColor: '#7c5cff', primaryTextColor: '#1d1b26',
    lineColor: '#6b6880', secondaryColor: '#e6f4ff', tertiaryColor: '#f6f5fa', fontSize: '15px' }} }});
(async () => {{
  const out = [];
  for (const [i, src] of {payload}.entries()) {{
    try {{ out.push((await mermaid.render('schema' + i, src)).svg) }} catch (e) {{ out.push(null) }}
  }}
  document.getElementById('out').textContent = JSON.stringify(out);
}})();
</script></body></html>"""
    with tempfile.TemporaryDirectory(prefix="youtube-mermaid-") as tmp:
        page_path = Path(tmp) / "render.html"
        page_path.write_text(page, encoding="utf-8")
        r = subprocess.run([chrome, "--headless=new", "--disable-gpu", f"--user-data-dir={tmp}/profile",
                            "--allow-file-access-from-files", "--virtual-time-budget=15000", "--dump-dom",
                            page_path.as_uri()], capture_output=True, text=True, timeout=90)
    m = re.search(r'<div id="out">(.*?)</div>', r.stdout, re.S)
    try:
        svgs = json.loads(html.unescape(m.group(1))) if m else []
    except json.JSONDecodeError:
        svgs = []
    return svgs if len(svgs) == len(sources) else [None] * len(sources)


def thumbnail(video_id, size="hqdefault"):
    try:
        data = urllib.request.urlopen(f"https://i.ytimg.com/vi/{video_id}/{size}.jpg", timeout=8).read()
        return "data:image/jpeg;base64," + base64.b64encode(data).decode()
    except Exception:
        return None


def host_label(url):
    return re.sub(r"^https?://(www\.)?", "", url).split("/")[0]


def likes_label(comment):
    return f" · {int(comment['likes'])} j’aime" if comment.get("likes") is not None else ""


def fiche_sections(fiche, video_id, svgs, prefix=""):
    ts = lambda t: f'<a class="ts" href="https://youtu.be/{video_id}?t={int(t)}" target="_blank" rel="noopener">{clock(t)}</a>'
    schemas = fiche.get("schemas") or []
    sections = []

    verdict = fiche.get("verdict") or {}
    label, tone = VERDICTS.get(verdict.get("avis"), ("Verdict", "mid"))
    moments = "".join(f'<li>{ts(m["t"])} {inline(m.get("label"))}</li>' for m in verdict.get("moments") or [])
    sections.append((f"{prefix}verdict", "Verdict", f"""
<div class="verdict {tone}"><span class="badge">{label}</span><p>{inline(verdict.get("texte"))}</p>
{f'<ul class="moments">{moments}</ul>' if moments else ''}</div>"""))

    if fiche.get("points_cles"):
        cards = "".join(f'<li class="card">{ts(p["t"]) if p.get("t") is not None else ""}<h3>{inline(p.get("titre"))}</h3>'
                        f'<p>{inline(p.get("texte"))}</p></li>' for p in fiche["points_cles"])
        sections.append((f"{prefix}points", "Points clés", f'<ol class="points">{cards}</ol>'))

    if schemas:
        figs = []
        for s, svg in zip(schemas, svgs):
            body = f'<div class="svg">{svg}</div>' if svg else f'<pre class="mermaid-src">{esc(s["mermaid"])}</pre>'
            caption = f'<figcaption>{inline(s.get("legende"))}</figcaption>' if s.get("legende") else ""
            figs.append(f'<figure class="schema"><h3>{inline(s.get("titre"))}</h3>{body}{caption}</figure>')
        sections.append((f"{prefix}schemas", "Schémas", "".join(figs)))

    if fiche.get("etapes"):
        steps = []
        for e in fiche["etapes"]:
            code = (f'<div class="codeblock"><button class="copy" type="button">Copier</button>'
                    f'<pre><code>{esc(e["code"])}</code></pre></div>') if e.get("code") else ""
            when = ts(e["t"]) if e.get("t") is not None else ""
            steps.append(f'<li><div class="step-head"><h3>{inline(e.get("titre"))}</h3>{when}</div>'
                         f'<p>{inline(e.get("texte"))}</p>{code}</li>')
        sections.append((f"{prefix}etapes", "Pas à pas", f'<ol class="steps">{"".join(steps)}</ol>'))

    if fiche.get("ressources"):
        items = "".join(
            f'<li><a href="{esc(r["url"])}" target="_blank" rel="noopener">{inline(r.get("titre") or r["url"])}</a>'
            + ('<span class="lu">lu</span>' if r.get("lu") else "")
            + f'<span class="host">{esc(host_label(r["url"]))}</span><p>{inline(r.get("apport"))}</p></li>'
            for r in fiche["ressources"])
        sections.append((f"{prefix}ressources", "Ressources", f'<ul class="resources">{items}</ul>'))

    com = fiche.get("commentaires") or {}
    points = "".join(
        f'<li><span class="kind {esc(c.get("type"))}">{COMMENT_KINDS.get(c.get("type"), "Avis")}</span>'
        f'<p>{inline(c.get("texte"))}</p><span class="who">{esc(c.get("auteur"))}{likes_label(c)}</span></li>'
        for c in com.get("points") or [])
    sections.append((f"{prefix}commentaires", "Ce que disent les commentaires",
                     f'<p class="lead">{inline(com.get("resume") or "Commentaires non analysés.")}</p>'
                     f'{f"<ul class=comments>{points}</ul>" if points else ""}'))

    if fiche.get("angles_morts"):
        blind = "".join(f'<li>{ts(a["t"]) if a.get("t") is not None else ""} {inline(a.get("texte"))}</li>'
                        for a in fiche["angles_morts"])
        sections.append((f"{prefix}angles", "Angles morts", f'<ul class="blind">{blind}</ul>'))

    return sections


def build(video_id):
    folder = DATA / video_id
    fiche_path = folder / "fiche.json"
    if not fiche_path.exists():
        sys.exit(f"{fiche_path} manquant : écrire la fiche avant le rapport.")
    fiche = json.loads(fiche_path.read_text(encoding="utf-8"))
    doc = parse_transcript(folder / "transcript.md")
    ts = lambda t: f'<a class="ts" href="https://youtu.be/{video_id}?t={int(t)}" target="_blank" rel="noopener">{clock(t)}</a>'

    svgs = render_mermaid([sc["mermaid"] for sc in fiche.get("schemas") or []])
    sections = fiche_sections(fiche, video_id, svgs)

    transcript = []
    for kind, start, text in doc["blocks"]:
        transcript.append(f'<h3>{ts(start)} {esc(text)}</h3>' if kind == "h" else f'<p>{ts(start)} {esc(text)}</p>')
    words = sum(len(t.split()) for k, _, t in doc["blocks"] if k == "p")
    raw_comments = "".join(f'<li><strong>{esc(a)}</strong> <span class="who">{esc(tags)}</span><p>{esc(t)}</p></li>'
                           for a, tags, t in doc["comments"])
    annexes = (
        f'<details id="transcription"><summary>Transcription complète · {words} mots</summary>'
        f'<div class="transcript">{"".join(transcript)}</div></details>'
        f'<details><summary>Description de la vidéo</summary><div class="description">{linkify(doc["description"])}</div></details>'
        + (f'<details><summary>Les {len(doc["comments"])} commentaires les plus appréciés</summary>'
           f'<ul class="raw-comments">{raw_comments}</ul></details>' if raw_comments else "")
    )

    thumb = thumbnail(video_id)
    nav = "".join(f'<a href="#{sid}">{title}</a>' for sid, title, _ in sections) + '<a href="#transcription">Transcription</a>'
    body = "".join(f'<section id="{sid}"><h2>{title}</h2>{content}</section>' for sid, title, content in sections)
    page = f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(doc["title"])} · rapport</title>
<style>{CSS}</style></head>
<body><header class="hero">
{f'<img class="thumb" src="{thumb}" alt="">' if thumb else ''}
<div><p class="kicker">Rapport de vidéo</p><h1>{esc(doc["title"])}</h1>
<p class="meta">{esc(doc["meta"])}</p>
<p class="one-liner">{inline(fiche.get("en_une_phrase"))}</p>
<p class="links"><a href="{esc(doc["link"])}" target="_blank" rel="noopener">Ouvrir sur YouTube</a><span>{esc(doc["source"])}</span></p></div>
</header>
<nav>{nav}</nav>
<main>{body}<section class="annexes"><h2>Annexes</h2>{annexes}</section></main>
<script>{COPY_JS}</script>
</body></html>"""
    out = folder / "rapport.html"
    out.write_text(page, encoding="utf-8")
    return out, doc, sum(1 for s in svgs if s), sum(1 for s in svgs if not s)


CSS = """
:root{--bg:#f6f5f2;--panel:#fff;--ink:#1d1b26;--muted:#6b6880;--line:#e4e1ea;--accent:#6d4cff;--accent-soft:#efeaff;
--go:#1f8a5b;--go-soft:#e3f5ec;--mid:#b7791f;--mid-soft:#fbf1dc;--stop:#b4443c;--stop-soft:#f9e5e3;--code:#f2f0f7}
@media (prefers-color-scheme:dark){:root{--bg:#141519;--panel:#1c1d23;--ink:#ecebf2;--muted:#9a98ab;--line:#2c2d36;
--accent:#a48bff;--accent-soft:#2a2540;--go:#5fd19b;--go-soft:#173528;--mid:#f0b85a;--mid-soft:#3a2f17;--stop:#f08a80;--stop-soft:#3b1f1d;--code:#24252d}}
*{box-sizing:border-box}html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.6 system-ui,-apple-system,"Segoe UI",sans-serif}
a{color:var(--accent)}code{font:0.88em ui-monospace,SFMono-Regular,Menlo,monospace;background:var(--code);padding:.1em .35em;border-radius:5px}
.hero{display:flex;gap:28px;align-items:center;max-width:1040px;margin:0 auto;padding:40px 28px 20px}
.thumb{width:300px;border-radius:14px;flex:none;box-shadow:0 8px 30px rgba(0,0,0,.18)}
.kicker{margin:0;text-transform:uppercase;letter-spacing:.12em;font-size:12px;color:var(--accent);font-weight:700}
h1{margin:6px 0 8px;font-size:30px;line-height:1.2}.meta{margin:0;color:var(--muted);font-size:14px}
.one-liner{font-size:18px;margin:14px 0}.links{display:flex;gap:16px;flex-wrap:wrap;align-items:center;font-size:14px;margin:0}
.links span{color:var(--muted)}
nav{position:sticky;top:0;z-index:2;background:color-mix(in srgb,var(--bg) 88%,transparent);backdrop-filter:blur(8px);
border-bottom:1px solid var(--line);display:flex;gap:6px;overflow-x:auto;padding:10px 28px;justify-content:center}
nav a{white-space:nowrap;text-decoration:none;color:var(--muted);font-size:14px;padding:5px 12px;border-radius:999px}
nav a:hover{background:var(--accent-soft);color:var(--accent)}
main{max-width:1040px;margin:0 auto;padding:8px 28px 80px}
section{margin-top:40px;scroll-margin-top:64px}h2{font-size:21px;margin:0 0 16px}h3{font-size:16px;margin:0}
.verdict{border-radius:16px;padding:20px 22px;border:1px solid var(--line);background:var(--panel)}
.verdict p{margin:10px 0 0;font-size:17px}.badge{display:inline-block;font-weight:700;font-size:13px;padding:4px 12px;border-radius:999px}
.verdict.go .badge{background:var(--go-soft);color:var(--go)}.verdict.mid .badge{background:var(--mid-soft);color:var(--mid)}
.verdict.stop .badge{background:var(--stop-soft);color:var(--stop)}
.moments{list-style:none;padding:0;margin:14px 0 0;display:flex;flex-wrap:wrap;gap:8px 18px;font-size:14px}
.ts{display:inline-block;font:600 12px ui-monospace,monospace;text-decoration:none;color:var(--accent);background:var(--accent-soft);
padding:2px 8px;border-radius:6px;margin-right:6px;vertical-align:1px}
.points{list-style:none;padding:0;margin:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:16px 18px}
.card h3{display:inline;font-size:16px}.card p{margin:8px 0 0;color:var(--ink)}
.schema{margin:0 0 18px;background:#fff;border:1px solid var(--line);border-radius:14px;padding:18px;color:#1d1b26}
.schema h3{margin-bottom:12px}.schema .svg{overflow-x:auto;text-align:center}.schema svg{max-width:100%;height:auto}
.schema figcaption{margin-top:10px;font-size:14px;color:#5d5a70}.mermaid-src{white-space:pre-wrap;font-size:13px}
.steps{counter-reset:step;list-style:none;padding:0;margin:0}
.steps>li{counter-increment:step;position:relative;padding:0 0 22px 48px;border-left:2px solid var(--line);margin-left:16px}
.steps>li:last-child{border-left-color:transparent}
.steps>li::before{content:counter(step);position:absolute;left:-17px;top:-2px;width:32px;height:32px;border-radius:50%;
background:var(--accent);color:#fff;font-weight:700;display:grid;place-items:center;font-size:14px}
.step-head{display:flex;gap:10px;align-items:center;flex-wrap:wrap}.steps p{margin:6px 0}
pre{background:var(--code);border-radius:10px;padding:12px 14px;overflow-x:auto;margin:8px 0 0}pre code{background:none;padding:0;font-size:13px}
.codeblock{position:relative}.codeblock pre{padding-right:84px}
.copy{position:absolute;top:8px;right:8px;font:600 12px system-ui,sans-serif;color:var(--accent);background:var(--panel);
border:1px solid var(--line);border-radius:7px;padding:4px 10px;cursor:pointer}
.copy:hover{border-color:var(--accent)}.copy.done{color:var(--go);border-color:var(--go)}
.resources,.comments,.blind,.raw-comments{list-style:none;padding:0;margin:0;display:grid;gap:10px}
.resources li,.comments li{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:12px 16px}
.resources p,.comments p{margin:6px 0 0}.host{margin-left:10px;color:var(--muted);font-size:13px}
.lu{margin-left:10px;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:var(--go);background:var(--go-soft);padding:2px 7px;border-radius:5px}
.lead{margin:0 0 12px}.kind{font-size:12px;font-weight:700;padding:2px 9px;border-radius:999px;background:var(--accent-soft);color:var(--accent)}
.kind.correction,.kind.alerte{background:var(--mid-soft);color:var(--mid)}.kind.alternative{background:var(--go-soft);color:var(--go)}
.who{color:var(--muted);font-size:13px}
.blind li{background:var(--mid-soft);border-radius:12px;padding:10px 14px}
.annexes details{background:var(--panel);border:1px solid var(--line);border-radius:12px;margin-bottom:10px}
.annexes summary{cursor:pointer;padding:14px 18px;font-weight:600}
.transcript,.description,.raw-comments{padding:4px 22px 18px;max-height:none}
.transcript h3{margin:22px 0 8px;font-size:15px}.transcript p{margin:0 0 12px}.description{white-space:pre-wrap;font-size:14px}
.raw-comments p{margin:4px 0 0}
@media (max-width:720px){.hero{flex-direction:column;align-items:flex-start;padding:24px 18px 12px}.thumb{width:100%}
main{padding:0 18px 60px}nav{justify-content:flex-start;padding:8px 18px}h1{font-size:24px}}
"""

COPY_JS = """
document.addEventListener('click', async (event) => {
  const button = event.target.closest('.copy');
  if (!button) return;
  const code = button.parentElement.querySelector('code');
  const text = code.innerText;
  let label = 'Copié';
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    const area = document.createElement('textarea');
    area.value = text;
    area.style.position = 'fixed';
    area.style.opacity = '0';
    document.body.append(area);
    area.select();
    const copied = document.execCommand('copy');
    area.remove();
    if (!copied) {
      const range = document.createRange();
      range.selectNodeContents(code);
      getSelection().removeAllRanges();
      getSelection().addRange(range);
      label = 'Sélectionné : Ctrl+C';
    }
  }
  button.textContent = label;
  button.classList.add('done');
  setTimeout(() => { button.textContent = 'Copier'; button.classList.remove('done'); }, 1800);
});
"""

def deliver(out, doc, video_id, mode):
    transcript = DATA / video_id / "transcript.md"
    name = slug(doc["title"])
    if mode == "pupitre":
        report_copy = Path(tempfile.gettempdir()) / f"youtube-{name}-rapport.html"
        transcript_copy = Path(tempfile.gettempdir()) / f"youtube-{name}-transcription.md"
    else:
        downloads = Path.home() / "Downloads"
        report_copy = downloads / f"youtube-{name}-rapport.html"
        transcript_copy = downloads / f"youtube-{name}-transcription.md"
    shutil.copy(out, report_copy)
    shutil.copy(transcript, transcript_copy)
    if mode == "downloads":
        open_in_browser(report_copy)
    return report_copy, transcript_copy


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video_id")
    ap.add_argument("--deliver", choices=["pupitre", "downloads"], help="copier les deux fichiers à livrer")
    a = ap.parse_args()
    out, doc, ok, failed = build(a.video_id)
    result = {"report": str(out), "title": doc["title"], "schemas_rendered": ok, "schemas_failed": failed,
              "size_kb": round(out.stat().st_size / 1024)}
    if a.deliver:
        report_copy, transcript_copy = deliver(out, doc, a.video_id, a.deliver)
        result.update({"report_copy": str(report_copy), "transcript_copy": str(transcript_copy)})
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
