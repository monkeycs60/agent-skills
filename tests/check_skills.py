#!/usr/bin/env python3
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote

try:
    import yaml
except ImportError:
    sys.exit("check_skills.py needs PyYAML: python3 -m pip install PyYAML\n"
             "or, without touching your Python: uv run --no-project --with PyYAML python3 tests/check_skills.py")

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = "tests/skills.txt"
MAX_DESCRIPTION = 300
MAX_NAME = 64
MAX_SKILL_LINES = 150
MAX_FILE_BYTES = 5 * 1024 * 1024
ROOT_ENTRIES = {".github", ".gitignore", "LICENSE", "README.md", "docs", "install.sh", "tests"}
SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__"}
JUNK = re.compile(r"(^|/)(\.DS_Store|Thumbs\.db|desktop\.ini|__pycache__|\.venv|node_modules|\.idea|\.vscode|\.env(\.[^/]*)?)(/|$)"
                  r"|\.(pyc|pyo|log|swp|swo|orig|rej|bak|tmp)$|~$")
TEXT = {".md", ".py", ".sh", ".js", ".mjs", ".cjs", ".json", ".yml", ".yaml", ".html", ".css", ".txt", ".toml", ".csv"}
FILE_EXT = {"md", "py", "sh", "js", "mjs", "cjs", "json", "jsonl", "txt", "html", "css", "yaml", "yml", "toml", "csv",
            "tsv", "png", "jpg", "jpeg", "webp", "gif", "svg", "mp4", "webm", "mov", "woff2", "zip", "gz", "fit",
            "tcx", "gpx", "pdf", "xml", "ini", "cfg"}
USER_FILES = {
    "ART_DIRECTION.md", "CLAUDE.md", "fiche.json", "index.json", "notes.json", "recipe.json", "report.html",
    "state.json", "still-XXXXX.jpg", "strava.json", "summarizedActivities.json",
    "synthese.json", "synthesis.json", "transcript.md", "media/",
}
NAME = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
XML_TAG = re.compile(r"<[A-Za-z/!][^>]*>")
FRENCH = set("le la les un une des du au aux et ou pour par avec dans sur chaque qui que est sont ce cette ces son sa "
             "ses leur leurs pas ne votre vos nous vous il elle ils elles".split())
ENGLISH = set("the a an of to for with and or in on is are when use it this that your you by from as at be".split())
LINK = re.compile(r"\[(?:[^\[\]]|\[[^\]]*\])*\]\(\s*<?([^\s)>]+)>?(?:\s+(?:\"[^\"]*\"|'[^']*'))?\s*\)")
REF_DEF = re.compile(r"^ {0,3}\[[^\]]+\]:\s*<?(\S+?)>?(?:\s|$)", re.M)
HTML_REF = re.compile(r"""\b(?:src|href)\s*=\s*["']([^"']+)["']""", re.I)
JS_IMPORT = re.compile(r"""(?:require\s*\(\s*|import\s*\(\s*|\bfrom\s+|\bimport\s+)["'](\.\.?/[^"']+)["']""")
SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:|^//")
INSTALLED = re.compile(r"^(?:~|\$HOME)/\.(?:claude|codex|agents)/skills/([a-z0-9-]+)/(.+)$")


class StrictLoader(yaml.SafeLoader):
    pass


def _mapping_without_duplicates(loader, node):
    keys = [loader.construct_object(key, deep=True) for key, _ in node.value]
    duplicates = sorted({str(k) for k in keys if keys.count(k) > 1})
    if duplicates:
        raise yaml.constructor.ConstructorError(None, None, f"duplicate key {', '.join(duplicates)}", node.start_mark)
    return loader.construct_mapping(node, deep=True)


StrictLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping_without_duplicates)


def one_line(error):
    return " ".join(str(error).split())[:220]


def load_yaml(text):
    return list(yaml.load_all(text, Loader=StrictLoader))


