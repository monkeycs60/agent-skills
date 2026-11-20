from __future__ import annotations

import argparse
import gzip
import io
import json
import math
import random
import struct
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "fixtures"
LOCAL = timedelta(hours=2)
BASE = (40.7812, -73.9665)
FIT_EPOCH = 631065600
CRC_TABLE = [0x0000, 0xCC01, 0xD801, 0x1400, 0xF001, 0x3C00, 0x2800, 0xE401,
             0xA001, 0x6C00, 0x7800, 0xB401, 0x5000, 0x9C01, 0x8801, 0x4400]


def utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=timezone.utc)


def simulate(segments, start: datetime, dt: int, seed: int, hr0: float = 100):
    rng = random.Random(seed)
    points, laps = [], []
    t, d, hr = 0.0, 0.0, hr0
    for seg_dist, pace, hr_a, hr_b in segments:
        seg_start_t, seg_start_d, seg_hr = t, d, []
        while d - seg_start_d < seg_dist - 1e-6:
            speed = 1000 / (pace * (1 + rng.uniform(-0.02, 0.02)))
            step = min(speed * dt, seg_dist - (d - seg_start_d))
            used = step / speed
            t += used
            d += step
            frac = (d - seg_start_d) / seg_dist
            target = hr_a + (hr_b - hr_a) * frac
            hr += (target - hr) * min(1.0, used / 25) + rng.uniform(-1.2, 1.2)
            alt = 20 + 6 * math.sin(d / 900) + rng.uniform(-0.3, 0.3)
            points.append({"time": start + timedelta(seconds=round(t, 3)), "dist": d, "hr": round(hr), "alt": alt, "speed": speed})
            seg_hr.append(round(hr))
        laps.append({"start": start + timedelta(seconds=seg_start_t), "elapsed": t - seg_start_t, "distance": seg_dist,
                     "avg_hr": round(sum(seg_hr) / len(seg_hr)), "max_hr": max(seg_hr)})
    points.insert(0, {"time": start, "dist": 0.0, "hr": round(hr0), "alt": 20.0, "speed": 0.0})
    return points, laps


def km_laps(points, start: datetime):
    laps, last_t, last_d, bucket = [], start, 0.0, []
    for p in points[1:]:
        bucket.append(p["hr"])
        if p["dist"] - last_d >= 1000 - 1e-6 or p is points[-1]:
            laps.append({"start": last_t, "elapsed": (p["time"] - last_t).total_seconds(), "distance": p["dist"] - last_d,
                         "avg_hr": round(sum(bucket) / len(bucket)), "max_hr": max(bucket)})
            last_t, last_d, bucket = p["time"], p["dist"], []
    return laps


def latlon(dist: float):
    radius = 2000 / (2 * math.pi)
    angle = dist / radius
    dlat = radius * math.sin(angle) / 111320
    dlon = radius * (1 - math.cos(angle)) / (111320 * math.cos(math.radians(BASE[0])))
    return BASE[0] + dlat, BASE[1] + dlon


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def gpx(points, name: str) -> str:
    rows = []
    for p in points:
        lat, lon = latlon(p["dist"])
        rows.append(f'<trkpt lat="{lat:.7f}" lon="{lon:.7f}"><ele>{p["alt"]:.1f}</ele><time>{iso(p["time"])}</time>'
                    f'<extensions><gpxtpx:TrackPointExtension><gpxtpx:hr>{p["hr"]}</gpxtpx:hr></gpxtpx:TrackPointExtension></extensions></trkpt>')
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<gpx version="1.1" creator="fixture" xmlns="http://www.topografix.com/GPX/1/1" '
            'xmlns:gpxtpx="http://www.garmin.com/xmlschemas/TrackPointExtension/v1">\n'
            f'<metadata><time>{iso(points[0]["time"])}</time></metadata>\n'
            f'<trk><name>{name}</name><type>running</type><trkseg>\n' + "\n".join(rows) + "\n</trkseg></trk></gpx>\n")


