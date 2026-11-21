import os
import shutil
import tempfile
import textwrap
import unittest
from pathlib import Path

import check_skills as C

DESCRIPTION = "Builds a tiny report from a draft. Use when the user asks for a report."


def skill_md(name="alpha", description=DESCRIPTION, body="# Alpha\n\nRead [the guide](references/guide.md).\n"):
    return f"---\nname: {name}\ndescription: {description}\n---\n\n{body}"


class Repo:

    def __init__(self):
        self.root = Path(tempfile.mkdtemp(prefix="check-skills-"))
        self.write("tests/skills.txt", "alpha\n")
        self.write("README.md", "# Skills\n\n[`alpha`](alpha/)\n")
        self.write("alpha/SKILL.md", skill_md())
        self.write("alpha/references/guide.md", "# Guide\n\nRun `scripts/run.sh`.\n")
        self.write("alpha/scripts/run.sh", "#!/usr/bin/env bash\necho ok\n", executable=True)

    def write(self, rel, text, executable=False):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        path.chmod(0o755 if executable else 0o644)
        return path

    def problems(self):
        return C.check(self.root)[1]

    def cleanup(self):
        shutil.rmtree(self.root, ignore_errors=True)


class FrontmatterTest(unittest.TestCase):
    def parse(self, yaml_text):
        return C.frontmatter(f"---\n{textwrap.dedent(yaml_text).strip()}\n---\nBody\n")[0]

    def test_plain_and_quoted_values(self):
        self.assertEqual(self.parse("name: alpha\ndescription: Plain text."), {"name": "alpha", "description": "Plain text."})
        fields = self.parse('name: alpha\ndescription: "Says \\"hi\\": then stops."')
        self.assertEqual(fields["description"], 'Says "hi": then stops.')
        self.assertEqual(self.parse("name: alpha\ndescription: 'It''s fine.'")["description"], "It's fine.")

    def test_multiline_descriptions(self):
        folded = self.parse("""
            name: alpha
            description: >-
              First line
              second line.
        """)
        self.assertEqual(folded["description"], "First line second line.")
        literal = self.parse("""
            name: alpha
            description: |
              Two
              lines
        """)
        self.assertEqual(literal["description"], "Two\nlines\n")

    def test_windows_line_endings(self):
        fields, body = C.frontmatter("---\r\nname: alpha\r\ndescription: Text.\r\n---\r\nBody\r\n")
        self.assertEqual(fields["name"], "alpha")
        self.assertIn("Body", body)

    def test_invalid_yaml_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "invalid YAML"):
            self.parse("name: alpha\nbroken: [unterminated\ndescription: Text.")

    def test_duplicate_keys_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate key description"):
            self.parse("name: alpha\ndescription: One.\ndescription: Two.")

    def test_frontmatter_must_be_a_mapping(self):
        with self.assertRaisesRegex(ValueError, "mapping"):
            self.parse("- name\n- description")
        with self.assertRaisesRegex(ValueError, "mapping"):
            C.frontmatter("---\n---\nBody\n")

    def test_missing_or_unclosed_frontmatter(self):
        with self.assertRaisesRegex(ValueError, "no YAML frontmatter"):
            C.frontmatter("# Title\n")
        with self.assertRaisesRegex(ValueError, "no YAML frontmatter"):
            C.frontmatter("---\nname: alpha\n")