def frontmatter(text):
    match = re.match(r"\A---[ \t]*\r?\n(.*?)^---[ \t]*\r?(?:\n|\Z)", text, re.S | re.M)
    if not match:
        raise ValueError("no YAML frontmatter: the file must start with a line '---' and close it with another")
    try:
        fields = yaml.load(match.group(1), Loader=StrictLoader)
    except yaml.YAMLError as e:
        raise ValueError(f"invalid YAML frontmatter: {one_line(e)}") from None
    if not isinstance(fields, dict):
        raise ValueError(f"frontmatter must be a YAML mapping, got {type(fields).__name__}")
    return fields, text[match.end():]


def language_problem(description):
    if not re.match(r"[A-Za-z]", description):
        return "must start with an ASCII letter"
    if re.search(r"[àâçéèêëîïôûùüÿœ]", description[:80], re.I):
        return "has French accents in its first 80 characters"
    words = re.findall(r"[a-zà-ÿœ]+", description.lower())
    french, english = sum(w in FRENCH for w in words), sum(w in ENGLISH for w in words)
    if french >= 3 and french > english:
        return f"reads as French ({french} French function words, {english} English ones)"
    return None


def metadata_problems(name, fields):
    problems = []
    value = fields.get("name")
    if not isinstance(value, str):
        problems.append(f"name must be a string, got {type(value).__name__}")
    else:
        if value != name:
            problems.append(f"name '{value}' differs from the folder")
        if not NAME.match(value) or len(value) > MAX_NAME:
            problems.append(f"name '{value}' must be lowercase letters, digits and single hyphens, {MAX_NAME} characters at most")
        if "claude" in value or "anthropic" in value:
            problems.append("name must not contain 'claude' or 'anthropic' (reserved by Claude hosts)")
    description = fields.get("description")
    if description is None:
        problems.append("missing description")
    elif not isinstance(description, str):
        problems.append(f"description must be a string, got {type(description).__name__}")
    elif not description.strip():
        problems.append("description is empty")
    else:
        if len(description) > MAX_DESCRIPTION:
            problems.append(f"description is {len(description)} characters (> {MAX_DESCRIPTION})")
        if XML_TAG.search(description):
            problems.append("description must not contain XML tags")
        reason = language_problem(description)
        if reason:
            problems.append(f"description should be in English (heuristic): it {reason}")
    return problems


def shipped_files(root):
    if (root / ".git").exists() and shutil.which("git"):
        r = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "-co", "--exclude-standard"],
                           capture_output=True, text=True)
        if r.returncode == 0:
            paths = {p for p in r.stdout.split("\0") if p}
            return sorted(p for p in paths if (root / p).is_file() or (root / p).is_symlink())
    found = []
    for folder, dirs, names in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for name in names:
            if not name.endswith((".pyc", ".pyo")):
                found.append((Path(folder) / name).relative_to(root).as_posix())
    return sorted(found)


def split_markdown(text):
    prose, code, fence = [], [], None
    for line in text.splitlines():
        marker = re.match(r"^\s*(`{3,}|~{3,})", line)
        if fence:
            if marker and marker.group(1)[0] == fence[0] and len(marker.group(1)) >= len(fence):
                fence = None
            else:
                code.append(line)
            continue
        if marker:
            fence = marker.group(1)
            continue
        spans = re.findall(r"(`+)(.+?)\1", line)
        code.extend(span for _, span in spans)
        prose.append(re.sub(r"(`+)(.+?)\1", lambda m: " " * len(m.group(0)), line))
    return "\n".join(prose), "\n".join(code)


def slugs(markdown):
    prose, _ = split_markdown(markdown)
    seen, out = {}, set()
    for heading in re.findall(r"^#{1,6}\s+(.+?)\s*#*\s*$", prose, re.M):
        slug = re.sub(r"[^\w\- ]", "", heading.strip().lower()).replace(" ", "-")
        n = seen.get(slug, 0)
        seen[slug] = n + 1
        out.add(slug if n == 0 else f"{slug}-{n}")
    return out


