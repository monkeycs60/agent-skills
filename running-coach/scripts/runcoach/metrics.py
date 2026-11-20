from __future__ import annotations

import csv
import io
import math
from collections import defaultdict
from datetime import date, timedelta
from statistics import median
from typing import Any

from . import VERSION, store
from .importers import MAX_GAP_S, MOVING_SPEED
from .profile import Profile, load_profile
from .util import daterange, data_dir, num, read_json, today, week_label, week_of, write_json, write_text

DEFAULT_HR_REST = 55
SEED_DAYS = 28
NO_HR_TRIMP_PER_MIN = {"run": 1.2, "ride": 0.9, "strength": 0.8}
EASY = ("Récupération", "Footing", "Court", "Accélérations", "Sortie longue")
ACTIVITY_COLUMNS = ["id", "source", "sport", "date", "start_local", "name", "distance_km", "moving_min", "pace_s",
                    "avg_hr", "max_hr", "elev_gain_m", "trimp", "trimp_estimated", "structure", "kind", "quality_km",
                    "ef", "decoupling", "z1", "z2", "z3", "z4", "z5", "detail"]
DAILY_COLUMNS = ["date", "trimp", "run_km", "ctl", "atl", "tsb"]
WEEKLY_COLUMNS = ["week", "runs", "run_km", "run_min", "long_km", "quality", "trimp", "other_min", "easy_pct"]
NUMERIC = {"distance_km", "moving_min", "pace_s", "avg_hr", "max_hr", "elev_gain_m", "trimp", "quality_km", "ef",
           "decoupling", "z1", "z2", "z3", "z4", "z5", "detail", "runs", "run_km", "run_min", "long_km", "quality",
           "other_min", "easy_pct", "ctl", "atl", "tsb", "trimp_estimated"}


def metrics_dir():
    return data_dir() / "metrics"


def _hr_rest(profile: Profile) -> float:
    return profile.hr_rest or DEFAULT_HR_REST


def trimp_rate(hr: float, profile: Profile) -> float:
    k, b = profile.trimp_coeffs
    rest = _hr_rest(profile)
    hrr = max(0.0, min(1.0, (hr - rest) / (profile.hr_max - rest)))
    return hrr * k * math.exp(b * hrr)


def _intervals(samples: dict[str, list]):
    t, d = samples["t"], samples["d"]
    hr = samples.get("hr") or [None] * len(t)
    for i in range(1, len(t)):
        dt = t[i] - t[i - 1]
        if dt <= 0 or dt > MAX_GAP_S:
            continue
        dd = d[i] - d[i - 1]
        yield i, dt, dd, dd / dt >= MOVING_SPEED, hr[i]


def splits_from_samples(samples: dict[str, list]) -> list[dict[str, Any]]:
    t, d = samples["t"], samples["d"]
    hr = samples.get("hr") or [None] * len(t)
    splits: list[dict[str, Any]] = []
    cur = {"moving": 0.0, "hr_sum": 0.0, "hr_t": 0.0}
    km = 1

    def add(x: float, moving: bool, h: float | None) -> None:
        if moving:
            cur["moving"] += x
            if h:
                cur["hr_sum"] += h * x
                cur["hr_t"] += x

    def close(distance: float) -> None:
        moving = cur["moving"]
        splits.append({
            "km": len(splits) + 1,
            "distance_m": round(distance, 1),
            "moving_s": round(moving, 1),
            "pace_s": round(moving / (distance / 1000), 1) if moving > 0 and distance > 0 else None,
            "hr": round(cur["hr_sum"] / cur["hr_t"], 1) if cur["hr_t"] else None,
        })
        cur.update(moving=0.0, hr_sum=0.0, hr_t=0.0)

    for i in range(1, len(t)):
        dt = t[i] - t[i - 1]
        dd = d[i] - d[i - 1]
        if dt <= 0:
            continue
        moving = dt <= MAX_GAP_S and dd / dt >= MOVING_SPEED
        h = hr[i]
        done = 0.0
        while dd > 0 and d[i] >= km * 1000:
            frac = (km * 1000 - d[i - 1]) / dd
            add((frac - done) * dt, moving, h)
            close(1000.0)
            km += 1
            done = frac
        add((1 - done) * dt, moving, h)
    rest = (d[-1] if d else 0) - (km - 1) * 1000
    if rest >= 200:
        close(rest)
    return splits


