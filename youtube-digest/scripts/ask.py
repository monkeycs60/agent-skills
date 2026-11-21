#!/usr/bin/env python3
import argparse
import json
import math
import re
import sys
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import report as R

DATA = Path.home() / ".local" / "share" / "youtube"
PLAYLISTS = DATA / "playlists"
STOP = set("""le la les un une des de du d l et ou en au aux a à ce cet cette ces qui que quoi dont il ils elle elles on
nous vous je tu me te se sa son ses leur leurs mon ma mes ton ta tes est sont été être avoir ai as avez ont pour par sur
dans avec sans plus moins pas ne n y the a an of to in on for and or is are be it this that with as at by from you your""".split())


def fold(text):
    return unicodedata.normalize("NFKD", text.lower()).encode("ascii", "ignore").decode()


def tokens(text):
    out = []
    for tok in re.findall(r"[a-z0-9][a-z0-9_.+/]*", fold(text)):
        tok = tok.rstrip("./")
        if not tok or tok in STOP:
            continue
        out.append(tok[:-1] if len(tok) > 4 and tok.endswith("s") else tok)
    return out


def contiguous(haystack, needle):
    return any(haystack[i:i + len(needle)] == needle for i in range(len(haystack) - len(needle) + 1))


def resolve(target):
    if target == "all":
        dirs = sorted(p for p in DATA.iterdir() if (p / "transcript.md").exists())
        return "Whole library", [(i + 1, p.name) for i, p in enumerate(dirs)]
    playlist = PLAYLISTS / target / "playlist.json"
    if playlist.exists():
        data = json.loads(playlist.read_text(encoding="utf-8"))
        return data["title"], [(i + 1, v["id"]) for i, v in enumerate(data["videos"]) if v["status"] == "ok"]
    if (DATA / target / "transcript.md").exists():
        return target, [(1, target)]
    sys.exit(f"Unknown target: {target}. Run `yt ask list` to see the processed playlists and videos.")


def list_targets():
    lines = ["# Already processed", ""]
    if PLAYLISTS.exists():
        for p in sorted(PLAYLISTS.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            f = p / "playlist.json"
            if f.exists():
                data = json.loads(f.read_text(encoding="utf-8"))
                ok = sum(v["status"] == "ok" for v in data["videos"])
                when = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d")
                lines.append(f"- playlist `{data['id']}` · {data['title']} · {ok} videos · {when}")
    videos = [p for p in DATA.iterdir() if (p / "transcript.md").exists()]
    lines.append(f"- `all` · whole library · {len(videos)} videos")
    print("\n".join(lines))


def build_docs(videos):
    docs = []
    for n, vid in videos:
        doc = R.parse_transcript(DATA / vid / "transcript.md")
        chapter = None
        for kind, start, text in doc["blocks"]:
            if kind == "h":
                chapter = text
                continue
            docs.append({"n": n, "id": vid, "title": doc["title"], "kind": "transcript", "t": start,
                         "chapter": chapter, "text": text})
        for author, tags, text in doc["comments"]:
            docs.append({"n": n, "id": vid, "title": doc["title"], "kind": f"comment by {author} ({tags})",
                         "t": None, "chapter": None, "text": text})
    for i, d in enumerate(docs):
        d["i"], d["tokens"] = i, tokens(d["text"])
    return docs


def search(docs, terms, top):
    queries = [(term, tokens(term)) for term in terms]
    queries = [(term, toks) for term, toks in queries if toks]
    vocabulary = {tok for _, toks in queries for tok in toks}
    df = Counter(tok for d in docs for tok in set(d["tokens"]) if tok in vocabulary)
    avg = sum(len(d["tokens"]) for d in docs) / max(len(docs), 1)
    hits = []
    for d in docs:
        tf = Counter(t for t in d["tokens"] if t in vocabulary)
        if not tf:
            continue
        score = 0.0
        for tok, f in tf.items():
            idf = math.log(1 + (len(docs) - df[tok] + 0.5) / (df[tok] + 0.5))
            score += idf * f * 2.2 / (f + 1.2 * (0.25 + 0.75 * len(d["tokens"]) / avg))
        matched = [term for term, toks in queries if all(t in tf for t in toks)]
        score += 0.5 * len(matched) + sum(1.0 for _, toks in queries if len(toks) > 1 and contiguous(d["tokens"], toks))
        hits.append((score, d, matched))
    hits.sort(key=lambda h: -h[0])
    counts = {term: sum(1 for d in docs if all(t in d["tokens"] for t in toks)) for term, toks in queries}
    per_video = Counter(d["id"] for _, d, _ in hits)
    return hits[:top], counts, per_video


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("target", help="playlist id, video id, all, or list")
    ap.add_argument("--terms", help="comma-separated terms, including synonyms and other languages")
    ap.add_argument("--top", type=int, default=12)
    ap.add_argument("--context", type=int, default=1, help="neighbouring paragraphs shown around a passage")
    a = ap.parse_args()
    if a.target == "list":
        return list_targets()
    if not a.terms:
        sys.exit("--terms is required.")
    title, videos = resolve(a.target)
    docs = build_docs(videos)
    terms = [t.strip() for t in a.terms.split(",") if t.strip()]
    hits, counts, per_video = search(docs, terms, a.top)
    names = {vid: R.parse_transcript(DATA / vid / "transcript.md")["title"] for _, vid in videos}
    touched = {d["id"] for _, d, _ in hits}
    beyond = [f"#{n} ({per_video[v]})" for n, v in videos if v in per_video and v not in touched]
    out = [f"# Search in \"{title}\"", "",
           f"- {len(hits)} passages kept out of {len(docs)} paragraphs and comments, {len(touched)} of {len(videos)} videos.",
           "- Matches per term: " + ", ".join(f"{t} {c}" for t, c in counts.items()) + ".",
           "- No match for any term: " + (", ".join(f"#{n} {names[v]}" for n, v in videos if v not in per_video) or "no video") + ".",
           "- Matches outside the passages shown (rerun with a larger --top): " + (", ".join(beyond) or "none") + ".",
           ""]
    for score, d, matched in sorted(hits, key=lambda h: (h[1]["n"], h[1]["t"] if h[1]["t"] is not None else 1e9)):
        where = (f"[{R.clock(d['t'])}](https://youtu.be/{d['id']}?t={int(d['t'])})" if d["t"] is not None else d["kind"])
        out.append(f"## #{d['n']} {d['title']} · {where} · score {score:.1f}" + (f" · chapter \"{d['chapter']}\"" if d["chapter"] else ""))
        if d["t"] is not None and a.context:
            before = [x for x in docs[max(0, d["i"] - a.context):d["i"]] if x["id"] == d["id"] and x["t"] is not None]
            out += [f"> …{x['text'][-300:]}" for x in before]
        out.append(d["text"])
        if d["t"] is not None and a.context:
            after = [x for x in docs[d["i"] + 1:d["i"] + 1 + a.context] if x["id"] == d["id"] and x["t"] is not None]
            out += [f"> {x['text'][:300]}…" for x in after]
        out.append("")
    print("\n".join(out))


if __name__ == "__main__":
    main()
