from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any

from . import store
from .importers import strava_activity
from .util import CoachError, config_dir, parse_utc, read_json, write_json

API = "https://www.strava.com/api/v3"
TOKEN_URL = "https://www.strava.com/oauth/token"
AUTHORIZE_URL = "https://www.strava.com/oauth/authorize"
SCOPE = "read,activity:read_all"
STREAM_KEYS = "time,distance,heartrate,altitude"
PER_PAGE = 100
MAX_PAGES = 30


class SourceError(CoachError):
    pass


class RateLimited(SourceError):
    pass


def creds_path():
    return config_dir() / "strava.json"


def load_creds() -> dict[str, Any]:
    data = read_json(creds_path(), {}) or {}
    if os.environ.get("STRAVA_CLIENT_ID"):
        data["client_id"] = os.environ["STRAVA_CLIENT_ID"]
    if os.environ.get("STRAVA_CLIENT_SECRET"):
        data["client_secret"] = os.environ["STRAVA_CLIENT_SECRET"]
    return data


def save_creds(data: dict[str, Any]) -> None:
    write_json(creds_path(), data, private=True)


def is_configured() -> bool:
    c = load_creds()
    return bool(c.get("client_id") and c.get("client_secret") and c.get("refresh_token"))


def _request(url: str, data: dict[str, Any] | None = None, token: str | None = None) -> Any:
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    headers = {"Accept": "application/json", "User-Agent": "running-coach"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=body, headers=headers, method="POST" if body is not None else "GET")
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                raise RateLimited("limite de requêtes Strava atteinte (100 par 15 min) : relancer dans 15 minutes") from e
            if e.code in (401, 403):
                raise SourceError(f"Strava refuse l'accès ({e.code}) : relancer `coach auth strava`") from e
            if e.code >= 500 and attempt < 2:
                time.sleep(1 + attempt)
                continue
            raise SourceError(f"Strava a répondu {e.code} pour {url.split('?')[0]}") from e
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt < 2:
                time.sleep(1 + attempt)
                continue
            raise SourceError(f"Strava injoignable ({getattr(e, 'reason', e)})") from e
    raise SourceError("Strava injoignable")


def authorize_url(client_id: str) -> str:
    return AUTHORIZE_URL + "?" + urllib.parse.urlencode({
        "client_id": client_id, "response_type": "code", "redirect_uri": "http://localhost",
        "approval_prompt": "force", "scope": SCOPE,
    })


def extract_code(value: str) -> str:
    if "code=" in value:
        query = urllib.parse.urlparse(value).query or value.split("?", 1)[-1]
        code = urllib.parse.parse_qs(query).get("code", [""])[0]
        if code:
            return code
    return value.strip()


def _store_tokens(creds: dict[str, Any], resp: dict[str, Any]) -> dict[str, Any]:
    for key in ("access_token", "refresh_token", "expires_at"):
        if key not in resp:
            raise SourceError("réponse Strava inattendue lors de l'échange de jeton")
        creds[key] = resp[key]
    if resp.get("athlete", {}).get("id"):
        creds["athlete_id"] = resp["athlete"]["id"]
    if resp.get("scope"):
        creds["scope"] = resp["scope"]
    saved = read_json(creds_path(), {}) or {}
    saved.update({k: creds[k] for k in ("access_token", "refresh_token", "expires_at", "athlete_id", "scope") if k in creds})
    save_creds(saved)
    return creds


def exchange_code(code: str) -> dict[str, Any]:
    creds = load_creds()
    if not creds.get("client_id") or not creds.get("client_secret"):
        raise CoachError("identifiants d'application Strava absents : lancer dans un terminal `coach auth strava --client-id …`")
    try:
        resp = _request(TOKEN_URL, {"client_id": creds["client_id"], "client_secret": creds["client_secret"],
                                    "code": extract_code(code), "grant_type": "authorization_code"})
    except RateLimited:
        raise
    except SourceError as e:
        raise CoachError("Strava refuse le code : expiré (quelques minutes), déjà utilisé, ou Client ID/Secret d'une autre "
                         "application ; relancer `coach auth strava --reauthorize`") from e
    return _store_tokens(creds, resp)


