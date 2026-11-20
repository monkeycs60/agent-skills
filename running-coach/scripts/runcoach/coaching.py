from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from . import metrics
from .profile import Profile
from .util import CoachError, config_dir, day_fr, fmt_pace, parse_date, parse_day, parse_week, read_json, week_label, week_of

SESSION_TYPES = ("easy", "long", "quality", "race", "rest")
TYPE_FR = {"easy": "footing", "long": "sortie longue", "quality": "qualité", "race": "course", "rest": "repos"}
STATUS_FR = {"done": "✅ fait", "missed": "❌ manqué", "today": "▶ aujourd'hui", "upcoming": "⏳ à venir", "rest": "· repos"}
LONG_CAP_KM = {5.0: 14, 10.0: 18, 21.1: 22, 42.2: 32}


def plan_path():
    return config_dir() / "plan.json"


def load_plan() -> dict[str, Any] | None:
    plan = read_json(plan_path())
    if plan is None:
        return None
    if not isinstance(plan.get("weeks"), dict):
        raise CoachError(f"{plan_path()} : champ weeks (objet « AAAA-Wnn » → semaine) requis")
    for label, week in plan["weeks"].items():
        parse_week(label)
        for i, s in enumerate(week.get("sessions") or []):
            where = f"plan {label} séance {i + 1}"
            if "day" not in s:
                raise CoachError(f"{where} : day requis (mon…sun)")
            parse_day(s["day"])
            if s.get("type", "easy") not in SESSION_TYPES:
                raise CoachError(f"{where} : type parmi {', '.join(SESSION_TYPES)}")
            if s.get("priority", 2) not in (1, 2, 3):
                raise CoachError(f"{where} : priority vaut 1 (clé), 2 ou 3 (facultative)")
    if plan.get("start"):
        parse_date(plan["start"])
    return plan


def plan_week(plan: dict[str, Any] | None, d: date) -> dict[str, Any] | None:
    if not plan:
        return None
    y, w = week_of(d)
    for label, week in plan["weeks"].items():
        if parse_week(label) == (y, w):
            return week
    return None


def week_runs(rows: list[dict[str, Any]], d: date) -> list[dict[str, Any]]:
    y, w = week_of(d)
    return [r for r in rows if r["sport"] == "run" and week_of(date.fromisoformat(r["date"])) == (y, w)]


def adherence(week: dict[str, Any], runs: list[dict[str, Any]], d: date, ref: date) -> list[dict[str, Any]]:
    monday = d - timedelta(days=d.weekday())
    used: set[str] = set()
    out = []
    sessions = sorted(week.get("sessions") or [], key=lambda s: parse_day(s["day"]))
    ordered = sorted(sessions, key=lambda s: {"long": 0, "quality": 1, "race": 1}.get(s.get("type", "easy"), 2))
    matches: dict[int, dict[str, Any]] = {}
    for s in ordered:
        kind = s.get("type", "easy")
        day = monday + timedelta(days=parse_day(s["day"]))
        free = [r for r in runs if r["id"] not in used]
        match = None
        if kind == "long":
            longest = max(free, key=lambda r: r.get("distance_km") or 0, default=None)
            need = 0.75 * s["km"] if s.get("km") else 0
            if longest and (longest.get("kind") == "long" or (need and (longest.get("distance_km") or 0) >= need)):
                match = longest
        elif kind in ("quality", "race"):
            near = [r for r in free if abs((date.fromisoformat(r["date"]) - day).days) <= 1 and r.get("kind") == "quality"]
            match = near[0] if near else next((r for r in free if r.get("kind") == "quality"), None)
        elif kind == "easy":
            near = sorted(free, key=lambda r: abs((date.fromisoformat(r["date"]) - day).days))
            match = next((r for r in near if abs((date.fromisoformat(r["date"]) - day).days) <= 1), None)
        if match:
            used.add(match["id"])
        matches[id(s)] = match
    for s in sessions:
        day = monday + timedelta(days=parse_day(s["day"]))
        match = matches.get(id(s))
        if s.get("type") == "rest":
            status = "rest"
        elif match:
            status = "done"
        elif day < ref:
            status = "missed"
        elif day == ref:
            status = "today"
        else:
            status = "upcoming"
        out.append({**s, "date": day, "status": status, "run": match})
    return out


