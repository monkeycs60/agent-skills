# Analyzing a session or a week

## Session report grid
`coach analyze` supplies the numbers; the answer to the user interprets them, in this order:
1. Verdict in one or two sentences: did the session do its job (recover, build endurance, work on threshold…)?
2. Context: session planned that day, phase, fatigue before the session (TSB of the day before).
3. Structure: km splits or laps; spot warm-up, block, recoveries, cool-down, drift at the end of the run.
4. Metrics: TRIMP, time in zones, EF and decoupling for endurance runs.
5. Comparison with sessions of the same type ("Comparable sessions" table): pace at equal HR, EF.
6. Load impact: CTL, ATL and TSB before and after.
7. Consequence: what it changes for the next session.

## Formulas

| Measure | Computation |
|---|---|
| TRIMP (Banister) | Σ duration (min) × r × k × e^(b·r), with r = (HR − resting HR) / (max HR − resting HR) clamped to [0, 1]; k = 0.64, b = 1.92 (men); k = 0.86, b = 1.67 (women). Integrated second by second when the recording exists, otherwise on the average HR. No resting HR: 55. No HR: 1.2 per minute of running (0.9 cycling, 0.8 strength, 1 other), marked "estimated". |
| CTL (fitness) | CTL(d) = CTL(d−1) + (TRIMP(d) − CTL(d−1)) / 42 |
| ATL (fatigue) | ATL(d) = ATL(d−1) + (TRIMP(d) − ATL(d−1)) / 7 |
| TSB (freshness) | CTL(d−1) − ATL(d−1): form in the morning, before the day's session |
| Series start | CTL = ATL = average daily TRIMP of the first 28 days of data, so the athlete is not assumed to start from zero |
| Splits | exact cut at each kilometre by interpolation; moving time only (speed ≥ 0.8 m/s, gaps over 30 s excluded); otherwise automatic 1 km laps |
| EF (efficiency) | speed (m/min) / average HR, over full km excluding the first km; easy runs and long runs only |
| Decoupling | (EF 1st half − EF 2nd half) / EF 1st half × 100; at least 6 km and 40 min excluding the first km |

TRIMP values depend on the profile: changing max HR, resting HR or sex recomputes the whole history.

## Reading the indicators

| Indicator | Benchmarks |
|---|---|
| TSB | > +15 very fresh (detraining if it lasts); +5 to +15 fresh, good before a race; −10 to +5 balanced; −25 to −10 normal training fatigue in a block; < −25 high fatigue, lighten up; < −30 rest |
| Decoupling | < 5% solid endurance at this pace; 5-10% fair; > 10% pace too fast for the duration, heat, dehydration or aerobic base still to build |
| EF | only compare between similar easy runs (terrain, heat); a rise over 4 to 8 weeks signals aerobic progress |
| Time in zones | easy run or long run: more than 20-25% above Z2 = too fast; week: about 80% in Z1-Z2 |
| Volume | increase of 10-15% per week at most; a lighter week (−20 to −30%) every 3 or 4 weeks |

## Structure detection
On full km. "Fast" = pace ≤ 92% of the session's 3rd pace quartile, faster than 1.12 × threshold pace when known, and HR at least in Z3 when measured. "Long" = at least `long_run_min_minutes` (75 min by default).

| Label | Criterion | Type |
|---|---|---|
| `Intervals N×D` | manual laps: at least 3 fast laps (> 108% of the median lap speed) alternating with slow laps; D = the most regular distance or duration | quality |
| `Tempo/threshold` | continuous block of at least 3 fast km, or the whole session at threshold pace, or at least 3 km in Z4 | quality |
| `Continuous race pace` | whole session between threshold and marathon pace, at least 6 km | quality |
| `Progression run` | fast km grouped at the end of the session | quality |
| `Intervals` | at least 3 non-contiguous fast km | quality |
| `Strides` | 1 or 2 isolated fast km | easy |
| `Long run`, `Long run, fast finish`, `Long run with block` | long, without, with fast km at the end, with a block | long run |
| `Easy run`, `Recovery run` | no fast km; median HR in Z1 for recovery | easy |
| `Hard session`, `Long run, hard`, `Short run` | summary only (no splits): average HR in Z3 or higher; under 3 km | depends |

Short intervals (200-400 m) diluted in km splits look like an uneven easy run: manual laps or HR reveal them. Without laps, say so rather than assert.

## Weekly report (`coach week`)
Read in order: volume against the target and the average of the previous 4 weeks, number of quality sessions (1 to 2), long run (25 to 35% of the volume), intensity distribution, plan adherence, TSB trend. Conclude with one to three priorities for the next week.

## Measurement pitfalls
- Summary only (`detail` 0): no splits, no fine structure. `coach sync --details 50` or importing the original FIT completes the analysis.
- Automatic laps: they cut on a GPS point, so slightly beyond 1,000 m; the last lap is partial.
- Optical wrist sensor: aberrant HR spikes at the start or in cold weather; an isolated max HR far above the profile is probably an artefact.
- Treadmill: the watch distance is often 5 to 10% off; judge on HR.
- Heat, elevation, wind: HR rises at equal pace; do not conclude to a loss of form from a single session.
- Noisy GPS altitude: elevation gain is smoothed (3 m threshold) and stays approximate.
