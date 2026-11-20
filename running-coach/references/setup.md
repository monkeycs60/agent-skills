# Installation et profil

## Installation
`bash install.sh` (relançable, `--help` pour l'aide) :
1. lien `~/.claude/skills/running-coach` vers le skill, et dans `~/.codex/skills` ou `~/.agents/skills` s'ils existent ;
2. environnement `.venv` dans le skill : avec `uv`, Python 3.12 (téléchargé si besoin) ; sinon le Python 3.10+ le plus récent du système ;
3. `requirements.txt` : `fitdecode` (fichiers FIT) et `garminconnect` (Garmin Connect). Si `garminconnect` ne s'installe pas, Strava et l'import restent utilisables ;
4. dossiers de configuration (droits 700) et de données ;
5. essai hors ligne : import des fichiers de `tests/fixtures/files` dans un dossier temporaire et bilan de semaine.

| Situation | Conséquence | Remède |
|---|---|---|
| Python 3.10 ou 3.11 sans uv | `garminconnect` plafonne à 0.3.2 (les versions suivantes exigent 3.12) ; la connexion Garmin casse plus vite quand Garmin change son authentification | installer uv, supprimer `.venv`, relancer `install.sh` |
| Connexion Garmin cassée après une mise à jour Garmin | erreurs à la connexion ou à la synchro | `install.sh --upgrade` |
| `python3 -m venv` refusé (Debian, Ubuntu) | pas d'environnement | `sudo apt install python3-venv` ou installer uv |

## Dossiers et variables

| Élément | Par défaut | Variable |
|---|---|---|
| Configuration | `~/.config/running-coach/` (ou `$XDG_CONFIG_HOME/running-coach`) | `RUNNING_COACH_CONFIG` |
| Données | `~/.local/share/running-coach/` (ou `$XDG_DATA_HOME/running-coach`) | `RUNNING_COACH_DATA` |
| Python du lanceur | `.venv/bin/python` du skill | `RUNNING_COACH_PYTHON` |
| Application Strava | `strava.json` | `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET` (prioritaires) |
| Première connexion Garmin | saisie interactive | `GARMIN_EMAIL`, `GARMIN_PASSWORD` |

Données : `activities/<id>.json` (format normalisé), `index.json`, `metrics/activities.csv` (une ligne par activité), `metrics/daily.csv` (charge quotidienne), `metrics/weekly.csv`, `reports/runs/*.md`, `reports/weekly/*.md`, `state.json` (dernières synchros).

## Questions pour créer le profil
Poser dans cet ordre, une réponse « je ne sais pas » est acceptable sauf pour l'objectif :
1. FC max mesurée (test, fin de course en sprint) ? Sinon : année de naissance, et l'on affinera avec `--hr-max auto` après import.
2. FC de repos au réveil ? Elle active les zones de Karvonen, plus justes que le % de FC max.
3. Zones mesurées en laboratoire ou par test de terrain ? Elles priment sur tout calcul (`--hr-zones`).
4. Une course récente (distance et temps) ou une allure seuil connue ? Elle donne toutes les allures.
5. Objectif : nom, distance, date, temps visé (facultatif). Sans objectif : phase « entretien ».
6. Volume hebdomadaire visé, nombre de sorties par semaine, jour de la sortie longue.
7. Contraintes durables : blessures, jours impossibles, autres sports (`--note`, répétable).

Exemple :
```bash
coach profile set --hr-max 188 --hr-rest 52 --sex male --ref-race 10 46:30 \
  --goal-name "Marathon de printemps" --goal-distance 42.195 --goal-date 2027-04-11 --goal-time 3:55:00 \
  --weekly-km 40 --runs-per-week 4 --long-run-day sun --note "Tendon d'Achille sensible : pas de côtes"
```
`coach profile` affiche le profil, les zones et les allures calculées. Modifier le profil recalcule toutes les métriques.

## Champs de `profile.json`

| Clé | Option | Usage | Défaut |
|---|---|---|---|
| `hr_max` | `--hr-max N\|auto` | zones, TRIMP | maximum observé dans les données, sinon Tanaka (`birth_year`), sinon 185 ; tout est alors marqué provisoire |
| `hr_rest` | `--hr-rest` | zones de Karvonen, TRIMP | 55 pour le TRIMP, zones en % FC max |
| `hr_zones` | `--hr-zones a,b,c,d` | bornes hautes de Z1 à Z4 | calculées |
| `sex` | `--sex male\|female` | coefficients du TRIMP | coefficients masculins |
| `birth_year` | `--birth-year` | FC max estimée 208 − 0,7 × âge | — |
| `threshold_pace` | `--threshold-pace m:ss` | allures | déduite de `reference_race` |
| `reference_race` | `--ref-race KM TEMPS` | allure seuil par Riegel | — |
| `goal` | `--goal-name`, `--goal-distance`, `--goal-date`, `--goal-time`, `--clear-goal` | phases, allure cible, sortie longue maximale | aucun |
| `weekly_km` | `--weekly-km` | volume visé | moyenne des 4 dernières semaines |
| `runs_per_week` | `--runs-per-week` | séances par semaine | 4 |
| `long_run_day` | `--long-run-day` | jour de la sortie longue | `sun` |
| `long_run_min_minutes` | `--long-run-min` | durée à partir de laquelle une sortie est « longue » | 75 |
| `sources` | `--sources garmin,strava` | ordre de `coach sync` | `strava,garmin` |
| `notes` | `--note` | contraintes durables | — |

`--unset CLÉ` retire une clé.

## Zones de fréquence cardiaque
Priorité : `hr_zones` du profil, puis Karvonen si `hr_rest` est connue, puis % de FC max.

| Zone | Karvonen (% FC de réserve) | % FC max | Usage |
|---|---|---|---|
| Z1 Récupération | < 60 | < 70 | récupération, échauffement |
| Z2 Endurance | 60-74 | 70-80 | footings, sorties longues (plafond) |
| Z3 Tempo/marathon | 74-84 | 80-87 | allure marathon, tempo |
| Z4 Seuil | 84-91 | 87-93 | seuil |
| Z5 VMA | > 91 | > 93 | fractionné court |

## Allures
L'allure seuil T est celle qu'on tient environ une heure. Depuis une course récente : distance tenable en 60 min par la formule de Riegel (exposant 1,06), puis T = 60 min / cette distance.

| Zone | Rapport à T |
|---|---|
| Récupération | > 1,35 T |
| Endurance | 1,20-1,35 T |
| Endurance active | 1,10-1,20 T |
| Allure marathon | 1,04-1,10 T |
| Seuil | 0,97-1,04 T |
| VMA | 0,88-0,97 T |
| Vitesse | < 0,88 T |

Allure objectif : temps visé / distance ; sans temps visé, T × 0,95 (5 km), 0,985 (10 km), 1,03 (semi), 1,075 (marathon).