def access_token() -> str:
    creds = load_creds()
    if not is_configured():
        raise SourceError("Strava n'est pas connecté : `coach auth strava`")
    if int(creds.get("expires_at", 0)) - 300 > time.time():
        return creds["access_token"]
    try:
        resp = _request(TOKEN_URL, {"client_id": creds["client_id"], "client_secret": creds["client_secret"],
                                    "grant_type": "refresh_token", "refresh_token": creds["refresh_token"]})
    except RateLimited:
        raise
    except SourceError as e:
        if "injoignable" in str(e):
            raise
        raise SourceError("autorisation Strava révoquée ou expirée : `coach auth strava --reauthorize`, puis `--code`") from e
    return _store_tokens(creds, resp)["access_token"]


def status() -> str:
    creds = load_creds()
    if not creds.get("client_id"):
        return "Strava : non configuré (`coach auth strava --client-id …`, dans un terminal)"
    if not creds.get("refresh_token"):
        return "Strava : application enregistrée, autorisation manquante (`coach auth strava --code <URL de redirection>`)"
    remaining = int(creds.get("expires_at", 0) - time.time()) // 60
    state = f"jeton valide encore {remaining} min" if remaining > 0 else "jeton expiré, rafraîchi automatiquement au prochain appel"
    return f"Strava : connecté (scope {creds.get('scope', '?')}), {state}"


def sync(days: int | None, details: int, index: dict[str, Any], log) -> dict[str, Any]:
    token = access_token()
    state = store.load_state().get("strava", {})
    known = [e for e in index.values() if e["source"] == "strava"]
    if days is not None:
        after = datetime.now(timezone.utc) - timedelta(days=days)
    elif known:
        after = max(parse_utc(e["start_utc"]) for e in known) - timedelta(days=2)
    else:
        after = datetime.now(timezone.utc) - timedelta(days=90)
    listed: list[dict[str, Any]] = []
    for page in range(1, MAX_PAGES + 1):
        batch = _request(f"{API}/athlete/activities?" + urllib.parse.urlencode(
            {"after": int(after.timestamp()), "per_page": PER_PAGE, "page": page}), token=token)
        if not isinstance(batch, list):
            raise SourceError("réponse Strava inattendue pour la liste des activités")
        listed += batch
        if len(batch) < PER_PAGE:
            break
    counts = {"new": 0, "updated": 0, "duplicate": 0, "replaced": 0, "unchanged": 0}
    changed: set[str] = set()
    for obj in listed:
        act = strava_activity(obj)
        existing = index.get(act["id"])
        if existing and existing.get("detail", 0) > 0:
            counts["unchanged"] += 1
            continue
        status_ = store.put(act, index)
        counts[status_] += 1
        if status_ in ("new", "updated", "replaced"):
            changed.add(act["id"])
    skip = set(state.get("no_details", []))
    pending = [i for i in store.sorted_ids(index, "run")
               if index[i]["source"] == "strava" and index[i]["detail"] == 0 and i not in skip]
    pending.reverse()
    fetched, limited = 0, None
    for activity_id in pending[:details]:
        sid = index[activity_id]["source_id"]
        try:
            streams = _request(f"{API}/activities/{sid}/streams?" + urllib.parse.urlencode(
                {"keys": STREAM_KEYS, "key_by_type": "true"}), token=token)
            laps = _request(f"{API}/activities/{sid}/laps", token=token)
        except RateLimited as e:
            limited = str(e)
            break
        except SourceError as e:
            log(f"  ! détails indisponibles pour {activity_id} : {e}")
            skip.add(activity_id)
            continue
        base = store.get(activity_id)
        summary = {"id": sid, "name": base["name"], "sport_type": base["sport_raw"], "start_date": base["start_utc"],
                   "start_date_local": base["start_local"], "distance": base["distance_m"], "moving_time": base["moving_s"],
                   "elapsed_time": base["elapsed_s"], "average_heartrate": base["avg_hr"], "max_heartrate": base["max_hr"],
                   "total_elevation_gain": base["elev_gain_m"]}
        store.put(strava_activity(summary, streams if isinstance(streams, dict) else None,
                                  laps if isinstance(laps, list) else None), index)
        changed.add(activity_id)
        fetched += 1
        if index[activity_id]["detail"] == 0:
            skip.add(activity_id)
    remaining = len([i for i in pending if index[i]["detail"] == 0 and i not in skip])
    full_state = store.load_state()
    full_state["strava"] = {**state, "last_sync": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                            "pending_details": remaining, "no_details": sorted(skip & set(index))}
    store.save_state(full_state)
    return {"listed": len(listed), "counts": counts, "details": fetched, "pending": remaining,
            "rate_limited": limited, "changed": changed}
