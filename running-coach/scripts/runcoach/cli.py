from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from . import VERSION, coaching, metrics, reports, store
from .importers import Skip, iter_inputs, parse_bytes
from .profile import load_profile, profile_path, save_profile
from .util import CoachError, config_dir, data_dir, parse_date, parse_duration, parse_week, set_today, today, week_of, write_text


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def cmd_doctor(_: argparse.Namespace) -> int:
    from . import garmin, strava

    lines = ["# running-coach diagnostics", "", f"- Version {VERSION}, Python {sys.version.split()[0]} ({sys.executable})"]
    try:
        import fitdecode  # noqa: F401
        lines.append("- FIT reading: ok")
    except ImportError:
        lines.append("- FIT reading: ✗ fitdecode missing (run install.sh)")
    try:
        from importlib.metadata import version
        lines.append(f"- Garmin: garminconnect library {version('garminconnect')}")
    except Exception:
        lines.append("- Garmin: ✗ garminconnect missing (run install.sh); Strava and file import still work")
    index = store.load_index()
    profile = load_profile(store.observed_hr_max(index))
    plan_state = "none (optional)"
    if coaching.plan_path().exists():
        try:
            coaching.load_plan()
            plan_state = "ok"
        except CoachError as e:
            plan_state = f"✗ {e}"
    lines += [f"- Configuration: {config_dir()}",
              f"  - profile: {'ok' if profile.exists else 'none'}" + (" (max HR missing)" if profile.exists and profile.provisional else ""),
              f"  - plan: {plan_state}",
              f"- Data: {data_dir()} — {len(index)} activities, {sum(1 for e in index.values() if e['sport'] == 'run')} of them runs",
              f"- {strava.status()}", f"- {garmin.status()}"]
    steps = []
    if not profile.exists or profile.provisional:
        steps.append("create the profile with the user: `coach profile set --hr-max … --hr-rest … --goal-…` (references/setup.md)")
    if not strava.is_configured() and not garmin.is_configured():
        steps.append("connect a source (references/sources.md) or import files: `coach import <folder|zip|files>`")
    elif not index:
        steps.append("`coach sync`")
    lines += ["", "Next steps: " + ("; ".join(steps) if steps else "none, everything is ready.")]
    print("\n".join(lines))
    return 0


def _profile_update(args: argparse.Namespace) -> dict[str, Any]:
    current = load_profile().data
    data = dict(current)
    if args.hr_max is not None:
        if args.hr_max == "auto":
            observed = store.observed_hr_max(store.load_index())
            if not observed:
                raise CoachError("no max HR in the activities: import or sync first, or give the value")
            data["hr_max"] = int(observed)
            log(f"Highest max HR in the data: {observed:.0f} bpm")
        else:
            data["hr_max"] = int(args.hr_max)
    simple = {"hr_rest": args.hr_rest, "sex": args.sex, "birth_year": args.birth_year, "weekly_km": args.weekly_km,
              "runs_per_week": args.runs_per_week, "long_run_day": args.long_run_day, "long_run_min_minutes": args.long_run_min,
              "threshold_pace": args.threshold_pace}
    data.update({k: v for k, v in simple.items() if v is not None})
    if args.hr_zones:
        data["hr_zones"] = [int(x) for x in args.hr_zones.split(",")]
    if args.ref_race:
        km, time_ = args.ref_race
        parse_duration(time_)
        data["reference_race"] = {"distance_km": float(km), "time": time_}
    if args.sources:
        data["sources"] = [s.strip() for s in args.sources.split(",") if s.strip()]
    if args.clear_goal:
        data.pop("goal", None)
    goal = dict(data.get("goal") or {})
    for key, value in (("name", args.goal_name), ("distance_km", args.goal_distance), ("date", args.goal_date), ("target_time", args.goal_time)):
        if value is not None:
            goal[key] = value
    if goal:
        data["goal"] = goal
    if args.note:
        data["notes"] = list(data.get("notes") or []) + [args.note]
    for key in args.unset or []:
        data.pop(key, None)
    return data


def cmd_profile(args: argparse.Namespace) -> int:
    if args.action == "set":
        profile = save_profile(_profile_update(args))
        log(f"✓ profile saved: {profile_path()}")
        if store.load_index():
            metrics.refresh()
    print(metrics.current_profile().describe())
    return 0


