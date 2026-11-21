#!/usr/bin/env python3
"""Behaviour tests, offline: the repository's tests/test_*.py, then each listed skill's own tests/test_*.py and tests/*.sh."""
import argparse
import importlib.metadata
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQUIREMENTS = ROOT / "tests" / "requirements.txt"
INTERPRETERS = ["python", "python3"] + [f"python3.{minor}" for minor in range(10, 16)]


def requirements(path):
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line.startswith("-r "):
            yield from requirements(path.parent / line[3:].strip())
        elif line:
            yield re.split(r"[\s<>=!~;\[]", line, maxsplit=1)[0]


def missing_requirements():
    missing = []
    for name in requirements(REQUIREMENTS):
        try:
            importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            missing.append(name)
    return missing


def suites():
    yield "repository tests", [sys.executable, "-m", "unittest", "discover", "-s", str(ROOT / "tests"), "-p", "test_*.py"]
    for name in (ROOT / "tests" / "skills.txt").read_text(encoding="utf-8").split():
        tests = ROOT / name / "tests"
        if any(tests.glob("test_*.py")):
            yield f"{name} unit tests", [sys.executable, "-m", "unittest", "discover", "-s", str(tests), "-p", "test_*.py"]
        for script in sorted(tests.glob("*.sh")):
            yield f"{name} {script.name}", ["bash", str(script)]


def environment(tmp):
    home = tmp / "home"
    shim = tmp / "bin"
    for path in (home, shim):
        path.mkdir()
    # Skill launchers run the first python3.x they find on PATH: without these wrappers they can pick a system
    # Python that lacks the test dependencies. -B because launchers pass -I, which ignores PYTHONDONTWRITEBYTECODE.
    for name in INTERPRETERS:
        wrapper = shim / name
        wrapper.write_text(f'#!/bin/sh\nexec "{sys.executable}" -B "$@"\n', encoding="utf-8")
        wrapper.chmod(0o755)
    env = {k: v for k, v in os.environ.items() if not k.startswith(("XDG_", "RUNNING_COACH_", "YOUTUBE_SKILL_"))}
    env.update({
        "HOME": str(home), "PATH": f"{shim}{os.pathsep}{env.get('PATH', '')}", "PYTHONDONTWRITEBYTECODE": "1",
        "npm_config_cache": os.environ.get("npm_config_cache") or str(Path.home() / ".npm"),
        "DISABLE_TELEMETRY": "1", "DO_NOT_TRACK": "1",
    })
    return env


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-v", "--verbose", action="store_true", help="print the output of passing suites too")
    a = ap.parse_args()
    if sys.version_info < (3, 10):
        sys.exit("run_tests.py needs Python 3.10 or newer")
    missing = missing_requirements()
    if missing:
        sys.exit(f"missing test dependencies: {', '.join(missing)}\n"
                 f"install them: python3 -m pip install -r tests/requirements.txt\n"
                 f"or, without touching your Python: uv run --no-project --with-requirements tests/requirements.txt "
                 f"python3 tests/run_tests.py")
    failed, started = [], time.time()
    for name, command in suites():
        with tempfile.TemporaryDirectory(prefix="skill-tests-") as tmp:
            t0 = time.time()
            r = subprocess.run(command, cwd=tmp, env=environment(Path(tmp)), capture_output=True, text=True, timeout=600)
        output = (r.stdout + r.stderr).strip()
        print(f"{'✓' if r.returncode == 0 else '✗'} {name} ({time.time() - t0:.1f} s)")
        if r.returncode or a.verbose:
            print("\n".join("    " + line for line in output.splitlines()[-60:]))
        if r.returncode:
            failed.append(name)
    print(f"\n{'✗ ' + ', '.join(failed) + ' failed' if failed else '✓ all suites passed'} "
          f"in {time.time() - started:.1f} s (Python {sys.version_info[0]}.{sys.version_info[1]}).")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
