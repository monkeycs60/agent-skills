import base64
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent / "visual-report"
BUILD = SKILL / "scripts" / "build.py"
MEDIA = {
    "before.mp4": b"\x00\x00\x00\x18ftypmp42" + b"before" * 50,
    "after.mp4": b"\x00\x00\x00\x18ftypmp42" + b"after" * 50,
    "valid.png": b"\x89PNG\r\n\x1a\n" + b"valid" * 40,
    "invalid.png": b"\x89PNG\r\n\x1a\n" + b"invalid" * 40,
}


class BuildTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="visual-report-"))
        self.draft = self.tmp / "draft.html"
        shutil.copy(SKILL / "template" / "starter.html", self.draft)
        (self.tmp / "media").mkdir()
        for name, data in MEDIA.items():
            (self.tmp / "media" / name).write_bytes(data)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def build(self, *args, draft=None):
        r = subprocess.run([sys.executable, str(BUILD), str(draft or self.draft), *args], capture_output=True, text=True)
        summary = json.loads(r.stdout.strip().splitlines()[-1]) if r.stdout.strip() else None
        return r, summary

    def test_starter_builds_into_one_self_contained_file(self):
        out = self.tmp / "out" / "report.html"
        r, summary = self.build("-o", str(out), "--target", "browser")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((summary["images"], summary["videos"], summary["inlined"], summary["warnings"]), (2, 2, 4, []))
        page = out.read_text(encoding="utf-8")
        self.assertNotRegex(page, r"""(src|poster)=["']media/""")
        embedded = [base64.b64decode(m) for m in re.findall(r'data:[\w/+.-]+;base64,([A-Za-z0-9+/=]+)', page)]
        self.assertEqual(sorted(embedded), sorted(MEDIA.values()))
        self.assertIn((SKILL / "template" / "report.css").read_text(encoding="utf-8"), page)
        self.assertIn((SKILL / "template" / "viewer.js").read_text(encoding="utf-8"), page)
        self.assertIn('name="viewport"', page)
        self.assertEqual(summary["bytes"], out.stat().st_size)

    def test_pupitre_target_has_no_viewer(self):
        out = self.tmp / "pupitre.html"
        r, summary = self.build("-o", str(out), "--target", "pupitre")
        self.assertEqual(r.returncode, 0, r.stderr)
        page = out.read_text(encoding="utf-8")
        self.assertIn("<style data-visual-report=", page)
        self.assertNotIn("<script data-visual-report=", page)

    def test_over_budget_exits_2_with_the_summary(self):
        (self.tmp / "media" / "valid.png").write_bytes(b"\x89PNG" + b"\x00" * (2 * 1024 * 1024))
        out = self.tmp / "big.html"
        r, summary = self.build("-o", str(out), "--target", "pupitre")
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertGreater(summary["bytes"], 2 * 1024 * 1024)
        self.assertIn("over the 2 MiB budget", r.stderr)
        r, _ = self.build("-o", str(out), "--target", "browser")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_missing_and_remote_media_are_refused(self):
        (self.tmp / "media" / "after.mp4").unlink()
        r, _ = self.build("-o", str(self.tmp / "out.html"))
        self.assertEqual(r.returncode, 1)
        self.assertIn("missing media: media/after.mp4", r.stderr)
        remote = self.tmp / "remote.html"
        remote.write_text('<h1>Remote</h1><img src="https://example.com/a.png" alt="a">', encoding="utf-8")
        r, _ = self.build("-o", str(self.tmp / "remote-out.html"), draft=remote)
        self.assertEqual(r.returncode, 1)
        self.assertIn("remote media", r.stderr)
        r, summary = self.build("-o", str(self.tmp / "remote-out.html"), "--allow-remote", draft=remote)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('src="https://example.com/a.png"', (self.tmp / "remote-out.html").read_text(encoding="utf-8"))

    def test_fragment_and_local_link(self):
        fragment = self.tmp / "fragment.html"
        fragment.write_text('<h1>Disk <em>usage</em></h1><p>See <a href="notes.md">notes</a>.</p>', encoding="utf-8")
        out = self.tmp / "fragment-out.html"
        r, summary = self.build("-o", str(out), draft=fragment)
        self.assertEqual(r.returncode, 0, r.stderr)
        page = out.read_text(encoding="utf-8")
        self.assertIn("<title>Disk usage</title>", page)
        self.assertIn('<main class="report">', page)
        self.assertEqual(len(summary["warnings"]), 1)
        self.assertIn("notes.md", summary["warnings"][0])

    def test_output_cannot_overwrite_the_draft(self):
        r, _ = self.build("-o", str(self.draft))
        self.assertEqual(r.returncode, 1)
        self.assertIn("overwrite the draft", r.stderr)

    def test_copy_to_keeps_foreign_files_and_replaces_its_own(self):
        downloads = self.tmp / "downloads"
        downloads.mkdir()
        (downloads / "report.html").write_text("someone else's file", encoding="utf-8")
        out = self.tmp / "out" / "report.html"
        _, first = self.build("-o", str(out), "--copy-to", str(downloads))
        self.assertEqual(Path(first["copy"]).name, "report-2.html")
        _, again = self.build("-o", str(out), "--copy-to", str(downloads))
        self.assertEqual(again["copy"], first["copy"])
        other = self.tmp / "other" / "draft.html"
        other.parent.mkdir()
        shutil.copy(self.draft, other)
        shutil.copytree(self.tmp / "media", other.parent / "media")
        _, third = self.build("-o", str(self.tmp / "other" / "report.html"), "--copy-to", str(downloads), draft=other)
        self.assertEqual(Path(third["copy"]).name, "report-3.html")
        self.assertEqual((downloads / "report.html").read_text(encoding="utf-8"), "someone else's file")
        self.assertEqual(sorted(p.name for p in downloads.iterdir()), ["report-2.html", "report-3.html", "report.html"])


class StylesheetTest(unittest.TestCase):
    def test_documented_components_exist_in_the_stylesheet(self):
        layout = (SKILL / "references" / "layout.md").read_text(encoding="utf-8")
        table = layout.split("## Components of the stylesheet", 1)[1].split("\n## ", 1)[0]
        classes = {c for group in re.findall(r'class="([^"]+)"', table) for c in group.split()}
        classes |= set(re.findall(r'`"(\w+)"`', table))
        css = (SKILL / "template" / "report.css").read_text(encoding="utf-8")
        self.assertGreaterEqual(len(classes), 8)
        for name in sorted(classes):
            self.assertRegex(css, rf"\.{name}\b", f"layout.md documents .{name}, report.css does not style it")
        self.assertIn("[data-no-zoom]", (SKILL / "template" / "viewer.js").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
