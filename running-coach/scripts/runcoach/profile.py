from __future__ import annotations

import hashlib
import json
import math
from datetime import date
from typing import Any

from .util import CoachError, config_dir, fmt_hms, fmt_pace, parse_date, parse_day, parse_duration, parse_pace, read_json, write_json

ZONE_NAMES = ["Z1 Récupération", "Z2 Endurance", "Z3 Tempo/marathon", "Z4 Seuil", "Z5 VMA"]
HRR_BOUNDS = (0.60, 0.74, 0.84, 0.91)
HRMAX_BOUNDS = (0.70, 0.80, 0.87, 0.93)
PACE_ZONES = [
    ("Récupération", 1.35, None),
    ("Endurance", 1.20, 1.35),
    ("Endurance active", 1.10, 1.20),
    ("Allure marathon", 1.04, 1.10),
    ("Seuil", 0.97, 1.04),
    ("VMA", 0.88, 0.97),
    ("Vitesse", None, 0.88),
]
RACE_FACTORS = {5.0: 0.95, 10.0: 0.985, 21.1: 1.03, 42.2: 1.075}
SOURCES = ("strava", "garmin")
METRIC_KEYS = ("sex", "hr_max", "hr_rest", "hr_zones", "threshold_pace", "reference_race", "long_run_min_minutes")
DEFAULT_HR_MAX = 185


def profile_path():
    return config_dir() / "profile.json"


def riegel_threshold(distance_km: float, time_s: float) -> float:
    d60 = distance_km * (3600.0 / time_s) ** (1 / 1.06)
    return 3600.0 / d60


def race_factor(distance_km: float) -> float:
    best = min(RACE_FACTORS, key=lambda d: abs(math.log(d / distance_km)))
    return RACE_FACTORS[best]


