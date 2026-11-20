from __future__ import annotations

from typing import Any

from .util import CoachError, fmt_hms, fmt_pace, parse_duration, parse_pace

STEP_TYPES = {
    "warmup": (1, "warmup"),
    "cooldown": (2, "cooldown"),
    "interval": (3, "interval"),
    "recovery": (4, "recovery"),
    "rest": (5, "rest"),
}
KIND_FR = {"warmup": "échauffement", "cooldown": "retour au calme", "interval": "course", "recovery": "récupération", "rest": "repos"}
END_TIME = {"conditionTypeId": 2, "conditionTypeKey": "time", "displayOrder": 2, "displayable": True}
END_DIST = {"conditionTypeId": 3, "conditionTypeKey": "distance", "displayOrder": 3, "displayable": True}
END_LAP = {"conditionTypeId": 1, "conditionTypeKey": "lap.button", "displayOrder": 1, "displayable": True}
END_ITER = {"conditionTypeId": 7, "conditionTypeKey": "iterations", "displayOrder": 7, "displayable": False}
# Live workout-service IDs: pace.zone is 6 and distance is 3; the constants shipped in
# garminconnect.workout (DISTANCE=1, OPEN=6) are rejected or misread by the API.
TGT_NONE = {"workoutTargetTypeId": 1, "workoutTargetTypeKey": "no.target", "displayOrder": 1}
TGT_HR = {"workoutTargetTypeId": 4, "workoutTargetTypeKey": "heart.rate.zone", "displayOrder": 4}
TGT_PACE = {"workoutTargetTypeId": 6, "workoutTargetTypeKey": "pace.zone", "displayOrder": 6}
RUNNING = {"sportTypeId": 1, "sportTypeKey": "running", "displayOrder": 1}
DEFAULT_PACE_S = 330.0


def _check_step(step: Any, path: str) -> None:
    if not isinstance(step, dict):
        raise CoachError(f"{path} : une étape est un objet JSON")
    kind = step.get("kind")
    if kind == "repeat":
        if not isinstance(step.get("times"), int) or step["times"] < 1:
            raise CoachError(f"{path} : repeat exige times (entier ≥ 1)")
        if not step.get("steps"):
            raise CoachError(f"{path} : repeat exige steps")
        for i, sub in enumerate(step["steps"]):
            if isinstance(sub, dict) and sub.get("kind") == "repeat":
                raise CoachError(f"{path}.steps[{i}] : un repeat ne peut pas contenir de repeat")
            _check_step(sub, f"{path}.steps[{i}]")
        return
    if kind not in STEP_TYPES:
        raise CoachError(f"{path} : kind inconnu {kind!r} ({', '.join(list(STEP_TYPES) + ['repeat'])})")
    ends = [k for k in ("dur", "dist", "lap") if step.get(k) not in (None, False)]
    if len(ends) != 1:
        raise CoachError(f"{path} : exactement une fin parmi dur (\"mm:ss\"), dist (mètres) ou lap (true)")
    if "dur" in ends:
        parse_duration(step["dur"])
    if "dist" in ends and (not isinstance(step["dist"], (int, float)) or step["dist"] <= 0):
        raise CoachError(f"{path} : dist en mètres, nombre positif")
    target = step.get("target")
    if target is None or target.get("open"):
        return
    if "pace" in target:
        if len(target["pace"]) != 2:
            raise CoachError(f"{path} : target.pace = [\"m:ss\", \"m:ss\"]")
        for p in target["pace"]:
            parse_pace(p)
    elif "hr" in target:
        lo, hi = target["hr"]
        if not (40 <= min(lo, hi) and max(lo, hi) <= 230):
            raise CoachError(f"{path} : target.hr = [bas, haut] en bpm")
    else:
        raise CoachError(f"{path} : target = {{\"pace\": […]}}, {{\"hr\": […]}} ou {{\"open\": true}}")


def validate(spec: Any) -> dict[str, Any]:
    if not isinstance(spec, dict) or not spec.get("name"):
        raise CoachError("la séance exige un champ name")
    if not spec.get("steps"):
        raise CoachError("la séance exige une liste steps non vide")
    for i, step in enumerate(spec["steps"]):
        _check_step(step, f"steps[{i}]")
    return spec


