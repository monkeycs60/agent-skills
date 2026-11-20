#!/usr/bin/env python3
import argparse
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
VENV = SKILL / ".venv"
VENV_PY = VENV / "bin" / "python"
DATA = Path.home() / ".local" / "share" / "youtube"
COMMENTS = 20
PARAKEET_LANGS = {
    "bg", "hr", "cs", "da", "nl", "en", "et", "fi", "fr", "de", "el", "hu", "it",
    "lv", "lt", "mt", "pl", "pt", "ro", "sk", "sl", "es", "sv", "ru", "uk",
}
BLOCKED = ("not a bot", "Sign in to confirm", "HTTP Error 429", "HTTP Error 403")
NOISE = (
    "twitter.com", "x.com", "discord.gg", "discord.com", "instagram.com", "facebook.com", "fb.me",
    "tiktok.com", "linkedin.com", "patreon.com", "ko-fi.com", "buymeacoffee.com", "tipeee.com",
    "utip.io", "twitch.tv", "youtube.com", "youtu.be", "threads.net", "bsky.app", "t.me",
    "snapchat.com", "spotify.com", "amzn.to", "amzn.eu", "linktr.ee", "beacons.ai", "teespring.com",
    "skool.com", "partnerlinks.io", "stan.store", "calendly.com", "tally.so", "forms.gle", "typeform.com",
    "gumroad.com", "lemonsqueezy.com", "payhip.com", "systeme.io",
)
NOISE_HOST_PARTS = ("amazon.", "hostinger.")
NOISE_WORDS = ("subscribe", "sub_confirmation", "premium", "merch", "donate", "sponsor", "tchat", "coupon", "promo",
               "affiliate", "discount")
CODE = (
    "github.com", "gitlab.com", "codeberg.org", "bitbucket.org", "huggingface.co", "npmjs.com",
    "pypi.org", "colab.research.google.com", "stackblitz.com", "codesandbox.io", "replit.com",
)


class Blocked(Exception):
    pass


def log(msg):
    print(msg, file=sys.stderr, flush=True)


def js_runtime():
    if shutil.which("deno"):
        return []
    found = next((rt for rt in ("node", "bun") if shutil.which(rt)), None)
    return ["--js-runtimes", found] if found else []


def ytdlp(args, cookies):
    cmd = ["yt-dlp", "--no-warnings", "--no-playlist", *js_runtime(), *args]
    if cookies:
        cmd[1:1] = ["--cookies-from-browser", "chrome"]
    return subprocess.run(cmd, capture_output=True, text=True)


def clock(s):
    s = int(s)
    h, m, sec = s // 3600, s % 3600 // 60, s % 60
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m:02d}:{sec:02d}"


def one_line(text, limit=600):
    text = re.sub(r"\s+", " ", text or "").strip()
    return text if len(text) <= limit else text[:limit].rstrip() + "…"


def get_json(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())


def pick_track(info):
    lang = (info.get("language") or "").split("-")[0]
    manual = {k: v for k, v in (info.get("subtitles") or {}).items() if k != "live_chat"}
    auto = info.get("automatic_captions") or {}
    orig = next((k for k in auto if k.endswith("-orig")), None)
    if not lang and orig:
        lang = orig.split("-")[0]
    order = []
    for wanted in (lang, "orig", "en", "fr", "*"):
        if wanted == "orig":
            order += [("automatiques YouTube", auto, orig)] if orig else []
        elif wanted:
            order += [("manuels", manual, k) for k in manual if wanted == "*" or k.split("-")[0] == wanted]
    if lang and lang in auto:
        order.append(("automatiques YouTube", auto, lang))
    for kind, table, key in order:
        url = next((f["url"] for f in table[key] if f.get("ext") == "json3"), None)
        if url:
            return kind, key, url
    return None


def fetch_captions(url):
    cues = []
    for ev in get_json(url, timeout=20).get("events", []):
        text = "".join(s.get("utf8", "") for s in ev.get("segs", [])).replace("\n", " ").strip()
        if text:
            cues.append((ev.get("tStartMs", 0) / 1000, text))
    return cues


def ensure_venv():
    if VENV_PY.exists():
        return
    log("Installation du moteur local (une seule fois)…")
    if shutil.which("uv"):
        subprocess.run(["uv", "venv", "-q", str(VENV)], check=True)
        subprocess.run(["uv", "pip", "install", "-q", "--python", str(VENV_PY), "onnx-asr[cpu,hub]"], check=True)
    else:
        subprocess.run([sys.executable, "-m", "venv", str(VENV)], check=True)
        subprocess.run([str(VENV_PY), "-m", "pip", "install", "-q", "onnx-asr[cpu,hub]"], check=True)