class MetadataTest(unittest.TestCase):
    def problems(self, **fields):
        return C.metadata_problems("alpha", {"name": "alpha", "description": DESCRIPTION, **fields})

    def test_valid_metadata(self):
        self.assertEqual(self.problems(), [])

    def test_wrong_types(self):
        self.assertIn("name must be a string, got int", self.problems(name=12))
        self.assertIn("name must be a string, got bool", self.problems(name=True))
        self.assertIn("description must be a string, got list", self.problems(description=["a", "b"]))

    def test_empty_and_missing_description(self):
        self.assertIn("description is empty", self.problems(description="   "))
        self.assertIn("missing description", C.metadata_problems("alpha", {"name": "alpha"}))

    def test_length_is_measured_on_the_interpreted_value(self):
        self.assertEqual(self.problems(description="Use it. " + "x" * (C.MAX_DESCRIPTION - 8)), [])
        self.assertTrue(any("characters (>" in p for p in self.problems(description="Use it. " * 40)))

    def test_name_rules(self):
        self.assertIn("name 'beta' differs from the folder", self.problems(name="beta"))
        self.assertTrue(any("lowercase" in p for p in C.metadata_problems("Alpha_1", {"name": "Alpha_1", "description": DESCRIPTION})))
        self.assertTrue(any("reserved" in p for p in C.metadata_problems("claude-x", {"name": "claude-x", "description": DESCRIPTION})))

    def test_xml_tags(self):
        self.assertIn("description must not contain XML tags", self.problems(description="Use for <b>bold</b> reports."))

    def test_language_heuristic(self):
        self.assertIsNotNone(C.language_problem("Produit un rapport complet pour chaque projet."))
        self.assertIsNotNone(C.language_problem("Génère des images."))
        self.assertIsNotNone(C.language_problem("« Quote » first."))
        self.assertIsNone(C.language_problem("Plans meals a la carte for the week, one recipe per day."))

    def test_every_shipped_description_reads_as_english(self):
        for skill in sorted(C.ROOT.glob("*/SKILL.md")):
            fields, _ = C.frontmatter(skill.read_text(encoding="utf-8"))
            self.assertIsNone(C.language_problem(fields["description"]), skill.parent.name)


