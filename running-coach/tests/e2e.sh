#!/usr/bin/env bash
set -uo pipefail
case "${1:-}" in
  -h|--help) echo "usage : tests/e2e.sh — parcours complet hors ligne (import, analyses, bilans, séance, export) sur tests/fixtures, dans des dossiers temporaires, avec le temps de chaque étape"; exit 0 ;;
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
    printf '  ✗ %-34s (code %d, attendu « %s »)\n' "$name" "$code" "$expect"
    printf '%s\n' "$out" | tail -15 | sed 's/^/      /'
    failed=1
  fi
}

echo "Parcours hors ligne ($coach)"
step "doctor sans profil" "Étapes suivantes" "$coach" doctor
step "sync sans source" "Sans compte" bash -c "'$coach' sync; [ \$? -eq 2 ]"
step "import des fixtures" "29 nouvelle(s)" "$coach" import "$skill/tests/fixtures/files"
step "réimport idempotent" "0 nouvelle(s)" "$coach" import "$skill/tests/fixtures/files"
step "profil FC max auto" "(profil)" "$coach" profile set --hr-max auto --hr-rest 48 --sex female --ref-race 10 47:30 \
  --goal-name "Semi de printemps" --goal-distance 21.1 --goal-date 2027-03-14 --goal-time 1:44:00 --weekly-km 38
step "liste" "Fractionné 6×800 m" "$coach" --today 2026-10-11 list --days 14
step "analyse fractionné (TCX)" "Répétitions" "$coach" --today 2026-10-11 analyze 2026-10-06
step "analyse seuil (FIT)" "Tempo/seuil" "$coach" --today 2026-10-11 analyze 2026-10-10
step "analyse sortie longue (JSON)" "Découplage" "$coach" --today 2026-10-11 analyze last
step "bilan de semaine" "4 sortie(s), 43.2 km" "$coach" --today 2026-10-11 week
step "statut" "CTL" "$coach" --today 2026-10-11 status
step "bilan multi-semaines" "2026-W41" "$coach" --today 2026-10-11 recap
step "prochaine séance (lendemain SL)" "récupération" "$coach" --today 2026-10-12 next
step "prochaine séance (vendredi)" "Proposition : Footing" "$coach" --today 2026-10-09 next
cp "$skill/tests/fixtures/plan.json" "$RUNNING_COACH_CONFIG/"
step "plan" "Semaine en cours" "$coach" --today 2026-10-11 plan
step "prochaine séance (plan)" "Plan — Seuil 3 × 10 min" "$coach" --today 2026-10-13 next
step "séance montre (essai)" "rien n'a été envoyé" bash -c "'$coach' --today 2026-10-13 next --spec | '$coach' workout push - --date 2026-10-13 --dry-run"
step "export CSV" "activités exportées" "$coach" export --out "$tmp/export.csv"
step "reconstruction" "index reconstruit" "$coach" rebuild
echo
if [ "$failed" = 0 ]; then echo "✓ parcours complet sans erreur"; else echo "✗ des étapes ont échoué"; exit 1; fi