def phase(profile: Profile, d: date) -> tuple[str, int | None]:
    gd = profile.goal_date
    if not gd:
        return "Entretien", None
    days = (gd - d).days
    if days < 0:
        return ("Récupération après course" if days >= -14 else "Entretien"), days
    if days == 0:
        return "Jour de course", 0
    taper = 21 if (profile.goal_km or 0) >= 30 else 14
    if days <= 7:
        return "Semaine de course", days
    if days <= taper:
        return "Affûtage", days
    if days <= 56:
        return "Spécifique", days
    if days <= 112:
        return "Développement", days
    return "Base", days


def _hr(profile: Profile, zlo: int, zhi: int) -> dict[str, Any]:
    lo = profile.zone_range(zlo)[0]
    hi = profile.zone_range(zhi)[1]
    if zlo == 1:
        lo = max(lo, hi - 25)
    return {"hr": [lo, hi]}


def _pace(profile: Profile, name: str, around: float | None = None) -> dict[str, Any] | None:
    if around:
        return {"pace": [fmt_pace(around - 5), fmt_pace(around + 5)]}
    band = profile.pace_band(name)
    return {"pace": [fmt_pace(band[0]), fmt_pace(band[1])]} if band else None


def _target_txt(t: dict[str, Any] | None) -> str:
    if not t:
        return ""
    if "pace" in t:
        return f"{t['pace'][0]}–{t['pace'][1]}/km"
    return f"FC {t['hr'][0]}–{t['hr'][1]}"


def _wu(profile: Profile, minutes: int = 15) -> dict[str, Any]:
    return {"kind": "warmup", "dur": f"{minutes}:00", "target": _hr(profile, 1, 2)}


def _cd(profile: Profile, minutes: int = 10) -> dict[str, Any]:
    return {"kind": "cooldown", "dur": f"{minutes}:00", "target": _hr(profile, 1, 2)}


