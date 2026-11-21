#!/usr/bin/env python3
import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

DATA = Path.home() / ".local" / "share" / "youtube"
LIMIT = 60_000
GITHUB = re.compile(r"https?://(?:www\.)?github\.com/([^/\s]+)/([^/\s#?]+)(?:/(blob|tree)/([^/\s]+)/([^\s#?]+))?")
BROWSER_PATHS = (
    "~/.nvm/versions/node/current/bin/agent-browser",
    "~/.nvm/versions/node/*/bin/agent-browser",
    "~/.local/opt/pupitre-browser/*/agent-browser",
    "~/.local/bin/agent-browser",
    "~/.bun/bin/agent-browser",
    "/opt/homebrew/bin/agent-browser",
    "/usr/local/bin/agent-browser",
)
SESSION = f"youtube-skill-{os.getpid()}"


def run(cmd, timeout=60, env=None):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)


def find_browser():
    candidates = [os.environ.get("AGENT_BROWSER_BIN"), shutil.which("agent-browser")]
    for pattern in BROWSER_PATHS:
        candidates += sorted(glob.glob(os.path.expanduser(pattern)), reverse=True)
    return next((c for c in candidates if c and os.access(c, os.X_OK)), None)


BROWSER = find_browser()


def browser(*args, timeout=45):
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("AGENT_BROWSER_") or k == "AGENT_BROWSER_EXECUTABLE_PATH"}
    return run([BROWSER, "--session", SESSION, *args], timeout=timeout, env=env)


def close_browser():
    if BROWSER:
        browser("close", timeout=20)


class TextOnly(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "nav", "footer", "form", "iframe", "button"}
    BLOCK = {"p", "div", "br", "li", "tr", "section", "article", "pre", "h1", "h2", "h3", "h4", "h5", "h6", "table"}

    def __init__(self):
        super().__init__()
        self.parts, self.skip, self.pre = [], 0, 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        if tag == "pre":
            self.pre += 1
        if tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1
        if tag == "pre" and self.pre:
            self.pre -= 1
        if tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data if self.pre else re.sub(r"[ \t\r\f\v]+", " ", data))


def http_text(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) youtube-skill"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        raw = resp.read(3_000_000).decode(charset, errors="replace")
    parser = TextOnly()
    parser.feed(raw)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", "".join(parser.parts)).strip()
    if not text:
        raise RuntimeError("empty page (rendered with JavaScript?): install agent-browser")
    return text


def github(match):
    owner, repo, kind, ref, path = match.groups()
    repo = f"{owner}/{repo.removesuffix('.git')}"
    if not shutil.which("gh"):
        raise RuntimeError("gh missing: install GitHub CLI to read repositories")
    if kind == "tree":
        listing = run(["gh", "api", f"repos/{repo}/contents/{path}?ref={ref}", "--jq", ".[].path"])
        if listing.returncode:
            raise RuntimeError(listing.stderr.strip()[-300:])
        readme = run(["gh", "api", f"repos/{repo}/contents/{path}/README.md?ref={ref}",
                      "-H", "Accept: application/vnd.github.raw"])
        return f"# {repo} · {path} ({ref})\n\n{readme.stdout}\n\n## Files\n\n{listing.stdout}"
    if path:
        r = run(["gh", "api", f"repos/{repo}/contents/{path}?ref={ref}", "-H", "Accept: application/vnd.github.raw"])
        if r.returncode:
            raise RuntimeError(r.stderr.strip()[-300:])
        return f"# {repo} · {path} ({ref})\n\n{r.stdout}"
    readme = run(["gh", "repo", "view", repo])
    if readme.returncode:
        raise RuntimeError(readme.stderr.strip()[-300:])
    tree = run(["gh", "api", f"repos/{repo}/git/trees/HEAD?recursive=1", "--jq",
                '.tree[] | select(.type=="blob") | .path'])
    files = tree.stdout.splitlines()
    return f"# Repository {repo}\n\n{readme.stdout}\n\n## Files ({len(files)})\n\n" + "\n".join(files[:300])


def page(url, http_only=False):
    if BROWSER and not http_only:
        r = browser("open", url)
        if r.returncode == 0:
            browser("wait", "--load", "networkidle", timeout=30)
            r = browser("get", "text", "body")
            if r.returncode == 0 and r.stdout.strip():
                return f"# {url}\n\n{r.stdout}", "agent-browser"
    return f"# {url}\n\n{http_text(url)}", "http"


def read(video_id, urls, close=True, http_only=False):
    folder = DATA / video_id / "links"
    if not folder.exists() and (DATA / video_id / "liens").exists():
        folder = DATA / video_id / "liens"
    folder.mkdir(parents=True, exist_ok=True)
    results = []
    for n, url in enumerate(urls, 1):
        t = time.time()
        match = GITHUB.match(url)
        try:
            text, engine = (github(match), "gh") if match else page(url, http_only)
            slug = re.sub(r"[^a-z0-9]+", "-", url.lower().split("//")[-1])[:60].strip("-")
            path = folder / f"{n}-{slug}.txt"
            path.write_text(text[:LIMIT], encoding="utf-8")
            results.append({"url": url, "engine": engine, "path": str(path), "chars": min(len(text), LIMIT),
                            "truncated": len(text) > LIMIT, "seconds": round(time.time() - t, 1)})
        except Exception as e:
            results.append({"url": url, "error": str(e)[:300]})
    if close:
        close_browser()
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video_id", help="video folder where the texts are saved")
    ap.add_argument("urls", nargs="+")
    ap.add_argument("--http", action="store_true", help="do not launch a browser")
    a = ap.parse_args()
    results = read(a.video_id, a.urls, http_only=a.http)
    print(json.dumps(results, ensure_ascii=False, indent=1))
    sys.exit(0 if any("path" in r for r in results) else 1)


if __name__ == "__main__":
    main()
