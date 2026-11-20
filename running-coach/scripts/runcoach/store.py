from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .util import CoachError, data_dir, iso_utc, local_naive, parse_utc, read_json, write_json

SPORTS = ("run", "ride", "swim", "walk", "hike", "strength", "other")
DUP_WINDOW_S = 180


def activities_dir() -> Path:
    return data_dir() / "activities"


def index_path() -> Path:
    return data_dir() / "index.json"


def state_path() -> Path:
    return data_dir() / "state.json"


def safe_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", value)


def normalize_sport(raw: Any) -> str:
    s = str(raw or "").strip().lower()
    if s in ("9", "run", "running") or "run" in s or "jog" in s:
        return "run"
    if s == "1" or any(k in s for k in ("ride", "cycl", "bik", "velo", "vélo")):
        return "ride"
    if "swim" in s or "natation" in s:
        return "swim"
    if s == "10" or "walk" in s or "marche" in s:
        return "walk"
    if "hik" in s or "randonn" in s:
        return "hike"
    if any(k in s for k in ("strength", "weight", "muscu", "training")):
        return "strength"
    return "other"


def detail_level(act: dict[str, Any]) -> int:
    samples = act.get("samples") or {}
    if len(samples.get("t") or []) >= 10 and samples.get("d"):
        return 2
    if act.get("laps"):
        return 1
    return 0


def make_activity(source: str, source_id: str, sport_raw: Any, start_utc: datetime, **fields: Any) -> dict[str, Any]:
    act: dict[str, Any] = {
        "schema": 1,
        "id": safe_id(f"{source}-{source_id}"),
        "source": source,
        "source_id": str(source_id),
        "sport": normalize_sport(sport_raw),
        "sport_raw": str(sport_raw or ""),
        "name": "",
        "start_utc": iso_utc(start_utc),
        "start_local": local_naive(start_utc),
        "distance_m": 0.0,
        "moving_s": None,
        "elapsed_s": None,
        "avg_hr": None,
        "max_hr": None,
        "elev_gain_m": None,
        "laps": [],
        "samples": None,
    }
    act.update({k: v for k, v in fields.items() if v is not None})
    return act


def finalize(act: dict[str, Any]) -> dict[str, Any]:
    if act["sport"] not in SPORTS:
        act["sport"] = normalize_sport(act["sport"])
    act["detail"] = detail_level(act)
    act["imported_at"] = iso_utc(datetime.now(timezone.utc))
    for key in ("distance_m", "moving_s", "elapsed_s", "avg_hr", "max_hr", "elev_gain_m"):
        if act.get(key) is not None:
            act[key] = round(float(act[key]), 1)
    if not act.get("moving_s") and act.get("elapsed_s"):
        act["moving_s"] = act["elapsed_s"]
    return act


def load_index() -> dict[str, dict[str, Any]]:
    return read_json(index_path(), {}) or {}


def save_index(index: dict[str, dict[str, Any]]) -> None:
    write_json(index_path(), index)


def index_entry(act: dict[str, Any]) -> dict[str, Any]:
    return {
        "start_utc": act["start_utc"],
        "start_local": act["start_local"],
        "sport": act["sport"],
        "distance_m": act.get("distance_m") or 0,
        "max_hr": act.get("max_hr"),
        "detail": act.get("detail", 0),
        "source": act["source"],
        "source_id": act["source_id"],
        "name": act.get("name", ""),
    }


def _same_activity(a: dict[str, Any], b: dict[str, Any]) -> bool:
    if abs((parse_utc(a["start_utc"]) - parse_utc(b["start_utc"])).total_seconds()) > DUP_WINDOW_S:
        return False
    da, db = a.get("distance_m") or 0, b.get("distance_m") or 0
    if da < 100 and db < 100:
        return a["sport"] == b["sport"]
    return abs(da - db) <= max(300.0, 0.05 * max(da, db))


def get(activity_id: str) -> dict[str, Any]:
    act = read_json(activities_dir() / f"{activity_id}.json")
    if act is None:
        raise CoachError(f"activité introuvable : {activity_id}")
    return act


def remove(activity_id: str, index: dict[str, dict[str, Any]]) -> None:
    (activities_dir() / f"{activity_id}.json").unlink(missing_ok=True)
    index.pop(activity_id, None)


def put(act: dict[str, Any], index: dict[str, dict[str, Any]]) -> str:
    act = finalize(act)
    existing = index.get(act["id"])
    if existing is not None:
        if act["detail"] < existing.get("detail", 0):
            return "unchanged"
        status = "updated"
    else:
        dup = next((oid for oid, e in index.items() if _same_activity(e, act)), None)
        if dup is not None:
            if act["detail"] <= index[dup].get("detail", 0):
                return "duplicate"
            remove(dup, index)
            status = "replaced"
        else:
            status = "new"
    write_json(activities_dir() / f"{act['id']}.json", act, compact=True)
    index[act["id"]] = index_entry(act)
    return status


def sorted_ids(index: dict[str, dict[str, Any]], sport: str | None = None) -> list[str]:
    ids = [i for i, e in index.items() if sport is None or e["sport"] == sport]
    return sorted(ids, key=lambda i: index[i]["start_utc"])


def find(identifier: str, index: dict[str, dict[str, Any]], sport: str | None = "run") -> str:
    ids = sorted_ids(index, sport)
    if not ids:
        raise CoachError("aucune activité enregistrée : lancer `coach sync` ou `coach import <fichiers>`")
    ident = identifier.strip()
    m = re.fullmatch(r"last(?:-(\d+))?", ident)
    if m:
        back = int(m.group(1) or 0)
        if back >= len(ids):
            raise CoachError(f"seulement {len(ids)} activité(s) enregistrée(s)")
        return ids[-1 - back]
    if ident in index:
        return ident
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", ident):
        same_day = [i for i in ids if index[i]["start_local"].startswith(ident)]
        if not same_day:
            raise CoachError(f"aucune activité le {ident}")
        return max(same_day, key=lambda i: index[i]["distance_m"])
    matches = [i for i in ids if index[i]["source_id"] == ident or i.endswith(ident)]
    if not matches:
        raise CoachError(f"aucune activité ne correspond à {ident!r} (id, AAAA-MM-JJ, last ou last-N)")
    return matches[-1]


def reindex() -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    folder = activities_dir()
    if folder.exists():
        for path in folder.glob("*.json"):
            act = read_json(path)
            if act and act.get("id"):
                act["detail"] = detail_level(act)
                index[act["id"]] = index_entry(act)
    save_index(index)
    return index


def observed_hr_max(index: dict[str, dict[str, Any]]) -> float | None:
    values = [e["max_hr"] for e in index.values() if e.get("max_hr") and 120 <= e["max_hr"] <= 230]
    return max(values) if values else None


def load_state() -> dict[str, Any]:
    return read_json(state_path(), {}) or {}


def save_state(state: dict[str, Any]) -> None:
    write_json(state_path(), state)
