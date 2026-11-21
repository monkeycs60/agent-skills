from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"
sys.path.insert(0, str(HERE.parent / "scripts"))

from runcoach import cli, garmin, metrics, store, strava, util, workout  # noqa: E402
from runcoach.profile import Profile  # noqa: E402


def run(*argv: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = cli.main(list(argv))
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def http_error(url: str, code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(url, code, "error", {}, io.BytesIO(b"{}"))


class StravaRouter:
    def __init__(self, fail_list: int | None = None, fail_streams: int | None = None):
        self.calls: list[str] = []
        self.fail_list, self.fail_streams = fail_list, fail_streams

    def __call__(self, req, timeout=None):
        url = req.full_url
        self.calls.append(url)
        api = FIX / "strava_api"
        if url.startswith(strava.TOKEN_URL):
            return Response((api / "token_refresh.json").read_bytes())
        if "/athlete/activities" in url:
            if self.fail_list:
                raise http_error(url, self.fail_list)
            return Response((api / "activities.json").read_bytes())
        if url.split("?")[0].endswith("/streams"):
            if self.fail_streams:
                raise http_error(url, self.fail_streams)
            return Response((api / "streams_9000000001.json").read_bytes())
        if url.endswith("/laps"):
            return Response((api / "laps_9000000001.json").read_bytes())
        raise AssertionError(f"unexpected URL: {url}")


class FakeGarmin:
    class ActivityDownloadFormat:
        ORIGINAL = "original"

    def __init__(self):
        self.uploaded: list[dict] = []
        self.scheduled: list[tuple] = []
        self.downloads: list[str] = []

    def get_activities_by_date(self, start, end=None):
        return json.loads((FIX / "garmin_api" / "activities.json").read_text())

    def download_activity(self, activity_id, dl_fmt=None):
        self.downloads.append(str(activity_id))
        return (FIX / "garmin_api" / f"original_{activity_id}.zip").read_bytes()

    def upload_workout(self, payload):
        self.uploaded.append(payload)
        return {"workoutId": 777}

    def schedule_workout(self, workout_id, date_str):
        self.scheduled.append((workout_id, date_str))
        return {}


class CoachTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="running-coach-test-"))
        self.env = mock.patch.dict(os.environ, {"RUNNING_COACH_CONFIG": str(self.tmp / "config"),
                                                "RUNNING_COACH_DATA": str(self.tmp / "data")})
        self.env.start()
        util._today.clear()
        (self.tmp / "config").mkdir()
        shutil.copy(FIX / "profile.json", self.tmp / "config" / "profile.json")

    def tearDown(self):
        self.env.stop()
        util._today.clear()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def import_files(self) -> str:
        code, out, err = run("import", str(FIX / "files"))
        self.assertEqual(code, 0, out + err)
        return out

    def rows(self) -> dict[str, dict]:
        return {r["date"] + ":" + r["sport"]: r for r in metrics.read_csv("activities.csv")}

    def connect_strava(self, expired: bool = True):
        strava.save_creds({"client_id": "1", "client_secret": "s", "access_token": "fake-access-token-1",
                           "refresh_token": "fake-refresh-token-1", "expires_at": 0 if expired else 4102444800})

    def connect_garmin(self):
        garmin.token_dir().mkdir(parents=True)
        (garmin.token_dir() / "garmin_tokens.json").write_text("{}")


