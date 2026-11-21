from __future__ import annotations

import getpass
import io
import logging
import os
import shutil
import warnings
import zipfile
from datetime import datetime, timedelta, timezone
from typing import Any

from . import store
from .importers import Skip, garmin_api_activity, parse_fit
from .strava import RateLimited, SourceError
from .util import CoachError, config_dir, parse_utc, today

warnings.filterwarnings("ignore", message=".*[Gg]arth.*deprecated.*")
logging.getLogger("garminconnect").setLevel(logging.CRITICAL)


def token_dir():
    return config_dir() / "garmin"


def is_configured() -> bool:
    d = token_dir()
    return d.is_dir() and any(d.iterdir())


def _lib():
    try:
        import garminconnect
    except ImportError as e:
        raise SourceError("garminconnect library missing: run the skill's install.sh") from e
    return garminconnect


def _wrap(exc: Exception) -> SourceError:
    gc = _lib()
    if isinstance(exc, gc.GarminConnectTooManyRequestsError):
        return RateLimited("Garmin is rate limiting requests: retry in a few minutes")
    if isinstance(exc, gc.GarminConnectAuthenticationError):
        return SourceError("Garmin tokens expired or rejected: run `coach auth garmin login` in a terminal")
    return SourceError(f"Garmin Connect unreachable ({exc})")


def client(interactive: bool = False):
    gc = _lib()
    if not is_configured() and not interactive:
        raise SourceError("Garmin is not connected: run `coach auth garmin login` in a terminal (credentials + MFA code)")
    try:
        if is_configured():
            g = gc.Garmin()
        else:
            email = os.environ.get("GARMIN_EMAIL") or input("Garmin Connect email: ").strip()
            password = os.environ.get("GARMIN_PASSWORD") or getpass.getpass("Garmin Connect password: ")
            g = gc.Garmin(email, password, prompt_mfa=lambda: input("MFA code (if asked): ").strip())
            token_dir().mkdir(parents=True, exist_ok=True)
            os.chmod(token_dir(), 0o700)
        g.login(str(token_dir()))
        return g
    except SourceError:
        raise
    except EOFError as e:
        raise SourceError("cannot prompt here: run `coach auth garmin login` in a terminal") from e
    except Exception as e:
        raise _wrap(e) from e


def login() -> str:
    if is_configured():
        return status()
    g = client(interactive=True)
    return f"Garmin: connected ({g.get_full_name() or 'account'}), tokens saved in {token_dir()}"


def status(check: bool = False) -> str:
    if not is_configured():
        return "Garmin: not connected (`coach auth garmin login`, to run in a terminal)"
    if not check:
        return f"Garmin: tokens present in {token_dir()}"
    g = client()
    try:
        name = g.get_full_name()
    except Exception as e:
        raise _wrap(e) from e
    return f"Garmin: connected ({name or 'account'})"


def logout() -> str:
    shutil.rmtree(token_dir(), ignore_errors=True)
    return "Garmin: tokens deleted"


def _fit_from_download(data: bytes) -> bytes:
    if data[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            name = next((n for n in zf.namelist() if n.lower().endswith(".fit")), None)
            if name is None:
                raise Skip("Garmin archive without a FIT file")
            return zf.read(name)
    return data


def sync(days: int | None, details: int, index: dict[str, Any], log) -> dict[str, Any]:
    g = client()
    state = store.load_state().get("garmin", {})
    known = [e for e in index.values() if e["source"] == "garmin"]
    end = today()
    if days is not None:
        start = end - timedelta(days=days)
    elif known:
        start = max(parse_utc(e["start_utc"]) for e in known).date() - timedelta(days=2)
    else:
        start = end - timedelta(days=90)
    try:
        listed = g.get_activities_by_date(start.isoformat(), end.isoformat())
    except Exception as e:
        raise _wrap(e) from e
    counts = {"new": 0, "updated": 0, "duplicate": 0, "replaced": 0, "unchanged": 0}
    changed: set[str] = set()
    for obj in listed or []:
        act = garmin_api_activity(obj)
        existing = index.get(act["id"])
        if existing and existing.get("detail", 0) > 0:
            counts["unchanged"] += 1
            continue
        result = store.put(act, index)
        counts[result] += 1
        if result in ("new", "updated", "replaced"):
            changed.add(act["id"])
    skip = set(state.get("no_details", []))
    pending = [i for i in store.sorted_ids(index, "run")
               if index[i]["source"] == "garmin" and index[i]["detail"] == 0 and i not in skip]
    pending.reverse()
    fetched, limited = 0, None
    fmt = g.ActivityDownloadFormat.ORIGINAL
    for activity_id in pending[:details]:
        sid = index[activity_id]["source_id"]
        try:
            raw = g.download_activity(sid, dl_fmt=fmt)
            parsed = parse_fit(_fit_from_download(raw), f"garmin-{sid}.fit", sid)[0]
        except Skip as e:
            log(f"  ! {activity_id}: {e}")
            skip.add(activity_id)
            continue
        except CoachError:
            raise
        except Exception as e:
            err = _wrap(e)
            if isinstance(err, RateLimited):
                limited = str(err)
                break
            log(f"  ! details unavailable for {activity_id}: {err}")
            skip.add(activity_id)
            continue
        base = store.get(activity_id)
        base["samples"], base["laps"] = parsed["samples"], parsed["laps"]
        for key in ("avg_hr", "max_hr", "elev_gain_m", "moving_s"):
            if not base.get(key) and parsed.get(key):
                base[key] = parsed[key]
        store.put(base, index)
        changed.add(activity_id)
        fetched += 1
    remaining = len([i for i in pending if index[i]["detail"] == 0 and i not in skip])
    full_state = store.load_state()
    full_state["garmin"] = {**state, "last_sync": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                            "pending_details": remaining, "no_details": sorted(skip & set(index))}
    store.save_state(full_state)
    return {"listed": len(listed or []), "counts": counts, "details": fetched, "pending": remaining,
            "rate_limited": limited, "changed": changed}


def push_workout(payload: dict[str, Any], when: str | None) -> str:
    g = client()
    try:
        result = g.upload_workout(payload)
        workout_id = result.get("workoutId")
        lines = [f"✓ workout created in Garmin Connect: {payload['workoutName']} (id {workout_id})"]
        if when:
            g.schedule_workout(workout_id, when)
            lines.append(f"✓ scheduled on {when}: it reaches the watch at the next sync")
        else:
            lines.append("  not scheduled: add --date YYYY-MM-DD to put it on the calendar")
        return "\n".join(lines)
    except Exception as e:
        raise _wrap(e) from e


def list_workouts(limit: int = 30) -> list[dict[str, Any]]:
    g = client()
    try:
        return g.get_workouts(0, limit) or []
    except Exception as e:
        raise _wrap(e) from e


def delete_workout(workout_id: str) -> str:
    g = client()
    try:
        g.delete_workout(workout_id)
    except Exception as e:
        raise _wrap(e) from e
    return f"✓ workout {workout_id} deleted from Garmin Connect"
