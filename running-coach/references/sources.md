# Data sources

## Source choice by `coach sync`

| Option | Behaviour |
|---|---|
| `--source auto` (default) | first connected source in profile order (`strava,garmin` by default); if it fails (network, rejected token, outage), the next one |
| `--source strava` or `garmin` | that source only |
| `--source all` | every connected source, deduplicated |
| `--days N` | go back N days (first run: 90; then from the latest known activity minus 2 days) |
| `--details N` | maximum number of runs whose details are downloaded per run (30) |

A watch that does not publish to Strava (or publishes late): `coach profile set --sources garmin,strava`. Other sports are fetched at summary level (duration, HR, distance); only runs get their details.

## Strava
Official API, read-only (scope `read,activity:read_all`).
1. The user creates an application at https://www.strava.com/settings/api: any name, any website, **callback domain `localhost`**.
2. They run, in a terminal, `coach auth strava --client-id <id>`: the Client Secret is asked without echo, so it goes neither through the conversation nor into the shell history. Alternative: export `STRAVA_CLIENT_ID` and `STRAVA_CLIENT_SECRET`, then the agent runs `coach auth strava`. The command saves `~/.config/running-coach/strava.json` (mode 600) and shows the authorization address.
3. The user opens the address and authorizes; the browser lands on `http://localhost/?state=&code=…`, which does not load: this is expected. They copy the full address.
4. `coach auth strava --code '<full address or code>'`. The token then refreshes on its own.
- `coach auth strava --status`: status without a network call. `--reauthorize` shows the authorization address again.
- Strava limits: 100 requests per 15 minutes, 1,000 per day for reads. A detailed run costs 2 requests (streams and laps). At the limit (429), the sync keeps the summaries, stops without waiting and reports how many runs are pending; rerun 15 minutes later.
- Full history: faster through the export (see below) than through the API.

## Garmin Connect
Unofficial `garminconnect` library: Garmin publishes no API for individuals.
1. The user runs the login in a terminal, because it asks for a password and an MFA code: `~/.claude/skills/running-coach/scripts/coach auth garmin login`. `GARMIN_EMAIL` and `GARMIN_PASSWORD` skip the prompt. Never ask for this information in the conversation. Without an interactive terminal, the command stops with a message instead of waiting.
2. Tokens go to `~/.config/running-coach/garmin/` (mode 700) and refresh on their own as long as Garmin accepts them.
- `coach auth garmin status`: one read call to check the account. `logout` deletes the tokens.
- Run details: the original FIT file (one request per run), read like an import.
- Expired or rejected tokens: `coach auth garmin logout`, then log in again. Persistent failure: `install.sh --upgrade` (Garmin regularly changes its login).
- Chinese accounts (garmin.cn): not supported.

## File import, no account
`coach import <files | folders | archives>`; `--sport run` forces the sport.

| Format | What is read | Typical origin |
|---|---|---|
| `.fit` | records, laps, sport, local time | Garmin, Coros, Suunto, Wahoo, Polar watches |
| `.tcx` | points, laps, HR | Garmin Connect, older exports |
| `.gpx` | points, HR (extensions), type | Strava, apps, watches |
| `.json` | Strava activity (API), Garmin activity list (API), `*_summarizedActivities.json` from the Garmin export | scripts, exports |
| `.gz`, `.zip` | decompressed, nested zips included | full exports |

- Full Strava export: Settings › My Account › Download or Delete Your Account › Request Your Archive. `coach import export_<n>.zip` reads `activities/` (compressed FIT, GPX, TCX).
- Full Garmin export: Garmin account › Data Management › Export Your Data. `coach import <archive>.zip` reads `summarizedActivities.json` (summaries of the whole history) and the FIT files of the `UploadedFiles` zips; daily-tracking FIT files (sleep, health) are skipped.
- File without a sport type: sport guessed from speed (running between 1.9 and 6.5 m/s) and flagged.
- Re-importing is safe: a file already present is counted as "already present".

## Normalized format
Each activity is a JSON `activities/<source>-<id>.json`; analyses ignore the source.

| Field | Content |
|---|---|
| `id`, `source`, `source_id` | `strava-123`, `garmin-456`, `file-<hash>` |
| `sport`, `sport_raw` | `run`, `ride`, `swim`, `walk`, `hike`, `strength`, `other`; original label |
| `start_utc`, `start_local` | start in UTC and in the activity's local time |
| `distance_m`, `moving_s`, `elapsed_s` | distance, moving time, total time |
| `avg_hr`, `max_hr`, `elev_gain_m` | summary |
| `laps` | `start_s`, `distance_m`, `moving_s`, `elapsed_s`, `avg_hr`, `max_hr` |
| `samples` | aligned series `t` (s since start), `d` (cumulative m), `hr`, `alt` |
| `detail` | 2 full recording, 1 laps, 0 summary |

## Deduplication
- Same id: the most detailed version stays.
- Different sources: same activity if the starts are less than 3 minutes apart and the distances within 5% (at least 300 m); the most detailed version replaces the other, otherwise the new one is ignored.

## Error messages

| Message | Cause | Action |
|---|---|---|
| "No source connected" (code 2) | neither Strava nor Garmin | connect a source or `coach import` |
| "Strava refuses access (401)" | authorization revoked or insufficient scope | `coach auth strava --reauthorize`, then `--code` |
| "Strava rate limit reached" | 100 requests in 15 min | rerun later; nothing is lost |
| "Garmin tokens expired or rejected" | tokens too old | `coach auth garmin logout`, then `login` by the user |
| "garminconnect library missing" | partial install | `install.sh` |
| "skipped: FIT file of type …" | tracking file, not an activity | none |
| "sport guessed from speed" | file without a type | check, rerun with `--sport` |
