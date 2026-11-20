from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, timedelta
from statistics import mean
from typing import Any

from . import coaching, metrics, store
from .profile import ZONE_NAMES, Profile
from .util import data_dir, day_fr, parse_day, fmt_hms, fmt_minutes, fmt_pace, monday_of, today, week_label, week_of, write_text

SPORT_FR = {"run": "course", "ride": "vélo", "swim": "natation", "walk": "marche", "hike": "randonnée", "strength": "renfo", "other": "autre"}
DETAIL_FR = {0: "résumé seulement", 1: "tours", 2: "enregistrement complet"}


def _warn_profile(profile: Profile) -> list[str]:
    if not profile.exists:
        return [f"> ⚠ Aucun profil : zones et charge calculées avec une FC max provisoire de {profile.hr_max:.0f} bpm "
                "(`coach profile set --hr-max …`).", ""]
    if profile.provisional:
        return [f"> ⚠ FC max absente du profil : {profile.hr_max:.0f} bpm ({profile.hr_max_source}).", ""]
    return []


def _i(value: Any) -> str:
    return "—" if value is None else f"{value:.0f}"


def _bar(minutes: float, total: float) -> str:
    return "█" * max(1, round(20 * minutes / total)) if total and minutes else ""


def _zone_lines(row: dict[str, Any]) -> list[str]:
    zones = [row.get(f"z{i}") or 0 for i in range(1, 6)]
    total = sum(zones)
    if not total:
        return ["_Pas de fréquence cardiaque._"]
    return [f"- {ZONE_NAMES[i]} : {fmt_minutes(z)} ({100 * z / total:.0f} %) {_bar(z, total)}" for i, z in enumerate(zones) if z >= 0.5]