def session(kind: str, profile: Profile, volume: float, **kw: Any) -> dict[str, Any]:
    z2 = _hr(profile, 2, 2)
    easy_pace = profile.pace_band("Endurance")
    pace_hint = f", allure indicative {fmt_pace(easy_pace[0])}–{fmt_pace(easy_pace[1])}/km" if easy_pace else ""
    if kind == "rest":
        return {"title": "Repos", "lines": ["Repos complet, ou 20 à 30 min de marche, mobilité ou renforcement léger."], "spec": None}
    if kind == "recovery":
        minutes = kw.get("minutes", 30)
        t = _hr(profile, 1, 1)
        return {"title": f"Footing de récupération — {minutes} min",
                "lines": [f"{minutes} min très faciles en Z1 ({_target_txt(t)}), on doit pouvoir parler sans effort."],
                "spec": {"name": f"Récupération {minutes}'", "steps": [{"kind": "interval", "dur": f"{minutes}:00", "target": t}]}}
    if kind == "easy":
        minutes = kw.get("minutes", 45)
        strides = kw.get("strides", False)
        steps = [{"kind": "interval", "dur": f"{minutes}:00", "target": z2}]
        lines = [f"{minutes} min en Z2 ({_target_txt(z2)}){pace_hint}."]
        if strides:
            steps.append({"kind": "repeat", "times": 6, "steps": [
                {"kind": "interval", "dur": "0:20", "target": {"open": True}},
                {"kind": "recovery", "dur": "1:00", "target": {"open": True}}]})
            lines.append("Finir par 6 accélérations progressives de 20 s, récupération 1 min en trottinant.")
        return {"title": f"Footing — {minutes} min" + (" + lignes droites" if strides else ""), "lines": lines,
                "spec": {"name": f"Footing {minutes}'", "steps": steps}}
    if kind == "long":
        km = kw["km"]
        finish = kw.get("finish_pace")
        steps = [{"kind": "interval", "dist": int((km - (kw.get("finish_km") or 0)) * 1000), "target": z2}]
        lines = [f"{km:g} km en Z2 strict ({_target_txt(z2)}){pace_hint} : la FC ne dépasse pas le haut de Z2, même en fin de sortie."]
        if finish:
            fk = kw["finish_km"]
            steps.append({"kind": "interval", "dist": int(fk * 1000), "target": _pace(profile, "", finish)})
            lines.append(f"Dont les {fk:g} derniers km à l'allure objectif ({fmt_pace(finish)}/km).")
        if km >= 16:
            lines.append("Boire régulièrement ; au-delà de 1 h 15, tester la nutrition prévue pour la course.")
        return {"title": f"Sortie longue — {km:g} km", "lines": lines,
                "spec": {"name": f"Sortie longue {km:g} km", "steps": steps}}
    if kind == "threshold":
        reps, minutes = (2, 10) if volume < 30 else (3, 10) if volume < 50 else (4, 10)
        t = _pace(profile, "Seuil") or _hr(profile, 4, 4)
        return {"title": f"Seuil — {reps} × {minutes} min",
                "lines": [f"15 min d'échauffement en Z1-Z2, puis {reps} × {minutes} min au seuil ({_target_txt(t)} ; "
                          f"FC en Z4 {profile.zone_range(4)[0]}–{profile.zone_range(4)[1]}), récupération 2 min en trottinant, 10 min de retour au calme.",
                          "Effort « confortablement difficile » : on pourrait tenir 1 h. Les répétitions sont régulières, la dernière aussi rapide que la première."],
                "spec": {"name": f"Seuil {reps}x{minutes}'", "steps": [_wu(profile), {"kind": "repeat", "times": reps, "steps": [
                    {"kind": "interval", "dur": f"{minutes}:00", "target": t},
                    {"kind": "recovery", "dur": "2:00", "target": {"open": True}}]}, _cd(profile)]}}
    if kind == "vo2":
        reps, dist = (5, 800) if volume < 30 else (5, 1000) if volume < 50 else (6, 1000)
        t = _pace(profile, "VMA") or _hr(profile, 5, 5)
        return {"title": f"VMA — {reps} × {dist} m",
                "lines": [f"15 min d'échauffement avec 3 accélérations, puis {reps} × {dist} m ({_target_txt(t)}), "
                          f"récupération 2 min en trottinant, 10 min de retour au calme.",
                          "Arrêter la série si l'allure chute de plus de 5 s/km sur deux répétitions de suite."],
                "spec": {"name": f"VMA {reps}x{dist}m", "steps": [_wu(profile), {"kind": "repeat", "times": reps, "steps": [
                    {"kind": "interval", "dist": dist, "target": t},
                    {"kind": "recovery", "dur": "2:00", "target": {"open": True}}]}, _cd(profile)]}}
    if kind == "fartlek":
        reps = 8 if volume < 30 else 10 if volume < 50 else 12
        return {"title": f"Fartlek — {reps} × (1 min vite / 1 min lent)",
                "lines": [f"15 min faciles, puis {reps} × (1 min vite, allure 5-10 km ressentie / 1 min trottinée), 10 min faciles.",
                          "Séance de relance sans chrono strict : vite mais relâché."],
                "spec": {"name": f"Fartlek {reps}x1'", "steps": [_wu(profile), {"kind": "repeat", "times": reps, "steps": [
                    {"kind": "interval", "dur": "1:00", "target": {"open": True}},
                    {"kind": "recovery", "dur": "1:00", "target": {"open": True}}]}, _cd(profile)]}}
    if kind == "race_pace":
        goal_km = profile.goal_km or 10.0
        pace = profile.race_pace()
        taper = kw.get("taper", False)
        if goal_km >= 30:
            reps, dist, rec = (2, 3000, "1 km facile") if taper else (3, 3000, "1 km facile") if volume < 50 else (3, 4000, "1 km facile")
            rec_step = {"kind": "recovery", "dist": 1000, "target": z2}
        elif goal_km >= 15:
            reps, dist, rec = (2, 2000, "3 min") if taper else (3, 3000, "3 min")
            rec_step = {"kind": "recovery", "dur": "3:00", "target": {"open": True}}
        elif goal_km >= 8:
            reps, dist, rec = (3, 1000, "2 min") if taper else (5, 1600, "2 min")
            rec_step = {"kind": "recovery", "dur": "2:00", "target": {"open": True}}
        else:
            reps, dist, rec = (4, 400, "1 min 30") if taper else (6, 800, "2 min")
            rec_step = {"kind": "recovery", "dur": "2:00", "target": {"open": True}}
        t = _pace(profile, "", pace) if pace else _hr(profile, 3, 4)
        name = f"Allure objectif {reps}x{dist / 1000:g} km"
        return {"title": f"Allure objectif — {reps} × {dist / 1000:g} km",
                "lines": [f"15 min d'échauffement, {reps} × {dist / 1000:g} km à l'allure objectif ({_target_txt(t)}), "
                          f"récupération {rec}, 10 min de retour au calme.",
                          "Objectif : mémoriser l'allure, pas la dépasser."],
                "spec": {"name": name, "steps": [_wu(profile), {"kind": "repeat", "times": reps, "steps": [
                    {"kind": "interval", "dist": dist, "target": t}, rec_step]}, _cd(profile)]}}
    if kind == "activation":
        pace = profile.race_pace()
        t = _pace(profile, "", pace) if pace else {"open": True}
        return {"title": "Activation avant course",
                "lines": [f"20 min faciles, puis 3 × 1 min à l'allure objectif ({_target_txt(t) or 'ressentie'}), 1 min de trot entre, 5 min faciles."],
                "spec": {"name": "Activation", "steps": [{"kind": "interval", "dur": "20:00", "target": z2},
                                                         {"kind": "repeat", "times": 3, "steps": [
                                                             {"kind": "interval", "dur": "1:00", "target": t},
                                                             {"kind": "recovery", "dur": "1:00", "target": {"open": True}}]},
                                                         _cd(profile, 5)]}}
    if kind == "race":
        g = profile.goal
        pace = profile.race_pace()
        lines = [f"Jour de course : {g.get('name', 'objectif')} ({g.get('distance_km', '?')} km)."]
        if pace:
            lines.append(f"Allure cible {fmt_pace(pace)}/km ; partir 5 s/km plus lent sur les 2 premiers km.")
        return {"title": "Course", "lines": lines, "spec": None}
    raise CoachError(f"type de séance inconnu : {kind}")


