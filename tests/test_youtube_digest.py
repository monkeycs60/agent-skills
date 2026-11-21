import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SKILL = Path(__file__).resolve().parent.parent / "youtube-digest"
sys.path.insert(0, str(SKILL / "scripts"))

import report as R  # noqa: E402
import transcript as T  # noqa: E402

VIDEO = "abcdefghijk"
INFO = {
    "id": VIDEO, "title": "Agents in production", "channel": "Example Channel", "date": "2026-01-02", "duration": 185,
    "description": "Slides: https://example.org/slides", "links": ["https://github.com/example/agents", "https://example.org/slides"],
    "chapters": [(0, "Intro"), (60, "Demo")],
    "comments": [{"author": "@viewer", "text": "The retry loop at 1:10 saved my week.", "likes": 46, "pinned": False, "uploader": False},
                 {"author": "@host", "text": "Code: https://github.com/example/agents", "likes": 3, "pinned": True, "uploader": True}],
}
CUES = [(0, "Hello and welcome."), (12, "Today we ship agents."), (40, "First the setup."),
        (61, "Now the demo starts."), (70, "The retry loop keeps the agent alive."), (120, "That is all.")]
NOTES = {
    "lang": "en", "summary": "How to run **agents** in production.",
    "verdict": {"rating": "watch", "text": "Concrete and short.", "moments": [{"t": 61, "label": "The demo"}]},
    "key_points": [{"t": 70, "title": "Retry loop", "text": "Keeps the agent alive."}],
    "diagrams": [{"title": "Flow", "mermaid": "flowchart LR\n  A --> B", "caption": "Two steps."}],
    "steps": [{"title": "Install", "text": "Run it.", "code": "npx agents <init>", "t": 40}],
    "resources": [{"url": "https://github.com/example/agents", "title": "Repository", "adds": "The code.", "read": True}],
    "comments": {"summary": "Mostly thanks.", "points": [{"type": "warning", "text": "Pin the version.", "author": "@viewer", "likes": 46}]},
    "blind_spots": [{"t": 120, "text": "No word on cost."}],
}


class TranscriptToReportTest(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp(prefix="youtube-digest-"))
        self.data = self.home / ".local" / "share" / "youtube"
        self.folder = self.data / VIDEO
        self.folder.mkdir(parents=True)
        patches = [mock.patch.object(R, "DATA", self.data), mock.patch.object(R, "thumbnail", return_value=None),
                   mock.patch.object(R, "find_chrome", return_value=None)]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def tearDown(self):
        shutil.rmtree(self.home, ignore_errors=True)

    def write_transcript(self, lang):
        blocks = T.paragraphs(CUES, INFO["chapters"])
        source = T.LABELS[lang]["auto"].format(key="en")
        text = T.render(INFO, source, blocks, T.useful_links(INFO), lang)
        (self.folder / "transcript.md").write_text(text, encoding="utf-8")
        return blocks, source

    def test_transcript_round_trip(self):
        for lang in ("en", "fr"):
            with self.subTest(lang=lang):
                blocks, source = self.write_transcript(lang)
                doc = R.parse_transcript(self.folder / "transcript.md")
                self.assertEqual((doc["title"], doc["channel"], doc["date"], doc["duration"]),
                                 (INFO["title"], INFO["channel"], INFO["date"], "03:05"))
                self.assertEqual(doc["link"], f"https://youtu.be/{VIDEO}")
                self.assertEqual(doc["source"], source)
                self.assertEqual(doc["blocks"], blocks)
                self.assertEqual([c[0] for c in doc["comments"]], ["@viewer", "@host"])
                self.assertEqual(doc["description"], INFO["description"])

    def test_report_from_notes(self):
        self.write_transcript("en")
        (self.folder / "notes.json").write_text(json.dumps(NOTES), encoding="utf-8")
        out, doc, labels, rendered, failed = R.build(VIDEO)
        page = out.read_text(encoding="utf-8")
        self.assertEqual((rendered, failed), (0, 1))
        words = sum(len(text.split()) for _, text in CUES)
        for expected in ("Agents in production · report", "Watch it", "<strong>agents</strong>", "Retry loop",
                         f'href="https://youtu.be/{VIDEO}?t=61"', f"Full transcript · {words} words",
                         '<pre class="mermaid-src">flowchart LR', "npx agents &lt;init&gt;", "No word on cost.",
                         "The 2 most-liked comments"):
            self.assertIn(expected, page)
        self.assertNotIn('class="thumb"', page)

    def test_legacy_french_notes(self):
        self.write_transcript("fr")
        legacy = {"en_une_phrase": "Un résumé.", "verdict": {"avis": "survoler", "texte": "Inégal."},
                  "points_cles": [{"t": 61, "titre": "Démo", "texte": "La démo."}], "commentaires": {"resume": "Peu."}}
        (self.folder / "fiche.json").write_text(json.dumps(legacy), encoding="utf-8")
        out, *_ = R.build(VIDEO)
        page = out.read_text(encoding="utf-8")
        for expected in ('<html lang="fr">', "À survoler", "Points clés", "Un résumé.", "Transcription complète"):
            self.assertIn(expected, page)

    def test_ask_finds_the_passage(self):
        self.write_transcript("en")
        env = {**os.environ, "HOME": str(self.home)}
        yt = SKILL / "scripts" / "yt"
        r = subprocess.run([str(yt), "ask", VIDEO, "--terms", "retry loop"], capture_output=True, text=True, env=env, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("The retry loop keeps the agent alive.", r.stdout)
        self.assertIn(f"https://youtu.be/{VIDEO}?t=61", r.stdout)
        self.assertIn("comment by @viewer", r.stdout)
        r = subprocess.run([str(yt), "ask", "list"], capture_output=True, text=True, env=env, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("whole library · 1 videos", r.stdout)
        r = subprocess.run([str(yt), "nope"], capture_output=True, text=True, env=env, timeout=60)
        self.assertEqual(r.returncode, 2)


if __name__ == "__main__":
    unittest.main()
