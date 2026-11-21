# Install and profile

## Install
`bash install.sh` (safe to rerun, `--help` for help):
1. link `~/.claude/skills/running-coach` to the skill, and in `~/.codex/skills` or `~/.agents/skills` if they exist;
2. `.venv` environment inside the skill: with `uv`, Python 3.12 (downloaded if needed); otherwise the most recent system Python 3.10+;
3. `requirements.txt`: `fitdecode` (FIT files) and `garminconnect` (Garmin Connect). If `garminconnect` does not install, Strava and import still work;
4. configuration (mode 700) and data folders;
5. offline trial: import of the files in `tests/fixtures/files` into a temporary folder and a weekly report.

| Situation | Consequence | Fix |
|---|---|---|
| Python 3.10 or 3.11 without uv | `garminconnect` is capped at 0.3.2 (later versions require 3.12); the Garmin login breaks sooner when Garmin changes its authentication | install uv, delete `.venv`, rerun `install.sh` |
| Garmin login broken after a Garmin update | errors at login or sync | `install.sh --upgrade` |
| `python3 -m venv` refused (Debian, Ubuntu) | no environment | `sudo apt install python3-venv` or install uv |

## Folders and variables

| Item | Default | Variable |
|---|---|---|
| Configuration | `~/.config/running-coach/` (or `$XDG_CONFIG_HOME/running-coach`) | `RUNNING_COACH_CONFIG` |
| Data | `~/.local/share/running-coach/` (or `$XDG_DATA_HOME/running-coach`) | `RUNNING_COACH_DATA` |
| Launcher Python | the skill's `.venv/bin/python` | `RUNNING_COACH_PYTHON` |
| Strava application | `strava.json` | `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET` (take precedence) |
| First Garmin login | interactive prompt | `GARMIN_EMAIL`, `GARMIN_PASSWORD` |

Data: `activities/<id>.json` (normalized format), `index.json`, `metrics/activities.csv` (one row per activity), `metrics/daily.csv` (daily load), `metrics/weekly.csv`, `reports/runs/*.md`, `reports/weekly/*.md`, `state.json` (last syncs).

## Questions to build the profile
Ask in this order; "I don't know" is an acceptable answer except for the goal:
1. Measured max HR (test, sprint finish of a race)? Otherwise: birth year, refined later with `--hr-max auto` after an import.
2. Resting HR on waking? It enables Karvonen zones, more accurate than % of max HR.
3. Zones measured in a lab or by a field test? They override any computation (`--hr-zones`).
4. A recent race (distance and time) or a known threshold pace? It gives every pace.
5. Goal: name, distance, date, target time (optional). Without a goal: "maintenance" phase.
6. Target weekly volume, number of runs per week, long-run day.
7. Lasting constraints: injuries, impossible days, other sports (`--note`, repeatable).

Example:
```bash
coach profile set --hr-max 188 --hr-rest 52 --sex male --ref-race 10 46:30 \
  --goal-name "Spring marathon" --goal-distance 42.195 --goal-date 2027-04-11 --goal-time 3:55:00 \
  --weekly-km 40 --runs-per-week 4 --long-run-day sun --note "Sensitive Achilles tendon: no hills"
```
`coach profile` shows the profile, the zones and the computed paces. Changing the profile recomputes every metric.

## `profile.json` fields

| Key | Option | Use | Default |
|---|---|---|---|
| `hr_max` | `--hr-max N\|auto` | zones, TRIMP | highest value seen in the data, otherwise Tanaka (`birth_year`), otherwise 185; everything is then marked provisional |
| `hr_rest` | `--hr-rest` | Karvonen zones, TRIMP | 55 for TRIMP, zones as % of max HR |
| `hr_zones` | `--hr-zones a,b,c,d` | upper bounds of Z1 to Z4 | computed |
| `sex` | `--sex male\|female` | TRIMP coefficients | male coefficients |
| `birth_year` | `--birth-year` | estimated max HR 208 − 0.7 × age | — |
| `threshold_pace` | `--threshold-pace m:ss` | paces | derived from `reference_race` |
| `reference_race` | `--ref-race KM TIME` | threshold pace by Riegel | — |
| `goal` | `--goal-name`, `--goal-distance`, `--goal-date`, `--goal-time`, `--clear-goal` | phases, target pace, maximum long run | none |
| `weekly_km` | `--weekly-km` | target volume | average of the last 4 weeks |
| `runs_per_week` | `--runs-per-week` | sessions per week | 4 |
| `long_run_day` | `--long-run-day` | long-run day | `sun` |
| `long_run_min_minutes` | `--long-run-min` | duration from which a run is "long" | 75 |
| `sources` | `--sources garmin,strava` | `coach sync` order | `strava,garmin` |
| `notes` | `--note` | lasting constraints | — |

`--unset KEY` removes a key.

## Heart rate zones
Priority: the profile's `hr_zones`, then Karvonen if `hr_rest` is known, then % of max HR.

| Zone | Karvonen (% of HR reserve) | % max HR | Use |
|---|---|---|---|
| Z1 Recovery | < 60 | < 70 | recovery, warm-up |
| Z2 Endurance | 60-74 | 70-80 | easy runs, long runs (cap) |
| Z3 Tempo/marathon | 74-84 | 80-87 | marathon pace, tempo |
| Z4 Threshold | 84-91 | 87-93 | threshold |
| Z5 VO2max | > 91 | > 93 | short intervals |

## Paces
Threshold pace T is the pace you can hold for about an hour. From a recent race: distance sustainable in 60 min by Riegel's formula (exponent 1.06), then T = 60 min / that distance.

| Zone | Ratio to T |
|---|---|
| Recovery | > 1.35 T |
| Endurance | 1.20-1.35 T |
| Steady | 1.10-1.20 T |
| Marathon pace | 1.04-1.10 T |
| Threshold | 0.97-1.04 T |
| VO2max | 0.88-0.97 T |
| Speed | < 0.88 T |

Goal pace: target time / distance; without a target time, T × 0.95 (5 km), 0.985 (10 km), 1.03 (half), 1.075 (marathon).
