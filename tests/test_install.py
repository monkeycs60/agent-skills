import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import check_skills as C

SKILLS_CLI = "skills@1.9.0"


def clean_copy(dest):
    files = C.shipped_files(C.ROOT)
    for rel in files:
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(C.ROOT / rel, target)
    return files


class Sandbox(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="install-"))
        self.repo, self.home = self.tmp / "repo", self.tmp / "home"
        self.home.mkdir()
        self.files = clean_copy(self.repo)
        self.skills = (self.repo / "tests" / "skills.txt").read_text(encoding="utf-8").split()
        self.env = {**os.environ, "HOME": str(self.home)}

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class RootInstallerTest(Sandbox):
    def setUp(self):
        super().setUp()
        self.with_installer = sorted(s for s in self.skills if (self.repo / s / "install.sh").is_file())
        for skill in self.with_installer:
            (self.repo / skill / "install.sh").write_text(f'#!/usr/bin/env bash\ntouch "$HOME/ran-{skill}"\n', encoding="utf-8")
        (self.home / ".codex" / "skills").mkdir(parents=True)

    def install(self, *skills):
        return subprocess.run(["bash", str(self.repo / "install.sh"), *skills], capture_output=True, text=True,
                              env=self.env, timeout=60)

    def test_links_every_skill_and_runs_its_installer(self):
        r = self.install()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        for skill in self.skills:
            for agent in (".claude", ".codex"):
                link = self.home / agent / "skills" / skill
                self.assertTrue(link.is_symlink(), f"{link} missing")
                self.assertEqual(link.resolve(), (self.repo / skill).resolve())
        self.assertFalse((self.home / ".agents").exists())
        self.assertEqual(sorted(p.name[4:] for p in self.home.glob("ran-*")), self.with_installer)
        again = self.install()
        self.assertEqual(again.returncode, 0, again.stdout)
        self.assertNotIn("already exists", again.stdout)
        self.assertEqual(again.stdout.count("  ✓ "), 2 * len(self.skills))

    def test_never_replaces_an_existing_skill(self):
        mine = self.home / ".claude" / "skills" / self.skills[0]
        mine.mkdir(parents=True)
        (mine / "SKILL.md").write_text("my own version", encoding="utf-8")
        r = self.install(self.skills[0], "no-such-skill")
        self.assertIn(f"{mine} already exists: left as is", r.stdout)
        self.assertIn("✗ no-such-skill: unknown skill", r.stdout)
        self.assertEqual((mine / "SKILL.md").read_text(encoding="utf-8"), "my own version")
        self.assertTrue((self.home / ".codex" / "skills" / self.skills[0]).is_symlink())

    def test_exit_status_reflects_the_outcome(self):
        without_installer = next(s for s in self.skills if s not in self.with_installer)
        self.assertEqual(self.install(without_installer).returncode, 0)
        self.assertNotEqual(self.install("no-such-skill").returncode, 0)


class SkillsCliTest(Sandbox):
    def test_npx_skills_add_installs_every_file(self):
        if not shutil.which("npx"):
            if os.environ.get("CI"):
                self.fail("npx not found: the skills CLI needs Node 22.20 or newer")
            self.skipTest("npx not found (Node 22.20 or newer)")
        r = subprocess.run(["npx", "-y", SKILLS_CLI, "add", str(self.repo), "-g", "-y", "--skill", "*", "-a", "claude-code"],
                           capture_output=True, text=True, env=self.env, timeout=300)
        self.assertEqual(r.returncode, 0, r.stdout[-3000:] + r.stderr[-3000:])
        installed = self.home / ".claude" / "skills"
        self.assertEqual(sorted(p.name for p in installed.iterdir()), sorted(self.skills), r.stdout[-3000:])
        for rel in self.files:
            skill = rel.split("/")[0]
            if skill not in self.skills:
                continue
            source, copy = self.repo / rel, installed / rel
            self.assertTrue(copy.is_file(), f"{rel} not installed")
            self.assertEqual(copy.read_bytes(), source.read_bytes(), rel)
            self.assertEqual(bool(copy.stat().st_mode & 0o111), bool(source.stat().st_mode & 0o111), f"{rel} executable bit")


if __name__ == "__main__":
    unittest.main()
