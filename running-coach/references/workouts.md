# Structured workouts on the watch (Garmin Connect)

A workout created in Garmin Connect and scheduled on the calendar reaches the watch at the next sync. Other brands are not supported: give them the text description.

## Commands
| Command | Effect |
|---|---|
| `coach workout push <file.json \| -> --date YYYY-MM-DD --dry-run` | validates, shows the summary and the JSON that would be sent, sends nothing |
| `coach workout push <file.json \| -> --date YYYY-MM-DD` | creates the workout in the account then schedules it; without `--date`, it stays in the library |
| `coach workout list` | workouts in the account (id, name) |
| `coach workout delete <id>` | deletes a workout from the account |
| `coach next --spec` | the workout proposed by `coach next`, in the format below |

Always `--dry-run` first, show the summary to the user and send only after their agreement: the command writes to their account.

## Format
```json
{
  "name": "VO2max 6x800m",
  "description": "VO2max block",
  "steps": [
    {"kind": "warmup", "dur": "15:00", "target": {"hr": [110, 145]}},
    {"kind": "repeat", "times": 6, "steps": [
      {"kind": "interval", "dist": 800, "target": {"pace": ["4:10", "4:20"]}},
      {"kind": "recovery", "dur": "2:00", "target": {"open": true}}
    ]},
    {"kind": "cooldown", "dur": "10:00"}
  ]
}
```

| Element | Values |
|---|---|
| `kind` | `warmup`, `cooldown`, `interval` (effort, or continuous running), `recovery`, `rest`, `repeat` |
| step end, exactly one | `dur` (`"mm:ss"`, `"h:mm:ss"` or seconds), `dist` (metres), `lap` (`true`: until the Lap button is pressed) |
| `target`, optional | `{"pace": ["m:ss", "m:ss"]}` in min/km, in any order; `{"hr": [low, high]}` in bpm; `{"open": true}` or absent: open |
| `repeat` | `times` (integer ≥ 1) and `steps`; no `repeat` inside a `repeat` |

- Targets taken from `coach profile`: HR of the targeted zone, paces from the table.
- A 10 s/km pace range keeps the watch from beeping constantly; an HR target suits easy runs and long runs better.
- A long run is written as one `interval` step with `dist` and a Z2 HR target; a goal-pace finish as a second step.
