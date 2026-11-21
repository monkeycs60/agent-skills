# Training plan and next workout

## Format of `~/.config/running-coach/plan.json`
Optional. Without a plan, `coach next` applies the generic rules below.

```json
{
  "name": "Spring half",
  "start": "2027-01-04",
  "weeks": {
    "2027-W01": {"phase": "Base", "km": 32, "sessions": [
      {"day": "tue", "type": "quality", "priority": 1, "desc": "Fartlek 10 × 1 min", "km": 9},
      {"day": "thu", "type": "easy", "priority": 3, "desc": "Easy run 40 min", "km": 7},
      {"day": "sun", "type": "long", "priority": 1, "desc": "Long run 14 km in Z2", "km": 14}
    ]},
    "2027-W02": {"phase": "Base", "km": 34, "sessions": [
      {"day": "tue", "type": "quality", "priority": 1, "desc": "Threshold 3 × 8 min",
       "spec": {"name": "Threshold 3x8'", "steps": [
         {"kind": "warmup", "dur": "15:00"},
         {"kind": "repeat", "times": 3, "steps": [
           {"kind": "interval", "dur": "8:00", "target": {"pace": ["4:50", "5:00"]}},
           {"kind": "recovery", "dur": "2:00"}]},
         {"kind": "cooldown", "dur": "10:00"}]}}
    ]}
  }
}
```

| Field | Content |
|---|---|
| `start` | plan start; `coach recap` starts from this date |
| `weeks` | key `YYYY-Wnn` (ISO week, Monday → Sunday) |
| `phase`, `km` | displayed label (replaces the computed phase, and drives `coach next` when it is one of the phase names below) and target volume of the week |
| `day` | `mon` … `sun` |
| `type` | `easy`, `long`, `quality`, `race`, `rest` |
| `priority` | 1 key session, 2 important, 3 optional (default 2) |
| `desc` | text shown to the user |
| `km` | planned distance; gives the watch workout for easy runs and long runs |
| `spec` | structured workout, same format as `coach workout push` (example in week 2027-W02), reused by `coach next --spec` |

`coach plan` validates the file and shows the current week.

## Matching completed sessions
- Long run: the longest run of the week, whatever the day, if it is classified as long or reaches 75% of the planned `km`.
- Quality: a quality-type run within one day, otherwise any remaining quality run of the week.
- Easy run: a remaining run within one day.
- Statuses: done, missed (day passed), today, upcoming, rest.

## `coach next` logic
If the user has already run today, the proposal is for tomorrow. First case that applies:
1. no run recorded: 40 min easy run to calibrate;
2. goal day: race; less than 4 days after: rest; up to 14 days after: recovery runs;
3. TSB < −30: rest;
4. plan present for the week: the day's session (rest if there is none), replaced by an easy run if TSB < −25 for a hard session, moved one day if it is a quality session and the day before was hard; a missed key session is flagged with the make-up instruction;
5. the week's runs already done (`runs_per_week`): rest;
6. hard session the day before (quality or long): 30 to 40 min recovery, rest if TSB < −20;
7. race week: activation 3 or 2 days before, rest the day before, otherwise a short easy run with strides;
8. long run not done and long-run day reached: long run (postponed if TSB < −20);
9. quality to do (1 per week, 2 in Build and Specific from 5 runs a week), last hard session 2 or more days ago, TSB ≥ −20, and tomorrow is not long-run day: session by phase;
10. otherwise an easy run, sized on the week's remaining volume excluding the long run.

| Phase (from the goal date) | Proposed quality session |
|---|---|
| Base (more than 16 weeks) or Maintenance (no goal) | fartlek, or threshold in Maintenance |
| Build (16 to 9 weeks) | VO2max and threshold alternately |
| Specific (8 weeks to the taper) | goal pace; long run with a goal-pace finish for half and full marathon |
| Taper (3 weeks for a marathon, 2 otherwise) | goal pace at reduced volume; long run at 65% |
| Race week | activation |

Other phase names: `Race day`, `Post-race recovery` (14 days after the goal). Sizing: threshold 2, 3 or 4 × 10 min and VO2max 5 × 800 m, 5 × 1,000 m or 6 × 1,000 m depending on whether the target volume is under 30, under 50 or above 50 km; long run = the largest of 10 km, 30% of the volume and the longest run of the last 4 weeks (+1 km in Build and Specific), capped at 14, 18, 22 or 32 km for a 5 km, 10 km, half or marathon goal.

`coach next` is a starting proposal: adjust it to what the user reports (sleep, pain, heat, schedule) and say so.

## Writing a plan with the user
- Start from the current volume (`coach recap`), not the dream volume; progress by 10% per week at most, a lighter week every 3 or 4 weeks.
- One or two quality sessions per week, never two days in a row; the long run at 25-35% of the weekly volume.
- Taper: 2 weeks (3 for a marathon), volume cut by 30 to 50%, intensity kept.
- Paces and HR taken from `coach profile`; write a `spec` for the quality sessions the user wants on their watch.
- After writing: `coach plan` to validate, then `coach next` to check the day's proposal.
