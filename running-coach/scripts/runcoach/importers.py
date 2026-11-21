from __future__ import annotations

import gzip
import hashlib
import io
import json
import math
import shutil
import tempfile
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator
from xml.etree import ElementTree as ET

from .store import make_activity, normalize_sport
from .util import CoachError, parse_utc

FILE_EXTS = (".gpx", ".tcx", ".fit", ".json")
ARCHIVE_JSON_HINTS = ("summarizedactivities",)
MAX_GAP_S = 30
MOVING_SPEED = 0.8
FIT_EPOCH = datetime(1989, 12, 31, tzinfo=timezone.utc)


class Skip(Exception):
    pass


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _haversine(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371008.8 * math.asin(math.sqrt(h))


def elevation_gain(alts: list[float | None]) -> float | None:
    values = [a for a in alts if a is not None]
    if len(values) < 2:
        return None
    gain, ref = 0.0, values[0]
    for a in values[1:]:
        if a > ref + 3:
            gain += a - ref
            ref = a
        elif a < ref:
            ref = a
    return gain


def build_samples(points: list[dict[str, Any]]) -> tuple[datetime, dict[str, list], dict[str, Any]]:
    points = sorted((p for p in points if p.get("time") is not None), key=lambda p: p["time"])
    if len(points) < 2:
        raise Skip("fewer than two timestamped points")
    t0 = points[0]["time"]
    has_dist = sum(1 for p in points if p.get("dist") is not None) >= 0.8 * len(points)
    t, d, hr, alt = [], [], [], []
    total, last_pos, last_dist = 0.0, None, 0.0
    for p in points:
        if has_dist:
            if p.get("dist") is not None:
                last_dist = max(last_dist, float(p["dist"]))
            total = last_dist
        elif p.get("lat") is not None and p.get("lon") is not None:
            pos = (p["lat"], p["lon"])
            if last_pos is not None:
                total += _haversine(last_pos, pos)
            last_pos = pos
        t.append(int(round((p["time"] - t0).total_seconds())))
        d.append(round(total, 1))
        hr.append(int(p["hr"]) if p.get("hr") else None)
        alt.append(round(float(p["alt"]), 1) if p.get("alt") is not None else None)
    samples = {"t": t, "d": d, "hr": hr, "alt": alt}
    return t0, samples, sample_stats(samples)


def sample_stats(s: dict[str, list]) -> dict[str, Any]:
    t, d, hr = s["t"], s["d"], s.get("hr") or [None] * len(s["t"])
    moving = 0.0
    hr_sum, hr_time = 0.0, 0.0
    for i in range(1, len(t)):
        dt = t[i] - t[i - 1]
        if dt <= 0 or dt > MAX_GAP_S:
            continue
        if (d[i] - d[i - 1]) / dt >= MOVING_SPEED:
            moving += dt
        if hr[i]:
            hr_sum += hr[i] * dt
            hr_time += dt
    hrs = [h for h in hr if h]
    return {
        "distance_m": d[-1] if d else 0.0,
        "moving_s": moving,
        "elapsed_s": float(t[-1]) if t else None,
        "avg_hr": hr_sum / hr_time if hr_time else None,
        "max_hr": float(max(hrs)) if hrs else None,
        "elev_gain_m": elevation_gain(s.get("alt") or []),
    }


def guess_sport(distance_m: float, moving_s: float | None) -> str:
    if not moving_s or distance_m <= 0:
        return "run"
    speed = distance_m / moving_s
    if speed > 6.5:
        return "ride"
    if speed < 1.9:
        return "walk"
    return "run"


def _finish_file_activity(label: str, digest: str, sport: str | None, t0: datetime, samples: dict, stats: dict,
                          name: str | None = None, laps: list | None = None, overrides: dict | None = None,
                          local_offset: timedelta | None = None) -> dict[str, Any]:
    stats = {**stats, **{k: v for k, v in (overrides or {}).items() if v is not None}}
    sport_raw = sport or guess_sport(stats["distance_m"], stats["moving_s"])
    act = make_activity("file", digest, sport_raw, t0, name=name or Path(label).name, file=Path(label).name,
                        samples=samples, laps=laps or [], **stats)
    if sport is None:
        act["sport_guessed"] = True
    if local_offset is not None:
        act["start_local"] = (t0.replace(tzinfo=None) + local_offset).isoformat(timespec="seconds")
    return act


def parse_gpx(data: bytes, label: str, digest: str) -> list[dict[str, Any]]:
    root = ET.fromstring(data)
    name, sport, points = None, None, []
    for el in root.iter():
        tag = _local(el.tag)
        if tag == "trk":
            for child in el:
                if _local(child.tag) == "name" and child.text:
                    name = child.text.strip()
                elif _local(child.tag) == "type" and child.text:
                    sport = child.text.strip()
        elif tag == "trkpt":
            p: dict[str, Any] = {"lat": float(el.get("lat")), "lon": float(el.get("lon"))}
            for sub in el.iter():
                st = _local(sub.tag)
                if st == "time" and sub.text:
                    p["time"] = parse_utc(sub.text)
                elif st == "ele" and sub.text:
                    p["alt"] = float(sub.text)
                elif st in ("hr", "heartrate") and sub.text:
                    p["hr"] = float(sub.text)
            points.append(p)
    if not points:
        raise Skip("no track points")
    t0, samples, stats = build_samples(points)
    return [_finish_file_activity(label, digest, normalize_sport(sport) if sport else None, t0, samples, stats, name)]


def parse_tcx(data: bytes, label: str, digest: str) -> list[dict[str, Any]]:
    root = ET.fromstring(data)
    out = []
    for activity in (el for el in root.iter() if _local(el.tag) == "Activity"):
        sport = activity.get("Sport")
        points, laps = [], []
        t_start = None
        for lap in (el for el in activity if _local(el.tag) == "Lap"):
            lap_start = parse_utc(lap.get("StartTime")) if lap.get("StartTime") else None
            t_start = t_start or lap_start
            info: dict[str, Any] = {"start": lap_start}
            for child in lap:
                ct = _local(child.tag)
                if ct == "TotalTimeSeconds":
                    info["moving_s"] = float(child.text)
                elif ct == "DistanceMeters":
                    info["distance_m"] = float(child.text)
                elif ct in ("AverageHeartRateBpm", "MaximumHeartRateBpm"):
                    value = next((float(v.text) for v in child if _local(v.tag) == "Value"), None)
                    info["avg_hr" if ct.startswith("Average") else "max_hr"] = value
                elif ct == "Track":
                    for tp in child:
                        p: dict[str, Any] = {}
                        for sub in tp.iter():
                            st = _local(sub.tag)
                            if st == "Time":
                                p["time"] = parse_utc(sub.text)
                            elif st == "LatitudeDegrees":
                                p["lat"] = float(sub.text)
                            elif st == "LongitudeDegrees":
                                p["lon"] = float(sub.text)
                            elif st == "AltitudeMeters":
                                p["alt"] = float(sub.text)
                            elif st == "DistanceMeters":
                                p["dist"] = float(sub.text)
                        hr_el = next((e for e in tp if _local(e.tag) == "HeartRateBpm"), None)
                        if hr_el is not None:
                            p["hr"] = next((float(v.text) for v in hr_el if _local(v.tag) == "Value"), None)
                        points.append(p)
            laps.append(info)
        if not points:
            continue
        t0, samples, stats = build_samples(points)
        norm_laps = [{
            "start_s": round((lp["start"] - t0).total_seconds()) if lp.get("start") else None,
            "distance_m": lp.get("distance_m"),
            "moving_s": lp.get("moving_s"),
            "avg_hr": lp.get("avg_hr"),
            "max_hr": lp.get("max_hr"),
        } for lp in laps]
        overrides = {"moving_s": sum(lp.get("moving_s") or 0 for lp in laps) or None,
                     "distance_m": sum(lp.get("distance_m") or 0 for lp in laps) or None}
        out.append(_finish_file_activity(label, digest if len(out) == 0 else f"{digest}-{len(out)}",
                                         normalize_sport(sport) if sport and sport.lower() != "other" else None,
                                         t0, samples, stats, None, norm_laps, overrides))
    if not out:
        raise Skip("no activity with points")
    return out


def _fit_time(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        return FIT_EPOCH + timedelta(seconds=value)
    return None


def parse_fit(data: bytes, label: str, digest: str) -> list[dict[str, Any]]:
    try:
        import fitdecode
    except ImportError as e:
        raise CoachError("reading FIT files: fitdecode dependency missing, run install.sh") from e
    points, laps, session, sport = [], [], {}, None
    activity_local = activity_ts = None
    first = True
    with fitdecode.FitReader(io.BytesIO(data), check_crc=fitdecode.CrcCheck.WARN,
                             error_handling=fitdecode.ErrorHandling.IGNORE) as fit:
        for frame in fit:
            if not isinstance(frame, fitdecode.FitDataMessage):
                continue
            name = frame.name

            def val(field: str, _frame=frame) -> Any:
                return _frame.get_value(field, fallback=None) if _frame.has_field(field) else None

            if first and name == "file_id":
                first = False
                ftype = val("type")
                if ftype not in (None, "activity", 4):
                    raise Skip(f"FIT file of type {ftype}, not an activity")
            elif name == "record":
                ts = _fit_time(val("timestamp"))
                if ts is None:
                    continue
                lat, lon = val("position_lat"), val("position_long")
                alt = val("enhanced_altitude")
                points.append({
                    "time": ts,
                    "dist": val("distance"),
                    "hr": val("heart_rate"),
                    "alt": alt if alt is not None else val("altitude"),
                    "lat": lat * 180 / 2**31 if isinstance(lat, int) else None,
                    "lon": lon * 180 / 2**31 if isinstance(lon, int) else None,
                })
            elif name == "lap":
                laps.append({
                    "start": _fit_time(val("start_time")),
                    "distance_m": val("total_distance"),
                    "moving_s": val("total_timer_time"),
                    "elapsed_s": val("total_elapsed_time"),
                    "avg_hr": val("avg_heart_rate"),
                    "max_hr": val("max_heart_rate"),
                })
            elif name == "session" and not session:
                session = {
                    "start": _fit_time(val("start_time")),
                    "distance_m": val("total_distance"),
                    "moving_s": val("total_timer_time"),
                    "elapsed_s": val("total_elapsed_time"),
                    "avg_hr": val("avg_heart_rate"),
                    "max_hr": val("max_heart_rate"),
                    "elev_gain_m": val("total_ascent"),
                }
                sport = val("sport")
            elif name == "sport" and sport is None:
                sport = val("sport")
            elif name == "activity":
                activity_ts, activity_local = val("timestamp"), val("local_timestamp")
    if not points:
        raise Skip("no records")
    t0, samples, stats = build_samples(points)
    if session.get("start"):
        t0 = session["start"]
    norm_laps = [{
        "start_s": round((lp["start"] - t0).total_seconds()) if lp.get("start") else None,
        **{k: lp[k] for k in ("distance_m", "moving_s", "elapsed_s", "avg_hr", "max_hr")},
    } for lp in laps]
    offset = None
    if activity_ts is not None and activity_local is not None:
        ts = _fit_time(activity_ts)
        local = activity_local if isinstance(activity_local, (int, float)) else None
        if isinstance(activity_local, datetime):
            offset = activity_local.replace(tzinfo=None) - ts.replace(tzinfo=None)
        elif local is not None:
            offset = (FIT_EPOCH + timedelta(seconds=local)).replace(tzinfo=None) - ts.replace(tzinfo=None)
        if offset is not None:
            offset = timedelta(minutes=round(offset.total_seconds() / 900) * 15)
    sport_name = str(sport) if sport not in (None, "generic") else None
    overrides = {k: session.get(k) for k in ("distance_m", "moving_s", "elapsed_s", "avg_hr", "max_hr", "elev_gain_m")}
    return [_finish_file_activity(label, digest, normalize_sport(sport_name) if sport_name else None, t0, samples,
                                  stats, None, norm_laps, overrides, offset)]


def strava_activity(obj: dict[str, Any], streams: dict | None = None, laps: list | None = None) -> dict[str, Any]:
    start = parse_utc(obj["start_date"])
    local = str(obj.get("start_date_local") or "").rstrip("Z")
    raw_laps = laps if laps is not None else obj.get("laps") or []
    norm_laps = []
    for lap in raw_laps:
        lap_start = parse_utc(lap["start_date"]) if lap.get("start_date") else None
        norm_laps.append({
            "start_s": round((lap_start - start).total_seconds()) if lap_start else None,
            "distance_m": lap.get("distance"),
            "moving_s": lap.get("moving_time"),
            "elapsed_s": lap.get("elapsed_time"),
            "avg_hr": lap.get("average_heartrate"),
            "max_hr": lap.get("max_heartrate"),
        })
    samples = None
    if streams and streams.get("time") and streams.get("distance"):
        t = [int(x) for x in streams["time"]["data"]]
        n = len(t)

        def stream(key: str) -> list:
            values = (streams.get(key) or {}).get("data") or []
            return list(values) if len(values) == n else [None] * n

        samples = {"t": t, "d": [round(float(x or 0), 1) for x in streams["distance"]["data"]],
                   "hr": [int(h) if h else None for h in stream("heartrate")],
                   "alt": [round(float(a), 1) if a is not None else None for a in stream("altitude")]}
    act = make_activity(
        "strava", str(obj["id"]), obj.get("sport_type") or obj.get("type"), start,
        name=obj.get("name") or "",
        distance_m=obj.get("distance") or 0.0,
        moving_s=obj.get("moving_time"),
        elapsed_s=obj.get("elapsed_time"),
        avg_hr=obj.get("average_heartrate"),
        max_hr=obj.get("max_heartrate"),
        elev_gain_m=obj.get("total_elevation_gain"),
        laps=norm_laps,
        samples=samples,
    )
    if local:
        act["start_local"] = local
    return act


def garmin_api_activity(obj: dict[str, Any]) -> dict[str, Any]:
    type_key = (obj.get("activityType") or {}).get("typeKey") if isinstance(obj.get("activityType"), dict) else obj.get("activityType")
    start = parse_utc(obj["startTimeGMT"]) if obj.get("startTimeGMT") else parse_utc(obj["startTimeLocal"])
    act = make_activity(
        "garmin", str(obj["activityId"]), type_key, start,
        name=obj.get("activityName") or "",
        distance_m=obj.get("distance") or 0.0,
        moving_s=obj.get("movingDuration") or obj.get("duration"),
        elapsed_s=obj.get("elapsedDuration") or obj.get("duration"),
        avg_hr=obj.get("averageHR"),
        max_hr=obj.get("maxHR"),
        elev_gain_m=obj.get("elevationGain"),
    )
    if obj.get("startTimeLocal"):
        act["start_local"] = str(obj["startTimeLocal"]).replace(" ", "T")[:19]
    return act


def garmin_export_activity(obj: dict[str, Any]) -> dict[str, Any]:
    # Garmin account export: distance and elevation in centimetres, durations in milliseconds,
    # startTimeLocal = local wall clock encoded as if it were a UTC epoch in ms.
    def ms(key: str) -> float | None:
        return obj[key] / 1000.0 if obj.get(key) is not None else None

    start = datetime.fromtimestamp((obj.get("startTimeGmt") or obj.get("beginTimestamp")) / 1000, tz=timezone.utc)
    act = make_activity(
        "garmin", str(obj["activityId"]), obj.get("activityType") or obj.get("sportType"), start,
        name=obj.get("name") or "",
        distance_m=(obj.get("distance") or 0) / 100.0,
        moving_s=ms("movingDuration") or ms("duration"),
        elapsed_s=ms("elapsedDuration") or ms("duration"),
        avg_hr=obj.get("avgHr"),
        max_hr=obj.get("maxHr"),
        elev_gain_m=obj["elevationGain"] / 100.0 if obj.get("elevationGain") is not None else None,
    )
    if obj.get("startTimeLocal"):
        local = datetime.fromtimestamp(obj["startTimeLocal"] / 1000, tz=timezone.utc).replace(tzinfo=None)
        act["start_local"] = local.isoformat(timespec="seconds")
    return act


def parse_json(data: bytes, label: str, digest: str) -> list[dict[str, Any]]:
    try:
        obj = json.loads(data)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise Skip(f"unreadable JSON ({e})") from e
    items = obj if isinstance(obj, list) else [obj]
    out = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if "summarizedActivitiesExport" in item:
            out += [garmin_export_activity(a) for a in item["summarizedActivitiesExport"] if a.get("activityId")]
        elif "activityId" in item and ("startTimeGMT" in item or "startTimeLocal" in item) and isinstance(item.get("startTimeLocal", ""), str):
            out.append(garmin_api_activity(item))
        elif "activityId" in item and ("startTimeGmt" in item or "beginTimestamp" in item):
            out.append(garmin_export_activity(item))
        elif "id" in item and "start_date" in item and ("sport_type" in item or "type" in item):
            out.append(strava_activity(item))
    if not out:
        raise Skip("JSON without any recognised Strava or Garmin activity")
    return out


PARSERS = {".gpx": parse_gpx, ".tcx": parse_tcx, ".fit": parse_fit, ".json": parse_json}


def _kind(name: str) -> tuple[str | None, bool]:
    lower = name.lower()
    gz = lower.endswith(".gz")
    if gz:
        lower = lower[:-3]
    for ext in FILE_EXTS:
        if lower.endswith(ext):
            return ext, gz
    if lower.endswith(".zip"):
        return ".zip", gz
    return None, gz


def _from_archive(label: str, source: Any) -> Iterator[tuple[str, bytes, str]]:
    try:
        zf = zipfile.ZipFile(source)
    except zipfile.BadZipFile as e:
        raise CoachError(f"{label}: unreadable zip archive") from e
    with zf:
        for info in zf.infolist():
            if info.is_dir() or "__MACOSX" in info.filename:
                continue
            ext, gz = _kind(info.filename)
            if ext is None:
                continue
            if ext == ".json" and not any(h in info.filename.lower() for h in ARCHIVE_JSON_HINTS):
                continue
            sub = f"{label}:{info.filename}"
            if ext == ".zip" and not gz:
                with tempfile.TemporaryFile() as spool:
                    with zf.open(info) as member:
                        shutil.copyfileobj(member, spool)
                    spool.seek(0)
                    yield from _from_archive(sub, spool)
                continue
            inner = zf.read(info)
            if gz:
                inner = gzip.decompress(inner)
            if ext == ".zip":
                yield from _from_archive(sub, io.BytesIO(inner))
            else:
                yield sub, inner, ext


def iter_inputs(paths: list[str]) -> Iterator[tuple[str, bytes, str]]:
    for raw in paths:
        path = Path(raw).expanduser()
        if not path.exists():
            raise CoachError(f"not found: {raw}")
        files = sorted(p for p in path.rglob("*") if p.is_file()) if path.is_dir() else [path]
        for f in files:
            ext, gz = _kind(f.name)
            if ext is None:
                continue
            if ext == ".zip" and not gz:
                yield from _from_archive(str(f), f)
                continue
            data = f.read_bytes()
            if gz:
                data = gzip.decompress(data)
            if ext == ".zip":
                yield from _from_archive(str(f), io.BytesIO(data))
            else:
                yield str(f), data, ext


def parse_bytes(label: str, data: bytes, ext: str, sport: str | None = None) -> list[dict[str, Any]]:
    digest = hashlib.sha1(data).hexdigest()[:12]
    try:
        acts = PARSERS[ext](data, label, digest)
    except ET.ParseError as e:
        raise Skip(f"unreadable XML ({e})") from e
    if sport:
        for a in acts:
            a["sport"] = sport
            a.pop("sport_guessed", None)
    return acts