def cmd_auth(args: argparse.Namespace) -> int:
    from . import garmin, strava

    if args.service == "garmin":
        action = args.action or "status"
        if action == "login":
            print(garmin.login())
        elif action == "logout":
            print(garmin.logout())
        else:
            print(garmin.status(check=True))
        return 0
    if args.client_secret and not args.client_id:
        raise CoachError("--client-secret requires --client-id")
    if args.client_id and not args.client_secret:
        if not sys.stdin.isatty():
            raise CoachError("Client Secret needed: run `coach auth strava --client-id …` in a terminal, "
                             "or export STRAVA_CLIENT_SECRET")
        import getpass
        try:
            args.client_secret = getpass.getpass("Strava Client Secret (hidden input): ").strip()
        except EOFError as e:
            raise CoachError("cannot prompt here: run the command in a terminal") from e
        if not args.client_secret:
            raise CoachError("empty Client Secret")
    if args.client_id:
        saved = strava.load_creds()
        saved.update(client_id=args.client_id, client_secret=args.client_secret)
        strava.save_creds({k: v for k, v in saved.items() if k in ("client_id", "client_secret", "access_token", "refresh_token", "expires_at", "scope", "athlete_id")})
        log(f"✓ Strava application saved in {strava.creds_path()} (mode 600)")
    if args.code:
        creds = strava.exchange_code(args.code)
        print(f"✓ Strava authorized (scope {creds.get('scope', '?')}). Run `coach sync`.")
        return 0
    creds = strava.load_creds()
    if args.status or (creds.get("refresh_token") and not (args.client_id or args.reauthorize)):
        print(strava.status())
        return 0
    if not creds.get("client_id"):
        raise CoachError("create an application at https://www.strava.com/settings/api (callback domain: localhost), "
                         "then run `coach auth strava --client-id …` in a terminal (the secret is asked without echo)")
    print("1. Open this address, log in and authorize:\n")
    print(strava.authorize_url(str(creds["client_id"])))
    print("\n2. The browser lands on an http://localhost page that does not load: this is expected.")
    print("3. Copy the full address of that page, then: coach auth strava --code '<address>'")
    return 0


def _print_sync(name: str, result: dict[str, Any]) -> None:
    c = result["counts"]
    parts = [f"{result['listed']} listed", f"{c['new']} new"]
    if c["replaced"]:
        parts.append(f"{c['replaced']} replacing a less detailed version")
    if c["duplicate"]:
        parts.append(f"{c['duplicate']} already present from another source")
    parts.append(f"details downloaded for {result['details']} run(s)")
    print(f"✓ {name}: " + ", ".join(parts))
    if result["rate_limited"]:
        print(f"  ! {result['rate_limited']}; {result['pending']} run(s) waiting for their details.")
    elif result["pending"]:
        print(f"  {result['pending']} older run(s) waiting for their details: run `coach sync` again (--details N to take more).")


def cmd_sync(args: argparse.Namespace) -> int:
    from . import garmin, strava

    modules = {"strava": strava, "garmin": garmin}
    profile = load_profile()
    if args.source in ("auto", "all"):
        order = [s for s in profile.sources if modules[s].is_configured()]
        if not order:
            print("No source connected.\n- Strava: `coach auth strava` (references/sources.md)\n"
                  "- Garmin: `coach auth garmin login`, in a terminal\n- No account: `coach import <GPX/TCX/FIT files or zip export>`")
            return 2
    else:
        if not modules[args.source].is_configured():
            raise CoachError(f"{args.source} is not connected: see `coach auth {args.source}`")
        order = [args.source]
    index = store.load_index()
    changed: set[str] = set()
    ok = False
    for i, name in enumerate(order):
        try:
            result = modules[name].sync(args.days, args.details, index, log)
        except strava.SourceError as e:
            store.save_index(index)
            nxt = order[i + 1] if i + 1 < len(order) else None
            print(f"✗ {name}: {e}" + (f" → falling back to {nxt}" if nxt and args.source == "auto" else ""))
            continue
        store.save_index(index)
        changed |= result["changed"]
        _print_sync(name.capitalize(), result)
        ok = True
        if args.source != "all":
            break
    if changed or ok:
        info = metrics.refresh(changed)
        print(f"✓ metrics up to date: {info['activities']} activities ({info['analyzed']} recomputed)")
    return 0 if ok else 1


