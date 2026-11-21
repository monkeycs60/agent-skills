#!/usr/bin/env python3
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAX_DESCRIPTION = 300
MAX_SKILL_LINES = 150


def frontmatter(text):
    match = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not match:
        return None
    fields = {}
    for line in match.group(1).splitlines():
        key, _, value = line.partition(":")
        if value:
            fields[key.strip()] = value.strip().strip('"')
    return fields


def check_skill(skill):
    problems = []
    text = (skill / "SKILL.md").read_text(encoding="utf-8")
    meta = frontmatter(text)
    if meta is None:
        return [f"{skill.name}: SKILL.md has no YAML frontmatter"]
    if meta.get("name") != skill.name:
        problems.append(f"{skill.name}: name '{meta.get('name')}' differs from the folder")
    description = meta.get("description", "")
    if not description:
        problems.append(f"{skill.name}: missing description")
    elif len(description) > MAX_DESCRIPTION:
        problems.append(f"{skill.name}: description is {len(description)} characters (> {MAX_DESCRIPTION})")
    if not re.match(r"^[A-Za-z]", description) or re.search(r"[àâçéèêëîïôûùüÿœ]", description[:80]):
        problems.append(f"{skill.name}: description must be in English")
    if len(text.splitlines()) > MAX_SKILL_LINES:
        problems.append(f"{skill.name}: SKILL.md exceeds {MAX_SKILL_LINES} lines")
    for ref in sorted(set(re.findall(r"(?<![\w./~-])((?:references|scripts|template|templates|example|tests)/[\w./-]+\.\w+)", text))):
        if not (skill / ref).exists():
            problems.append(f"{skill.name}: referenced file not found: {ref}")
    for path in sorted(skill.rglob("*")):
        if not path.is_file() or ".venv" in path.parts or "node_modules" in path.parts:
            continue
        rel = path.relative_to(ROOT)
        head = path.read_bytes()[:64]
        shebang = head.startswith(b"#!")
        if shebang and not path.stat().st_mode & 0o111:
            problems.append(f"{rel}: shebang without executable bit")
        if path.suffix == ".sh" or (shebang and b"bash" in head.split(b"\n")[0]):
            r = subprocess.run(["bash", "-n", str(path)], capture_output=True, text=True)
            if r.returncode:
                problems.append(f"{rel}: bash -n : {r.stderr.strip()[:200]}")
        elif path.suffix == ".py":
            try:
                compile(path.read_text(encoding="utf-8"), str(path), "exec")
            except SyntaxError as e:
                problems.append(f"{rel}: line {e.lineno}: {e.msg}")
        elif path.suffix in {".js", ".mjs"} and shutil.which("node"):
            r = subprocess.run(["node", "--check", str(path)], capture_output=True, text=True)
            if r.returncode:
                problems.append(f"{rel}: node --check : {r.stderr.strip().splitlines()[-1][:200]}")
    return problems


def main():
    skills = sorted(p.parent for p in ROOT.glob("*/SKILL.md"))
    problems = [p for skill in skills for p in check_skill(skill)]
    for skill in skills:
        print(f"{'✗' if any(p.startswith(skill.name) for p in problems) else '✓'} {skill.name}")
    if problems:
        print("\n" + "\n".join(problems))
        sys.exit(1)
    print(f"\n{len(skills)} skills checked (Python {sys.version_info.major}.{sys.version_info.minor}).")


if __name__ == "__main__":
    main()
