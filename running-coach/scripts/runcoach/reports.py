from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, timedelta
from statistics import mean
from typing import Any

from . import coaching, metrics, store
from .profile import ZONE_NAMES, Profile
from .util import data_dir, day_abbr, parse_day, fmt_hms, fmt_minutes, fmt_pace, monday_of, today, week_label, week_of, write_text

SPORT_LABELS = {"run": "run", "ride": "ride", "swim": "swim", "walk": "walk", "hike": "hike", "strength": "strength", "other": "other"}
DETAIL_LABELS = {0: "summary only", 1: "laps", 2: "full recording"}


def _warn_profile(profile: Profile) -> list[str]:
    if not profile.exists:
        return [f"> ⚠ No profile: zones and load computed with a provisional max HR of {profile.hr_max:.0f} bpm "
                "(`coach profile set --hr-max …`).", ""]
    if profile.provisional:
        return [f"> ⚠ No max HR in the profile: {profile.hr_max:.0f} bpm ({profile.hr_max_source}).", ""]
    return []


def _i(value: Any) -> str:
    return "—" if value is None else f"{value:.0f}"


def _bar(minutes: float, total: float) -> str:
    return "█" * max(1, round(20 * minutes / total)) if total and minutes else ""


def _zone_lines(row: dict[str, Any]) -> list[str]:
    zones = [row.get(f"z{i}") or 0 for i in range(1, 6)]
    total = sum(zones)
    if not total:
        return ["_No heart rate._"]
    return [f"- {ZONE_NAMES[i]}: {fmt_minutes(z)} ({100 * z / total:.0f}%) {_bar(z, total)}" for i, z in enumerate(zones) if z >= 0.5]