def tcx(points, laps) -> str:
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<TrainingCenterDatabase xmlns="http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2">',
           f'<Activities><Activity Sport="Running"><Id>{iso(points[0]["time"])}</Id>']
    for lap in laps:
        end = lap["start"] + timedelta(seconds=lap["elapsed"])
        out.append(f'<Lap StartTime="{iso(lap["start"])}"><TotalTimeSeconds>{lap["elapsed"]:.1f}</TotalTimeSeconds>'
                   f'<DistanceMeters>{lap["distance"]:.1f}</DistanceMeters>'
                   f'<AverageHeartRateBpm><Value>{lap["avg_hr"]}</Value></AverageHeartRateBpm>'
                   f'<MaximumHeartRateBpm><Value>{lap["max_hr"]}</Value></MaximumHeartRateBpm><Track>')
        for p in points:
            if lap["start"] <= p["time"] <= end:
                lat, lon = latlon(p["dist"])
                out.append(f'<Trackpoint><Time>{iso(p["time"])}</Time><Position><LatitudeDegrees>{lat:.7f}</LatitudeDegrees>'
                           f'<LongitudeDegrees>{lon:.7f}</LongitudeDegrees></Position><AltitudeMeters>{p["alt"]:.1f}</AltitudeMeters>'
                           f'<DistanceMeters>{p["dist"]:.1f}</DistanceMeters><HeartRateBpm><Value>{p["hr"]}</Value></HeartRateBpm></Trackpoint>')
        out.append("</Track></Lap>")
    out.append("</Activity></Activities></TrainingCenterDatabase>")
    return "\n".join(out) + "\n"


def crc16(data: bytes, crc: int = 0) -> int:
    for b in data:
        tmp = CRC_TABLE[crc & 0xF]
        crc = ((crc >> 4) & 0x0FFF) ^ tmp ^ CRC_TABLE[b & 0xF]
        tmp = CRC_TABLE[crc & 0xF]
        crc = ((crc >> 4) & 0x0FFF) ^ tmp ^ CRC_TABLE[(b >> 4) & 0xF]
    return crc


class FitWriter:
    def __init__(self) -> None:
        self.buf = bytearray()
        self.defs: dict[int, list] = {}

    def define(self, local: int, global_num: int, fields: list[tuple[int, int, int, str]]) -> None:
        self.buf += struct.pack("<BBBHB", 0x40 | local, 0, 0, global_num, len(fields))
        for num, size, base, _ in fields:
            self.buf += struct.pack("BBB", num, size, base)
        self.defs[local] = fields

    def write(self, local: int, values: list[int]) -> None:
        self.buf += struct.pack("B", local)
        for (_, _, _, fmt), value in zip(self.defs[local], values):
            self.buf += struct.pack("<" + fmt, value)

    def data(self) -> bytes:
        body = bytes(self.buf)
        header = struct.pack("<BBHI4s", 14, 0x20, 2132, len(body), b".FIT")
        header += struct.pack("<H", crc16(header))
        whole = header + body
        return whole + struct.pack("<H", crc16(whole))


def fit_ts(dt: datetime) -> int:
    return int(dt.timestamp()) - FIT_EPOCH