class ImportTests(CoachTestCase):
    def test_import_all_formats(self):
        out = self.import_files()
        self.assertIn("29 new", out)
        self.assertIn("1 already present", out)
        rows = self.rows()
        self.assertEqual(rows["2026-10-06:run"]["structure"], "Intervals 6×800 m")
        self.assertEqual(rows["2026-10-08:run"]["structure"], "Easy run")
        self.assertAlmostEqual(rows["2026-10-08:run"]["distance_km"], 8.0, delta=0.1)
        self.assertEqual(rows["2026-10-10:run"]["structure"], "Tempo/threshold")
        self.assertEqual(rows["2026-10-10:run"]["quality_km"], 5)
        self.assertEqual(rows["2026-10-11:run"]["structure"], "Long run")
        self.assertIsNotNone(rows["2026-10-11:run"]["decoupling"])
        self.assertEqual(rows["2026-09-02:ride"]["sport"], "ride")
        self.assertEqual(rows["2026-09-01:run"]["structure"], "Hard session")
        self.assertEqual(rows["2026-10-08:run"]["source"], "file")

    def test_reimport_is_idempotent(self):
        self.import_files()
        out = self.import_files()
        self.assertIn("0 new", out)
        self.assertEqual(len(store.load_index()), 29)

    def test_richer_file_replaces_summary(self):
        run("import", str(FIX / "files" / "garmin_summarizedActivities.json"))
        code, out, _ = run("import", str(FIX / "files" / "2026-10-08_easy.gpx"))
        self.assertEqual(code, 0)
        self.assertIn("1 replacing", out)
        self.assertEqual(self.rows()["2026-10-08:run"]["detail"], 2)

    def test_zip_and_unknown_files(self):
        import zipfile
        inner = io.BytesIO()
        with zipfile.ZipFile(inner, "w") as zf:
            zf.write(FIX / "files" / "2026-10-10_tempo.fit", "123_ACTIVITY.fit")
        archive = self.tmp / "export.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("DI_CONNECT/DI-Connect-Uploaded-Files/UploadedFiles_0-_Part1.zip", inner.getvalue())
            zf.write(FIX / "files" / "garmin_summarizedActivities.json", "DI_CONNECT/DI-Connect-Fitness/x_0_summarizedActivities.json")
            zf.writestr("activities/notes.txt", "nothing")
            zf.writestr("DI_CONNECT/DI-Connect-Wellness/sleepData.json", "[]")
        code, out, _ = run("import", str(archive))
        self.assertEqual(code, 0, out)
        self.assertIn("27 new", out)
        self.assertEqual(self.rows()["2026-10-10:run"]["detail"], 2)

    def test_bad_file_is_reported_not_fatal(self):
        bad = self.tmp / "broken.gpx"
        bad.write_text("<gpx><trk>")
        code, out, _ = run("import", str(bad), str(FIX / "files" / "2026-10-08_easy.gpx"))
        self.assertEqual(code, 0)
        self.assertIn("skipped", out)
        self.assertIn("1 new", out)


class MetricsTests(CoachTestCase):
    def test_trimp_constant_hr(self):
        profile = Profile({"hr_max": 192, "hr_rest": 46, "sex": "male"})
        samples = {"t": list(range(0, 3601, 5)), "d": [i * 15.0 for i in range(721)], "hr": [150] * 721, "alt": [None] * 721}
        act = store.make_activity("file", "x", "run", util.parse_utc("2026-01-01T08:00:00Z"), samples=samples,
                                  distance_m=10800.0, moving_s=3600.0, avg_hr=150.0)
        value, estimated = metrics.trimp(act, profile)
        hrr = 104 / 146
        self.assertFalse(estimated)
        self.assertAlmostEqual(value, 60 * hrr * 0.64 * 2.718281828 ** (1.92 * hrr), delta=0.5)
        splits = metrics.splits_from_samples(samples)
        self.assertEqual(len(splits), 11)
        self.assertAlmostEqual(splits[0]["pace_s"], 1000 / 3.0, delta=0.5)

    def test_zones_methods(self):
        self.assertEqual(Profile({"hr_max": 200}).hr_bounds, [140, 160, 174, 186])
        self.assertEqual(Profile({"hr_max": 187, "hr_rest": 48}).hr_bounds, [131, 151, 165, 174])
        self.assertEqual(Profile({"hr_max": 187, "hr_zones": [128, 146, 158, 170]}).zone_of(150), 3)
        with self.assertRaises(util.CoachError):
            Profile({"hr_max": 150, "hr_rest": 160})

    def test_profile_change_recomputes(self):
        self.import_files()
        before = self.rows()["2026-10-11:run"]["trimp"]
        code, _, _ = run("profile", "set", "--hr-rest", "60")
        self.assertEqual(code, 0)
        self.assertNotEqual(self.rows()["2026-10-11:run"]["trimp"], before)