def transcribe_audio(info_path, workdir, cookies):
    ensure_venv()
    t = time.time()
    r = ytdlp(["--load-info-json", str(info_path), "-f", "wa/ba", "-N", "4",
               "-o", str(workdir / "audio.%(ext)s")], cookies)
    audio = next(workdir.glob("audio.*"), None)
    if r.returncode or not audio:
        sys.exit(f"Téléchargement de l'audio impossible :\n{r.stderr[-800:]}")
    wav = workdir / "audio16k.wav"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(audio), "-ar", "16000", "-ac", "1",
                    "-c:a", "pcm_s16le", str(wav)], check=True)
    audio.unlink()
    log(f"Audio prêt en {time.time() - t:.0f} s, transcription Parakeet…")
    r = subprocess.run([str(VENV_PY), "-I", str(SKILL / "scripts" / "asr.py"), str(wav)],
                       stdout=subprocess.PIPE, text=True)
    wav.unlink()
    if r.returncode:
        sys.exit("La transcription locale a échoué (voir les messages au-dessus).")
    return [(seg["start"], seg["text"]) for seg in map(json.loads, r.stdout.splitlines()) if seg["text"]]


def via_ytdlp(url, args):
    if not shutil.which("yt-dlp"):
        raise Blocked("yt-dlp absent")
    r = ytdlp(["-J", "--write-comments", "--extractor-args",
               f"youtube:max_comments={COMMENTS},{COMMENTS},0,0;comment_sort=top", url], args.cookies)
    if r.returncode:
        if any(b in r.stderr for b in BLOCKED):
            raise Blocked(r.stderr.strip().splitlines()[-1])
        sys.exit(f"yt-dlp n'a pas pu lire la vidéo :\n{r.stderr[-800:]}")
    raw = json.loads(r.stdout)
    date = raw.get("upload_date") or ""
    info = {
        "id": raw["id"], "title": raw.get("title"), "channel": raw.get("channel") or raw.get("uploader"),
        "date": f"{date[:4]}-{date[4:6]}-{date[6:]}" if date else "?", "duration": raw.get("duration") or 0,
        "description": raw.get("description") or "", "language": (raw.get("language") or "").split("-")[0],
        "links": find_urls(raw.get("description") or ""),
        "chapters": [(c["start_time"], c["title"]) for c in raw.get("chapters") or []],
        "comments": [{"author": c.get("author"), "likes": c.get("like_count") or 0, "text": c.get("text"),
                      "pinned": c.get("is_pinned"), "uploader": c.get("author_is_uploader")}
                     for c in (raw.get("comments") or []) if c.get("parent", "root") == "root"][:COMMENTS],
    }
    workdir = DATA / info["id"]
    workdir.mkdir(parents=True, exist_ok=True)
    track = None if args.asr else pick_track(raw)
    if track:
        kind, key, cap_url = track
        for attempt in range(2):
            try:
                return info, fetch_captions(cap_url), f"sous-titres {kind} ({key})"
            except Exception as e:
                log(f"Sous-titres illisibles ({e})" + (", nouvel essai dans 3 s." if attempt == 0 else "."))
                time.sleep(3 if attempt == 0 else 0)
    if args.no_asr:
        log("Pas de sous-titres exploitables, vidéo ignorée (--no-asr).")
        sys.exit(3)
    if info["language"] and info["language"] not in PARAKEET_LANGS:
        log(f"Attention : langue « {info['language']} » hors des 25 langues de Parakeet, texte peu fiable.")
    info_path = workdir / "info.full.json"
    info_path.write_text(r.stdout)
    try:
        cues = transcribe_audio(info_path, workdir, args.cookies)
    finally:
        info_path.unlink(missing_ok=True)
    return info, cues, "transcription locale Parakeet TDT 0.6B v3"


def find_urls(text):
    return [u.rstrip(".,;:!?") for u in re.findall(r"https?://[^\s<>\"'()\[\]]+", text)]


def host_of(url):
    return urllib.parse.urlparse(url).netloc.lower().removeprefix("www.")


def is_noise(url):
    host = host_of(url)
    return (not host or any(host == d or host.endswith("." + d) for d in NOISE)
            or any(part in host for part in NOISE_HOST_PARTS) or any(w in url.lower() for w in NOISE_WORDS))