def fit(points, laps) -> bytes:
    w = FitWriter()
    start = points[0]["time"]
    w.define(0, 0, [(0, 1, 0x00, "B"), (1, 2, 0x84, "H"), (2, 2, 0x84, "H"), (3, 4, 0x8C, "I"), (4, 4, 0x86, "I")])
    w.write(0, [4, 255, 1, 12345, fit_ts(start)])
    w.define(1, 20, [(253, 4, 0x86, "I"), (5, 4, 0x86, "I"), (3, 1, 0x02, "B"), (2, 2, 0x84, "H"), (6, 2, 0x84, "H")])
    for p in points:
        w.write(1, [fit_ts(p["time"]), round(p["dist"] * 100), p["hr"], round((p["alt"] + 500) * 5), round(p["speed"] * 1000)])
    w.define(2, 19, [(253, 4, 0x86, "I"), (2, 4, 0x86, "I"), (7, 4, 0x86, "I"), (8, 4, 0x86, "I"), (9, 4, 0x86, "I"),
                     (15, 1, 0x02, "B"), (16, 1, 0x02, "B"), (0, 1, 0x00, "B"), (1, 1, 0x00, "B"), (25, 1, 0x00, "B")])
    for lap in laps:
        end = lap["start"] + timedelta(seconds=lap["elapsed"])
        w.write(2, [fit_ts(end), fit_ts(lap["start"]), round(lap["elapsed"] * 1000), round(lap["elapsed"] * 1000),
                    round(lap["distance"] * 100), lap["avg_hr"], lap["max_hr"], 9, 1, 1])
    end = points[-1]["time"]
    elapsed = (end - start).total_seconds()
    hrs = [p["hr"] for p in points]
    w.define(3, 18, [(253, 4, 0x86, "I"), (2, 4, 0x86, "I"), (7, 4, 0x86, "I"), (8, 4, 0x86, "I"), (9, 4, 0x86, "I"),
                     (5, 1, 0x00, "B"), (6, 1, 0x00, "B"), (16, 1, 0x02, "B"), (17, 1, 0x02, "B"), (22, 2, 0x84, "H"),
                     (0, 1, 0x00, "B"), (1, 1, 0x00, "B"), (26, 2, 0x84, "H")])
    w.write(3, [fit_ts(end), fit_ts(start), round(elapsed * 1000), round(elapsed * 1000), round(points[-1]["dist"] * 100),
                1, 0, round(sum(hrs) / len(hrs)), max(hrs), 38, 8, 1, len(laps)])
    w.define(4, 34, [(253, 4, 0x86, "I"), (0, 4, 0x86, "I"), (1, 2, 0x84, "H"), (2, 1, 0x00, "B"), (3, 1, 0x00, "B"),
                     (4, 1, 0x00, "B"), (5, 4, 0x86, "I")])
    w.write(4, [fit_ts(end), round(elapsed * 1000), 1, 0, 26, 1, fit_ts(end) + int(LOCAL.total_seconds())])
    return w.data()


def strava_detail(activity_id: int, name: str, points, laps) -> dict:
    start = points[0]["time"]
    hrs = [p["hr"] for p in points[1:]]
    elapsed = (points[-1]["time"] - start).total_seconds()
    return {
        "id": activity_id, "name": name, "type": "Run", "sport_type": "Run",
        "start_date": iso(start), "start_date_local": iso(start + LOCAL),
        "distance": round(points[-1]["dist"], 1), "moving_time": round(elapsed), "elapsed_time": round(elapsed) + 25,
        "total_elevation_gain": 41.0, "has_heartrate": True,
        "average_heartrate": round(sum(hrs) / len(hrs), 1), "max_heartrate": float(max(hrs)),
        "laps": [{"id": activity_id * 100 + i, "name": f"Lap {i + 1}", "lap_index": i + 1, "split": i + 1,
                  "start_date": iso(lap["start"]), "start_date_local": iso(lap["start"] + LOCAL),
                  "elapsed_time": round(lap["elapsed"]), "moving_time": round(lap["elapsed"]),
                  "distance": round(lap["distance"], 1), "average_speed": round(lap["distance"] / lap["elapsed"], 3),
                  "average_heartrate": float(lap["avg_hr"]), "max_heartrate": float(lap["max_hr"])} for i, lap in enumerate(laps)],
    }


def streams(points, step: int = 1) -> dict:
    sel = points[::step]
    t0 = sel[0]["time"]
    return {
        "time": {"data": [round((p["time"] - t0).total_seconds()) for p in sel], "series_type": "distance", "resolution": "high"},
        "distance": {"data": [round(p["dist"], 1) for p in sel], "series_type": "distance", "resolution": "high"},
        "heartrate": {"data": [p["hr"] for p in sel], "series_type": "distance", "resolution": "high"},
        "altitude": {"data": [round(p["alt"], 1) for p in sel], "series_type": "distance", "resolution": "high"},
    }


def garmin_export(history: list[dict]) -> list:
    out = []
    for i, h in enumerate(history):
        start_ms = h["start"].timestamp() * 1000
        out.append({
            "activityId": 20000000001 + i, "name": h["name"], "activityType": h["type"], "sportType": h["type"].upper(),
            "startTimeGmt": start_ms, "startTimeLocal": start_ms + LOCAL.total_seconds() * 1000, "beginTimestamp": start_ms,
            "duration": h["moving"] * 1000 + 20000, "movingDuration": h["moving"] * 1000, "elapsedDuration": h["moving"] * 1000 + 20000,
            "distance": h["distance"] * 100, "elevationGain": 2500.0, "avgHr": h["hr"], "maxHr": h["max"], "calories": 500.0,
        })
    return [{"summarizedActivitiesExport": out}]