def cmd_import(args: argparse.Namespace) -> int:
    index = store.load_index()
    counts: Counter = Counter()
    skipped: Counter = Counter()
    errors: list[str] = []
    changed: set[str] = set()
    files = 0
    for label, data, ext in iter_inputs(args.paths):
        files += 1
        if files % 200 == 0:
            log(f"  … {files} files read")
        if ext != ".json" and f"file-{hashlib.sha1(data).hexdigest()[:12]}" in index:
            counts["unchanged"] += 1
            continue
        try:
            acts = parse_bytes(label, data, ext, args.sport)
        except Skip as e:
            skipped[str(e)] += 1
            continue
        except CoachError:
            raise
        except Exception as e:
            errors.append(f"{label}: {type(e).__name__} {e}")
            continue
        for act in acts:
            status = store.put(act, index)
            counts[status] += 1
            if status in ("new", "updated", "replaced"):
                changed.add(act["id"])
    store.save_index(index)
    print(f"✓ {files} file(s) read: {counts['new']} new activity(ies), {counts['replaced']} replacing a less detailed version, "
          f"{counts['updated']} updated, {counts['duplicate'] + counts['unchanged']} already present")
    for reason, n in skipped.most_common(5):
        print(f"  skipped ({n}): {reason}")
    for err in errors[:10]:
        print(f"  ✗ {err}")
    if len(errors) > 10:
        print(f"  ✗ … {len(errors) - 10} more errors")
    if changed:
        guessed = [i for i in changed if store.get(i).get("sport_guessed")]
        if guessed:
            print(f"  ! sport guessed from speed for {len(guessed)} activity(ies): run again with --sport run if needed")
        info = metrics.refresh(changed)
        print(f"✓ metrics up to date: {info['activities']} activities ({info['analyzed']} recomputed)")
    return 1 if errors and not changed else 0


def cmd_list(args: argparse.Namespace) -> int:
    print(reports.list_report(args.days, None if args.sport == "all" else args.sport), end="")
    return 0


def cmd_analyze(args: argparse.Namespace) -> int:
    index = store.load_index()
    activity_id = store.find(args.activity, index, sport=None if args.any_sport else "run")
    text, path = reports.run_report(activity_id)
    print(text + f"\n_Report: {path}_")
    return 0


def cmd_week(args: argparse.Namespace) -> int:
    year, week = parse_week(args.week) if args.week else week_of(today())
    text, path = reports.week_report(year, week)
    print(text + (f"\n_Report: {path}_" if path else ""))
    return 0


def cmd_status(_: argparse.Namespace) -> int:
    print(reports.status_report(), end="")
    return 0


def cmd_next(args: argparse.Namespace) -> int:
    metrics.ensure_fresh()
    profile = metrics.current_profile()
    rec = coaching.recommend(profile, metrics.activity_rows(), metrics.read_csv("daily.csv"),
                             metrics.read_csv("weekly.csv"), coaching.load_plan(), today())
    if args.spec:
        spec = rec["proposal"].get("spec")
        if not spec:
            raise CoachError("no structured workout to send for this proposal")
        print(json.dumps(spec, ensure_ascii=False, indent=2))
        return 0
    print(reports.next_report(rec, profile), end="")
    return 0


def cmd_recap(args: argparse.Namespace) -> int:
    print(reports.recap_report(args.weeks), end="")
    return 0


def cmd_plan(_: argparse.Namespace) -> int:
    plan = coaching.load_plan()
    if plan is None:
        print(f"No plan ({coaching.plan_path()}). Format: references/plan.md. Without a plan, `coach next` follows the generic rules.")
        return 0
    metrics.ensure_fresh()
    rows = metrics.activity_rows()
    labels = sorted(plan["weeks"])
    print(f"# Plan {plan.get('name', '')}: {len(labels)} week(s), {labels[0]} → {labels[-1]}".rstrip())
    ref = today()
    week = coaching.plan_week(plan, ref)
    if week:
        print(f"\n## Current week — {week.get('phase', '')} ({week.get('km', '?')} km planned)\n")
        print("\n".join(coaching.render_plan_rows(coaching.adherence(week, coaching.week_runs(rows, ref), ref, ref))))
    else:
        print("\n_No plan week for today._")
    return 0


def _load_spec(arg: str) -> dict[str, Any]:
    text = sys.stdin.read() if arg == "-" else Path(arg).expanduser().read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise CoachError(f"workout: invalid JSON ({e})") from e