class Docs:
    def __init__(self, root, files, skills):
        self.root, self.skills = root, set(skills)
        self.names = {}
        for rel in files:
            top = rel.split("/")[0] if "/" in rel else ""
            self.names.setdefault((top, rel.rsplit("/", 1)[-1]), []).append(rel)

    def scope(self, rel):
        top = rel.split("/")[0]
        return top if "/" in rel and top in self.skills else ""

    def base(self, rel):
        scope = self.scope(rel)
        return self.root / scope if scope else self.root

    def inside(self, path, rel):
        scope = self.root / self.scope(rel) if self.scope(rel) else self.root
        try:
            path.resolve().relative_to(scope.resolve())
            return True
        except ValueError:
            return False

    def link(self, rel, target):
        if SCHEME.match(target) or re.search(r"[<>{}$]", target) or any(
                target.startswith(u) for u in USER_FILES if u.endswith("/")):
            return None, None
        doc = self.root / rel
        address, _, fragment = target.partition("#")
        address = unquote(address.split("?")[0])
        path = doc if not address else (self.root / address.lstrip("/") if address.startswith("/") else doc.parent / address)
        if not path.exists():
            return None, f"broken link to {target}"
        if not self.inside(path, rel):
            return None, f"link to {target} leaves the skill folder: it breaks when the skill is installed alone"
        if address.endswith("/") and not path.is_dir():
            return None, f"link to {target} expects a folder, found a file"
        if re.search(r"\.\w{1,5}$", address) and not path.is_file():
            return None, f"link to {target} expects a file, found a folder"
        if fragment and path.suffix == ".md" and fragment.lower() not in slugs(path.read_text(encoding="utf-8")):
            return None, f"link to {target}: no heading with the anchor #{fragment}"
        return path, None

    def mention(self, rel, token):
        token = token.rstrip(".:,;!?")
        if token.startswith("./"):
            token = token[2:]
        base = self.base(rel)
        candidates = ((self.root / rel).parent, base)
        installed = INSTALLED.match(token)
        if token.startswith("<skill>/") and self.scope(rel):
            token, candidates = token[len("<skill>/"):], (base,)
        elif installed:
            if installed.group(1) not in self.skills:
                return [], None
            base, token = self.root / installed.group(1), installed.group(2)
            candidates = (base,)
        if not token or re.search(r"[<>{}$*?~@]|://|^[/-]|\.\.", token) or token in USER_FILES:
            return [], None
        leaf = token.rstrip("/").rsplit("/", 1)[-1]
        has_ext = bool(re.search(r"[^.]\.[A-Za-z0-9]{1,5}$", leaf)) and leaf.rsplit(".", 1)[-1].lower() in FILE_EXT
        if "/" in token:
            first = token.split("/")[0]
            for candidate in candidates:
                if (candidate / first).is_dir():
                    path = candidate / token
                    if not path.exists() or (has_ext and not path.is_file()):
                        return [], f"mentions {token}, which is not in the {'skill' if self.scope(rel) else 'repository'}"
                    return [path], None
            return [], None
        if not has_ext:
            return [], None
        scope = base.relative_to(self.root).as_posix() if base != self.root else ""
        if scope:
            hits = self.names.get((scope, token), [])
        else:
            hits = [p for (_, leaf_name), paths in self.names.items() if leaf_name == token for p in paths]
        if not hits:
            where = f"the {scope} skill" if scope else "the repository"
            return [], (f"mentions {token}, which is not in {where} "
                        f"(add it to USER_FILES in tests/check_skills.py if the user or the skill creates it)")
        return [self.root / h for h in hits], None

    def markdown(self, rel):
        try:
            text = (self.root / rel).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return [], []
        prose, code = split_markdown(text)
        targets, problems = [], []
        links = LINK.findall(prose) + REF_DEF.findall(prose) + HTML_REF.findall(prose)
        for target in links:
            path, problem = self.link(rel, target)
            if problem:
                problems.append(f"{rel}: {problem}")
            elif path:
                targets.append(path)
        for token in set(re.split(r"[\s\"'()\[\]{},;|&=`]+", code)):
            paths, problem = self.mention(rel, token)
            if problem:
                problems.append(f"{rel}: {problem}")
            targets.extend(paths)
        return targets, problems

    def html(self, rel):
        problems = []
        try:
            text = (self.root / rel).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return []
        for target in HTML_REF.findall(text):
            _, problem = self.link(rel, target)
            if problem:
                problems.append(f"{rel}: {problem}")
        return problems