def history() -> list[dict]:
    rows = []
    longs = [12000, 13000, 14000, 11000, 15000]
    for w, long_m in enumerate(longs):
        monday = utc(2026, 8, 31) + timedelta(weeks=w)
        rows.append({"start": monday + timedelta(days=1, hours=5), "name": "Séance", "type": "running", "distance": 9000,
                     "moving": 2900, "hr": 158, "max": 176})
        rows.append({"start": monday + timedelta(days=2, hours=16, minutes=30), "name": "Vélo", "type": "cycling",
                     "distance": 25000, "moving": 3600, "hr": 126, "max": 148})
        rows.append({"start": monday + timedelta(days=3, hours=5), "name": "Footing", "type": "running", "distance": 7000,
                     "moving": 2555, "hr": 142, "max": 151})
        rows.append({"start": monday + timedelta(days=5, hours=7), "name": "Footing", "type": "running", "distance": 6000,
                     "moving": 2220, "hr": 139, "max": 149})
        rows.append({"start": monday + timedelta(days=6, hours=7), "name": "Sortie longue", "type": "running",
                     "distance": long_m, "moving": round(long_m / 1000 * 365), "hr": 146, "max": 158})
    rows.append({"start": utc(2026, 10, 8, 5, 0, 30), "name": "Footing", "type": "running", "distance": 8010,
                 "moving": 2905, "hr": 143, "max": 151})
    return rows


