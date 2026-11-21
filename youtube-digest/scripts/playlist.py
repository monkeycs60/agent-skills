#!/usr/bin/env python3
import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import links as L
import report as R
import transcript as T

DATA = Path.home() / ".local" / "share" / "youtube"
PLAYLISTS = DATA / "playlists"
DIRECT_LIMIT_WORDS = 40_000
PART_BYTES = 1_800_000
LABELS = {
    "en": {
        "where_to_start": "Where to start", "takeaways": "Takeaways", "comparison": "Comparison", "video": "Video",
        "duration": "Duration", "agreements": "Agreements and disagreements", "agree": "Where they agree",
        "differ": "Where they differ", "nothing": "Nothing notable.", "gaps": "What the playlist does not cover",
        "words": "{n} words", "full_report": "Full report", "missing": "Notes missing: rerun a subagent on this video.",
        "skipped": "Not analysed: ", "no_captions": "no captions", "error": "error", "videos": "The videos",
        "reports": "Video reports", "kicker": "Playlist report", "page_title": "playlist report",
        "meta": "{ok} of {total} videos analysed · {duration} of video · {words} words", "open": "Open the playlist",
        "transcripts": "Transcripts", "continued": "continued", "video_n": "Video", "transcripts_file": "transcripts",
    },
    "fr": {
        "where_to_start": "Par où commencer", "takeaways": "À retenir", "comparison": "Comparatif", "video": "Vidéo",
        "duration": "Durée", "agreements": "Accords et désaccords", "agree": "Ce sur quoi elles s’accordent",
        "differ": "Ce sur quoi elles divergent", "nothing": "Rien de notable.", "gaps": "Ce que la playlist ne couvre pas",
        "words": "{n} mots", "full_report": "Compte rendu complet",
        "missing": "Fiche absente : relancer un sous-agent sur cette vidéo.",
        "skipped": "Non analysées : ", "no_captions": "sans sous-titres", "error": "erreur", "videos": "Les vidéos",
        "reports": "Comptes rendus", "kicker": "Rapport de playlist", "page_title": "rapport de playlist",
        "meta": "{ok} vidéos analysées sur {total} · {duration} de vidéo · {words} mots", "open": "Ouvrir la playlist",
        "transcripts": "Transcriptions", "continued": "suite", "video_n": "Vidéo", "transcripts_file": "transcriptions",
    },
}