def _is_auto_km(laps: list[dict[str, Any]]) -> bool:
    body = [lp for lp in laps[:-1] if lp.get("distance_m")]
    return len(body) >= 2 and sum(1 for lp in body if 950 <= lp["distance_m"] <= 1050) >= 0.7 * len(body)


def splits_from_laps(laps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for lp in laps:
        dist, mov = lp.get("distance_m") or 0, lp.get("moving_s") or 0
        if dist < 200 or mov <= 0:
            continue
        out.append({"km": len(out) + 1, "distance_m": dist, "moving_s": mov, "pace_s": round(mov / (dist / 1000), 1), "hr": lp.get("avg_hr")})
    return out


def km_splits(act: dict[str, Any]) -> list[dict[str, Any]]:
    if act.get("detail") == 2 or store.detail_level(act) == 2:
        return splits_from_samples(act["samples"])
    laps = act.get("laps") or []
    if laps and _is_auto_km(laps):
        return splits_from_laps(laps)
    return []


def _fmt_rep(values: list[float], unit: str) -> str:
    v = median(values)
    if unit == "m":
        return f"{v / 1000:g} km" if v >= 2000 else f"{int(round(v / 100.0) * 100)} m"
    minutes = v / 60
    return f"{round(minutes)}'" if minutes >= 1.5 else f"{int(round(v / 15.0) * 15)}\""


def lap_structure(laps: list[dict[str, Any]]) -> dict[str, Any] | None:
    usable = [lp for lp in laps if (lp.get("distance_m") or 0) > 50 and (lp.get("moving_s") or 0) > 20]
    if len(usable) < 5 or _is_auto_km(laps):
        return None
    speeds = [lp["distance_m"] / lp["moving_s"] for lp in usable]
    med = median(speeds)
    work = [i for i, s in enumerate(speeds) if s > med * 1.08]
    if len(work) < 3:
        return None
    switches = sum(1 for a, b in zip(work, work[1:]) if b - a >= 2)
    if switches < 2:
        return None
    reps = [usable[i] for i in work]
    dists = [lp["distance_m"] for lp in reps]
    times = [lp["moving_s"] for lp in reps]

    def cv(xs: list[float]) -> float:
        m = sum(xs) / len(xs)
        return (sum((x - m) ** 2 for x in xs) / len(xs)) ** 0.5 / m if m else 1.0

    size = _fmt_rep(dists, "m") if cv(dists) <= cv(times) else _fmt_rep(times, "s")
    pace = sum(times) / (sum(dists) / 1000)
    hrs = [lp["avg_hr"] for lp in reps if lp.get("avg_hr")]
    return {"label": f"Fractionné {len(reps)}×{size}", "reps": len(reps), "work_km": sum(dists) / 1000,
            "pace_s": pace, "hr": sum(hrs) / len(hrs) if hrs else None}


def _percentile(values: list[float], q: float) -> float:
    s = sorted(values)
    pos = (len(s) - 1) * q
    lo, hi = int(math.floor(pos)), int(math.ceil(pos))
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def classify(act: dict[str, Any], splits: list[dict[str, Any]], profile: Profile, moving_min: float) -> tuple[str, str, list[int]]:
    is_long = moving_min >= profile.long_run_min
    laps_info = lap_structure(act.get("laps") or [])
    if laps_info:
        return laps_info["label"], "quality", []
    full = [s for s in splits if s["distance_m"] >= 900 and s["pace_s"]]
    if len(full) < 3:
        zone = profile.zone_of(act.get("avg_hr"))
        if is_long:
            return ("Sortie longue soutenue" if zone and zone >= 3 else "Sortie longue"), "long", []
        if zone and zone >= 3:
            return "Séance soutenue", "quality", []
        if zone == 1:
            return "Récupération", "easy", []
        return ("Court" if (act.get("distance_m") or 0) < 3000 else "Footing"), "easy", []
    t = profile.threshold_s
    paces = [s["pace_s"] for s in full]
    med = median(paces)
    limit = _percentile(paces, 0.75) * 0.92
    if t:
        limit = min(limit, t * 1.12)
    fast = [s["km"] for s in full if s["pace_s"] <= limit and (not s.get("hr") or (profile.zone_of(s["hr"]) or 0) >= 3)]
    hard_hr = [s["km"] for s in full if s.get("hr") and (profile.zone_of(s["hr"]) or 0) >= 4]
    n = full[-1]["km"]
    if not fast:
        hrs = [s["hr"] for s in full if s.get("hr")]
        zmed = profile.zone_of(median(hrs)) if hrs else None
        if (t and med <= t * 1.04) or len(hard_hr) >= max(3, len(full) / 2):
            return "Tempo/seuil", "quality", [s["km"] for s in full]
        if t and med <= t * 1.10 and len(full) >= 6:
            return "Allure spécifique continue", "quality", [s["km"] for s in full]
        if is_long:
            return "Sortie longue", "long", []
        if len(hard_hr) >= 3:
            return "Tempo/seuil", "quality", hard_hr
        return ("Récupération" if zmed == 1 else "Footing"), "easy", []
    fast.sort()
    contiguous = fast[-1] - fast[0] + 1 == len(fast)
    if len(fast) >= 2 and fast[-1] >= n - 1 and fast[0] >= n - max(2, n // 4) and contiguous:
        return ("Sortie longue progressive" if is_long else "Progressif"), ("long" if is_long else "quality"), fast
    if contiguous and len(fast) >= 3:
        return ("Sortie longue avec bloc" if is_long else "Tempo/seuil"), ("long" if is_long else "quality"), fast
    if len(fast) >= 3:
        return "Fractionné", "quality", fast
    if is_long:
        return "Sortie longue", "long", fast
    return "Accélérations", "easy", fast


def _steady(splits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [s for s in splits[1:] if s["distance_m"] >= 900 and s.get("hr") and s.get("moving_s")]


def _ef(body: list[dict[str, Any]]) -> float | None:
    if len(body) < 3:
        return None
    dist = sum(s["distance_m"] for s in body)
    mov = sum(s["moving_s"] for s in body)
    hr = sum(s["hr"] * s["moving_s"] for s in body) / mov
    return round(dist / mov * 60 / hr, 3)


def efficiency(splits: list[dict[str, Any]]) -> float | None:
    return _ef(_steady(splits))


def decoupling(splits: list[dict[str, Any]]) -> float | None:
    body = _steady(splits)
    if len(body) < 6 or sum(s["moving_s"] for s in body) < 40 * 60:
        return None
    mid = len(body) // 2
    first, second = _ef(body[:mid]), _ef(body[mid:])
    if not first or not second:
        return None
    return round((first - second) / first * 100, 1)


def zone_minutes(act: dict[str, Any], splits: list[dict[str, Any]], profile: Profile) -> list[float]:
    zones = [0.0] * 5
    if store.detail_level(act) == 2 and any(act["samples"].get("hr") or []):
        for _, dt, _, _, h in _intervals(act["samples"]):
            z = profile.zone_of(h)
            if z:
                zones[z - 1] += dt / 60
    elif splits and any(s.get("hr") for s in splits):
        for s in splits:
            z = profile.zone_of(s.get("hr"))
            if z:
                zones[z - 1] += s["moving_s"] / 60
    elif act.get("avg_hr"):
        z = profile.zone_of(act["avg_hr"])
        if z:
            zones[z - 1] += (act.get("moving_s") or 0) / 60
    return [round(z, 1) for z in zones]


def trimp(act: dict[str, Any], profile: Profile) -> tuple[float, bool]:
    samples = act.get("samples")
    if samples and store.detail_level(act) == 2 and sum(1 for h in samples.get("hr") or [] if h) >= 10:
        total = sum(dt / 60 * trimp_rate(h, profile) for _, dt, _, _, h in _intervals(samples) if h)
        return round(total, 1), False
    minutes = (act.get("moving_s") or act.get("elapsed_s") or 0) / 60
    if act.get("avg_hr"):
        return round(minutes * trimp_rate(act["avg_hr"], profile), 1), False
    return round(minutes * NO_HR_TRIMP_PER_MIN.get(act["sport"], 1.0), 1), True


def analyze(act: dict[str, Any], profile: Profile) -> dict[str, Any]:
    dist = act.get("distance_m") or 0
    moving_s = act.get("moving_s") or act.get("elapsed_s") or 0
    moving_min = moving_s / 60
    row: dict[str, Any] = {
        "id": act["id"], "source": act["source"], "sport": act["sport"],
        "date": act["start_local"][:10], "start_local": act["start_local"], "name": act.get("name", ""),
        "distance_km": round(dist / 1000, 2), "moving_min": round(moving_min, 1),
        "pace_s": round(moving_s / (dist / 1000), 1) if dist > 0 and moving_s else None,
        "avg_hr": round(act["avg_hr"]) if act.get("avg_hr") else None,
        "max_hr": round(act["max_hr"]) if act.get("max_hr") else None,
        "elev_gain_m": round(act["elev_gain_m"]) if act.get("elev_gain_m") is not None else None,
        "detail": store.detail_level(act),
    }
    row["trimp"], estimated = trimp(act, profile)
    row["trimp_estimated"] = 1 if estimated else 0
    splits: list[dict[str, Any]] = []
    if act["sport"] == "run":
        splits = km_splits(act)
        structure, kind, quality = classify(act, splits, profile, moving_min)
        row.update(structure=structure, kind=kind, quality_km=len(quality))
        if kind in ("easy", "long"):
            row["ef"] = efficiency(splits)
            row["decoupling"] = decoupling(splits)
    else:
        row.update(structure="", kind="other", quality_km=None)
    for i, minutes in enumerate(zone_minutes(act, splits, profile)):
        row[f"z{i + 1}"] = minutes
    return row


def _csv_text(columns: list[str], rows: list[dict[str, Any]]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for r in rows:
        writer.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in columns})
    return buf.getvalue()


def read_csv(name: str) -> list[dict[str, Any]]:
    path = metrics_dir() / name
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        for k in list(r):
            if k in NUMERIC:
                r[k] = num(r[k])
    return rows


def activity_rows() -> list[dict[str, Any]]:
    cut = today().isoformat()
    return [r for r in read_csv("activities.csv") if r["date"] <= cut]


def current_profile(index: dict[str, Any] | None = None) -> Profile:
    index = store.load_index() if index is None else index
    return load_profile(store.observed_hr_max(index))


def refresh(changed: set[str] | None = None, full: bool = False) -> dict[str, Any]:
    index = store.load_index()
    profile = current_profile(index)
    meta_path = metrics_dir() / "meta.json"
    meta = read_json(meta_path, {}) or {}
    rebuild_all = full or changed is None or meta.get("profile") != profile.metrics_hash() or meta.get("version") != VERSION
    rows = {} if rebuild_all else {r["id"]: r for r in read_csv("activities.csv")}
    todo = [i for i in index if rebuild_all or i not in rows or i in (changed or set())]
    for activity_id in todo:
        rows[activity_id] = analyze(store.get(activity_id), profile)
    rows = {i: r for i, r in rows.items() if i in index}
    ordered = sorted(rows.values(), key=lambda r: r["start_local"])
    write_text(metrics_dir() / "activities.csv", _csv_text(ACTIVITY_COLUMNS, ordered))
    daily = daily_series(ordered)
    write_text(metrics_dir() / "daily.csv", _csv_text(DAILY_COLUMNS, daily))
    write_text(metrics_dir() / "weekly.csv", _csv_text(WEEKLY_COLUMNS, weekly_series(ordered, daily)))
    write_json(meta_path, {"profile": profile.metrics_hash(), "version": VERSION})
    return {"analyzed": len(todo), "activities": len(ordered)}


def daily_series(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return []
    load: dict[str, float] = defaultdict(float)
    km: dict[str, float] = defaultdict(float)
    for r in rows:
        load[r["date"]] += r.get("trimp") or 0
        if r["sport"] == "run":
            km[r["date"]] += r.get("distance_km") or 0
    start = date.fromisoformat(min(load))
    end = max(date.fromisoformat(max(load)), today())
    seed_days = [load.get(d.isoformat(), 0.0) for d in daterange(start, min(start + timedelta(days=SEED_DAYS - 1), end))]
    ctl = atl = sum(seed_days) / len(seed_days)
    out = []
    for d in daterange(start, end):
        key = d.isoformat()
        t = load.get(key, 0.0)
        tsb = ctl - atl
        ctl += (t - ctl) / 42
        atl += (t - atl) / 7
        out.append({"date": key, "trimp": round(t, 1), "run_km": round(km.get(key, 0.0), 2),
                    "ctl": round(ctl, 1), "atl": round(atl, 1), "tsb": round(tsb, 1)})
    return out


def weekly_series(rows: list[dict[str, Any]], daily: list[dict[str, Any]]) -> list[dict[str, Any]]:
    weeks: dict[str, dict[str, Any]] = {}
    for r in rows:
        y, w = week_of(date.fromisoformat(r["date"]))
        wk = weeks.setdefault(week_label(y, w), {"runs": 0, "run_km": 0.0, "run_min": 0.0, "long_km": 0.0, "quality": 0,
                                                 "trimp": 0.0, "other_min": 0.0, "easy": 0.0, "zoned": 0.0})
        wk["trimp"] += r.get("trimp") or 0
        if r["sport"] == "run":
            wk["runs"] += 1
            wk["run_km"] += r.get("distance_km") or 0
            wk["run_min"] += r.get("moving_min") or 0
            wk["long_km"] = max(wk["long_km"], r.get("distance_km") or 0)
            wk["quality"] += 1 if r.get("kind") == "quality" or (r.get("quality_km") or 0) >= 3 else 0
            zones = [r.get(f"z{i}") or 0 for i in range(1, 6)]
            wk["easy"] += zones[0] + zones[1]
            wk["zoned"] += sum(zones)
        else:
            wk["other_min"] += r.get("moving_min") or 0
    out = []
    for label in sorted(weeks):
        wk = weeks[label]
        out.append({"week": label, "runs": wk["runs"], "run_km": round(wk["run_km"], 1), "run_min": round(wk["run_min"]),
                    "long_km": round(wk["long_km"], 1), "quality": wk["quality"], "trimp": round(wk["trimp"]),
                    "other_min": round(wk["other_min"]),
                    "easy_pct": round(100 * wk["easy"] / wk["zoned"]) if wk["zoned"] else None})
    return out


def load_on(daily: list[dict[str, Any]], d: date) -> dict[str, Any] | None:
    key = d.isoformat()
    candidates = [x for x in daily if x["date"] <= key]
    return candidates[-1] if candidates else None


def ensure_fresh() -> None:
    meta = read_json(metrics_dir() / "meta.json", None)
    index = store.load_index()
    if meta is None or not (metrics_dir() / "activities.csv").exists():
        if index:
            refresh()
        return
    if meta.get("profile") != current_profile(index).metrics_hash() or meta.get("version") != VERSION:
        refresh()
        return
    daily = read_csv("daily.csv")
    if daily and daily[-1]["date"] < today().isoformat():
        rows = read_csv("activities.csv")
        write_text(metrics_dir() / "daily.csv", _csv_text(DAILY_COLUMNS, daily_series(rows)))


def week_dates(year: int, week: int) -> list[date]:
    monday = date.fromisocalendar(year, week, 1)
    return [monday + timedelta(days=i) for i in range(7)]