def tsb_label(tsb: float | None) -> str:
    if tsb is None:
        return "inconnue"
    if tsb > 15:
        return "très frais (désentraînement si cela dure)"
    if tsb > 5:
        return "frais"
    if tsb > -10:
        return "équilibre"
    if tsb > -25:
        return "fatigue d'entraînement"
    return "fatigue élevée"


def _volume_target(profile: Profile, weekly: list[dict[str, Any]], d: date) -> float:
    if profile.get("weekly_km"):
        return float(profile.data["weekly_km"])
    y, w = week_of(d)
    current = week_label(y, w)
    past = [x["run_km"] or 0 for x in weekly if x["week"] < current][-4:]
    return round(sum(past) / len(past), 1) if past else 25.0


def _long_km(profile: Profile, volume: float, rows: list[dict[str, Any]], d: date, ph: str) -> float:
    cap = 32.0
    if profile.goal_km:
        cap = LONG_CAP_KM[min(LONG_CAP_KM, key=lambda k: abs(k - profile.goal_km))]
    recent = [r["distance_km"] or 0 for r in rows
              if r["sport"] == "run" and d - timedelta(days=28) <= date.fromisoformat(r["date"]) < d]
    base = max(10.0, 0.3 * volume)
    longest = max(recent, default=0.0)
    if ph == "Affûtage":
        target = 0.65 * max(longest, base)
    elif ph in ("Développement", "Spécifique"):
        target = max(base, longest + 1) if longest else base
    else:
        target = max(base, longest)
    return float(round(min(cap, target)))