class PackageTest(unittest.TestCase):
    def setUp(self):
        self.repo = Repo()

    def tearDown(self):
        self.repo.cleanup()

    def assertProblem(self, fragment):
        problems = self.repo.problems()
        self.assertTrue(any(fragment in p for p in problems), f"no problem with {fragment!r} in {problems}")

    def test_valid_repository(self):
        self.assertEqual(self.repo.problems(), [])

    def test_skill_list(self):
        (self.repo.root / "alpha/SKILL.md").unlink()
        self.assertProblem("alpha: listed in tests/skills.txt but alpha/SKILL.md is missing")
        self.assertProblem("no skill found")
        self.repo.write("alpha/SKILL.md", skill_md())
        self.repo.write("beta/SKILL.md", skill_md("beta"))
        self.assertProblem("beta: has a SKILL.md but is not listed in tests/skills.txt")
        self.repo.write("alpha/template/SKILL.md", skill_md("template"))
        self.assertProblem("alpha/template/SKILL.md: nested SKILL.md")

    def test_unexpected_root_entry(self):
        self.repo.write("notes.txt", "scratch\n")
        self.assertProblem("notes.txt: unexpected entry at the repository root")

    def test_references_follow_documents_and_survive_cycles(self):
        self.repo.write("alpha/references/guide.md", "# Guide\n\nSee [more](more.md).\n")
        self.repo.write("alpha/references/more.md", "# More\n\nBack to [the guide](guide.md#guide).\n")
        self.assertEqual(self.repo.problems(), [])
        self.repo.write("alpha/references/more.md", "# More\n\nSee [layout](layout.md).\n")
        self.assertProblem("alpha/references/more.md: broken link to layout.md")

    def test_any_local_link_is_checked(self):
        self.repo.write("alpha/SKILL.md", skill_md(body="Install [requirements](requirements-audit.txt).\n[g](references/guide.md)\n"))
        self.assertProblem("alpha/SKILL.md: broken link to requirements-audit.txt")

    def test_link_kinds(self):
        self.repo.write("alpha/SKILL.md", skill_md(body="[g](references/guide.md#nope) [s](scripts/run.sh/) [x](../README.md)\n"))
        self.assertProblem("no heading with the anchor #nope")
        self.assertProblem("expects a folder, found a file")
        self.assertProblem("leaves the skill folder")
        (self.repo.root / "alpha/scripts/run.sh").unlink()
        (self.repo.root / "alpha/scripts/run.sh").mkdir()
        self.repo.write("alpha/SKILL.md", skill_md(body="[g](references/guide.md) [s](scripts/run.sh)\n"))
        self.assertProblem("expects a file, found a folder")

    def test_code_mentions(self):
        self.repo.write("alpha/references/guide.md", "# Guide\n\n`scripts/gone.sh` then `missing.py`, `notes.json`, `media/a.png`.\n")
        self.assertProblem("mentions scripts/gone.sh, which is not in the skill")
        self.assertProblem("mentions missing.py, which is not in the alpha skill")
        problems = " ".join(self.repo.problems())
        self.assertNotIn("notes.json", problems)
        self.assertNotIn("media/a.png", problems)

    def test_installed_paths_point_into_their_skill(self):
        self.repo.write("tests/skills.txt", "alpha\nbeta\n")
        self.repo.write("README.md", "[`alpha`](alpha/) [`beta`](beta/)\n")
        self.repo.write("beta/SKILL.md", skill_md("beta", body="# Beta\n"))
        self.repo.write("beta/scripts/ab", "#!/usr/bin/env bash\n", executable=True)
        self.repo.write("alpha/references/guide.md", "# Guide\n\n`scripts/run.sh`, `~/.claude/skills/beta/scripts/ab open`.\n")
        self.assertEqual(self.repo.problems(), [])
        self.repo.write("alpha/references/guide.md", "# Guide\n\n`scripts/run.sh`, `~/.claude/skills/beta/scripts/zz`.\n")
        self.assertProblem("alpha/references/guide.md: mentions scripts/zz")

    def test_orphan_document(self):
        self.repo.write("alpha/references/unused.md", "# Unused\n")
        self.assertProblem("alpha/references/unused.md: not referenced from SKILL.md")

    def test_root_installer_and_scripts(self):
        self.repo.write("install.sh", "#!/usr/bin/env bash\nif then\n", executable=True)
        self.assertProblem("install.sh: bash -n")
        self.repo.write("alpha/scripts/run.sh", "#!/usr/bin/env bash\necho ok\n")
        self.assertProblem("alpha/scripts/run.sh: shebang without executable bit")
        self.repo.write("alpha/references/guide.md", "# Guide\n\n`scripts/run.sh`\n", executable=True)
        self.assertProblem("alpha/references/guide.md: executable bit without a shebang line")
        self.repo.write("alpha/scripts/win.sh", "#!/usr/bin/env bash\r\necho ok\r\n", executable=True)
        self.assertProblem("alpha/scripts/win.sh: Windows line endings")

    def test_syntax_of_data_files(self):
        self.repo.write("alpha/agents/openai.yaml", "a: 1\na: 2\n")
        self.repo.write("alpha/template/data.json", "{\"a\": }\n")
        self.repo.write("alpha/scripts/tool.py", "def f(:\n")
        self.assertProblem("alpha/agents/openai.yaml: invalid YAML")
        self.assertProblem("alpha/template/data.json: invalid JSON")
        self.assertProblem("alpha/scripts/tool.py: line 1")

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_javascript(self):
        self.repo.write("alpha/scripts/a.js", "const b = require('./b');\n")
        self.assertProblem("alpha/scripts/a.js: imports ./b, which does not exist")
        self.repo.write("alpha/scripts/b.js", "function (\n")
        self.assertProblem("alpha/scripts/b.js: node --check")

    def test_stray_files(self):
        self.repo.write("alpha/.DS_Store", "x")
        self.repo.write("alpha/scripts/debug.log", "x")
        self.assertProblem("alpha/.DS_Store: stray file")
        self.assertProblem("alpha/scripts/debug.log: stray file")
        link = self.repo.root / "alpha/outside"
        os.symlink("/etc/hostname", link)
        self.assertProblem("alpha/outside: symlink")

    def test_readme(self):
        self.repo.write("docs/shot.png", "png")
        self.assertProblem("docs/shot.png: not used by README.md")
        self.repo.write("README.md", "# Skills\n\n<img src=\"docs/shot.png\"> [missing](docs/gone.png)\n")
        self.assertProblem("README.md: does not link to the alpha skill")
        self.assertProblem("README.md: broken link to docs/gone.png")


if __name__ == "__main__":
    unittest.main()