class ReportTests(CoachTestCase):
    def test_reports(self):
        self.import_files()
        code, out, _ = run("--today", "2026-10-11", "week")
        self.assertEqual(code, 0)
        self.assertIn("4 run(s), 43.2 km", out)
        code, out, _ = run("--today", "2026-10-11", "analyze", "last")
        self.assertIn("End of run above Z2", out)
        code, out, _ = run("--today", "2026-10-11", "status")
        self.assertIn("TSB", out)
        code, out, _ = run("--today", "2026-10-11", "recap")
        self.assertIn("2026-W41", out)
        self.assertTrue(list((self.tmp / "data" / "reports" / "runs").glob("*.md")))

    def test_next_rules(self):
        self.import_files()
        _, out, _ = run("--today", "2026-10-12", "next")
        self.assertIn("Recovery run", out)
        _, out, _ = run("--today", "2026-10-09", "next")
        self.assertIn("Proposal: Easy run", out)
        code, out, _ = run("--today", "2026-10-12", "next", "--spec")
        self.assertEqual(code, 0)
        workout.validate(json.loads(out))

    def test_plan_driven_next(self):
        self.import_files()
        shutil.copy(FIX / "plan.json", self.tmp / "config" / "plan.json")
        _, out, _ = run("--today", "2026-10-10", "next")
        self.assertIn("Plan — Long run 16 km", out)
        _, out, _ = run("--today", "2026-10-13", "next")
        self.assertIn("Plan — Threshold 3 × 10 min", out)
        code, out, _ = run("--today", "2026-10-14", "plan")
        self.assertEqual(code, 0)
        self.assertIn("❌ missed", out)

    def test_export(self):
        self.import_files()
        target = self.tmp / "out.csv"
        code, out, _ = run("export", "--sport", "run", "--out", str(target))
        self.assertEqual(code, 0)
        self.assertEqual(len(target.read_text().splitlines()), 25)


class StravaTests(CoachTestCase):
    def test_sync_with_refresh_and_details(self):
        self.connect_strava(expired=True)
        router = StravaRouter()
        with mock.patch("urllib.request.urlopen", router):
            code, out, err = run("--today", "2026-10-15", "sync", "--days", "7")
        self.assertEqual(code, 0, out + err)
        self.assertIn("2 listed, 2 new", out)
        self.assertTrue(router.calls[0].startswith(strava.TOKEN_URL))
        creds = json.loads(strava.creds_path().read_text())
        self.assertEqual(creds["access_token"], "fake-access-token-2")
        self.assertEqual(oct(strava.creds_path().stat().st_mode & 0o777), "0o600")
        act = store.get("strava-9000000001")
        self.assertEqual(act["detail"], 2)
        self.assertEqual(self.rows()["2026-10-13:run"]["structure"], "Easy run")

    def test_rate_limit_keeps_summary(self):
        self.connect_strava(expired=False)
        with mock.patch("urllib.request.urlopen", StravaRouter(fail_streams=429)):
            code, out, _ = run("sync", "--days", "7")
        self.assertEqual(code, 0)
        self.assertIn("Strava rate limit", out)
        self.assertEqual(store.get("strava-9000000001")["detail"], 0)

    def test_auth_registration(self):
        with mock.patch("sys.stdin", io.StringIO("")):
            code, _, err = run("auth", "strava", "--client-id", "42")
        self.assertEqual(code, 1)
        self.assertIn("in a terminal", err)
        code, out, _ = run("auth", "strava", "--client-id", "42", "--client-secret", "s3cr3t")
        self.assertEqual(code, 0)
        self.assertIn("client_id=42", out)
        self.assertNotIn("s3cr3t", out)
        self.assertEqual(oct(strava.creds_path().stat().st_mode & 0o777), "0o600")

    def test_refused_refresh_token(self):
        self.connect_strava(expired=True)

        def refuse(req, timeout=None):
            raise http_error(req.full_url, 400)

        with mock.patch("urllib.request.urlopen", refuse):
            code, out, _ = run("sync", "--source", "strava")
        self.assertEqual(code, 1)
        self.assertIn("--reauthorize", out)
        self.assertNotIn("fake-refresh-token-1", out)

    def test_revoked_token_message(self):
        self.connect_strava(expired=False)
        with mock.patch("urllib.request.urlopen", StravaRouter(fail_list=401)):
            code, out, _ = run("sync")
        self.assertEqual(code, 1)
        self.assertIn("coach auth strava", out)