def recommend(profile: Profile, rows: list[dict[str, Any]], daily: list[dict[str, Any]], weekly: list[dict[str, Any]],
              plan: dict[str, Any] | None, ref: date) -> dict[str, Any]:
    runs = [r for r in rows if r["sport"] == "run"]
    ran_today = [r for r in runs if r["date"] == ref.isoformat()]
    target = ref + timedelta(days=1) if ran_today else ref
    before = [r for r in runs if r["date"] < target.isoformat()]
    yesterday = [r for r in before if r["date"] == (target - timedelta(days=1)).isoformat()]
    load = metrics.load_on(daily, target)
    tsb = load["tsb"] if load else None
    ph, days_to_goal = phase(profile, target)
    volume = _volume_target(profile, weekly, target)
    wk = [r for r in week_runs(before, target)]
    done_km = sum(r["distance_km"] or 0 for r in wk)
    quality_done = sum(1 for r in wk if r.get("kind") == "quality")
    long_done = any(r.get("kind") == "long" for r in wk)
    rpw = profile.runs_per_week
    remaining_runs = rpw - len(wk)
    last_hard = max((date.fromisoformat(r["date"]) for r in before if r.get("kind") in ("quality", "long")), default=None)
    days_since_hard = (target - last_hard).days if last_hard else None
    quality_target = 2 if rpw >= 5 and ph in ("Développement", "Spécifique") else 1
    if ph in ("Récupération après course", "Semaine de course", "Jour de course"):
        quality_target = 0
    last_quality = next((r for r in reversed(before) if r.get("kind") == "quality"), None)
    reasons: list[str] = []
    kind, kw = "easy", {}
    remaining_km = max(volume - done_km, 0)
    band = profile.pace_band("Endurance")
    easy_pace_min = (band[0] + band[1]) / 120 if band else 6.0
    long_km = _long_km(profile, volume, rows, target, ph)
    easy_km, easy_runs = remaining_km, remaining_runs
    if not long_done and remaining_runs > 1:
        easy_km, easy_runs = max(remaining_km - long_km, 0), remaining_runs - 1
    per_run = easy_km / easy_runs if easy_runs > 0 else 8.0
    easy_min = int(max(30, min(60, round(per_run * easy_pace_min / 5) * 5)))

    plan_rows = None
    pw = plan_week(plan, target)
    if pw:
        plan_rows = adherence(pw, week_runs(before, target), target, target)
        ph = pw.get("phase") or ph

    if not before:
        kind, kw = "easy", {"minutes": 40}
        reasons.append("Aucune sortie enregistrée : commencer par un footing facile pour calibrer FC et allures.")
    elif ph == "Jour de course":
        kind = "race"
        reasons.append("C'est le jour de l'objectif.")
    elif ph == "Récupération après course":
        if days_to_goal is not None and days_to_goal >= -3:
            kind = "rest"
            reasons.append("Moins de 4 jours après la course : repos.")
        else:
            kind, kw = "recovery", {"minutes": 30}
            reasons.append("Deux semaines de récupération après la course : footings courts seulement.")
    elif tsb is not None and tsb < -30:
        kind = "rest"
        reasons.append(f"Fatigue élevée (TSB {tsb:+.0f}) : repos.")
    elif plan_rows is not None:
        kind, kw = _from_plan(plan_rows, target, yesterday, tsb, profile, easy_pace_min, reasons)
    elif remaining_runs <= 0:
        kind = "rest"
        reasons.append(f"Les {rpw} sorties prévues cette semaine sont faites.")
    elif yesterday and any(r.get("kind") in ("quality", "long") for r in yesterday):
        kind, kw = ("rest", {}) if (tsb is not None and tsb < -20) else ("recovery", {"minutes": 30 if volume < 40 else 40})
        reasons.append("Séance dure la veille : récupération.")
    elif ph == "Semaine de course":
        if days_to_goal in (2, 3):
            kind = "activation"
            reasons.append(f"J-{days_to_goal} : activation courte pour garder du rythme sans fatigue.")
        elif days_to_goal == 1:
            kind = "rest"
            reasons.append("Veille de course : repos ou 15 min de trot.")
        else:
            kind, kw = "easy", {"minutes": 30, "strides": True}
            reasons.append("Semaine de course : volume réduit, intensité préservée par quelques accélérations.")
    elif not long_done and target.weekday() >= profile.long_run_day:
        if tsb is not None and tsb < -20:
            kind, kw = "easy", {"minutes": easy_min}
            reasons.append(f"Sortie longue repoussée : fatigue d'entraînement marquée (TSB {tsb:+.0f}).")
        else:
            km = long_km
            kind, kw = "long", {"km": km}
            pace = profile.race_pace()
            if ph == "Spécifique" and pace and (profile.goal_km or 0) >= 15:
                kw.update(finish_pace=pace, finish_km=float(min(8, round(km * 0.3))))
            reasons.append("Sortie longue de la semaine pas encore faite, et c'est son jour.")
    elif (quality_done < quality_target and (days_since_hard is None or days_since_hard >= 2)
          and (tsb is None or tsb >= -20) and (target + timedelta(days=1)).weekday() != profile.long_run_day):
        if ph == "Base":
            kind = "fartlek"
        elif ph in ("Spécifique", "Affûtage"):
            kind, kw = "race_pace", {"taper": ph == "Affûtage"}
        elif last_quality and str(last_quality.get("structure", "")).startswith("Fractionné"):
            kind = "threshold"
        else:
            kind = "vo2" if ph == "Développement" else "threshold"
        since = f"il y a {days_since_hard} j" if days_since_hard is not None else "aucune récente"
        reasons.append(f"Séance de qualité {quality_done + 1}/{quality_target} de la semaine (phase {ph.lower()}), dernière séance dure : {since}.")
    else:
        kind, kw = "easy", {"minutes": easy_min, "strides": ph in ("Développement", "Spécifique") and quality_done == 0}
        reasons.append("Footing pour construire le volume sans fatigue.")
        if (target + timedelta(days=1)).weekday() == profile.long_run_day and not long_done:
            reasons.append("Sortie longue prévue demain : rester facile aujourd'hui.")

    if kind == "plan":
        proposal = kw
    else:
        proposal = session(kind, profile, volume, **kw)
    return {
        "date": target, "ran_today": bool(ran_today), "phase": ph, "days_to_goal": days_to_goal, "tsb": tsb,
        "volume": volume, "done_km": done_km, "runs_done": len(wk), "rpw": rpw, "quality_done": quality_done,
        "quality_target": quality_target, "long_done": long_done, "kind": kind, "proposal": proposal,
        "reasons": reasons, "plan": plan_rows, "last": before[-1] if before else None,
    }