def skill_problems(root, name, docs, files):
    skill_md = root / name / "SKILL.md"
    try:
        text = skill_md.read_text(encoding="utf-8")
        fields, body = frontmatter(text)
    except UnicodeDecodeError:
        return [f"{name}/SKILL.md: not valid UTF-8"]
    except ValueError as e:
        return [f"{name}/SKILL.md: {e}"]
    problems = [f"{name}/SKILL.md: {p}" for p in metadata_problems(name, fields)]
    if not body.strip():
        problems.append(f"{name}/SKILL.md: no instructions after the frontmatter")
    if len(text.splitlines()) > MAX_SKILL_LINES:
        problems.append(f"{name}/SKILL.md: exceeds {MAX_SKILL_LINES} lines")

    reached, queue = set(), [f"{name}/SKILL.md"]
    while queue:
        rel = queue.pop()
        if rel in reached:
            continue
        reached.add(rel)
        targets, _ = docs.markdown(rel)
        for path in targets:
            if path.is_file() and path.suffix == ".md":
                queue.append(path.resolve().relative_to(root.resolve()).as_posix())
    for rel in files:
        if rel.startswith(f"{name}/") and rel.endswith(".md") and rel not in reached:
            problems.append(f"{rel}: not referenced from SKILL.md, directly or through another document")
    return problems


def file_problems(root, rel, node):
    path = root / rel
    problems = []
    if JUNK.search(rel):
        problems.append(f"{rel}: stray file that must not be shipped")
    if path.is_symlink():
        target = path.resolve()
        if not target.exists() or root.resolve() not in (target, *target.parents):
            problems.append(f"{rel}: symlink to {os.readlink(path)} does not stay inside the repository")
        return problems
    if path.stat().st_size > MAX_FILE_BYTES:
        problems.append(f"{rel}: {path.stat().st_size / 1048576:.1f} MiB (> {MAX_FILE_BYTES // 1048576} MiB)")
    data = path.read_bytes()
    first = data.split(b"\n", 1)[0]
    shebang = first.startswith(b"#!")
    executable = bool(path.stat().st_mode & 0o111)
    if shebang and not executable:
        problems.append(f"{rel}: shebang without executable bit")
    if executable and not shebang:
        problems.append(f"{rel}: executable bit without a shebang line")
    text = None
    if path.suffix in TEXT or shebang:
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as e:
            return problems + [f"{rel}: not valid UTF-8 ({e.reason} at byte {e.start})"]
    if path.suffix == ".sh" or (shebang and re.search(rb"\b(ba)?sh\b", first)):
        if b"\r\n" in data:
            problems.append(f"{rel}: Windows line endings break the script under bash")
        r = subprocess.run(["bash", "-n", str(path)], capture_output=True, text=True)
        if r.returncode:
            problems.append(f"{rel}: bash -n: {one_line(r.stderr)}")
    elif path.suffix == ".py" or (shebang and b"python" in first):
        try:
            compile(text, str(path), "exec")
        except SyntaxError as e:
            problems.append(f"{rel}: line {e.lineno}: {e.msg} (Python {sys.version_info[0]}.{sys.version_info[1]})")
    elif path.suffix in {".js", ".mjs", ".cjs"}:
        if node:
            r = subprocess.run([node, "--check", str(path)], capture_output=True, text=True)
            if r.returncode:
                problems.append(f"{rel}: node --check: {one_line((r.stderr.strip().splitlines() or ['failed'])[-1])}")
        for target in JS_IMPORT.findall(text):
            base = path.parent / target
            candidates = [base, *(base.with_name(base.name + ext) for ext in (".js", ".mjs", ".cjs", ".json")), base / "index.js"]
            if not any(c.is_file() for c in candidates):
                problems.append(f"{rel}: imports {target}, which does not exist")
    elif path.suffix == ".json":
        try:
            json.loads(text)
        except json.JSONDecodeError as e:
            problems.append(f"{rel}: invalid JSON: {e.msg} at line {e.lineno}")
    elif path.suffix in {".yml", ".yaml"}:
        try:
            load_yaml(text)
        except yaml.YAMLError as e:
            problems.append(f"{rel}: invalid YAML: {one_line(e)}")
    return problems