class Profile:
    def __init__(self, data: dict[str, Any] | None, observed_hr_max: float | None = None):
        self.exists = data is not None
        self.data = dict(data or {})
        self.observed_hr_max = observed_hr_max
        self.validate()

    def get(self, key: str, default: Any = None) -> Any:
        value = self.data.get(key)
        return default if value is None else value

    def validate(self) -> None:
        d = self.data
        for key in ("hr_max", "hr_rest", "weekly_km", "runs_per_week", "long_run_min_minutes"):
            if d.get(key) is not None and not isinstance(d[key], (int, float)):
                raise CoachError(f"profil : {key} doit être un nombre")
        if d.get("hr_max") and d.get("hr_rest") and d["hr_rest"] >= d["hr_max"]:
            raise CoachError("profil : hr_rest doit être inférieure à hr_max")
        zones = d.get("hr_zones")
        if zones is not None and (len(zones) != 4 or sorted(zones) != list(zones)):
            raise CoachError("profil : hr_zones = 4 bornes hautes croissantes (Z1 à Z4), par exemple [130, 148, 160, 170]")
        if d.get("sex") not in (None, "male", "female"):
            raise CoachError("profil : sex vaut male ou female")
        if d.get("threshold_pace") is not None:
            parse_pace(d["threshold_pace"])
        race = d.get("reference_race")
        if race is not None:
            if not race.get("distance_km") or not race.get("time"):
                raise CoachError("profil : reference_race = {distance_km, time}")
            parse_duration(race["time"])
        goal = d.get("goal")
        if goal is not None:
            if goal.get("date"):
                parse_date(goal["date"])
            if goal.get("target_time"):
                parse_duration(goal["target_time"])
            if goal.get("target_time") and not goal.get("distance_km"):
                raise CoachError("profil : goal.distance_km est requis avec goal.target_time")
        if d.get("long_run_day") is not None:
            parse_day(d["long_run_day"])
        for s in d.get("sources") or []:
            if s not in SOURCES:
                raise CoachError(f"profil : source inconnue {s!r} (strava, garmin)")

    @property
    def hr_max(self) -> float:
        if self.data.get("hr_max"):
            return float(self.data["hr_max"])
        if self.observed_hr_max:
            return float(self.observed_hr_max)
        if self.data.get("birth_year"):
            return round(208 - 0.7 * (date.today().year - int(self.data["birth_year"])))
        return DEFAULT_HR_MAX

    @property
    def hr_max_source(self) -> str:
        if self.data.get("hr_max"):
            return "profil"
        if self.observed_hr_max:
            return "maximum observé dans les données (provisoire)"
        if self.data.get("birth_year"):
            return "formule de Tanaka (provisoire)"
        return "valeur par défaut (provisoire)"

    @property
    def hr_rest(self) -> float | None:
        return float(self.data["hr_rest"]) if self.data.get("hr_rest") else None

    @property
    def provisional(self) -> bool:
        return not self.data.get("hr_max")

    @property
    def hr_bounds(self) -> list[float]:
        if self.data.get("hr_zones"):
            return [float(x) for x in self.data["hr_zones"]]
        hmax, rest = self.hr_max, self.hr_rest
        if rest:
            return [round(rest + f * (hmax - rest)) for f in HRR_BOUNDS]
        return [round(f * hmax) for f in HRMAX_BOUNDS]

    @property
    def zone_method(self) -> str:
        if self.data.get("hr_zones"):
            return "bornes du profil"
        return "Karvonen (% FC de réserve)" if self.hr_rest else "% FC max"

    def zone_ranges(self) -> list[tuple[str, float, float]]:
        b = self.hr_bounds
        lows = [self.hr_rest or 0] + b
        highs = b + [self.hr_max]
        return [(ZONE_NAMES[i], lows[i], highs[i]) for i in range(5)]

    def zone_of(self, hr: float | None) -> int | None:
        if not hr:
            return None
        for i, bound in enumerate(self.hr_bounds):
            if hr < bound:
                return i + 1
        return 5

    def zone_range(self, zone: int) -> tuple[int, int]:
        _, lo, hi = self.zone_ranges()[zone - 1]
        return int(round(lo)), int(round(hi))

    @property
    def threshold_s(self) -> float | None:
        if self.data.get("threshold_pace"):
            return parse_pace(self.data["threshold_pace"])
        race = self.data.get("reference_race")
        if race:
            return riegel_threshold(float(race["distance_km"]), parse_duration(race["time"]))
        return None

    @property
    def threshold_source(self) -> str:
        if self.data.get("threshold_pace"):
            return "profil"
        if self.data.get("reference_race"):
            r = self.data["reference_race"]
            return f"estimée depuis {r['distance_km']} km en {r['time']} (Riegel)"
        return "inconnue"

    def pace_ranges(self) -> list[tuple[str, float | None, float | None]]:
        t = self.threshold_s
        if not t:
            return []
        return [(name, lo * t if lo else None, hi * t if hi else None) for name, lo, hi in PACE_ZONES]

    def pace_zone_of(self, pace_s: float | None) -> str:
        t = self.threshold_s
        if not t or not pace_s:
            return "—"
        ratio = pace_s / t
        for name, lo, hi in PACE_ZONES:
            if (lo is None or ratio >= lo) and (hi is None or ratio < hi):
                return name
        return "—"

    def pace_band(self, name: str) -> tuple[float, float] | None:
        t = self.threshold_s
        if not t:
            return None
        for zname, lo, hi in PACE_ZONES:
            if zname == name:
                lo = lo or hi * 0.92
                hi = hi or lo * 1.10
                return lo * t, hi * t
        return None

    @property
    def goal(self) -> dict[str, Any]:
        return self.data.get("goal") or {}

    @property
    def goal_date(self) -> date | None:
        return parse_date(self.goal["date"]) if self.goal.get("date") else None

    @property
    def goal_km(self) -> float | None:
        return float(self.goal["distance_km"]) if self.goal.get("distance_km") else None

    def race_pace(self) -> float | None:
        if self.goal.get("target_time") and self.goal_km:
            return parse_duration(self.goal["target_time"]) / self.goal_km
        if self.threshold_s and self.goal_km:
            return self.threshold_s * race_factor(self.goal_km)
        return None

    @property
    def trimp_coeffs(self) -> tuple[float, float]:
        return (0.86, 1.67) if self.data.get("sex") == "female" else (0.64, 1.92)

    @property
    def sources(self) -> list[str]:
        return list(self.data.get("sources") or SOURCES)

    @property
    def long_run_min(self) -> float:
        return float(self.get("long_run_min_minutes", 75))

    @property
    def long_run_day(self) -> int:
        return parse_day(self.get("long_run_day", "sun"))

    @property
    def runs_per_week(self) -> int:
        return int(self.get("runs_per_week", 4))

    def metrics_hash(self) -> str:
        subset = {k: self.data.get(k) for k in METRIC_KEYS}
        subset["_hr_max"] = self.hr_max
        return hashlib.sha1(json.dumps(subset, sort_keys=True, default=str).encode()).hexdigest()[:12]

    def describe(self) -> str:
        lines = ["# Profil athlète", ""]
        if not self.exists:
            lines += ["_Aucun profil : `coach profile set --hr-max N …` le crée._", ""]
        lines.append(f"- FC max : {self.hr_max:.0f} bpm ({self.hr_max_source})")
        lines.append(f"- FC repos : {self.hr_rest:.0f} bpm" if self.hr_rest else "- FC repos : inconnue (zones en % FC max)")
        sex = {"male": "homme", "female": "femme"}.get(self.data.get("sex"), "non renseigné, coefficients masculins")
        lines.append(f"- Sexe (coefficients TRIMP) : {sex}")
        t = self.threshold_s
        lines.append(f"- Allure seuil : {fmt_pace(t)}/km ({self.threshold_source})" if t else "- Allure seuil : inconnue (allures non calculées)")
        g = self.goal
        if g:
            target = f", objectif {g['target_time']}" if g.get("target_time") else ""
            pace = self.race_pace()
            pace_txt = f", allure {fmt_pace(pace)}/km" if pace else ""
            lines.append(f"- Objectif : {g.get('name', 'course')} — {g.get('distance_km', '?')} km le {g.get('date', '?')}{target}{pace_txt}")
        else:
            lines.append("- Objectif : aucun")
        lines.append(f"- Volume visé : {self.data['weekly_km']} km/sem" if self.data.get("weekly_km") else "- Volume visé : moyenne des 4 dernières semaines")
        day = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"][self.long_run_day]
        lines.append(f"- Sorties par semaine : {self.runs_per_week} ; sortie longue le {day}, à partir de {self.long_run_min:.0f} min")
        lines.append(f"- Sources : {', '.join(self.sources)}")
        for note in self.data.get("notes") or []:
            lines.append(f"- Note : {note}")
        lines += ["", f"## Zones FC ({self.zone_method})", "", "| Zone | FC |", "|---|---|"]
        for name, lo, hi in self.zone_ranges():
            lines.append(f"| {name} | {lo:.0f}–{hi:.0f} |")
        paces = self.pace_ranges()
        if paces:
            lines += ["", "## Allures (déduites de l'allure seuil)", "", "| Zone | min/km |", "|---|---|"]
            for name, lo, hi in paces:
                if lo is None:
                    rng = f"< {fmt_pace(hi)}"
                elif hi is None:
                    rng = f"> {fmt_pace(lo)}"
                else:
                    rng = f"{fmt_pace(lo)}–{fmt_pace(hi)}"
                lines.append(f"| {name} | {rng} |")
            if self.goal_km:
                rp = self.race_pace()
                lines.append(f"| Allure objectif ({self.goal_km:g} km) | {fmt_pace(rp)} → {fmt_hms(rp * self.goal_km)} |")
        return "\n".join(lines)


def load_profile(observed_hr_max: float | None = None) -> Profile:
    return Profile(read_json(profile_path()), observed_hr_max)


def save_profile(data: dict[str, Any]) -> Profile:
    profile = Profile(data)
    write_json(profile_path(), profile.data)
    return profile
