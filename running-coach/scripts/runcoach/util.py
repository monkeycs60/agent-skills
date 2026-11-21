from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

DAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
DAY_FR = ["lun", "mar", "mer", "jeu", "ven", "sam", "dim"]
DAY_ABBR = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_DAY_ALIASES = {
    **{k: i for i, k in enumerate(DAY_KEYS)},
    **{k: i for i, k in enumerate(DAY_FR)},
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6,
    "lundi": 0, "mardi": 1, "mercredi": 2, "jeudi": 3, "vendredi": 4, "samedi": 5, "dimanche": 6,
}


class CoachError(Exception):
    pass


_today: list[date] = []


def set_today(d: date) -> None:
    _today[:] = [d]


def today() -> date:
    return _today[0] if _today else date.today()


def _base(env: str, xdg: str, default: str) -> Path:
    if os.environ.get(env):
        return Path(os.environ[env]).expanduser()
    root = os.environ.get(xdg)
    return (Path(root).expanduser() if root else Path.home() / default) / "running-coach"


def config_dir() -> Path:
    return _base("RUNNING_COACH_CONFIG", "XDG_CONFIG_HOME", ".config")


def data_dir() -> Path:
    return _base("RUNNING_COACH_DATA", "XDG_DATA_HOME", ".local/share")


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default
    except json.JSONDecodeError as e:
        raise CoachError(f"{path} is not valid JSON ({e})") from e


def write_text(path: Path, text: str, private: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if private:
        os.chmod(path.parent, 0o700)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        if private:
            os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def write_json(path: Path, obj: Any, private: bool = False, compact: bool = False) -> None:
    text = json.dumps(obj, ensure_ascii=False, separators=(",", ":")) if compact else json.dumps(obj, ensure_ascii=False, indent=2)
    write_text(path, text + "\n", private=private)


def parse_pace(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    m = re.fullmatch(r"\s*(\d+):(\d{1,2})(?:\s*/\s*km)?\s*", str(value))
    if not m:
        raise CoachError(f"invalid pace: {value!r} (expected m:ss, e.g. 5:10)")
    return int(m.group(1)) * 60 + int(m.group(2))


def parse_duration(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    parts = str(value).strip().split(":")
    if not all(p.isdigit() for p in parts) or not 1 <= len(parts) <= 3:
        raise CoachError(f"invalid duration: {value!r} (expected h:mm:ss, mm:ss or seconds)")
    total = 0
    for p in parts:
        total = total * 60 + int(p)
    return float(total)


def fmt_pace(sec: float | None) -> str:
    if not sec or sec <= 0:
        return "—"
    sec = round(sec)
    return f"{sec // 60}:{sec % 60:02d}"


def fmt_hms(sec: float | None) -> str:
    if sec is None:
        return "—"
    sec = int(round(sec))
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def fmt_minutes(minutes: float | None) -> str:
    if minutes is None:
        return "—"
    total = int(round(minutes))
    h, m = divmod(total, 60)
    return f"{h}h{m:02d}" if h else f"{m} min"


def parse_utc(value: Any) -> datetime:
    if isinstance(value, datetime):
        dt = value
    else:
        s = str(value).strip().replace(" ", "T")
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def local_naive(dt_utc: datetime) -> str:
    return dt_utc.astimezone().replace(tzinfo=None).isoformat(timespec="seconds")


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as e:
        raise CoachError(f"invalid date: {value!r} (expected YYYY-MM-DD)") from e


def week_of(d: date) -> tuple[int, int]:
    iso = d.isocalendar()
    return iso[0], iso[1]


def week_label(year: int, week: int) -> str:
    return f"{year}-W{week:02d}"


def parse_week(label: str) -> tuple[int, int]:
    m = re.fullmatch(r"(\d{4})-?W(\d{1,2})", label.strip(), re.IGNORECASE)
    if not m:
        raise CoachError(f"invalid week: {label!r} (expected YYYY-Wnn)")
    year, week = int(m.group(1)), int(m.group(2))
    monday_of(year, week)
    return year, week


def monday_of(year: int, week: int) -> date:
    try:
        return date.fromisocalendar(year, week, 1)
    except ValueError as e:
        raise CoachError(f"no such week: {year}-W{week}") from e


def parse_day(value: str) -> int:
    key = str(value).strip().lower()
    if key not in _DAY_ALIASES:
        raise CoachError(f"invalid day: {value!r} (expected mon…sun)")
    return _DAY_ALIASES[key]


def day_abbr(d: date) -> str:
    return DAY_ABBR[d.weekday()]


def daterange(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def num(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