def _observations(act: dict[str, Any], row: dict[str, Any], splits: list[dict[str, Any]], profile: Profile,
                  laps_info: dict[str, Any] | None) -> list[str]:
    obs = []
    zones = [row.get(f"z{i}") or 0 for i in range(1, 6)]
    total = sum(zones)
    hard_share = (zones[2] + zones[3] + zones[4]) / total if total else 0
    z2_top = profile.zone_range(2)[1]
    if row.get("detail") == 0:
        obs.append("ℹ Summary only: no splits. `coach sync --details 50` or importing the FIT file gives the km-by-km analysis.")
    if row.get("trimp_estimated"):
        obs.append("ℹ No heart rate: load estimated from duration.")
    if row["kind"] == "long" and row["structure"] == "Long run" and hard_share > 0.2:
        obs.append(f"⚠ Long run too hard: {100 * hard_share:.0f}% of the time above Z2 (HR cap {z2_top}).")
    if row["kind"] == "easy" and row["structure"] in ("Easy run", "Recovery run") and hard_share > 0.25:
        obs.append(f"⚠ Easy run too fast: {100 * hard_share:.0f}% of the time above Z2. An easy run stays below {z2_top} bpm.")
    full = [s for s in splits if s["distance_m"] >= 500 and s.get("hr")]
    if row["kind"] in ("easy", "long") and len(full) >= 6:
        tail = full[-3:]
        if mean(s["hr"] for s in tail) > z2_top and mean(s["hr"] for s in full[:-3]) <= z2_top:
            obs.append(f"⚠ End of run above Z2 (average HR over the last 3 km {mean(s['hr'] for s in tail):.0f}): "
                       "the overall average hides the drift, read the last km.")
    dec = row.get("decoupling")
    if dec is not None:
        if dec < 5:
            obs.append(f"✓ Aerobic decoupling {dec:g}%: solid endurance at this pace.")
        elif dec <= 10:
            obs.append(f"• Aerobic decoupling {dec:g}%: fair, keep an eye on it in long runs.")
        else:
            obs.append(f"⚠ Aerobic decoupling {dec:g}%: pace too fast for the duration, heat, or aerobic base still to build.")
    if laps_info:
        reps = [lp for lp in act.get("laps") or [] if (lp.get("distance_m") or 0) > 50 and (lp.get("moving_s") or 0) > 20]
        speeds = [lp["distance_m"] / lp["moving_s"] for lp in reps]
        if speeds:
            med = sorted(speeds)[len(speeds) // 2]
            work = [lp["moving_s"] / (lp["distance_m"] / 1000) for lp, sp in zip(reps, speeds) if sp > med * 1.08]
            if len(work) >= 3:
                spread = max(work) - min(work)
                verdict = "very even" if spread < 6 else "even" if spread < 12 else "uneven"
                obs.append(f"{'✓' if spread < 12 else '⚠'} Reps {verdict}: {spread:.0f} s/km between the fastest and the slowest "
                           f"({fmt_pace(min(work))} → {fmt_pace(max(work))}).")
                if work[-1] > work[0] + 8:
                    obs.append("⚠ The last rep is clearly slower than the first: started too fast or set too long.")
            warm = reps[0] if reps else None
            if warm and warm["moving_s"] < 600 and speeds[0] <= med * 1.08:
                obs.append("⚠ Warm-up shorter than 10 min before the first rep.")
    if act.get("max_hr") and act["max_hr"] > profile.hr_max + 1:
        obs.append(f"⚠ Session max HR ({act['max_hr']:.0f}) above the profile max HR ({profile.hr_max:.0f}): "
                   "unless it is a sensor artefact, update the profile (`coach profile set --hr-max …`).")
    return obs


def run_report(activity_id: str) -> tuple[str, str]:
    metrics.ensure_fresh()
    index = store.load_index()
    profile = metrics.current_profile(index)
    act = store.get(activity_id)
    rows = metrics.read_csv("activities.csv")
    row = next((r for r in rows if r["id"] == activity_id), None) or metrics.analyze(act, profile)
    splits = metrics.km_splits(act) if act["sport"] == "run" else []
    laps_info = metrics.lap_structure(act.get("laps") or [])
    _, quality = (metrics.classify(act, splits, profile, row["moving_min"] or 0)[1:] if act["sport"] == "run" else ("", []))
    start = datetime.fromisoformat(act["start_local"])
    title = row["structure"] or SPORT_LABELS.get(act["sport"], act["sport"])
    lines = [f"# {row['date']} — {title} ({row['distance_km']:g} km)",
             f"> `{activity_id}` · {day_abbr(start.date())} {start.strftime('%H:%M')} · {act.get('name') or 'untitled'} · "
             f"source {act['source']} ({DETAIL_LABELS[row['detail']]})", ""]
    lines += _warn_profile(profile)
    lines += ["## Summary", "",
              f"- Distance: {row['distance_km']:g} km in {fmt_hms(act.get('moving_s'))} moving time"
              + (f" ({fmt_hms(act['elapsed_s'])} total)" if act.get("elapsed_s") and act.get("moving_s") and act["elapsed_s"] - act["moving_s"] > 60 else ""),
              f"- Average pace: {fmt_pace(row['pace_s'])}/km · average HR {_i(row['avg_hr'])} · max HR {_i(row['max_hr'])}"
              + (f" · elevation gain {row['elev_gain_m']:.0f} m" if row.get("elev_gain_m") else ""),
              f"- Load (TRIMP): {row['trimp']:g}" + (" (estimated without HR)" if row.get("trimp_estimated") else ""),
              ]
    if act["sport"] == "run":
        lines.append(f"- Detected structure: **{row['structure']}**" + (f" · {int(row['quality_km'])} quality km ★" if row.get("quality_km") else ""))
        if row.get("ef"):
            lines.append(f"- Efficiency (EF): {row['ef']:.3f} m/min per beat" + (f" · decoupling {row['decoupling']:g}%" if row.get("decoupling") is not None else ""))
    plan = coaching.load_plan()
    week = coaching.plan_week(plan, start.date())
    if week:
        planned = [s for s in week.get("sessions") or [] if parse_day(s["day"]) == start.weekday()]
        lines += ["", "## Plan", ""]
        lines += [f"- Planned that day: {s.get('desc') or coaching.TYPE_LABELS[s.get('type', 'easy')]} (priority {s.get('priority', 2)})" for s in planned] or ["- Nothing planned that day."]
    if splits:
        lines += ["", "## Km splits", "", "| Km | Pace | HR | HR zone | Pace zone | |", "|---|---|---|---|---|---|"]
        for s in splits:
            km = f"{s['km']}" if s["distance_m"] >= 999 else f"{s['km']} ({s['distance_m'] / 1000:.2f})"
            z = profile.zone_of(s.get("hr"))
            lines.append(f"| {km} | {fmt_pace(s['pace_s'])} | {round(s['hr']) if s.get('hr') else '—'} | {ZONE_NAMES[z - 1] if z else '—'} | "
                         f"{profile.pace_zone_of(s['pace_s'])} | {'★' if s['km'] in quality else ''} |")
    laps = act.get("laps") or []
    if laps and (laps_info or not splits):
        lines += ["", "## Laps", "", "| Lap | Distance | Time | Pace | Avg HR |", "|---|---|---|---|---|"]
        for i, lp in enumerate(laps, 1):
            dist, mov = lp.get("distance_m") or 0, lp.get("moving_s") or 0
            pace = mov / (dist / 1000) if dist > 0 and mov else None
            lines.append(f"| {i} | {dist:.0f} m | {fmt_hms(mov)} | {fmt_pace(pace)} | {round(lp['avg_hr']) if lp.get('avg_hr') else '—'} |")
        if laps_info:
            lines.append(f"\nReps: {laps_info['reps']} × {laps_info['work_km'] / laps_info['reps'] * 1000:.0f} m on average, "
                         f"pace {fmt_pace(laps_info['pace_s'])}/km" + (f", HR {laps_info['hr']:.0f}" if laps_info.get("hr") else ""))
    lines += ["", "## Time in HR zones", ""] + _zone_lines(row)
    if act["sport"] == "run":
        family = row["structure"].split(" ")[0]
        similar = [r for r in rows if r["sport"] == "run" and r["id"] != activity_id and r["date"] < row["date"]
                   and (r.get("structure") or "").split(" ")[0] == family][-3:]
        lines += ["", "## Comparable sessions", ""]
        if similar:
            lines += ["| Date | Km | Pace | Avg HR | EF | TRIMP |", "|---|---|---|---|---|---|"]
            for r in reversed(similar):
                lines.append(f"| {r['date']} | {r['distance_km']:g} | {fmt_pace(r['pace_s'])} | {_i(r['avg_hr'])} | "
                             f"{r['ef'] if r.get('ef') else '—'} | {r['trimp']:g} |")
        else:
            lines.append("_No earlier session of the same type._")
    obs = _observations(act, row, splits, profile, laps_info)
    lines += ["", "## Observations", ""] + ([f"- {o}" for o in obs] or ["_Nothing to report._"])
    daily = metrics.read_csv("daily.csv")
    before = metrics.load_on(daily, start.date() - timedelta(days=1))
    after = metrics.load_on(daily, start.date() + timedelta(days=1))
    if before and after:
        lines += ["", "## Load", "", f"- CTL {before['ctl']:g} → {after['ctl']:g} · ATL {before['atl']:g} → {after['atl']:g} · "
                  f"TSB {before['tsb']:+g} → {after['tsb']:+g}"]
    text = "\n".join(lines) + "\n"
    slug = unicodedata.normalize("NFKD", row["structure"] or act["sport"]).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", slug.lower()).strip("-")
    path = data_dir() / "reports" / "runs" / f"{row['date']}_{slug}_{activity_id}.md"
    for old in path.parent.glob(f"*_{activity_id}.md"):
        if old != path:
            old.unlink()
    write_text(path, text)
    return text, str(path)


def _week_rows(rows: list[dict[str, Any]], year: int, week: int) -> list[dict[str, Any]]:
    return [r for r in rows if week_of(date.fromisoformat(r["date"])) == (year, week)]


def week_report(year: int, week: int) -> tuple[str, str]:
    metrics.ensure_fresh()
    profile = metrics.current_profile()
    rows = metrics.read_csv("activities.csv")
    daily = metrics.read_csv("daily.csv")
    weekly = metrics.read_csv("weekly.csv")
    monday = monday_of(year, week)
    sunday = monday + timedelta(days=6)
    label = week_label(year, week)
    acts = _week_rows(rows, year, week)
    runs = [r for r in acts if r["sport"] == "run"]
    others = [r for r in acts if r["sport"] != "run"]
    lines = [f"# Week {label} ({monday.strftime('%d %b')} → {sunday.strftime('%d %b %Y')})", ""]
    lines += _warn_profile(profile)
    if not acts:
        lines.append("_No activity this week._")
        return "\n".join(lines) + "\n", ""
    km = sum(r["distance_km"] or 0 for r in runs)
    minutes = sum(r["moving_min"] or 0 for r in runs)
    load = sum(r["trimp"] or 0 for r in acts)
    longest = max((r["distance_km"] or 0 for r in runs), default=0)
    quality = sum(1 for r in runs if r.get("kind") == "quality")
    previous = [w for w in weekly if w["week"] < label][-4:]
    avg_prev = mean(w["run_km"] or 0 for w in previous) if previous else None
    target = profile.get("weekly_km")
    lines += ["## Volume", "",
              f"- Running: {len(runs)} run(s), {km:.1f} km, {fmt_minutes(minutes)}, longest run {longest:g} km, {quality} quality session(s)",
              f"- Total load (TRIMP, all sports): {load:.0f}"]
    if others:
        by_sport: dict[str, float] = {}
        for r in others:
            by_sport[r["sport"]] = by_sport.get(r["sport"], 0) + (r["moving_min"] or 0)
        lines.append("- Other sports: " + ", ".join(f"{SPORT_LABELS.get(s, s)} {fmt_minutes(m)}" for s, m in by_sport.items()))
    if target:
        lines.append(f"- Target volume: {target:g} km → {100 * km / target:.0f}%")
    if avg_prev:
        lines.append(f"- Average of the previous {len(previous)} weeks: {avg_prev:.1f} km ({100 * (km - avg_prev) / avg_prev:+.0f}%)")
    lines += ["", "## Sessions", "", "| Day | Sport | Type | Km | Time | Pace | Avg HR | TRIMP |", "|---|---|---|---|---|---|---|---|"]
    for r in sorted(acts, key=lambda x: x["start_local"]):
        d = date.fromisoformat(r["date"])
        lines.append(f"| {day_abbr(d)} {d.strftime('%d %b')} | {SPORT_LABELS.get(r['sport'], r['sport'])} | {r.get('structure') or '—'} | "
                     f"{r['distance_km']:g} | {fmt_minutes(r['moving_min'])} | {fmt_pace(r['pace_s']) if r['sport'] == 'run' else '—'} | "
                     f"{_i(r['avg_hr'])} | {r['trimp']:g} |")
    zones = [sum(r.get(f"z{i}") or 0 for r in runs) for i in range(1, 6)]
    total = sum(zones)
    if total:
        easy = 100 * (zones[0] + zones[1]) / total
        lines += ["", "## Intensity (running)", "",
                  f"- Z1-Z2: {easy:.0f}% · Z3: {100 * zones[2] / total:.0f}% · Z4-Z5: {100 * (zones[3] + zones[4]) / total:.0f}%",
                  "- Benchmark: about 80% of the time in Z1-Z2 to progress without wearing out."]
    plan = coaching.load_plan()
    pw = coaching.plan_week(plan, monday)
    if pw:
        ref = today()
        rows_plan = coaching.adherence(pw, runs, monday, ref)
        lines += ["", f"## Plan — {pw.get('phase', '')}".rstrip(" —"), ""] + coaching.render_plan_rows(rows_plan)
    start_load = metrics.load_on(daily, monday - timedelta(days=1))
    end_load = metrics.load_on(daily, min(sunday, today()))
    if end_load:
        a = start_load or {"ctl": 0, "atl": 0, "tsb": 0}
        lines += ["", "## Load", "", f"- CTL {a['ctl']:g} → {end_load['ctl']:g} · ATL {a['atl']:g} → {end_load['atl']:g} · "
                  f"TSB {a['tsb']:+g} → {end_load['tsb']:+g} ({coaching.tsb_label(end_load['tsb'])})"]
    obs = []
    if avg_prev and km > 1.25 * avg_prev and km - avg_prev > 5:
        obs.append(f"⚠ Volume up {100 * (km - avg_prev) / avg_prev:.0f}% on the recent average: increase by 10 to 15% per week at most.")
    if total and (zones[0] + zones[1]) / total < 0.7:
        obs.append("⚠ Less than 70% of the time in Z1-Z2: too much intensity to absorb the volume.")
    if quality == 0 and len(runs) >= 3:
        obs.append("• No quality session: fine in a recovery week, otherwise plan one.")
    if quality >= 3:
        obs.append("⚠ Three or more quality sessions: overload risk.")
    if runs and longest < 0.2 * km and len(runs) >= 3:
        obs.append("• No real long run this week.")
    if len(runs) < min(profile.runs_per_week, 3):
        obs.append(f"• {len(runs)} run(s) out of {profile.runs_per_week} planned.")
    lines += ["", "## Observations", ""] + ([f"- {o}" for o in obs] or ["_Nothing to report._"])
    text = "\n".join(lines) + "\n"
    path = data_dir() / "reports" / "weekly" / f"{label}.md"
    write_text(path, text)
    return text, str(path)


def _spark(values: list[float]) -> str:
    blocks = "▁▂▃▄▅▆▇█"
    if not values:
        return ""
    lo, hi = min(values), max(values)
    span = hi - lo or 1
    return "".join(blocks[int((v - lo) / span * (len(blocks) - 1))] for v in values)


def status_report() -> str:
    metrics.ensure_fresh()
    index = store.load_index()
    profile = metrics.current_profile(index)
    rows = metrics.activity_rows()
    daily = metrics.read_csv("daily.csv")
    ref = today()
    lines = [f"# Status — {ref.isoformat()} ({day_abbr(ref)})", ""]
    lines += _warn_profile(profile)
    if not rows:
        lines.append("_No activity: `coach sync` (Strava or Garmin) or `coach import <files>`._")
        return "\n".join(lines) + "\n"
    cur = metrics.load_on(daily, ref)
    if cur:
        lines += ["## Form", "",
                  f"- CTL (fitness, 42 d): **{cur['ctl']:g}** · ATL (fatigue, 7 d): **{cur['atl']:g}** · "
                  f"TSB: **{cur['tsb']:+g}** → {coaching.tsb_label(cur['tsb'])}"]
        last14 = [x for x in daily if x["date"] <= ref.isoformat()][-14:]
        if len(last14) >= 7:
            lines.append(f"- TSB over 14 days: {_spark([x['tsb'] for x in last14])} ({last14[0]['tsb']:+g} → {last14[-1]['tsb']:+g})")
    y, w = week_of(ref)
    wk = [r for r in _week_rows(rows, y, w) if r["sport"] == "run"]
    km = sum(r["distance_km"] or 0 for r in wk)
    target = profile.get("weekly_km")
    lines += ["", "## Current week", "",
              f"- {len(wk)}/{profile.runs_per_week} runs, {km:.1f} km" + (f" of {target:g} planned" if target else "")]
    ph, days = coaching.phase(profile, ref)
    ph = (coaching.plan_week(coaching.load_plan(), ref) or {}).get("phase") or ph
    if profile.goal:
        lines.append(f"- Goal: {profile.goal.get('name', 'race')} on {profile.goal.get('date')} "
                     + (f"({days} days to go, {ph.lower()} phase)" if days is not None and days >= 0 else f"({ph.lower()})"))
    lines += ["", "## Latest activities", "", "| Date | Sport | Type | Km | Pace | Avg HR | TRIMP |", "|---|---|---|---|---|---|---|"]
    for r in rows[-6:][::-1]:
        lines.append(f"| {r['date']} | {SPORT_LABELS.get(r['sport'], r['sport'])} | {r.get('structure') or '—'} | {r['distance_km']:g} | "
                     f"{fmt_pace(r['pace_s']) if r['sport'] == 'run' else '—'} | {_i(r['avg_hr'])} | {r['trimp']:g} |")
    last = date.fromisoformat(rows[-1]["date"])
    state = store.load_state()
    lines += ["", "## Data", "", f"- Latest activity: {last.isoformat()} ({(ref - last).days} days ago), {len(rows)} activities stored"]
    for src in ("strava", "garmin"):
        if state.get(src, {}).get("last_sync"):
            pending = state[src].get("pending_details", 0)
            lines.append(f"- {src} sync: {state[src]['last_sync'][:16].replace('T', ' ')} UTC"
                         + (f", {pending} run(s) waiting for details" if pending else ""))
    if (ref - last).days > 3:
        lines.append("- ⚠ Nothing for more than 3 days: run `coach sync` before concluding it is a break.")
    return "\n".join(lines) + "\n"


def recap_report(weeks: int = 12) -> str:
    metrics.ensure_fresh()
    profile = metrics.current_profile()
    rows = metrics.activity_rows()
    daily = metrics.read_csv("daily.csv")
    weekly = metrics.read_csv("weekly.csv")
    ref = today()
    plan = coaching.load_plan()
    start = date.fromisoformat(plan["start"]) if plan and plan.get("start") else ref - timedelta(weeks=weeks)
    start_label = week_label(*week_of(start))
    lines = [f"# Recap since {start.isoformat()}", ""]
    lines += _warn_profile(profile)
    sel = [w for w in weekly if start_label <= w["week"] <= week_label(*week_of(ref))]
    if not sel:
        lines.append("_No week with data in this period._")
        return "\n".join(lines) + "\n"
    lines += ["| Week | Runs | Km | Longest | Quality | % Z1-Z2 | TRIMP | End CTL |", "|---|---|---|---|---|---|---|---|"]
    for w in sel:
        y, n = int(w["week"][:4]), int(w["week"][-2:])
        end = metrics.load_on(daily, min(monday_of(y, n) + timedelta(days=6), ref))
        easy = "—" if w["easy_pct"] is None else f"{w['easy_pct']:.0f}"
        lines.append(f"| {w['week']} | {w['runs']:.0f} | {w['run_km']:g} | {w['long_km']:g} | {w['quality']:.0f} | "
                     f"{easy} | {w['trimp']:.0f} | {end['ctl'] if end else '—'} |")
    first = metrics.load_on(daily, start) or next((x for x in daily if x["date"] >= start.isoformat()), None)
    last = metrics.load_on(daily, ref)
    runs = [r for r in rows if r["sport"] == "run" and r["date"] >= start.isoformat()]
    lines += ["", "## Trends", ""]
    if first and last:
        lines.append(f"- CTL {first['ctl']:g} → {last['ctl']:g} ({last['ctl'] - first['ctl']:+.1f})")
    lines.append(f"- {len(runs)} runs, {sum(r['distance_km'] or 0 for r in runs):.0f} km, "
                 f"{sum(r['distance_km'] or 0 for r in runs) / max(len(sel), 1):.1f} km per week on average")
    if runs:
        best = max(runs, key=lambda r: r["distance_km"] or 0)
        lines.append(f"- Longest run: {best['distance_km']:g} km on {best['date']}")
    recent_cut = (ref - timedelta(days=28)).isoformat()
    older_cut = (ref - timedelta(days=56)).isoformat()
    ef_recent = [r["ef"] for r in runs if r.get("ef") and r["date"] >= recent_cut]
    ef_older = [r["ef"] for r in rows if r["sport"] == "run" and r.get("ef") and older_cut <= r["date"] < recent_cut]
    if ef_recent and ef_older:
        delta = 100 * (mean(ef_recent) - mean(ef_older)) / mean(ef_older)
        lines.append(f"- Easy-run efficiency (EF): {mean(ef_older):.3f} → {mean(ef_recent):.3f} ({delta:+.1f}%) "
                     + ("— aerobic progress" if delta > 1 else "— stable" if delta > -1 else "— down: fatigue, heat or pace"))
    ph, days = coaching.phase(profile, ref)
    ph = (coaching.plan_week(plan, ref) or {}).get("phase") or ph
    if profile.goal:
        lines += ["", "## Goal", "", f"- {profile.goal.get('name', 'race')}: {profile.goal.get('distance_km', '?')} km on "
                  f"{profile.goal.get('date', '?')}" + (f", {days} days to go" if days is not None and days >= 0 else "") + f", {ph.lower()} phase"]
        pace = profile.race_pace()
        if pace and profile.goal_km:
            lines.append(f"- Goal pace {fmt_pace(pace)}/km, i.e. {fmt_hms(pace * profile.goal_km)}")
    return "\n".join(lines) + "\n"


def list_report(days: int, sport: str | None) -> str:
    metrics.ensure_fresh()
    rows = metrics.activity_rows()
    cut = (today() - timedelta(days=days)).isoformat()
    sel = [r for r in rows if r["date"] >= cut and (sport is None or r["sport"] == sport)]
    if not sel:
        return f"_No activity in the last {days} days._\n"
    lines = ["| Id | Date | Sport | Type | Km | Time | Pace | Avg HR | Detail |", "|---|---|---|---|---|---|---|---|---|"]
    for r in sel[::-1]:
        lines.append(f"| {r['id']} | {r['start_local'][:16].replace('T', ' ')} | {SPORT_LABELS.get(r['sport'], r['sport'])} | "
                     f"{r.get('structure') or '—'} | {r['distance_km']:g} | {fmt_minutes(r['moving_min'])} | "
                     f"{fmt_pace(r['pace_s']) if r['sport'] == 'run' else '—'} | {_i(r['avg_hr'])} | {DETAIL_LABELS[int(r['detail'] or 0)]} |")
    return "\n".join(lines) + "\n"


def next_report(rec: dict[str, Any], profile: Profile) -> str:
    from .workout import describe

    d = rec["date"]
    lines = [f"# Next session — {day_abbr(d)} {d.isoformat()}", ""]
    lines += _warn_profile(profile)
    if rec["ran_today"]:
        lines += ["_Today's session is already recorded: proposal for tomorrow._", ""]
    ctx = [f"{rec['phase'].lower()} phase" + (f" ({rec['days_to_goal']} days to go)" if rec["days_to_goal"] and rec["days_to_goal"] > 0 else ""),
           f"week: {rec['runs_done']}/{rec['rpw']} runs, {rec['done_km']:.1f}/{rec['volume']:g} km, "
           f"quality {rec['quality_done']}/{rec['quality_target']}, long run {'done' if rec['long_done'] else 'to do'}",
           f"TSB {rec['tsb']:+g} ({coaching.tsb_label(rec['tsb'])})" if rec["tsb"] is not None else "TSB unknown"]
    if rec["last"]:
        last = rec["last"]
        ctx.append(f"last run: {last['date']}, {last.get('structure') or 'run'} {last['distance_km']:g} km")
    lines += ["## Context", ""] + [f"- {c}" for c in ctx]
    if rec.get("plan"):
        lines += ["", "## This week's plan", ""] + coaching.render_plan_rows(rec["plan"])
    p = rec["proposal"]
    lines += ["", f"## Proposal: {p['title']}", ""] + [f"- {x}" for x in p["lines"] if x]
    lines += ["", "## Why", ""] + [f"- {r}" for r in rec["reasons"]]
    if p.get("spec"):
        lines += ["", "## Watch format", "", describe(p["spec"]), "",
                  "`coach next --spec` prints this format as JSON for `coach workout push -`."]
    return "\n".join(lines) + "\n"