def cmd_workout(args: argparse.Namespace) -> int:
    from . import garmin, workout

    if args.action == "push":
        spec = _load_spec(args.spec)
        payload = workout.payload(spec)
        if args.date:
            parse_date(args.date)
        print(workout.describe(spec))
        if args.dry_run:
            print("\n```json\n" + json.dumps(payload, ensure_ascii=False, indent=2) + "\n```")
            print(f"\n[dry run] nothing was sent{'; planned date ' + args.date if args.date else ''}.")
            return 0
        print(garmin.push_workout(payload, args.date))
    elif args.action == "list":
        items = garmin.list_workouts()
        print("\n".join(f"- {w.get('workoutId')} · {w.get('workoutName')}" for w in items) or "No workouts in Garmin Connect.")
    elif args.action == "delete":
        print(garmin.delete_workout(args.workout_id))
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    metrics.ensure_fresh()
    rows = metrics.read_csv("activities.csv")
    if args.sport != "all":
        rows = [r for r in rows if r["sport"] == args.sport]
    if args.format == "json":
        text = json.dumps(rows, ensure_ascii=False, indent=2) + "\n"
    else:
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=metrics.ACTIVITY_COLUMNS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for r in rows:
            writer.writerow({k: "" if r.get(k) is None else (int(r[k]) if isinstance(r[k], float) and r[k].is_integer() else r[k])
                             for k in metrics.ACTIVITY_COLUMNS})
        text = buf.getvalue()
    if args.out:
        out = Path(args.out).expanduser()
        write_text(out, text)
        print(f"✓ {len(rows)} activities exported to {out}")
    else:
        print(text, end="")
    return 0


