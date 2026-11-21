#!/usr/bin/env bash
set -uo pipefail
case "${1:-}" in
  -h|--help) echo "usage: tests/e2e.sh — full offline run (import, analyses, reports, workout, export) on tests/fixtures, in temporary folders, timing each step"; exit 0 ;;
esac

skill="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
coach="$skill/scripts/coach"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
export RUNNING_COACH_CONFIG="$tmp/config" RUNNING_COACH_DATA="$tmp/data"
mkdir -p "$RUNNING_COACH_CONFIG"
failed=0

ms() { python3 -c 'import time; print(int(time.time() * 1000))' 2>/dev/null || date +%s000; }

step() {
  local name="$1" expect="$2" start out code
  shift 2
  start=$(ms)
  out="$("$@" 2>&1)"; code=$?
  if [ "$code" -eq 0 ] && printf '%s' "$out" | grep -qF -- "$expect"; then
    printf '  ✓ %-34s %6d ms\n' "$name" $(( $(ms) - start ))
  else
    printf '  ✗ %-34s (code %d, expected "%s")\n' "$name" "$code" "$expect"
    printf '%s\n' "$out" | tail -15 | sed 's/^/      /'
    failed=1
  fi
}

echo "Offline run ($coach)"
step "doctor without profile" "Next steps" "$coach" doctor
step "sync without source" "No account" bash -c "'$coach' sync; [ \$? -eq 2 ]"
step "import fixtures" "29 new" "$coach" import "$skill/tests/fixtures/files"
step "idempotent re-import" "0 new" "$coach" import "$skill/tests/fixtures/files"
step "profile, auto max HR" "(profile)" "$coach" profile set --hr-max auto --hr-rest 48 --sex female --ref-race 10 47:30 \
  --goal-name "Spring half" --goal-distance 21.1 --goal-date 2027-03-14 --goal-time 1:44:00 --weekly-km 38
step "list" "Intervals 6×800 m" "$coach" --today 2026-10-11 list --days 14
step "analyze intervals (TCX)" "Reps" "$coach" --today 2026-10-11 analyze 2026-10-06
step "analyze threshold (FIT)" "Tempo/threshold" "$coach" --today 2026-10-11 analyze 2026-10-10
step "analyze long run (JSON)" "decoupling" "$coach" --today 2026-10-11 analyze last
step "weekly report" "4 run(s), 43.2 km" "$coach" --today 2026-10-11 week
step "status" "CTL" "$coach" --today 2026-10-11 status
step "multi-week recap" "2026-W41" "$coach" --today 2026-10-11 recap
step "next (day after long run)" "Recovery run" "$coach" --today 2026-10-12 next
step "next (Friday)" "Proposal: Easy run" "$coach" --today 2026-10-09 next
cp "$skill/tests/fixtures/plan.json" "$RUNNING_COACH_CONFIG/"
step "plan" "Current week" "$coach" --today 2026-10-11 plan
step "next (plan)" "Plan — Threshold 3 × 10 min" "$coach" --today 2026-10-13 next
step "watch workout (dry run)" "nothing was sent" bash -c "'$coach' --today 2026-10-13 next --spec | '$coach' workout push - --date 2026-10-13 --dry-run"
step "CSV export" "activities exported" "$coach" export --out "$tmp/export.csv"
step "rebuild" "index rebuilt" "$coach" rebuild
echo
if [ "$failed" = 0 ]; then echo "✓ full run without errors"; else echo "✗ some steps failed"; exit 1; fi
