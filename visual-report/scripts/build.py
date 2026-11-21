#!/usr/bin/env python3
"""Turn a draft HTML page and its local media into one self-contained report."""
import argparse
import base64
import hashlib
import html
import json
import os
import pathlib
import re
import shutil
import sys
import webbrowser
from urllib.parse import unquote

SKILL = pathlib.Path(__file__).resolve().parent.parent
TEMPLATE = SKILL / "template"
MIME = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp",
    ".gif": "image/gif", ".svg": "image/svg+xml", ".avif": "image/avif",
    ".mp4": "video/mp4", ".webm": "video/webm", ".mov": "video/quicktime",
}
BUDGETS = {"pupitre": 2 * 1024 * 1024, "browser": 25 * 1024 * 1024}
MARKER = "data-visual-report"
TAG = re.compile(r"<(img|video|source)\b[^>]*>", re.I)
ATTR = re.compile(r"""\b(src|poster)\s*=\s*(["'])(.*?)\2""", re.I | re.S)
CONSOLE_BROWSERS = {"www-browser", "links", "elinks", "lynx", "w3m"}
LOCAL_LINK = re.compile(r"""<a\b[^>]*\bhref\s*=\s*(["'])(?!https?:|mailto:|#|data:)([^"']+)\1""", re.I)


def fail(message, code=1):
    print(f"build.py: {message}", file=sys.stderr)
    sys.exit(code)


def inline(draft_html, base, problems):
    stats = {"inlined": 0, "remote": [], "missing": []}

    def replace_attr(match):
        name, quote, value = match.group(1), match.group(2), html.unescape(match.group(3)).strip()
        if not value or value.startswith("data:"):
            return match.group(0)
        if re.match(r"^(https?:)?//", value):
            stats["remote"].append(value)
            return match.group(0)
        if value.startswith("blob:"):
            problems.append(f"blob: URL cannot be embedded: {value[:60]}")
            return match.group(0)
        raw = value[7:] if value.startswith("file://") else value
        path = pathlib.Path(unquote(raw.split("#")[0].split("?")[0])).expanduser()
        if not path.is_absolute():
            path = base / path
        mime = MIME.get(path.suffix.lower())
        if not path.is_file():
            stats["missing"].append(value)
            return match.group(0)
        if not mime:
            problems.append(f"unknown media type, left as is: {value}")
            return match.group(0)
        data = base64.b64encode(path.read_bytes()).decode("ascii")
        stats["inlined"] += 1
        return f"{name}={quote}data:{mime};base64,{data}{quote}"

    def replace_tag(match):
        return ATTR.sub(replace_attr, match.group(0))

    return TAG.sub(replace_tag, draft_html), stats


def ensure_document(text, title):
    if re.search(r"<html\b", text, re.I):
        if not re.search(r"<head\b", text, re.I):
            text = re.sub(r"(<html\b[^>]*>)", r"\1<head></head>", text, count=1, flags=re.I)
        return text
    heading = re.search(r"<h1[^>]*>(.*?)</h1>", text, re.I | re.S)
    page_title = title or (re.sub(r"<[^>]+>", "", heading.group(1)).strip() if heading else "Report")
    return (f'<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<title>{html.escape(page_title)}</title>\n</head>\n'
            f'<body>\n<main class="report">\n{text}\n</main>\n</body>\n</html>\n')


def inject(text, target, build_id):
    if MARKER in text:
        return text
    head_extra = []
    if not re.search(r"<meta\s+charset", text, re.I):
        head_extra.append('<meta charset="utf-8">')
    if not re.search(r'<meta\s+name=["\']viewport', text, re.I):
        head_extra.append('<meta name="viewport" content="width=device-width, initial-scale=1">')
    if head_extra:
        text = re.sub(r"(<head\b[^>]*>)", lambda m: m.group(1) + "\n" + "\n".join(head_extra), text, count=1, flags=re.I)
    css = (TEMPLATE / "report.css").read_text(encoding="utf-8")
    style = f'<style {MARKER}="{build_id}">\n{css}</style>\n'
    text = re.sub(r"(</head>)", lambda m: style + m.group(1), text, count=1, flags=re.I)
    if target == "browser":
        js = (TEMPLATE / "viewer.js").read_text(encoding="utf-8")
        script = f'<script {MARKER}="{build_id}">\n{js}</script>\n'
        if re.search(r"</body>", text, re.I):
            text = re.sub(r"(</body>)", lambda m: script + m.group(1), text, count=1, flags=re.I)
        else:
            text += script
    return text