def _observations(act: dict[str, Any], row: dict[str, Any], splits: list[dict[str, Any]], profile: Profile,
                  laps_info: dict[str, Any] | None) -> list[str]:
    obs = []
    zones = [row.get(f"z{i}") or 0 for i in range(1, 6)]
    total = sum(zones)
    hard_share = (zones[2] + zones[3] + zones[4]) / total if total else 0
    z2_top = profile.zone_range(2)[1]
    if row.get("detail") == 0:
        obs.append("ℹ Résumé seulement : pas de splits. `coach sync --details 50` ou l'import du fichier FIT donne l'analyse km par km.")
    if row.get("trimp_estimated"):
        obs.append("ℹ Pas de fréquence cardiaque : charge estimée d'après la durée.")
    if row["kind"] == "long" and row["structure"] == "Sortie longue" and hard_share > 0.2:
        obs.append(f"⚠ Sortie longue trop intense : {100 * hard_share:.0f} % du temps au-dessus de Z2 (plafond FC {z2_top}).")
    if row["kind"] == "easy" and row["structure"] in ("Footing", "Récupération") and hard_share > 0.25:
        obs.append(f"⚠ Footing trop rapide : {100 * hard_share:.0f} % du temps au-dessus de Z2. Un footing reste sous {z2_top} bpm.")
    full = [s for s in splits if s["distance_m"] >= 500 and s.get("hr")]
    if row["kind"] in ("easy", "long") and len(full) >= 6:
        tail = full[-3:]
        if mean(s["hr"] for s in tail) > z2_top and mean(s["hr"] for s in full[:-3]) <= z2_top:
            obs.append(f"⚠ Fin de sortie au-dessus de Z2 (FC moyenne des 3 derniers km {mean(s['hr'] for s in tail):.0f}) : "
                       "la moyenne globale cache la dérive, lire les derniers km.")
    dec = row.get("decoupling")
    if dec is not None:
        if dec < 5:
            obs.append(f"✓ Découplage aérobie {dec:g} % : endurance solide à cette allure.")
        elif dec <= 10:
            obs.append(f"• Découplage aérobie {dec:g} % : correct, à surveiller sur les sorties longues.")
        else:
            obs.append(f"⚠ Découplage aérobie {dec:g} % : allure trop rapide pour la durée, chaleur, ou base aérobie à construire.")
    if laps_info:
        reps = [lp for lp in act.get("laps") or [] if (lp.get("distance_m") or 0) > 50 and (lp.get("moving_s") or 0) > 20]
        speeds = [lp["distance_m"] / lp["moving_s"] for lp in reps]
        if speeds:
            med = sorted(speeds)[len(speeds) // 2]
            work = [lp["moving_s"] / (lp["distance_m"] / 1000) for lp, sp in zip(reps, speeds) if sp > med * 1.08]
            if len(work) >= 3:
                spread = max(work) - min(work)
                verdict = "très régulières" if spread < 6 else "régulières" if spread < 12 else "irrégulières"
                obs.append(f"{'✓' if spread < 12 else '⚠'} Répétitions {verdict} : écart de {spread:.0f} s/km entre la plus rapide et la plus lente "
                           f"({fmt_pace(min(work))} → {fmt_pace(max(work))}).")
                if work[-1] > work[0] + 8:
                    obs.append("⚠ La dernière répétition est nettement plus lente que la première : départ trop rapide ou série trop longue.")
            warm = reps[0] if reps else None
            if warm and warm["moving_s"] < 600 and speeds[0] <= med * 1.08:
                obs.append("⚠ Échauffement de moins de 10 min avant la première répétition.")
    if act.get("max_hr") and act["max_hr"] > profile.hr_max + 1:
        obs.append(f"⚠ FC max de la séance ({act['max_hr']:.0f}) au-dessus de la FC max du profil ({profile.hr_max:.0f}) : "
                   "si ce n'est pas un artefact du capteur, mettre à jour le profil (`coach profile set --hr-max …`).")
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
    title = row["structure"] or SPORT_FR.get(act["sport"], act["sport"])
    lines = [f"# {row['date']} — {title} ({row['distance_km']:g} km)",
             f"> `{activity_id}` · {day_fr(start.date())} {start.strftime('%H:%M')} · {act.get('name') or 'sans titre'} · "
             f"source {act['source']} ({DETAIL_FR[row['detail']]})", ""]
    lines += _warn_profile(profile)
    lines += ["## Résumé", "",
              f"- Distance : {row['distance_km']:g} km en {fmt_hms(act.get('moving_s'))} de mouvement"
              + (f" ({fmt_hms(act['elapsed_s'])} au total)" if act.get("elapsed_s") and act.get("moving_s") and act["elapsed_s"] - act["moving_s"] > 60 else ""),
              f"- Allure moyenne : {fmt_pace(row['pace_s'])}/km · FC moyenne {_i(row['avg_hr'])} · FC max {_i(row['max_hr'])}"
              + (f" · D+ {row['elev_gain_m']:.0f} m" if row.get("elev_gain_m") else ""),
              f"- Charge (TRIMP) : {row['trimp']:g}" + (" (estimée sans FC)" if row.get("trimp_estimated") else ""),
              ]
    if act["sport"] == "run":
        lines.append(f"- Structure détectée : **{row['structure']}**" + (f" · {int(row['quality_km'])} km de qualité ★" if row.get("quality_km") else ""))
        if row.get("ef"):
            lines.append(f"- Efficience (EF) : {row['ef']:.3f} m/min par battement" + (f" · découplage {row['decoupling']:g} %" if row.get("decoupling") is not None else ""))
    plan = coaching.load_plan()
    week = coaching.plan_week(plan, start.date())
    if week:
        planned = [s for s in week.get("sessions") or [] if parse_day(s["day"]) == start.weekday()]
        lines += ["", "## Plan", ""]
        lines += [f"- Prévu ce jour : {s.get('desc') or coaching.TYPE_FR[s.get('type', 'easy')]} (priorité {s.get('priority', 2)})" for s in planned] or ["- Rien de prévu ce jour au plan."]
    if splits:
        lines += ["", "## Splits km par km", "", "| Km | Allure | FC | Zone FC | Zone d'allure | |", "|---|---|---|---|---|---|"]
        for s in splits:
            km = f"{s['km']}" if s["distance_m"] >= 999 else f"{s['km']} ({s['distance_m'] / 1000:.2f})"
            z = profile.zone_of(s.get("hr"))
            lines.append(f"| {km} | {fmt_pace(s['pace_s'])} | {round(s['hr']) if s.get('hr') else '—'} | {ZONE_NAMES[z - 1] if z else '—'} | "
                         f"{profile.pace_zone_of(s['pace_s'])} | {'★' if s['km'] in quality else ''} |")
    laps = act.get("laps") or []
    if laps and (laps_info or not splits):
        lines += ["", "## Tours", "", "| Tour | Distance | Durée | Allure | FC moy |", "|---|---|---|---|---|"]
        for i, lp in enumerate(laps, 1):
            dist, mov = lp.get("distance_m") or 0, lp.get("moving_s") or 0
            pace = mov / (dist / 1000) if dist > 0 and mov else None
            lines.append(f"| {i} | {dist:.0f} m | {fmt_hms(mov)} | {fmt_pace(pace)} | {round(lp['avg_hr']) if lp.get('avg_hr') else '—'} |")
        if laps_info:
            lines.append(f"\nRépétitions : {laps_info['reps']} × {laps_info['work_km'] / laps_info['reps'] * 1000:.0f} m en moyenne, "
                         f"allure {fmt_pace(laps_info['pace_s'])}/km" + (f", FC {laps_info['hr']:.0f}" if laps_info.get("hr") else ""))
    lines += ["", "## Temps par zone FC", ""] + _zone_lines(row)
    if act["sport"] == "run":
        family = row["structure"].split(" ")[0]
        similar = [r for r in rows if r["sport"] == "run" and r["id"] != activity_id and r["date"] < row["date"]
                   and (r.get("structure") or "").split(" ")[0] == family][-3:]
        lines += ["", "## Séances comparables", ""]
        if similar:
            lines += ["| Date | Km | Allure | FC moy | EF | TRIMP |", "|---|---|---|---|---|---|"]
            for r in reversed(similar):
                lines.append(f"| {r['date']} | {r['distance_km']:g} | {fmt_pace(r['pace_s'])} | {_i(r['avg_hr'])} | "
                             f"{r['ef'] if r.get('ef') else '—'} | {r['trimp']:g} |")
        else:
            lines.append("_Aucune séance du même type avant celle-ci._")
    obs = _observations(act, row, splits, profile, laps_info)
    lines += ["", "## Observations", ""] + ([f"- {o}" for o in obs] or ["_Rien à signaler._"])
    daily = metrics.read_csv("daily.csv")
    before = metrics.load_on(daily, start.date() - timedelta(days=1))
    after = metrics.load_on(daily, start.date() + timedelta(days=1))
    if before and after:
        lines += ["", "## Charge", "", f"- CTL {before['ctl']:g} → {after['ctl']:g} · ATL {before['atl']:g} → {after['atl']:g} · "
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
    lines = [f"# Semaine {label} ({monday.strftime('%d/%m')} → {sunday.strftime('%d/%m/%Y')})", ""]
    lines += _warn_profile(profile)
    if not acts:
        lines.append("_Aucune activité cette semaine._")
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
              f"- Course : {len(runs)} sortie(s), {km:.1f} km, {fmt_minutes(minutes)}, sortie la plus longue {longest:g} km, {quality} séance(s) de qualité",
              f"- Charge totale (TRIMP, tous sports) : {load:.0f}"]
    if others:
        by_sport: dict[str, float] = {}
        for r in others:
            by_sport[r["sport"]] = by_sport.get(r["sport"], 0) + (r["moving_min"] or 0)
        lines.append("- Autres sports : " + ", ".join(f"{SPORT_FR.get(s, s)} {fmt_minutes(m)}" for s, m in by_sport.items()))
    if target:
        lines.append(f"- Volume visé : {target:g} km → {100 * km / target:.0f} %")
    if avg_prev:
        lines.append(f"- Moyenne des {len(previous)} semaines précédentes : {avg_prev:.1f} km ({100 * (km - avg_prev) / avg_prev:+.0f} %)")
    lines += ["", "## Séances", "", "| Jour | Sport | Type | Km | Durée | Allure | FC moy | TRIMP |", "|---|---|---|---|---|---|---|---|"]
    for r in sorted(acts, key=lambda x: x["start_local"]):
        d = date.fromisoformat(r["date"])
        lines.append(f"| {day_fr(d)} {d.strftime('%d/%m')} | {SPORT_FR.get(r['sport'], r['sport'])} | {r.get('structure') or '—'} | "
                     f"{r['distance_km']:g} | {fmt_minutes(r['moving_min'])} | {fmt_pace(r['pace_s']) if r['sport'] == 'run' else '—'} | "
                     f"{_i(r['avg_hr'])} | {r['trimp']:g} |")
    zones = [sum(r.get(f"z{i}") or 0 for r in runs) for i in range(1, 6)]
    total = sum(zones)
    if total:
        easy = 100 * (zones[0] + zones[1]) / total
        lines += ["", "## Intensité (course)", "",
                  f"- Z1-Z2 : {easy:.0f} % · Z3 : {100 * zones[2] / total:.0f} % · Z4-Z5 : {100 * (zones[3] + zones[4]) / total:.0f} %",
                  "- Repère : environ 80 % du temps en Z1-Z2 pour progresser sans s'user."]
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
        lines += ["", "## Charge", "", f"- CTL {a['ctl']:g} → {end_load['ctl']:g} · ATL {a['atl']:g} → {end_load['atl']:g} · "
                  f"TSB {a['tsb']:+g} → {end_load['tsb']:+g} ({coaching.tsb_label(end_load['tsb'])})"]
    obs = []
    if avg_prev and km > 1.25 * avg_prev and km - avg_prev > 5:
        obs.append(f"⚠ Volume en hausse de {100 * (km - avg_prev) / avg_prev:.0f} % sur la moyenne récente : augmenter de 10 à 15 % au plus par semaine.")
    if total and (zones[0] + zones[1]) / total < 0.7:
        obs.append("⚠ Moins de 70 % du temps en Z1-Z2 : trop d'intensité pour encaisser le volume.")
    if quality == 0 and len(runs) >= 3:
        obs.append("• Aucune séance de qualité : normal en récupération, sinon en prévoir une.")
    if quality >= 3:
        obs.append("⚠ Trois séances de qualité ou plus : risque de surcharge.")
    if runs and longest < 0.2 * km and len(runs) >= 3:
        obs.append("• Pas de vraie sortie longue cette semaine.")
    if len(runs) < min(profile.runs_per_week, 3):
        obs.append(f"• {len(runs)} sortie(s) pour {profile.runs_per_week} visées.")
    lines += ["", "## Observations", ""] + ([f"- {o}" for o in obs] or ["_Rien à signaler._"])
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
    lines = [f"# Statut — {ref.isoformat()} ({day_fr(ref)})", ""]
    lines += _warn_profile(profile)
    if not rows:
        lines.append("_Aucune activité : `coach sync` (Strava ou Garmin) ou `coach import <fichiers>`._")
        return "\n".join(lines) + "\n"
    cur = metrics.load_on(daily, ref)
    if cur:
        lines += ["## Forme", "",
                  f"- CTL (forme de fond, 42 j) : **{cur['ctl']:g}** · ATL (fatigue, 7 j) : **{cur['atl']:g}** · "
                  f"TSB : **{cur['tsb']:+g}** → {coaching.tsb_label(cur['tsb'])}"]
        last14 = [x for x in daily if x["date"] <= ref.isoformat()][-14:]
        if len(last14) >= 7:
            lines.append(f"- TSB sur 14 jours : {_spark([x['tsb'] for x in last14])} ({last14[0]['tsb']:+g} → {last14[-1]['tsb']:+g})")
    y, w = week_of(ref)
    wk = [r for r in _week_rows(rows, y, w) if r["sport"] == "run"]
    km = sum(r["distance_km"] or 0 for r in wk)
    target = profile.get("weekly_km")
    lines += ["", "## Semaine en cours", "",
              f"- {len(wk)}/{profile.runs_per_week} sorties, {km:.1f} km" + (f" sur {target:g} visés" if target else "")]
    ph, days = coaching.phase(profile, ref)
    ph = (coaching.plan_week(coaching.load_plan(), ref) or {}).get("phase") or ph
    if profile.goal:
        lines.append(f"- Objectif : {profile.goal.get('name', 'course')} le {profile.goal.get('date')} "
                     + (f"(J-{days}, phase {ph.lower()})" if days is not None and days >= 0 else f"({ph.lower()})"))
    lines += ["", "## Dernières activités", "", "| Date | Sport | Type | Km | Allure | FC moy | TRIMP |", "|---|---|---|---|---|---|---|"]
    for r in rows[-6:][::-1]:
        lines.append(f"| {r['date']} | {SPORT_FR.get(r['sport'], r['sport'])} | {r.get('structure') or '—'} | {r['distance_km']:g} | "
                     f"{fmt_pace(r['pace_s']) if r['sport'] == 'run' else '—'} | {_i(r['avg_hr'])} | {r['trimp']:g} |")
    last = date.fromisoformat(rows[-1]["date"])
    state = store.load_state()
    lines += ["", "## Données", "", f"- Dernière activité : {last.isoformat()} (il y a {(ref - last).days} j), {len(rows)} activités enregistrées"]
    for src in ("strava", "garmin"):
        if state.get(src, {}).get("last_sync"):
            pending = state[src].get("pending_details", 0)
            lines.append(f"- Synchro {src} : {state[src]['last_sync'][:16].replace('T', ' ')} UTC"
                         + (f", {pending} sortie(s) sans détail en attente" if pending else ""))
    if (ref - last).days > 3:
        lines.append("- ⚠ Rien depuis plus de 3 jours : lancer `coach sync` avant de conclure à une pause.")
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
    lines = [f"# Bilan depuis le {start.isoformat()}", ""]
    lines += _warn_profile(profile)
    sel = [w for w in weekly if start_label <= w["week"] <= week_label(*week_of(ref))]
    if not sel:
        lines.append("_Aucune semaine avec des données sur la période._")
        return "\n".join(lines) + "\n"
    lines += ["| Semaine | Sorties | Km | Plus longue | Qualité | % Z1-Z2 | TRIMP | CTL fin |", "|---|---|---|---|---|---|---|---|"]
    for w in sel:
        y, n = int(w["week"][:4]), int(w["week"][-2:])
        end = metrics.load_on(daily, min(monday_of(y, n) + timedelta(days=6), ref))
        easy = "—" if w["easy_pct"] is None else f"{w['easy_pct']:.0f}"
        lines.append(f"| {w['week']} | {w['runs']:.0f} | {w['run_km']:g} | {w['long_km']:g} | {w['quality']:.0f} | "
                     f"{easy} | {w['trimp']:.0f} | {end['ctl'] if end else '—'} |")
    first = metrics.load_on(daily, start) or next((x for x in daily if x["date"] >= start.isoformat()), None)
    last = metrics.load_on(daily, ref)
    runs = [r for r in rows if r["sport"] == "run" and r["date"] >= start.isoformat()]
    lines += ["", "## Tendances", ""]
    if first and last:
        lines.append(f"- CTL {first['ctl']:g} → {last['ctl']:g} ({last['ctl'] - first['ctl']:+.1f})")
    lines.append(f"- {len(runs)} sorties, {sum(r['distance_km'] or 0 for r in runs):.0f} km, "
                 f"{sum(r['distance_km'] or 0 for r in runs) / max(len(sel), 1):.1f} km par semaine en moyenne")
    if runs:
        best = max(runs, key=lambda r: r["distance_km"] or 0)
        lines.append(f"- Plus longue sortie : {best['distance_km']:g} km le {best['date']}")
    recent_cut = (ref - timedelta(days=28)).isoformat()
    older_cut = (ref - timedelta(days=56)).isoformat()
    ef_recent = [r["ef"] for r in runs if r.get("ef") and r["date"] >= recent_cut]
    ef_older = [r["ef"] for r in rows if r["sport"] == "run" and r.get("ef") and older_cut <= r["date"] < recent_cut]
    if ef_recent and ef_older:
        delta = 100 * (mean(ef_recent) - mean(ef_older)) / mean(ef_older)
        lines.append(f"- Efficience des footings (EF) : {mean(ef_older):.3f} → {mean(ef_recent):.3f} ({delta:+.1f} %) "
                     + ("— progrès aérobie" if delta > 1 else "— stable" if delta > -1 else "— en baisse : fatigue, chaleur ou allure"))
    ph, days = coaching.phase(profile, ref)
    ph = (coaching.plan_week(plan, ref) or {}).get("phase") or ph
    if profile.goal:
        lines += ["", "## Objectif", "", f"- {profile.goal.get('name', 'course')} : {profile.goal.get('distance_km', '?')} km le "
                  f"{profile.goal.get('date', '?')}" + (f", J-{days}" if days is not None and days >= 0 else "") + f", phase {ph.lower()}"]
        pace = profile.race_pace()
        if pace and profile.goal_km:
            lines.append(f"- Allure objectif {fmt_pace(pace)}/km soit {fmt_hms(pace * profile.goal_km)}")
    return "\n".join(lines) + "\n"


def list_report(days: int, sport: str | None) -> str:
    metrics.ensure_fresh()
    rows = metrics.activity_rows()
    cut = (today() - timedelta(days=days)).isoformat()
    sel = [r for r in rows if r["date"] >= cut and (sport is None or r["sport"] == sport)]
    if not sel:
        return f"_Aucune activité sur les {days} derniers jours._\n"
    lines = ["| Id | Date | Sport | Type | Km | Durée | Allure | FC moy | Détail |", "|---|---|---|---|---|---|---|---|---|"]
    for r in sel[::-1]:
        lines.append(f"| {r['id']} | {r['start_local'][:16].replace('T', ' ')} | {SPORT_FR.get(r['sport'], r['sport'])} | "
                     f"{r.get('structure') or '—'} | {r['distance_km']:g} | {fmt_minutes(r['moving_min'])} | "
                     f"{fmt_pace(r['pace_s']) if r['sport'] == 'run' else '—'} | {_i(r['avg_hr'])} | {DETAIL_FR[int(r['detail'] or 0)]} |")
    return "\n".join(lines) + "\n"


def next_report(rec: dict[str, Any], profile: Profile) -> str:
    from .workout import describe

    d = rec["date"]
    lines = [f"# Prochaine séance — {day_fr(d)} {d.isoformat()}", ""]
    lines += _warn_profile(profile)
    if rec["ran_today"]:
        lines += ["_Séance du jour déjà enregistrée : proposition pour demain._", ""]
    ctx = [f"phase {rec['phase'].lower()}" + (f" (J-{rec['days_to_goal']})" if rec["days_to_goal"] and rec["days_to_goal"] > 0 else ""),
           f"semaine : {rec['runs_done']}/{rec['rpw']} sorties, {rec['done_km']:.1f}/{rec['volume']:g} km, "
           f"qualité {rec['quality_done']}/{rec['quality_target']}, sortie longue {'faite' if rec['long_done'] else 'à faire'}",
           f"TSB {rec['tsb']:+g} ({coaching.tsb_label(rec['tsb'])})" if rec["tsb"] is not None else "TSB inconnu"]
    if rec["last"]:
        last = rec["last"]
        ctx.append(f"dernière sortie : {last['date']}, {last.get('structure') or 'course'} {last['distance_km']:g} km")
    lines += ["## Contexte", ""] + [f"- {c}" for c in ctx]
    if rec.get("plan"):
        lines += ["", "## Plan de la semaine", ""] + coaching.render_plan_rows(rec["plan"])
    p = rec["proposal"]
    lines += ["", f"## Proposition : {p['title']}", ""] + [f"- {x}" for x in p["lines"] if x]
    lines += ["", "## Pourquoi", ""] + [f"- {r}" for r in rec["reasons"]]
    if p.get("spec"):
        lines += ["", "## Format montre", "", describe(p["spec"]), "",
                  "`coach next --spec` sort ce format en JSON pour `coach workout push -`."]
    return "\n".join(lines) + "\n"