def _from_plan(plan_rows: list[dict[str, Any]], target: date, yesterday: list[dict[str, Any]], tsb: float | None,
               profile: Profile, easy_pace_min: float, reasons: list[str]) -> tuple[str, dict[str, Any]]:
    for s in plan_rows:
        if s["status"] == "missed" and s.get("priority", 2) == 1:
            reasons.append(f"Séance clé manquée le {day_fr(s['date'])} ({s.get('desc') or TYPE_FR[s.get('type', 'easy')]}) : "
                           "la placer à la place de la prochaine séance facultative (priorité 3), à 48 h d'une autre séance dure ; "
                           "ne jamais rattraper une séance facultative.")
    todays = [s for s in plan_rows if s["date"] == target and s["status"] == "today"]
    upcoming = [s for s in plan_rows if s["date"] > target and s["status"] == "upcoming"]
    if not todays:
        reasons.append("Rien au plan aujourd'hui.")
        if upcoming:
            nxt = upcoming[0]
            reasons.append(f"Prochaine séance du plan : {day_fr(nxt['date'])} {nxt['date'].strftime('%d/%m')} — "
                           f"{nxt.get('desc') or TYPE_FR[nxt.get('type', 'easy')]}.")
        else:
            reasons.append("Toutes les séances de la semaine sont passées.")
        return "rest", {}
    s = todays[0]
    stype = s.get("type", "easy")
    hard_yesterday = any(r.get("kind") in ("quality", "long") for r in yesterday)
    if stype in ("quality", "long") and tsb is not None and tsb < -25:
        reasons.append(f"Séance du plan ({s.get('desc') or TYPE_FR[stype]}) remplacée par un footing : TSB {tsb:+.0f}. La décaler de 48 h.")
        return "easy", {"minutes": 40}
    if stype == "quality" and hard_yesterday:
        reasons.append("Séance dure hier : décaler la qualité du plan d'un jour et faire un footing de récupération.")
        return "recovery", {"minutes": 30}
    reasons.append(f"Séance prévue au plan (priorité {s.get('priority', 2)}).")
    if s.get("spec"):
        return "plan", {"title": f"Plan — {s.get('desc') or TYPE_FR[stype]}", "lines": [s.get("desc", "")], "spec": s["spec"]}
    if stype == "long" and s.get("km"):
        built = session("long", profile, 0, km=float(s["km"]))
    elif stype == "easy" and s.get("km"):
        built = session("easy", profile, 0, minutes=int(round(float(s["km"]) * easy_pace_min / 5) * 5))
    elif stype == "rest":
        built = session("rest", profile, 0)
    else:
        built = {"title": "", "lines": [], "spec": None}
    built["title"] = f"Plan — {s.get('desc') or built['title'] or TYPE_FR[stype]}"
    if s.get("desc"):
        built["lines"] = [s["desc"]] + [line for line in built["lines"] if line != s["desc"]]
    if not built.get("spec") and stype == "quality":
        built["lines"].append("Pas de format montre dans le plan : l'agent l'écrit d'après la description (references/plan.md).")
    return "plan", built


def render_plan_rows(plan_rows: list[dict[str, Any]]) -> list[str]:
    lines = ["| Jour | Prévu | Priorité | Statut | Réalisé |", "|---|---|---|---|---|"]
    for s in plan_rows:
        run = s.get("run")
        done = f"{run['distance_km']:g} km, {run['structure']}" if run else ""
        lines.append(f"| {day_fr(s['date'])} {s['date'].strftime('%d/%m')} | {s.get('desc') or TYPE_FR[s.get('type', 'easy')]} | "
                     f"{s.get('priority', 2)} | {STATUS_FR[s['status']]} | {done} |")
    return lines