def deliver(out, folder, build_id):
    folder.mkdir(parents=True, exist_ok=True)
    target, n = folder / out.name, 2
    while target.exists() and f'{MARKER}="{build_id}"' not in target.read_text(encoding="utf-8", errors="ignore"):
        target, n = folder / f"{out.stem}-{n}{out.suffix}", n + 1
    shutil.copyfile(out, target)
    return target


def find_desktop():
    if not sys.platform.startswith("linux") or os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
        return
    run = pathlib.Path(os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}")
    wayland = sorted(run.glob("wayland-[0-9]"))
    x11 = sorted(pathlib.Path("/tmp/.X11-unix").glob("X[0-9]"))
    if wayland:
        os.environ["WAYLAND_DISPLAY"] = wayland[0].name
    elif x11:
        os.environ["DISPLAY"] = ":" + x11[0].name[1:]
    else:
        return
    os.environ.setdefault("XDG_RUNTIME_DIR", str(run))
    if (run / "bus").exists():
        os.environ.setdefault("DBUS_SESSION_BUS_ADDRESS", f"unix:path={run / 'bus'}")


def open_in_browser(path):
    find_desktop()
    try:
        browser = webbrowser.get()
    except webbrowser.Error:
        return False
    if pathlib.Path(getattr(browser, "name", "")).name in CONSOLE_BROWSERS:
        return False
    return browser.open(path.as_uri())


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("draft", help="draft HTML whose <img>/<video>/<source> point to local files")
    ap.add_argument("-o", "--output", help="output file (default: <draft>-report.html next to the draft)")
    ap.add_argument("--target", choices=["browser", "pupitre"], default="browser",
                    help="browser: built-in viewer, 25 MB budget; pupitre: Pupitre's own viewer, 2 MiB limit")
    ap.add_argument("--title", help="page title when the draft is a fragment without <html>")
    ap.add_argument("--allow-remote", action="store_true", help="keep media loaded from http(s) URLs")
    ap.add_argument("--copy-to", metavar="DIR",
                    help="also copy the result into DIR (e.g. the user's Downloads); a rebuild of the same draft "
                         "replaces its copy, any other file of that name is kept and the copy gets a -2 suffix")
    ap.add_argument("--open", action="store_true", help="open the result, or its copy, in the default browser")
    a = ap.parse_args()

    draft = pathlib.Path(a.draft).expanduser().resolve()
    if not draft.is_file():
        fail(f"draft not found: {draft}")
    out = pathlib.Path(a.output).expanduser().resolve() if a.output else draft.with_name(draft.stem + "-report.html")
    if out == draft:
        fail("output would overwrite the draft: pass another -o")

    problems = []
    text, stats = inline(draft.read_text(encoding="utf-8"), draft.parent, problems)
    if stats["missing"]:
        fail("missing media: " + ", ".join(stats["missing"]))
    if stats["remote"] and not a.allow_remote:
        fail("remote media would not load offline or in Pupitre's preview: " + ", ".join(stats["remote"][:5])
             + ". Download them next to the draft, or pass --allow-remote.")
    for match in LOCAL_LINK.finditer(text):
        problems.append(f"link to a local file will break once the report is shared: {match.group(2)}")

    build_id = hashlib.sha1(str(draft).encode()).hexdigest()[:12]
    text = inject(ensure_document(text, a.title), a.target, build_id)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")

    size = out.stat().st_size
    budget = BUDGETS[a.target]
    images = len(re.findall(r"<img\b", text, re.I))
    videos = len(re.findall(r"<video\b", text, re.I))
    summary = {"path": str(out), "bytes": size, "size": f"{size / 1048576:.2f} MiB", "target": a.target,
               "images": images, "videos": videos, "inlined": stats["inlined"], "warnings": problems}
    if size > budget:
        print(json.dumps(summary, ensure_ascii=False))
        fail(f"{size / 1048576:.2f} MiB is over the {budget / 1048576:.0f} MiB budget for {a.target}: "
             "shorten or downscale the videos (scripts/to-mp4.sh <in> <out> 960 12), convert screenshots to WebP "
             "or JPEG, or crop them.", 2)
    shown = out
    if a.copy_to:
        shown = deliver(out, pathlib.Path(a.copy_to).expanduser().resolve(), build_id)
        summary["copy"] = str(shown)
    print(json.dumps(summary, ensure_ascii=False))
    if a.open and not open_in_browser(shown):
        print("build.py: no graphical browser reachable from this shell; give the user the path instead", file=sys.stderr)


if __name__ == "__main__":
    main()
