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

    lines = ["# Diagnostic running-coach", "", f"- Version {VERSION}, Python {sys.version.split()[0]} ({sys.executable})"]
    try:
        import fitdecode  # noqa: F401
        lines.append("- Lecture FIT : ok")
    except ImportError:
        lines.append("- Lecture FIT : ✗ fitdecode absent (lancer install.sh)")
    try:
        from importlib.metadata import version
        lines.append(f"- Garmin : bibliothèque garminconnect {version('garminconnect')}")
    except Exception:
        lines.append("- Garmin : ✗ garminconnect absent (lancer install.sh) ; Strava et l'import de fichiers restent utilisables")
    index = store.load_index()
    profile = load_profile(store.observed_hr_max(index))
    plan_state = "absent (facultatif)"
    if coaching.plan_path().exists():
        try:
            coaching.load_plan()
            plan_state = "ok"
        except CoachError as e:
            plan_state = f"✗ {e}"
    lines += [f"- Configuration : {config_dir()}",
              f"  - profil : {'ok' if profile.exists else 'absent'}" + (" (FC max manquante)" if profile.exists and profile.provisional else ""),
              f"  - plan : {plan_state}",
              f"- Données : {data_dir()} — {len(index)} activités dont {sum(1 for e in index.values() if e['sport'] == 'run')} courses",
              f"- {strava.status()}", f"- {garmin.status()}"]
    steps = []
    if not profile.exists or profile.provisional:
        steps.append("créer le profil avec l'utilisateur : `coach profile set --hr-max … --hr-rest … --goal-…` (references/setup.md)")
    if not strava.is_configured() and not garmin.is_configured():
        steps.append("connecter une source (references/sources.md) ou importer des fichiers : `coach import <dossier|zip|fichiers>`")
    elif not index:
        steps.append("`coach sync`")
    lines += ["", "Étapes suivantes : " + ("; ".join(steps) if steps else "aucune, tout est prêt.")]
    print("\n".join(lines))
    return 0


def _profile_update(args: argparse.Namespace) -> dict[str, Any]:
    current = load_profile().data
    data = dict(current)
    if args.hr_max is not None:
        if args.hr_max == "auto":
            observed = store.observed_hr_max(store.load_index())
            if not observed:
                raise CoachError("aucune FC max dans les activités : importer ou synchroniser d'abord, ou donner la valeur")
            data["hr_max"] = int(observed)
            log(f"FC max observée dans les données : {observed:.0f} bpm")
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
        log(f"✓ profil enregistré : {profile_path()}")
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
        raise CoachError("--client-secret exige --client-id")
    if args.client_id and not args.client_secret:
        if not sys.stdin.isatty():
            raise CoachError("Client Secret à saisir : lancer `coach auth strava --client-id …` dans un terminal, "
                             "ou exporter STRAVA_CLIENT_SECRET")
        import getpass
        try:
            args.client_secret = getpass.getpass("Client Secret Strava (saisie masquée) : ").strip()
        except EOFError as e:
            raise CoachError("saisie impossible ici : lancer la commande dans un terminal") from e
        if not args.client_secret:
            raise CoachError("Client Secret vide")
    if args.client_id:
        saved = strava.load_creds()
        saved.update(client_id=args.client_id, client_secret=args.client_secret)
        strava.save_creds({k: v for k, v in saved.items() if k in ("client_id", "client_secret", "access_token", "refresh_token", "expires_at", "scope", "athlete_id")})
        log(f"✓ application Strava enregistrée dans {strava.creds_path()} (droits 600)")
    if args.code:
        creds = strava.exchange_code(args.code)
        print(f"✓ Strava autorisé (scope {creds.get('scope', '?')}). Lancer `coach sync`.")
        return 0
    creds = strava.load_creds()
    if args.status or (creds.get("refresh_token") and not (args.client_id or args.reauthorize)):
        print(strava.status())
        return 0
    if not creds.get("client_id"):
        raise CoachError("créer une application sur https://www.strava.com/settings/api (domaine de rappel : localhost), "
                         "puis lancer dans un terminal `coach auth strava --client-id …` (le secret est demandé sans écho)")
    print("1. Ouvrir cette adresse, se connecter et autoriser :\n")
    print(strava.authorize_url(str(creds["client_id"])))
    print("\n2. Le navigateur arrive sur une page http://localhost qui ne charge pas : c'est normal.")
    print("3. Copier l'adresse complète de cette page, puis : coach auth strava --code '<adresse>'")
    return 0