def main() -> None:
    files = ROOT / "files"
    strava_api = ROOT / "strava_api"
    garmin_api = ROOT / "garmin_api"
    for d in (files, strava_api, garmin_api):
        d.mkdir(parents=True, exist_ok=True)

    warm = [(2000, 370, 125, 140)]
    reps = []
    for _ in range(6):
        reps += [(800, 265, 166, 175), (400, 420, 150, 146)]
    pts, laps = simulate(warm + reps + [(1500, 380, 140, 135)], utc(2026, 10, 6, 5, 0), 5, seed=1)
    (files / "2026-10-06_intervals.tcx.gz").write_bytes(gzip.compress(tcx(pts, laps).encode(), mtime=0))

    pts, _ = simulate([(8000, 365, 141, 147)], utc(2026, 10, 8, 5, 0), 10, seed=2)
    (files / "2026-10-08_easy.gpx").write_text(gpx(pts, "Footing du jeudi"), encoding="utf-8")

    tempo = [(2000, 365, 135, 145), (5000, 292, 163, 170), (1500, 375, 145, 138)]
    pts, _ = simulate(tempo, utc(2026, 10, 10, 7, 0), 2, seed=3)
    tempo_fit = fit(pts, km_laps(pts, pts[0]["time"]))
    (files / "2026-10-10_tempo.fit").write_bytes(tempo_fit)

    pts, _ = simulate([(13000, 360, 141, 149), (3000, 360, 153, 157)], utc(2026, 10, 11, 7, 30), 5, seed=4)
    detail = strava_detail(8000000001, "Sortie longue du dimanche", pts, km_laps(pts, pts[0]["time"]))
    (files / "2026-10-11_strava_long_run.json").write_text(json.dumps(detail, indent=1), encoding="utf-8")

    (files / "garmin_summarizedActivities.json").write_text(json.dumps(garmin_export(history()), indent=1), encoding="utf-8")

    run_start = utc(2026, 10, 13, 5, 5)
    pts, _ = simulate([(10000, 362, 140, 148)], run_start, 5, seed=5)
    run_laps = km_laps(pts, run_start)
    ride_start = utc(2026, 10, 14, 16, 30)
    listing = [
        {k: v for k, v in strava_detail(9000000001, "Footing matinal", pts, run_laps).items() if k != "laps"},
        {"id": 9000000002, "name": "Vélo du soir", "type": "Ride", "sport_type": "Ride", "start_date": iso(ride_start),
         "start_date_local": iso(ride_start + LOCAL), "distance": 30500.0, "moving_time": 4200, "elapsed_time": 4400,
         "total_elevation_gain": 210.0, "has_heartrate": True, "average_heartrate": 128.0, "max_heartrate": 155.0},
    ]
    (strava_api / "activities.json").write_text(json.dumps(listing, indent=1), encoding="utf-8")
    (strava_api / "streams_9000000001.json").write_text(json.dumps(streams(pts)), encoding="utf-8")
    laps_payload = strava_detail(9000000001, "Footing matinal", pts, run_laps)["laps"]
    (strava_api / "laps_9000000001.json").write_text(json.dumps(laps_payload, indent=1), encoding="utf-8")
    (strava_api / "token_refresh.json").write_text(json.dumps({
        "token_type": "Bearer", "access_token": "fake-access-token-2", "expires_at": 4102444800, "expires_in": 21600,
        "refresh_token": "fake-refresh-token-2"}, indent=1), encoding="utf-8")

    easy_fit = fit(pts, run_laps)
    garmin_list = [
        {"activityId": 30000000001, "activityName": "Footing", "startTimeLocal": "2026-10-13 07:05:20",
         "startTimeGMT": "2026-10-13 05:05:20", "activityType": {"typeId": 1, "typeKey": "running"},
         "distance": round(pts[-1]["dist"], 1), "duration": 3650.0, "movingDuration": 3620.0, "elapsedDuration": 3650.0,
         "averageHR": 144.0, "maxHR": 153.0, "elevationGain": 31.0},
        {"activityId": 30000000002, "activityName": "Seuil", "startTimeLocal": "2026-10-15 07:00:00",
         "startTimeGMT": "2026-10-15 05:00:00", "activityType": {"typeId": 1, "typeKey": "running"},
         "distance": 8500.0, "duration": 2700.0, "movingDuration": 2680.0, "elapsedDuration": 2700.0,
         "averageHR": 158.0, "maxHR": 172.0, "elevationGain": 38.0},
    ]
    (garmin_api / "activities.json").write_text(json.dumps(garmin_list, indent=1), encoding="utf-8")
    for activity_id, data in ((30000000001, easy_fit), (30000000002, tempo_fit)):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            info = zipfile.ZipInfo(f"{activity_id}_ACTIVITY.fit", date_time=(2026, 10, 15, 0, 0, 0))
            zf.writestr(info, data)
        (garmin_api / f"original_{activity_id}.zip").write_bytes(buf.getvalue())

    (ROOT / "profile.json").write_text(json.dumps({
        "sex": "female", "hr_max": 187, "hr_rest": 48, "reference_race": {"distance_km": 10, "time": "47:30"},
        "goal": {"name": "Semi-marathon de printemps", "distance_km": 21.1, "date": "2027-03-14", "target_time": "1:44:00"},
        "weekly_km": 38, "runs_per_week": 4, "long_run_day": "sun"}, indent=1, ensure_ascii=False), encoding="utf-8")
    (ROOT / "plan.json").write_text(json.dumps({
        "name": "Semi de printemps", "start": "2026-08-31",
        "weeks": {"2026-W41": {"phase": "Développement", "km": 38, "sessions": [
            {"day": "tue", "type": "quality", "priority": 1, "desc": "6 × 800 m VMA, récupération 400 m"},
            {"day": "thu", "type": "easy", "priority": 3, "desc": "Footing 8 km", "km": 8},
            {"day": "sat", "type": "quality", "priority": 2, "desc": "Seuil 5 km continu"},
            {"day": "sun", "type": "long", "priority": 1, "desc": "Sortie longue 16 km en Z2", "km": 16}]},
            "2026-W42": {"phase": "Développement", "km": 40, "sessions": [
                {"day": "tue", "type": "quality", "priority": 1, "desc": "Seuil 3 × 10 min", "spec": {
                    "name": "Seuil 3x10'", "steps": [
                        {"kind": "warmup", "dur": "15:00"},
                        {"kind": "repeat", "times": 3, "steps": [
                            {"kind": "interval", "dur": "10:00", "target": {"pace": ["4:45", "4:55"]}},
                            {"kind": "recovery", "dur": "2:00"}]},
                        {"kind": "cooldown", "dur": "10:00"}]}},
                {"day": "thu", "type": "easy", "priority": 3, "desc": "Footing 45 min", "km": 7.5},
                {"day": "sun", "type": "long", "priority": 1, "desc": "Sortie longue 17 km", "km": 17}]}}},
        indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"fixtures écrites dans {ROOT}")


if __name__ == "__main__":
    argparse.ArgumentParser(description="Régénère les données synthétiques de tests/fixtures (aucune dépendance).").parse_args()
    main()