def cmd_rebuild(_: argparse.Namespace) -> int:
    index = store.reindex()
    info = metrics.refresh(full=True)
    print(f"✓ index rebuilt ({len(index)} activities), metrics recomputed for {info['analyzed']} activities")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="coach", description="Running coach: Strava, Garmin Connect or GPX/TCX/FIT files → analyses, reports, next workout.")
    p.add_argument("--today", metavar="YYYY-MM-DD", help="replay the computations as if today were that day")
    p.add_argument("--version", action="version", version=f"running-coach {VERSION}")
    sub = p.add_subparsers(dest="command", required=True, metavar="command")

    s = sub.add_parser("doctor", help="check the install, profile, sources and data")
    s.set_defaults(func=cmd_doctor)

    s = sub.add_parser("profile", help="show or edit the athlete profile (HR, zones, goal)")
    s.add_argument("action", choices=["show", "set"], nargs="?", default="show")
    s.add_argument("--hr-max", help="max HR in bpm, or auto (highest value seen in the activities)")
    s.add_argument("--hr-rest", type=int, help="resting HR in bpm (Karvonen zones)")
    s.add_argument("--hr-zones", help="measured upper bounds of Z1,Z2,Z3,Z4 (stress test), e.g. 130,148,160,170")
    s.add_argument("--sex", choices=["male", "female"], help="TRIMP coefficients")
    s.add_argument("--birth-year", type=int, help="max HR estimate when unknown (Tanaka)")
    s.add_argument("--threshold-pace", metavar="M:SS", help="threshold pace in min/km")
    s.add_argument("--ref-race", nargs=2, metavar=("KM", "TIME"), help="recent reference race, e.g. 10 47:30")
    s.add_argument("--goal-name", help="goal race name")
    s.add_argument("--goal-distance", type=float, metavar="KM", help="goal distance in km")
    s.add_argument("--goal-date", metavar="YYYY-MM-DD", help="goal date")
    s.add_argument("--goal-time", metavar="H:MM:SS", help="target time")
    s.add_argument("--clear-goal", action="store_true", help="remove the goal")
    s.add_argument("--weekly-km", type=float, help="target weekly volume")
    s.add_argument("--runs-per-week", type=int, help="number of runs per week")
    s.add_argument("--long-run-day", metavar="DAY", help="long-run day (mon…sun)")
    s.add_argument("--long-run-min", type=int, metavar="MIN", help="duration from which a run counts as long (75 by default)")
    s.add_argument("--sources", help="source order for sync, e.g. garmin,strava")
    s.add_argument("--note", help="add a lasting note (injury, constraint, preference)")
    s.add_argument("--unset", action="append", metavar="KEY", help="remove a key from the profile")
    s.set_defaults(func=cmd_profile)

    s = sub.add_parser("auth", help="connect Strava or Garmin Connect")
    auth = s.add_subparsers(dest="service", required=True, metavar="service")
    a = auth.add_parser("strava", help="register the Strava application, authorize, token status")
    a.add_argument("--client-id", help="Strava application Client ID")
    a.add_argument("--client-secret", help="Client Secret (otherwise asked without echo, or STRAVA_CLIENT_SECRET)")
    a.add_argument("--code", metavar="URL|CODE", help="redirect address (or code) after authorization")
    a.add_argument("--status", action="store_true", help="status without a network call")
    a.add_argument("--reauthorize", action="store_true", help="show the authorization address again")
    a = auth.add_parser("garmin", help="Garmin Connect login (interactive, MFA)")
    a.add_argument("action", choices=["login", "status", "logout"], nargs="?", default="status")
    s.set_defaults(func=cmd_auth)

    s = sub.add_parser("sync", help="fetch new activities (Strava, otherwise Garmin)")
    s.add_argument("--source", choices=["auto", "strava", "garmin", "all"], default="auto",
                   help="auto: first connected source in profile order, the next one on failure")
    s.add_argument("--days", type=int, help="go back N days (first run: 90)")
    s.add_argument("--details", type=int, default=30, help="maximum number of runs whose details are downloaded (30)")
    s.set_defaults(func=cmd_sync)

    s = sub.add_parser("import", help="import GPX, TCX, FIT, Strava/Garmin JSON, .gz or .zip export files")
    s.add_argument("paths", nargs="+", help="files, folders or archives")
    s.add_argument("--sport", choices=["run", "ride", "walk", "hike", "swim", "other"], help="force the sport")
    s.set_defaults(func=cmd_import)

    s = sub.add_parser("list", help="list recent activities with their id")
    s.add_argument("--days", type=int, default=30)
    s.add_argument("--sport", default="all", choices=["all", "run", "ride", "swim", "walk", "hike", "strength", "other"])
    s.set_defaults(func=cmd_list)

    s = sub.add_parser("analyze", help="detailed report of one session")
    s.add_argument("activity", nargs="?", default="last", help="id, YYYY-MM-DD, last or last-N (default: last)")
    s.add_argument("--any-sport", action="store_true", help="accept an activity other than running")
    s.set_defaults(func=cmd_analyze)

    s = sub.add_parser("week", help="report for one ISO week")
    s.add_argument("--week", metavar="YYYY-Wnn", help="week (default: the current week)")
    s.set_defaults(func=cmd_week)

    s = sub.add_parser("status", help="fitness, fatigue, current week, latest activities")
    s.set_defaults(func=cmd_status)

    s = sub.add_parser("next", help="propose the next workout")
    s.add_argument("--spec", action="store_true", help="print the workout in the JSON format of `workout push`")
    s.set_defaults(func=cmd_next)

    s = sub.add_parser("recap", help="multi-week recap and trends")
    s.add_argument("--weeks", type=int, default=12, help="period when there is no plan (12 weeks)")
    s.set_defaults(func=cmd_recap)

    s = sub.add_parser("plan", help="validate the plan and show the current week")
    s.add_argument("action", choices=["show"], nargs="?", default="show")
    s.set_defaults(func=cmd_plan)

    s = sub.add_parser("workout", help="structured workouts on Garmin Connect (watch)")
    w = s.add_subparsers(dest="action", required=True, metavar="action")
    a = w.add_parser("push", help="create a workout and schedule it")
    a.add_argument("spec", help="workout JSON file, or - for standard input")
    a.add_argument("--date", metavar="YYYY-MM-DD", help="Garmin calendar day")
    a.add_argument("--dry-run", action="store_true", help="show without sending anything")
    w.add_parser("list", help="workouts in the account")
    a = w.add_parser("delete", help="delete a workout from the account")
    a.add_argument("workout_id")
    s.set_defaults(func=cmd_workout)

    s = sub.add_parser("export", help="export the activity table (CSV or JSON)")
    s.add_argument("--format", choices=["csv", "json"], default="csv")
    s.add_argument("--out", metavar="FILE", help="output file (default: standard output)")
    s.add_argument("--sport", default="all", choices=["all", "run", "ride", "swim", "walk", "hike", "strength", "other"])
    s.set_defaults(func=cmd_export)

    s = sub.add_parser("rebuild", help="rebuild the index and recompute all metrics")
    s.set_defaults(func=cmd_rebuild)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.today:
            set_today(parse_date(args.today))
        return args.func(args)
    except CoachError as e:
        print(f"✗ {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