def _print_sync(name: str, result: dict[str, Any]) -> None:
    c = result["counts"]
    parts = [f"{result['listed']} listées", f"{c['new']} nouvelles"]
    if c["replaced"]:
        parts.append(f"{c['replaced']} remplaçant une version moins détaillée")
    if c["duplicate"]:
        parts.append(f"{c['duplicate']} déjà présentes via une autre source")
    parts.append(f"détails téléchargés pour {result['details']} course(s)")
    print(f"✓ {name} : " + ", ".join(parts))
    if result["rate_limited"]:
        print(f"  ! {result['rate_limited']} ; {result['pending']} course(s) attendent leurs détails.")
    elif result["pending"]:
        print(f"  {result['pending']} course(s) plus anciennes attendent leurs détails : relancer `coach sync` (--details N pour en prendre plus).")


def cmd_sync(args: argparse.Namespace) -> int:
    from . import garmin, strava

    modules = {"strava": strava, "garmin": garmin}
    profile = load_profile()
    if args.source in ("auto", "all"):
        order = [s for s in profile.sources if modules[s].is_configured()]
        if not order:
            print("Aucune source connectée.\n- Strava : `coach auth strava` (references/sources.md)\n"
                  "- Garmin : `coach auth garmin login`, dans un terminal\n- Sans compte : `coach import <fichiers GPX/TCX/FIT ou export zip>`")
            return 2
    else:
        if not modules[args.source].is_configured():
            raise CoachError(f"{args.source} n'est pas connecté : voir `coach auth {args.source}`")
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
            print(f"✗ {name} : {e}" + (f" → bascule sur {nxt}" if nxt and args.source == "auto" else ""))
            continue
        store.save_index(index)
        changed |= result["changed"]
        _print_sync(name.capitalize(), result)
        ok = True
        if args.source != "all":
            break
    if changed or ok:
        info = metrics.refresh(changed)
        print(f"✓ métriques à jour : {info['activities']} activités ({info['analyzed']} recalculées)")
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
            log(f"  … {files} fichiers lus")
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
            errors.append(f"{label} : {type(e).__name__} {e}")
            continue
        for act in acts:
            status = store.put(act, index)
            counts[status] += 1
            if status in ("new", "updated", "replaced"):
                changed.add(act["id"])
    store.save_index(index)
    print(f"✓ {files} fichier(s) lu(s) : {counts['new']} nouvelle(s) activité(s), {counts['replaced']} remplaçant une version moins détaillée, "
          f"{counts['updated']} mise(s) à jour, {counts['duplicate'] + counts['unchanged']} déjà présente(s)")
    for reason, n in skipped.most_common(5):
        print(f"  ignoré ({n}) : {reason}")
    for err in errors[:10]:
        print(f"  ✗ {err}")
    if len(errors) > 10:
        print(f"  ✗ … {len(errors) - 10} autres erreurs")
    if changed:
        guessed = [i for i in changed if store.get(i).get("sport_guessed")]
        if guessed:
            print(f"  ! sport deviné d'après la vitesse pour {len(guessed)} activité(s) : relancer avec --sport run si besoin")
        info = metrics.refresh(changed)
        print(f"✓ métriques à jour : {info['activities']} activités ({info['analyzed']} recalculées)")
    return 1 if errors and not changed else 0


def cmd_list(args: argparse.Namespace) -> int:
    print(reports.list_report(args.days, None if args.sport == "all" else args.sport), end="")
    return 0


def cmd_analyze(args: argparse.Namespace) -> int:
    index = store.load_index()
    activity_id = store.find(args.activity, index, sport=None if args.any_sport else "run")
    text, path = reports.run_report(activity_id)
    print(text + f"\n_Rapport : {path}_")
    return 0


def cmd_week(args: argparse.Namespace) -> int:
    year, week = parse_week(args.week) if args.week else week_of(today())
    text, path = reports.week_report(year, week)
    print(text + (f"\n_Rapport : {path}_" if path else ""))
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
            raise CoachError("pas de séance structurée à envoyer pour cette proposition")
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
        print(f"Aucun plan ({coaching.plan_path()}). Format : references/plan.md. Sans plan, `coach next` suit les règles génériques.")
        return 0
    metrics.ensure_fresh()
    rows = metrics.activity_rows()
    labels = sorted(plan["weeks"])
    print(f"# Plan {plan.get('name', '')} : {len(labels)} semaine(s), {labels[0]} → {labels[-1]}".rstrip())
    ref = today()
    week = coaching.plan_week(plan, ref)
    if week:
        print(f"\n## Semaine en cours — {week.get('phase', '')} ({week.get('km', '?')} km visés)\n")
        print("\n".join(coaching.render_plan_rows(coaching.adherence(week, coaching.week_runs(rows, ref), ref, ref))))
    else:
        print("\n_Pas de semaine du plan pour aujourd'hui._")
    return 0


