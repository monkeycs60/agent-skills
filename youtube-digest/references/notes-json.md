# `notes.json` format

`scripts/report.py` reads `~/.local/share/youtube/<id>/notes.json` and turns it into `report.html`. Write every text in the user's language and set `lang` to match: `fr` gives French report labels, `en` (the default) English ones; any other language keeps the English labels. Texts accept `code`, **bold**, *italic* and [link](https://…), nothing else. `t` is a number of seconds, taken from the `?t=` links of the transcript.

```json
{
  "lang": "en",
  "summary": "What the video is about and for whom, in one sentence.",
  "verdict": {
    "rating": "watch | skim | skip",
    "text": "Why, in two or three sentences.",
    "moments": [{"t": 38, "label": "The demo"}]
  },
  "key_points": [{"t": 190, "title": "Short title", "text": "One or two sentences."}],
  "diagrams": [{"title": "Who talks to whom", "mermaid": "flowchart LR\n  A[Client] -->|JSON-RPC| B[Server]", "caption": "What to take away from the diagram."}],
  "steps": [{"title": "Step", "text": "What to do.", "code": "npx …", "language": "bash", "t": 383}],
  "resources": [{"url": "https://…", "title": "Companion article", "adds": "What it adds beyond the video.", "read": true}],
  "comments": {
    "summary": "One sentence on the overall tone of the comments.",
    "points": [{"type": "correction | warning | alternative | question | opinion", "text": "What is said.", "author": "@handle", "likes": 46}]
  },
  "blind_spots": [{"t": 519, "text": "What is shown without being said, and where to find it."}]
}
```

## Required
- `summary`, `verdict` and `comments.summary`: always, even when the comments are only thanks; then say so in one sentence, with `points` empty.
- `key_points`: 5 to 10, each with `t`.
- `steps`: only for a tutorial. The `code` comes from the article or repository read, otherwise from the transcript. Never invent it: reconstructed code says so in `text`.
- `resources`: every useful link of the transcript, with `read: true` for those actually read.
- `blind_spots`: only what no resource filled in.

## Diagrams
- Make one as soon as the video describes a process, an installation, an architecture or an exchange between components. One or two are expected, three at most.
- `flowchart LR` for an architecture or a pipeline, `flowchart TD` for steps with choices, `sequenceDiagram` for a protocol or calls between services.
- Short labels, `<br>` to break a line, quotes around a label that contains parentheses, colons or a slash.
- A diagram that fails to render appears as source in the report: `report.py` returns `schemas_failed`. Fix the syntax and rerun.

## Older caches
Earlier videos have `fiche.json` with French keys (`en_une_phrase`, `points_cles`, `schemas`, `etapes`, `ressources`, `commentaires`, `angles_morts`, `titre`, `texte`, `legende`, `apport`, `lu`, `avis: regarder | survoler | passer`, comment types `alerte` and `avis`) and their linked pages in `liens/`. `report.py` and `playlist.py` still read them and render them with French labels; `notes.json` wins when both exist. French `transcript.md` labels (`Chaîne`, `Transcription`, `Commentaires les plus appréciés`) are parsed too, by `report.py` and `ask.py`.