def _target(target: dict | None) -> dict[str, Any]:
    if not target or target.get("open"):
        return {"targetType": TGT_NONE}
    if "pace" in target:
        speeds = [1000.0 / parse_pace(p) for p in target["pace"]]
        return {"targetType": TGT_PACE, "targetValueOne": round(min(speeds), 3), "targetValueTwo": round(max(speeds), 3)}
    lo, hi = target["hr"]
    return {"targetType": TGT_HR, "targetValueOne": float(min(lo, hi)), "targetValueTwo": float(max(lo, hi))}


def _step_seconds(step: dict[str, Any]) -> float:
    if step.get("kind") == "repeat":
        return step["times"] * sum(_step_seconds(s) for s in step["steps"])
    if "dur" in step:
        return parse_duration(step["dur"])
    if "dist" in step:
        pace = DEFAULT_PACE_S
        target = step.get("target") or {}
        if "pace" in target:
            pace = sum(parse_pace(p) for p in target["pace"]) / 2
        return step["dist"] / 1000 * pace
    return 60.0


def _step_meters(step: dict[str, Any]) -> float:
    if step.get("kind") == "repeat":
        return step["times"] * sum(_step_meters(s) for s in step["steps"])
    if "dist" in step:
        return float(step["dist"])
    target = step.get("target") or {}
    pace = sum(parse_pace(p) for p in target["pace"]) / 2 if "pace" in target else DEFAULT_PACE_S
    return _step_seconds(step) / pace * 1000


def _build(steps: list[dict[str, Any]], counter: list[int]) -> list[dict[str, Any]]:
    out = []
    for step in steps:
        counter[0] += 1
        order = counter[0]
        if step["kind"] == "repeat":
            out.append({
                "type": "RepeatGroupDTO", "stepOrder": order,
                "stepType": {"stepTypeId": 6, "stepTypeKey": "repeat", "displayOrder": 6},
                "numberOfIterations": step["times"], "workoutSteps": _build(step["steps"], counter),
                "endCondition": END_ITER, "endConditionValue": float(step["times"]), "smartRepeat": False,
            })
            continue
        type_id, key = STEP_TYPES[step["kind"]]
        item: dict[str, Any] = {"type": "ExecutableStepDTO", "stepOrder": order,
                                "stepType": {"stepTypeId": type_id, "stepTypeKey": key, "displayOrder": type_id}}
        if "dur" in step:
            item.update(endCondition=END_TIME, endConditionValue=parse_duration(step["dur"]))
        elif "dist" in step:
            item.update(endCondition=END_DIST, endConditionValue=float(step["dist"]))
        else:
            item.update(endCondition=END_LAP)
        item.update(_target(step.get("target")))
        out.append(item)
    return out


def payload(spec: dict[str, Any]) -> dict[str, Any]:
    validate(spec)
    data = {
        "workoutName": spec["name"],
        "sportType": RUNNING,
        "estimatedDurationInSecs": int(sum(_step_seconds(s) for s in spec["steps"])),
        "workoutSegments": [{"segmentOrder": 1, "sportType": RUNNING, "workoutSteps": _build(spec["steps"], [0])}],
        "author": {},
    }
    if spec.get("description"):
        data["description"] = spec["description"]
    return data


def _target_text(target: dict | None) -> str:
    if not target or target.get("open"):
        return "libre"
    if "pace" in target:
        a, b = sorted(parse_pace(p) for p in target["pace"])
        return f"{fmt_pace(a)}–{fmt_pace(b)}/km"
    lo, hi = sorted(target["hr"])
    return f"FC {lo:.0f}–{hi:.0f}"


def _step_text(step: dict[str, Any]) -> str:
    if step["kind"] == "repeat":
        inner = " + ".join(_step_text(s) for s in step["steps"])
        return f"{step['times']} × ({inner})"
    if "dur" in step:
        end = fmt_hms(parse_duration(step["dur"]))
    elif "dist" in step:
        end = f"{step['dist']:g} m" if step["dist"] < 2000 else f"{step['dist'] / 1000:g} km"
    else:
        end = "jusqu'au tour"
    return f"{KIND_FR[step['kind']]} {end} @ {_target_text(step.get('target'))}"


def describe(spec: dict[str, Any]) -> str:
    validate(spec)
    seconds = sum(_step_seconds(s) for s in spec["steps"])
    meters = sum(_step_meters(s) for s in spec["steps"])
    lines = [f"**{spec['name']}** — environ {fmt_hms(seconds)}, {meters / 1000:.1f} km"]
    lines += [f"- {_step_text(s)}" for s in spec["steps"]]
    return "\n".join(lines)