def fetch(args):
    if not shutil.which("yt-dlp"):
        sys.exit("yt-dlp not found: run install.sh.")
    r = subprocess.run(["yt-dlp", "--no-warnings", "--flat-playlist", "-J", "-I", f"1:{args.max}", args.url],
                       capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"yt-dlp could not read the playlist:\n{r.stderr[-800:]}")
    pl = json.loads(r.stdout)
    entries = [e for e in pl.get("entries") or [] if len(e.get("id") or "") == 11]
    if not entries:
        sys.exit("No video listed: give a playlist URL (?list=…) or a channel's /videos tab.")
    folder = PLAYLISTS / pl["id"]
    folder.mkdir(parents=True, exist_ok=True)

    def one(entry):
        cmd = [sys.executable, "-I", str(HERE / "transcript.py"), f"https://youtu.be/{entry['id']}", "--lang", args.lang]
        if not args.asr:
            cmd.append("--no-asr")
        p = subprocess.run(cmd, capture_output=True, text=True)
        meta = json.loads(p.stdout.strip().splitlines()[-1]) if p.returncode == 0 else {}
        status = "ok" if p.returncode == 0 else "no-captions" if p.returncode == 3 else "error"
        return {
            "id": entry["id"], "title": entry.get("title"), "duration": entry.get("duration") or meta.get("duration"),
            "status": status, "words": meta.get("words", 0), "source": meta.get("source"),
            "transcript": meta.get("path"),
            "error": None if status == "ok" else (p.stderr.strip().splitlines() or ["?"])[-1],
        }

    t0 = time.time()
    with ThreadPoolExecutor(args.jobs) as pool:
        videos = list(pool.map(one, entries))
    data = {"id": pl["id"], "title": pl.get("title"), "channel": pl.get("channel") or pl.get("uploader"),
            "url": args.url, "total": pl.get("playlist_count") or len(entries), "videos": videos}
    (folder / "playlist.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    ok = [v for v in videos if v["status"] == "ok"]
    words = sum(v["words"] for v in ok)
    print(json.dumps({
        "id": data["id"], "title": data["title"], "total_in_playlist": data["total"], "listed": len(entries),
        "ok": len(ok), "words": words, "mode": "direct" if words <= DIRECT_LIMIT_WORDS else "subagents",
        "videos": [{"n": i + 1, "id": v["id"], "title": v["title"], "status": v["status"], "words": v["words"]}
                   for i, v in enumerate(videos)],
        "folder": str(folder), "seconds": round(time.time() - t0, 1),
    }, ensure_ascii=False))


def pick_links(found, per_video):
    ranked = []
    for i, url in enumerate((found.get("code") or []) + (found.get("pages") or [])):
        if T.is_noise(url) or not urlparse(url).path.strip("/"):
            continue
        score = 1 + 2 * T.is_code(url) + bool(re.search(r"doc|guide|tuto|blog|article|stor|learn|setup|integration", url.lower()))
        ranked.append((-score, i, url))
    return [url for _, _, url in sorted(ranked)[:per_video]]


def read_links(args):
    folder = PLAYLISTS / args.playlist_id
    data = json.loads((folder / "playlist.json").read_text(encoding="utf-8"))
    t0, summary = time.time(), []
    for n, v in enumerate(data["videos"], 1):
        if v["status"] != "ok":
            continue
        meta = json.loads((DATA / v["id"] / "meta.json").read_text(encoding="utf-8"))
        urls = pick_links(meta.get("links") or {}, args.per_video)
        results = L.read(v["id"], urls, close=False) if urls else []
        v.pop("liens", None)
        v["links"] = results
        summary.append({"n": n, "id": v["id"], "read": [r["url"] for r in results if "path" in r],
                        "errors": [r["url"] for r in results if "error" in r]})
    L.close_browser()
    (folder / "playlist.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"videos": summary, "seconds": round(time.time() - t0, 1)}, ensure_ascii=False, indent=1))


EXTRA_CSS = """
.order{list-style:none;padding:0;margin:16px 0 0;display:grid;gap:10px}
.order li{display:flex;gap:14px;align-items:center;background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:10px 14px}
.thumbimg{display:block;aspect-ratio:16/9;background-size:cover;background-position:center}
.order .thumbimg{width:120px;border-radius:8px;flex:none}.order .rank{font-weight:800;color:var(--accent);font-size:20px;width:26px;flex:none}
.order p{margin:2px 0 0;color:var(--muted);font-size:14px}
.sources{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
table.compare{width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--line);border-radius:12px;overflow:hidden;font-size:14px}
.compare th,.compare td{text-align:left;padding:10px 12px;border-bottom:1px solid var(--line);vertical-align:top}
.compare th{font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);background:var(--bg)}
.compare tr:last-child td{border-bottom:0}.compare .num{font-weight:800;color:var(--accent)}
.duo{display:grid;grid-template-columns:1fr 1fr;gap:16px}.duo ul{list-style:none;padding:0;margin:0;display:grid;gap:10px}
.duo li{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:12px 14px}.duo h3{margin:0 0 10px}
.vgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px}
.vcard{background:var(--panel);border:1px solid var(--line);border-radius:14px;overflow:hidden}
.vcard .thumbimg{width:100%}.vcard .body{padding:12px 16px 16px}.vcard h3{font-size:15px;margin:6px 0}
.vcard .num{font-weight:800;color:var(--accent)}.vcard ul{margin:8px 0 0;padding-left:18px;font-size:14px}.vcard li{margin:4px 0}
.pill{white-space:nowrap;font-size:12px;font-weight:700;padding:2px 9px;border-radius:999px;background:var(--accent-soft);color:var(--accent)}
.pill.go{background:var(--go-soft);color:var(--go)}.pill.mid{background:var(--mid-soft);color:var(--mid)}.pill.stop{background:var(--stop-soft);color:var(--stop)}
.skipped{color:var(--muted);font-size:14px}
.more{display:inline-block;margin-top:8px;font-size:14px;font-weight:600}
.vreport{background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:24px 26px;margin-bottom:28px;scroll-margin-top:64px}
.vreport-head{display:flex;gap:20px;align-items:center}.vreport-head .thumbimg{width:240px;border-radius:12px;flex:none}
.vreport-title{font-size:20px;margin:6px 0 4px}.vreport .one-liner{font-size:16px;margin:8px 0 0}
.vreport-part{margin-top:26px}.vreport-part h4{margin:0 0 12px;font-size:12px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted)}
.vreport .card,.vreport .resources li,.vreport .comments li{background:var(--bg)}.vreport .verdict{background:var(--bg)}
@media (max-width:720px){.duo{grid-template-columns:1fr}.order .thumbimg{width:84px}.vreport{padding:18px}.vreport-head{flex-direction:column;align-items:flex-start}.vreport-head .thumbimg{width:100%}}
"""


def render(playlist_id):
    folder = PLAYLISTS / playlist_id
    data = json.loads((folder / "playlist.json").read_text(encoding="utf-8"))
    syn = R.load_notes(folder / "synthesis.json", folder / "synthese.json")
    if syn is None:
        sys.exit(f"{folder / 'synthesis.json'} missing: write the synthesis before the report.")
    lang = syn["lang"]
    txt = {**R.LABELS[lang], **LABELS[lang]}
    number = {v["id"]: i + 1 for i, v in enumerate(data["videos"])}
    videos = {v["id"]: v for v in data["videos"]}
    ok = [v for v in data["videos"] if v["status"] == "ok"]
    notes = {}
    for v in ok:
        found = R.load_notes(DATA / v["id"] / "notes.json", DATA / v["id"] / "fiche.json")
        if found is not None:
            notes[v["id"]] = found
    with ThreadPoolExecutor(8) as pool:
        thumbs = dict(zip([v["id"] for v in ok], pool.map(lambda v: R.thumbnail(v["id"], "mqdefault"), ok)))

    def chip(source):
        vid, t = source["id"], int(source.get("t") or 0)
        title = R.esc(videos.get(vid, {}).get("title") or vid)
        return (f'<a class="ts" title="{title}" href="https://youtu.be/{vid}?t={t}" target="_blank" '
                f'rel="noopener">#{number.get(vid, "?")} {R.clock(t)}</a>')

    def chips(item):
        found = "".join(chip(s) for s in item.get("sources") or [])
        return f'<div class="sources">{found}</div>' if found else ""

    def pill(vid):
        rating = (notes.get(vid, {}).get("verdict") or {}).get("rating")
        return f'<span class="pill {R.TONES[rating]}">{txt["ratings"][rating]}</span>' if rating in R.TONES else ""

    sections = []
    verdict = syn.get("verdict") or {}
    order = []
    for rank, vid in enumerate(verdict.get("order") or [], 1):
        v = videos.get(vid)
        if not v:
            continue
        img = f'<span class="thumbimg th-{number[vid]}" role="img"></span>' if thumbs.get(vid) else ""
        one = (notes.get(vid) or {}).get("summary")
        order.append(f'<li><span class="rank">{rank}</span>{img}<div><strong>#{number[vid]} '
                     f'<a href="https://youtu.be/{vid}" target="_blank" rel="noopener">{R.esc(v["title"])}</a></strong> '
                     f'{pill(vid)} <span class="who">{R.clock(v.get("duration") or 0)}</span>'
                     f'{f"<p>{R.inline(one)}</p>" if one else ""}</div></li>')
    sections.append(("verdict", txt["verdict"], f'<div class="verdict mid"><span class="badge">{txt["where_to_start"]}</span>'
                     f'<p>{R.inline(verdict.get("text"))}</p></div>'
                     f'{f"<ol class=order>{chr(10).join(order)}</ol>" if order else ""}'))

    if syn.get("takeaways"):
        cards = "".join(f'<li class="card"><h3>{R.inline(a.get("title"))}</h3><p>{R.inline(a.get("text"))}</p>{chips(a)}</li>'
                        for a in syn["takeaways"])
        sections.append(("takeaways", txt["takeaways"], f'<ol class="points">{cards}</ol>'))

    comp = syn.get("comparison") or {}
    if comp.get("rows"):
        head = "".join(f"<th>{R.esc(c)}</th>" for c in comp.get("columns") or [])
        rows = []
        for line in comp["rows"]:
            vid = line["id"]
            v = videos.get(vid, {})
            cells = "".join(f"<td>{R.inline(x)}</td>" for x in line.get("values") or [])
            rows.append(f'<tr><td class="num">#{number.get(vid, "?")}</td><td><a href="https://youtu.be/{vid}" target="_blank" '
                        f'rel="noopener">{R.esc(v.get("title") or vid)}</a></td><td>{R.clock(v.get("duration") or 0)}</td>'
                        f'<td>{pill(vid)}</td>{cells}</tr>')
        sections.append(("comparison", txt["comparison"], f'<div style="overflow-x:auto"><table class="compare"><thead><tr><th>#</th>'
                         f'<th>{txt["video"]}</th><th>{txt["duration"]}</th><th>{txt["verdict"]}</th>{head}</tr></thead>'
                         f'<tbody>{"".join(rows)}</tbody></table></div>'))

    if syn.get("consensus") or syn.get("divergences"):
        def column(title, items):
            lis = "".join(f"<li>{R.inline(i.get('text'))}{chips(i)}</li>" for i in items or []) or f"<li>{txt['nothing']}</li>"
            return f'<div><h3>{title}</h3><ul>{lis}</ul></div>'
        sections.append(("agreements", txt["agreements"],
                         f'<div class="duo">{column(txt["agree"], syn.get("consensus"))}'
                         f'{column(txt["differ"], syn.get("divergences"))}</div>'))

    diagrams = syn.get("diagrams") or []
    owners = [None] * len(diagrams) + [v["id"] for v in ok for _ in notes.get(v["id"], {}).get("diagrams") or []]
    sources = [s["mermaid"] for s in diagrams] + [d["mermaid"] for v in ok for d in notes.get(v["id"], {}).get("diagrams") or []]
    rendered = R.render_mermaid(sources) if sources else []
    video_svgs = {}
    for owner, svg in zip(owners, rendered):
        if owner:
            video_svgs.setdefault(owner, []).append(svg)
    if diagrams:
        svgs = rendered[:len(diagrams)]
        figs = "".join(
            f'<figure class="schema"><h3>{R.inline(s.get("title"))}</h3>'
            + (f'<div class="svg">{svg}</div>' if svg else f'<pre class="mermaid-src">{R.esc(s["mermaid"])}</pre>')
            + (f'<figcaption>{R.inline(s.get("caption"))}</figcaption>' if s.get("caption") else "") + "</figure>"
            for s, svg in zip(diagrams, svgs))
        sections.append(("diagrams", txt["diagrams"], figs))

    if syn.get("gaps"):
        sections.append(("gaps", txt["gaps"],
                         '<ul class="blind">' + "".join(f"<li>{R.inline(m)}</li>" for m in syn["gaps"]) + "</ul>"))

    cards, reports = [], []
    for v in ok:
        f = notes.get(v["id"], {})
        n = number[v["id"]]
        words = txt["words"].format(n=v["words"])
        img = f'<span class="thumbimg th-{n}" role="img"></span>' if thumbs.get(v["id"]) else ""
        cards.append(f'<article class="vcard">{img}<div class="body"><span class="num">#{n}</span> {pill(v["id"])} '
                     f'<span class="who">{R.clock(v.get("duration") or 0)} · {words}</span>'
                     f'<h3><a href="https://youtu.be/{v["id"]}" target="_blank" rel="noopener">{R.esc(v["title"])}</a></h3>'
                     f'<p>{R.inline(f.get("summary") or "")}</p><a class="more" href="#report-{n}">{txt["full_report"]}</a></div></article>')
        parts = "".join(f'<div class="vreport-part"><h4>{title}</h4>{content}</div>'
                        for _, title, content in R.notes_sections(f, v["id"], video_svgs.get(v["id"], []), txt, prefix=f"v{n}-")) if f \
            else f'<p class="skipped">{txt["missing"]}</p>'
        source = R.source_label(v.get("source") or "", lang)
        reports.append(f'<article class="vreport" id="report-{n}"><header class="vreport-head">{img}<div><span class="num">#{n}</span> {pill(v["id"])}'
                       f'<h3 class="vreport-title"><a href="https://youtu.be/{v["id"]}" target="_blank" rel="noopener">{R.esc(v["title"])}</a></h3>'
                       f'<p class="who">{R.clock(v.get("duration") or 0)} · {words} · {R.esc(source)}</p>'
                       f'<p class="one-liner">{R.inline(f.get("summary") or "")}</p></div></header>{parts}</article>')
    skipped = [v for v in data["videos"] if v["status"] != "ok"]
    skipped_html = (f"<p class='skipped'>{txt['skipped']}" + " · ".join(
        f'#{number[v["id"]]} {R.esc(v["title"])} '
        f'({txt["no_captions"] if v["status"] in ("no-captions", "sans-sous-titres") else txt["error"]})'
        for v in skipped) + "</p>") if skipped else ""
    sections.append(("videos", txt["videos"], f'<div class="vgrid">{"".join(cards)}</div>{skipped_html}'))
    sections.append(("reports", txt["reports"], "".join(reports)))

    thumb_css = "".join(f".th-{number[vid]}{{background-image:url({uri})}}" for vid, uri in thumbs.items() if uri)
    total_duration = sum(v.get("duration") or 0 for v in ok)
    words = sum(v["words"] for v in ok)
    meta = txt["meta"].format(ok=len(ok), total=data["total"], duration=R.clock(total_duration), words=words)
    nav = "".join(f'<a href="#{sid}">{title}</a>' for sid, title, _ in sections)
    body = "".join(f'<section id="{sid}"><h2>{title}</h2>{content}</section>' for sid, title, content in sections)
    page = f"""<!doctype html>
<html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{R.esc(data["title"])} · {txt["page_title"]}</title><style>{R.CSS}{EXTRA_CSS}{thumb_css}</style></head>
<body><header class="hero"><div><p class="kicker">{txt["kicker"]}</p><h1>{R.esc(data["title"])}</h1>
<p class="meta">{R.esc(data.get("channel") or "")} · {meta}</p>
<p class="one-liner">{R.inline(syn.get("summary"))}</p>
<p class="links"><a href="{R.esc(data["url"])}" target="_blank" rel="noopener">{txt["open"]}</a></p></div></header>
<nav>{nav}</nav><main>{body}</main><script>{R.copy_js(txt)}</script></body></html>"""
    out = folder / "report.html"
    out.write_text(page, encoding="utf-8")
    return out, data, ok, txt


def transcripts(folder, data, ok, txt):
    parts, current = [], f"# {txt['transcripts']} · {data['title']}\n\n"
    for i, v in enumerate(ok, 1):
        text = Path(v["transcript"]).read_text(encoding="utf-8")
        block = f"\n\n---\n\n<!-- {txt['video_n']} {i}/{len(ok)} -->\n\n{text}"
        if len(current.encode()) + len(block.encode()) > PART_BYTES and current.strip():
            parts.append(current)
            current = f"# {txt['transcripts']} · {data['title']} ({txt['continued']})\n\n"
        current += block
    parts.append(current)
    paths = []
    stem = txt["transcripts_file"]
    for i, content in enumerate(parts, 1):
        path = folder / (f"{stem}-{i}.md" if len(parts) > 1 else f"{stem}.md")
        path.write_text(content, encoding="utf-8")
        paths.append(path)
    return paths


def report_cmd(args):
    out, data, ok, txt = render(args.playlist_id)
    folder = PLAYLISTS / args.playlist_id
    files = transcripts(folder, data, ok, txt)
    result = {"report": str(out), "transcripts": [str(p) for p in files], "size_kb": round(out.stat().st_size / 1024)}
    if args.deliver:
        name = R.slug(data["title"])
        target = Path(tempfile.gettempdir()) if args.deliver == "pupitre" else Path.home() / "Downloads"
        report_copy = target / f"youtube-playlist-{name}-{txt['report']}.html"
        shutil.copy(out, report_copy)
        copies = []
        for p in files:
            dest = target / f"youtube-playlist-{name}-{p.name}"
            shutil.copy(p, dest)
            copies.append(str(dest))
        if args.deliver == "downloads":
            R.open_in_browser(report_copy)
        result.update({"report_copy": str(report_copy), "transcript_copies": copies})
    print(json.dumps(result, ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="command", required=True)
    f = sub.add_parser("fetch", help="list the playlist and fetch the transcripts")
    f.add_argument("url")
    f.add_argument("--max", type=int, default=25, help="number of videos processed, in playlist order")
    f.add_argument("--asr", action="store_true", help="also transcribe videos without captions (slow)")
    f.add_argument("--jobs", type=int, default=3)
    f.add_argument("--lang", choices=sorted(T.LABELS), default="en", help="language of the transcript.md labels")
    k = sub.add_parser("links", help="read each video's useful links (headless agent-browser, HTTP, gh)")
    k.add_argument("playlist_id")
    k.add_argument("--per-video", type=int, default=3)
    r = sub.add_parser("report", help="build the comparative report and the transcript collection")
    r.add_argument("playlist_id")
    r.add_argument("--deliver", choices=["pupitre", "downloads"])
    a = ap.parse_args()
    {"fetch": fetch, "links": read_links, "report": report_cmd}[a.command](a)


if __name__ == "__main__":
    main()