class GarminTests(CoachTestCase):
    def test_fallback_when_strava_fails(self):
        self.connect_strava(expired=False)
        self.connect_garmin()
        fake = FakeGarmin()
        with mock.patch("urllib.request.urlopen", StravaRouter(fail_list=503)), \
             mock.patch("time.sleep"), mock.patch.object(garmin, "client", return_value=fake):
            code, out, err = run("--today", "2026-10-16", "sync")
        self.assertEqual(code, 0, out + err)
        self.assertIn("falling back to garmin", out)
        self.assertIn("Garmin: 2 listed, 2 new", out)
        self.assertEqual(sorted(fake.downloads), ["30000000001", "30000000002"])
        self.assertEqual(store.get("garmin-30000000002")["detail"], 2)
        self.assertEqual(self.rows()["2026-10-15:run"]["structure"], "Tempo/threshold")

    def test_all_sources_deduplicate(self):
        self.connect_strava(expired=False)
        self.connect_garmin()
        with mock.patch("urllib.request.urlopen", StravaRouter()), \
             mock.patch.object(garmin, "client", return_value=FakeGarmin()):
            code, out, _ = run("--today", "2026-10-16", "sync", "--source", "all")
        self.assertEqual(code, 0, out)
        self.assertIn("1 already present from another source", out)
        self.assertEqual(len([r for r in metrics.read_csv("activities.csv") if r["date"] == "2026-10-13"]), 1)

    def test_not_connected(self):
        code, _, err = run("sync", "--source", "garmin")
        self.assertEqual(code, 1)
        self.assertIn("coach auth garmin", err)

    def test_workout_push(self):
        self.connect_garmin()
        fake = FakeGarmin()
        spec = self.tmp / "w.json"
        spec.write_text(json.dumps(json.loads((FIX / "plan.json").read_text())["weeks"]["2026-W42"]["sessions"][0]["spec"]))
        with mock.patch.object(garmin, "client", return_value=fake):
            code, out, _ = run("workout", "push", str(spec), "--date", "2026-10-20")
        self.assertEqual(code, 0, out)
        self.assertEqual(fake.scheduled, [(777, "2026-10-20")])
        steps = fake.uploaded[0]["workoutSegments"][0]["workoutSteps"]
        self.assertEqual([s["type"] for s in steps], ["ExecutableStepDTO", "RepeatGroupDTO", "ExecutableStepDTO"])
        rep = steps[1]["workoutSteps"][0]
        self.assertEqual(rep["targetType"]["workoutTargetTypeKey"], "pace.zone")
        self.assertAlmostEqual(rep["targetValueOne"], 1000 / 295, places=3)
        self.assertEqual([s["stepOrder"] for s in [steps[0], steps[1], *steps[1]["workoutSteps"], steps[2]]], [1, 2, 3, 4, 5])

    def test_invalid_spec(self):
        bad = self.tmp / "bad.json"
        bad.write_text(json.dumps({"name": "x", "steps": [{"kind": "interval", "dur": "5:00", "dist": 1000}]}))
        code, _, err = run("workout", "push", str(bad), "--dry-run")
        self.assertEqual(code, 1)
        self.assertIn("exactly one end", err)


class CliTests(CoachTestCase):
    def test_every_command_has_help(self):
        commands = [[], ["doctor"], ["profile"], ["auth"], ["auth", "strava"], ["auth", "garmin"], ["sync"], ["import"],
                    ["list"], ["analyze"], ["week"], ["status"], ["next"], ["recap"], ["plan"], ["workout"],
                    ["workout", "push"], ["workout", "list"], ["workout", "delete"], ["export"], ["rebuild"]]
        for cmd in commands:
            code, out, _ = run(*cmd, "--help")
            self.assertEqual(code, 0, cmd)
            self.assertIn("usage", out.lower(), cmd)

    def test_empty_state_messages(self):
        os.remove(self.tmp / "config" / "profile.json")
        for cmd in (["status"], ["next"], ["week"], ["recap"], ["doctor"], ["list"]):
            code, out, err = run(*cmd)
            self.assertIn(code, (0, 1), cmd)
            self.assertNotIn("Traceback", out + err, cmd)
        code, _, err = run("analyze")
        self.assertEqual(code, 1)
        self.assertIn("no activities", err)

    def test_profile_set_auto_hr_max(self):
        os.remove(self.tmp / "config" / "profile.json")
        self.import_files()
        code, out, err = run("profile", "set", "--hr-max", "auto", "--goal-distance", "10", "--goal-date", "2027-05-01")
        self.assertEqual(code, 0, err)
        self.assertIn("Max HR: 176 bpm (profile)", out)


if __name__ == "__main__":
    unittest.main()