def _load_spec(arg: str) -> dict[str, Any]:
    text = sys.stdin.read() if arg == "-" else Path(arg).expanduser().read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise CoachError(f"séance : JSON invalide ({e})") from e


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
            print(f"\n[essai] rien n'a été envoyé{' ; date prévue ' + args.date if args.date else ''}.")
            return 0
        print(garmin.push_workout(payload, args.date))
    elif args.action == "list":
        items = garmin.list_workouts()
        print("\n".join(f"- {w.get('workoutId')} · {w.get('workoutName')}" for w in items) or "Aucune séance dans Garmin Connect.")
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
        print(f"✓ {len(rows)} activités exportées dans {out}")
    else:
        print(text, end="")
    return 0


def cmd_rebuild(_: argparse.Namespace) -> int:
    index = store.reindex()
    info = metrics.refresh(full=True)
    print(f"✓ index reconstruit ({len(index)} activités), métriques recalculées pour {info['analyzed']} activités")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="coach", description="Coach course à pied : Strava, Garmin Connect ou fichiers GPX/TCX/FIT → analyses, bilans, prochaine séance.")
    p.add_argument("--today", metavar="AAAA-MM-JJ", help="rejouer les calculs comme si l'on était ce jour-là")
    p.add_argument("--version", action="version", version=f"running-coach {VERSION}")
    sub = p.add_subparsers(dest="command", required=True, metavar="commande")

    s = sub.add_parser("doctor", help="vérifier l'installation, le profil, les sources et les données")
    s.set_defaults(func=cmd_doctor)

    s = sub.add_parser("profile", help="afficher ou modifier le profil athlète (FC, zones, objectif)")
    s.add_argument("action", choices=["show", "set"], nargs="?", default="show")
    s.add_argument("--hr-max", help="FC max en bpm, ou auto (maximum observé dans les activités)")
    s.add_argument("--hr-rest", type=int, help="FC de repos en bpm (zones Karvonen)")
    s.add_argument("--hr-zones", help="bornes hautes Z1,Z2,Z3,Z4 mesurées (test d'effort), par exemple 130,148,160,170")
    s.add_argument("--sex", choices=["male", "female"], help="coefficients du TRIMP")
    s.add_argument("--birth-year", type=int, help="estimation de la FC max si inconnue (Tanaka)")
    s.add_argument("--threshold-pace", metavar="M:SS", help="allure seuil en min/km")
    s.add_argument("--ref-race", nargs=2, metavar=("KM", "TEMPS"), help="course de référence récente, par exemple 10 47:30")
    s.add_argument("--goal-name", help="nom de la course objectif")
    s.add_argument("--goal-distance", type=float, metavar="KM", help="distance de l'objectif en km")
    s.add_argument("--goal-date", metavar="AAAA-MM-JJ", help="date de l'objectif")
    s.add_argument("--goal-time", metavar="H:MM:SS", help="temps visé")
    s.add_argument("--clear-goal", action="store_true", help="supprimer l'objectif")
    s.add_argument("--weekly-km", type=float, help="volume hebdomadaire visé")
    s.add_argument("--runs-per-week", type=int, help="nombre de sorties par semaine")
    s.add_argument("--long-run-day", metavar="JOUR", help="jour de la sortie longue (mon…sun ou lun…dim)")
    s.add_argument("--long-run-min", type=int, metavar="MIN", help="durée à partir de laquelle une sortie est longue (75 par défaut)")
    s.add_argument("--sources", help="ordre des sources pour sync, par exemple garmin,strava")
    s.add_argument("--note", help="ajouter une note durable (blessure, contrainte, préférence)")
    s.add_argument("--unset", action="append", metavar="CLÉ", help="retirer une clé du profil")
    s.set_defaults(func=cmd_profile)

    s = sub.add_parser("auth", help="connecter Strava ou Garmin Connect")
    auth = s.add_subparsers(dest="service", required=True, metavar="service")
    a = auth.add_parser("strava", help="enregistrer l'application Strava, autoriser, état du jeton")
    a.add_argument("--client-id", help="Client ID de l'application Strava")
    a.add_argument("--client-secret", help="Client Secret (sinon demandé sans écho, ou STRAVA_CLIENT_SECRET)")
    a.add_argument("--code", metavar="URL|CODE", help="adresse de redirection (ou code) après autorisation")
    a.add_argument("--status", action="store_true", help="état sans appel réseau")
    a.add_argument("--reauthorize", action="store_true", help="réafficher l'adresse d'autorisation")
    a = auth.add_parser("garmin", help="connexion Garmin Connect (interactive, MFA)")
    a.add_argument("action", choices=["login", "status", "logout"], nargs="?", default="status")
    s.set_defaults(func=cmd_auth)

    s = sub.add_parser("sync", help="récupérer les nouvelles activités (Strava, sinon Garmin)")
    s.add_argument("--source", choices=["auto", "strava", "garmin", "all"], default="auto",
                   help="auto : première source connectée dans l'ordre du profil, la suivante en cas d'échec")
    s.add_argument("--days", type=int, help="remonter N jours (premier passage : 90)")
    s.add_argument("--details", type=int, default=30, help="nombre maximal de courses dont on télécharge le détail (30)")
    s.set_defaults(func=cmd_sync)

    s = sub.add_parser("import", help="importer des fichiers GPX, TCX, FIT, JSON Strava/Garmin, .gz ou export .zip")
    s.add_argument("paths", nargs="+", help="fichiers, dossiers ou archives")
    s.add_argument("--sport", choices=["run", "ride", "walk", "hike", "swim", "other"], help="forcer le sport")
    s.set_defaults(func=cmd_import)

    s = sub.add_parser("list", help="lister les activités récentes avec leur id")
    s.add_argument("--days", type=int, default=30)
    s.add_argument("--sport", default="all", choices=["all", "run", "ride", "swim", "walk", "hike", "strength", "other"])
    s.set_defaults(func=cmd_list)

    s = sub.add_parser("analyze", help="compte rendu détaillé d'une séance")
    s.add_argument("activity", nargs="?", default="last", help="id, AAAA-MM-JJ, last ou last-N (défaut : last)")
    s.add_argument("--any-sport", action="store_true", help="accepter une activité autre que la course")
    s.set_defaults(func=cmd_analyze)

    s = sub.add_parser("week", help="bilan d'une semaine ISO")
    s.add_argument("--week", metavar="AAAA-Wnn", help="semaine (défaut : la semaine en cours)")
    s.set_defaults(func=cmd_week)

    s = sub.add_parser("status", help="forme, fatigue, semaine en cours, dernières activités")
    s.set_defaults(func=cmd_status)

    s = sub.add_parser("next", help="proposer la prochaine séance")
    s.add_argument("--spec", action="store_true", help="sortir la séance au format JSON de `workout push`")
    s.set_defaults(func=cmd_next)

    s = sub.add_parser("recap", help="bilan multi-semaines et tendances")
    s.add_argument("--weeks", type=int, default=12, help="période sans plan (12 semaines)")
    s.set_defaults(func=cmd_recap)

    s = sub.add_parser("plan", help="valider le plan et afficher la semaine en cours")
    s.add_argument("action", choices=["show"], nargs="?", default="show")
    s.set_defaults(func=cmd_plan)

    s = sub.add_parser("workout", help="séances structurées sur Garmin Connect (montre)")
    w = s.add_subparsers(dest="action", required=True, metavar="action")
    a = w.add_parser("push", help="créer une séance et la planifier")
    a.add_argument("spec", help="fichier JSON de séance, ou - pour l'entrée standard")
    a.add_argument("--date", metavar="AAAA-MM-JJ", help="jour du calendrier Garmin")
    a.add_argument("--dry-run", action="store_true", help="afficher sans rien envoyer")
    w.add_parser("list", help="séances présentes sur le compte")
    a = w.add_parser("delete", help="supprimer une séance du compte")
    a.add_argument("workout_id")
    s.set_defaults(func=cmd_workout)

    s = sub.add_parser("export", help="exporter le tableau des activités (CSV ou JSON)")
    s.add_argument("--format", choices=["csv", "json"], default="csv")
    s.add_argument("--out", metavar="FICHIER", help="fichier de sortie (défaut : sortie standard)")
    s.add_argument("--sport", default="all", choices=["all", "run", "ride", "swim", "walk", "hike", "strength", "other"])
    s.set_defaults(func=cmd_export)

    s = sub.add_parser("rebuild", help="reconstruire l'index et recalculer toutes les métriques")
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