def is_code(url):
    host = host_of(url)
    return any(host == d or host.endswith("." + d) for d in CODE)


def useful_links(info):
    pinned = " ".join(c["text"] or "" for c in info["comments"] if c["pinned"] or c["uploader"])
    seen, links = set(), {"code": [], "pages": []}
    for u in info["links"] + find_urls(pinned):
        if u in seen or is_noise(u):
            continue
        seen.add(u)
        links["code" if is_code(u) else "pages"].append(u)
    return links


def paragraphs(cues, chapters):
    starts = [s for s, _ in chapters]
    out, cur, cur_start, ci = [], [], None, 0
    for start, text in cues:
        new_chapter = ci < len(starts) and start >= starts[ci]
        if cur and (new_chapter or start - cur_start >= 45
                    or (start - cur_start >= 30 and re.search(r"[.?!…]$", cur[-1]))):
            out.append(("p", cur_start, " ".join(cur)))
            cur = []
        while ci < len(starts) and start >= starts[ci]:
            out.append(("h", starts[ci], chapters[ci][1]))
            ci += 1
        if not cur:
            cur_start = start
        cur.append(text)
    if cur:
        out.append(("p", cur_start, " ".join(cur)))
    return out


def render(info, source, blocks, links):
    vid = info["id"]
    link = lambda s: f"[{clock(s)}](https://youtu.be/{vid}?t={int(s)})"
    lines = [
        f"# {info['title'] or vid}",
        "",
        f"- Chaîne : {info['channel'] or '?'} · Publiée : {info['date']} · Durée : {clock(info['duration'])}",
        f"- Lien : https://youtu.be/{vid}",
        f"- Texte : {source}",
        "",
    ]
    if links["code"] or links["pages"]:
        lines += ["## Liens utiles", ""]
        lines += [f"- Code : {u}" for u in links["code"]] + [f"- Page : {u}" for u in links["pages"]] + [""]
    lines += ["## Description", "", info["description"].strip()[:4000], "", "## Transcription", ""]
    for kind, start, text in blocks:
        lines += [f"### {link(start)} {text}", ""] if kind == "h" else [f"**{link(start)}** {text}", ""]
    if info["comments"]:
        lines += [f"## Commentaires les plus appréciés ({len(info['comments'])})", ""]
        for c in info["comments"]:
            tags = [f"{c['likes']} j'aime"] + (["épinglé"] if c["pinned"] else []) + (["auteur"] if c["uploader"] else [])
            lines.append(f"- **{c['author'] or '?'}** ({', '.join(tags)}) : {one_line(c['text'])}")
        lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--asr", action="store_true", help="ignorer les sous-titres et transcrire l'audio")
    ap.add_argument("--no-asr", action="store_true", help="s'arrêter (code 3) plutôt que transcrire l'audio")
    ap.add_argument("--cookies", action="store_true", help="utiliser les cookies YouTube de Chrome")
    ap.add_argument("--force", action="store_true", help="refaire même si déjà en cache")
    a = ap.parse_args()
    t0 = time.time()

    m = re.search(r"(?:v=|youtu\.be/|shorts/|live/|embed/)([\w-]{11})", a.url)
    cached = DATA / m.group(1) if m else None
    if cached and (cached / "transcript.md").exists() and not (a.force or a.asr):
        meta = json.loads((cached / "meta.json").read_text())
        print(json.dumps({**meta, "path": str(cached / "transcript.md"), "cache": True}, ensure_ascii=False))
        return

    try:
        info, cues, source = via_ytdlp(a.url, a)
    except Blocked as why:
        sys.exit(f"YouTube refuse cette machine ({why}) : lancer le skill depuis le PC, ou avec --cookies.")

    workdir = DATA / info["id"]
    workdir.mkdir(parents=True, exist_ok=True)
    links = useful_links(info)
    (workdir / "transcript.md").write_text(
        render(info, source, paragraphs(cues, info["chapters"]), links), encoding="utf-8")
    meta = {
        "id": info["id"], "title": info["title"], "duration": info["duration"], "source": source,
        "words": sum(len(t.split()) for _, t in cues), "chapters": len(info["chapters"]),
        "comments": len(info["comments"]), "links": links,
    }
    (workdir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False))
    print(json.dumps({**meta, "path": str(workdir / "transcript.md"), "cache": False,
                      "seconds": round(time.time() - t0, 1)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