def check(root=ROOT):
    files = shipped_files(root)
    problems = []
    manifest_path = root / MANIFEST
    expected = []
    if manifest_path.is_file():
        expected = [line.strip() for line in manifest_path.read_text(encoding="utf-8").splitlines()
                    if line.strip() and not line.startswith("#")]
    else:
        problems.append(f"{MANIFEST}: missing (one skill folder name per line)")
    found = sorted(rel.split("/")[0] for rel in files if rel.count("/") == 1 and rel.endswith("/SKILL.md"))
    if not found:
        problems.append("no skill found: no <folder>/SKILL.md in the repository")
    for name in expected:
        if name not in found:
            problems.append(f"{name}: listed in {MANIFEST} but {name}/SKILL.md is missing")
    for name in found:
        if name not in expected:
            problems.append(f"{name}: has a SKILL.md but is not listed in {MANIFEST}")
    for rel in files:
        if rel.endswith("/SKILL.md") and rel.count("/") > 1:
            problems.append(f"{rel}: nested SKILL.md, agents may load it as a separate skill")
    for top in sorted({rel.split("/")[0] for rel in files} - ROOT_ENTRIES - set(expected) - set(found)):
        problems.append(f"{top}: unexpected entry at the repository root")

    node = shutil.which("node")
    scripts = [rel for rel in files if rel.endswith((".js", ".mjs", ".cjs"))]
    if scripts and not node:
        problems.append(f"node not found: {len(scripts)} JavaScript files cannot be checked (install Node 20 or newer)")
    if not shutil.which("bash"):
        problems.append("bash not found: shell scripts cannot be checked")
    for rel in files:
        problems.extend(file_problems(root, rel, node))

    docs = Docs(root, files, sorted(set(found) | set(expected)))
    for name in found:
        problems.extend(skill_problems(root, name, docs, files))
    for rel in files:
        if rel.endswith(".md"):
            problems.extend(docs.markdown(rel)[1])
        elif rel.endswith(".html"):
            problems.extend(docs.html(rel))

    if "README.md" in files:
        targets, _ = docs.markdown("README.md")
        linked = {p.resolve() for p in targets}
        for name in expected:
            if (root / name).resolve() not in linked:
                problems.append(f"README.md: does not link to the {name} skill")
        for rel in files:
            if rel.startswith("docs/") and (root / rel).resolve() not in linked:
                problems.append(f"{rel}: not used by README.md")
    return found, sorted(set(problems))


def main():
    skills, problems = check(ROOT)
    for skill in skills:
        failed = any(p.startswith((f"{skill}/", f"{skill}:")) for p in problems)
        print(f"{'✗' if failed else '✓'} {skill}")
    if problems:
        print("\n" + "\n".join(problems))
        print(f"\n{len(problems)} problem(s).")
        sys.exit(1)
    print(f"\n{len(skills)} skills and {len(shipped_files(ROOT))} files checked (Python {sys.version_info[0]}.{sys.version_info[1]}).")


if __name__ == "__main__":
    main()
