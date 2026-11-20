# Sources de données

## Choix de la source par `coach sync`

| Option | Comportement |
|---|---|
| `--source auto` (défaut) | première source connectée dans l'ordre du profil (`strava,garmin` par défaut) ; si elle échoue (réseau, jeton refusé, panne), la suivante |
| `--source strava` ou `garmin` | cette source seulement |
| `--source all` | toutes les sources connectées, dédoublonnées |
| `--days N` | remonter N jours (premier passage : 90 ; ensuite depuis la dernière activité connue moins 2 jours) |
| `--details N` | nombre maximal de courses dont on télécharge le détail par passage (30) |

Une montre qui ne publie pas sur Strava (ou une publication en retard) : `coach profile set --sources garmin,strava`. Les autres sports sont récupérés au niveau résumé (durée, FC, distance) ; seules les courses reçoivent leur détail.

## Strava
API officielle, lecture seule (scope `read,activity:read_all`).
1. L'utilisateur crée une application sur https://www.strava.com/settings/api : nom libre, site web libre, **domaine de rappel `localhost`**.
2. Il lance lui-même, dans un terminal, `coach auth strava --client-id <id>` : le Client Secret est demandé sans écho, pour qu'il ne passe ni par la conversation ni par l'historique du shell. Variante : exporter `STRAVA_CLIENT_ID` et `STRAVA_CLIENT_SECRET`, puis l'agent lance `coach auth strava`. La commande enregistre `~/.config/running-coach/strava.json` (droits 600) et affiche l'adresse d'autorisation.
3. L'utilisateur ouvre l'adresse, autorise ; le navigateur arrive sur `http://localhost/?state=&code=…` qui ne charge pas, c'est attendu. Il copie l'adresse complète.
4. `coach auth strava --code '<adresse complète ou code>'`. Le jeton se rafraîchit ensuite seul.
- `coach auth strava --status` : état sans appel réseau. `--reauthorize` réaffiche l'adresse d'autorisation.
- Limites Strava : 100 requêtes par 15 minutes, 1 000 par jour pour la lecture. Une course détaillée coûte 2 requêtes (flux et tours). À la limite (429), la synchro garde les résumés, s'arrête sans attendre et annonce le nombre de courses en attente ; relancer 15 minutes plus tard.
- Historique complet : plus rapide par l'export (voir plus bas) que par l'API.

## Garmin Connect
Bibliothèque non officielle `garminconnect` : Garmin ne publie pas d'API pour les particuliers.
1. L'utilisateur lance lui-même la connexion dans un terminal, car elle demande mot de passe et code MFA : `~/.claude/skills/running-coach/scripts/coach auth garmin login`. `GARMIN_EMAIL` et `GARMIN_PASSWORD` évitent la saisie. Ne jamais demander ces informations dans la conversation. Sans terminal interactif, la commande s'arrête avec un message au lieu d'attendre.
2. Les jetons vont dans `~/.config/running-coach/garmin/` (droits 700) et se rafraîchissent seuls tant que Garmin les accepte.
- `coach auth garmin status` : un appel de lecture pour vérifier le compte. `logout` efface les jetons.
- Détail d'une course : le fichier FIT d'origine (une requête par course), lu comme un import.
- Jetons expirés ou refusés : `coach auth garmin logout`, puis nouvelle connexion. Échec persistant : `install.sh --upgrade` (Garmin modifie régulièrement sa connexion).
- Comptes chinois (garmin.cn) : non pris en charge.

## Import de fichiers, sans compte
`coach import <fichiers | dossiers | archives>` ; `--sport run` force le sport.

| Format | Contenu lu | Provenance typique |
|---|---|---|
| `.fit` | enregistrements, tours, sport, heure locale | montres Garmin, Coros, Suunto, Wahoo, Polar |
| `.tcx` | points, tours, FC | Garmin Connect, anciens exports |
| `.gpx` | points, FC (extensions), type | Strava, applications, montres |
| `.json` | activité Strava (API), liste d'activités Garmin (API), `*_summarizedActivities.json` de l'export Garmin | scripts, exports |
| `.gz`, `.zip` | décompressés, zips imbriqués compris | exports complets |

- Export complet Strava : Paramètres › Mon compte › Télécharger ou supprimer votre compte › Demander une archive. `coach import export_<n>.zip` lit `activities/` (FIT, GPX, TCX compressés).
- Export complet Garmin : compte Garmin › Gestion des données › Exporter vos données. `coach import <archive>.zip` lit `summarizedActivities.json` (résumés de tout l'historique) et les FIT des zips `UploadedFiles` ; les FIT de suivi quotidien (sommeil, santé) sont ignorés.
- Fichier sans type de sport : sport deviné d'après la vitesse (course entre 1,9 et 6,5 m/s) et signalé.
- Réimporter est sans risque : un fichier déjà présent est compté « déjà présent ».

## Format normalisé
Chaque activité est un JSON `activities/<source>-<id>.json` ; les analyses ignorent la source.

| Champ | Contenu |
|---|---|
| `id`, `source`, `source_id` | `strava-123`, `garmin-456`, `file-<empreinte>` |
| `sport`, `sport_raw` | `run`, `ride`, `swim`, `walk`, `hike`, `strength`, `other` ; libellé d'origine |
| `start_utc`, `start_local` | départ en UTC et à l'heure locale de l'activité |
| `distance_m`, `moving_s`, `elapsed_s` | distance, temps en mouvement, temps total |
| `avg_hr`, `max_hr`, `elev_gain_m` | résumé |
| `laps` | `start_s`, `distance_m`, `moving_s`, `elapsed_s`, `avg_hr`, `max_hr` |
| `samples` | séries alignées `t` (s depuis le départ), `d` (m cumulés), `hr`, `alt` |
| `detail` | 2 enregistrement complet, 1 tours, 0 résumé |

## Dédoublonnage
- Même identifiant : la version la plus détaillée reste.
- Sources différentes : même activité si les départs sont à moins de 3 minutes et les distances à moins de 5 % (300 m au moins) ; la version la plus détaillée remplace l'autre, sinon la nouvelle est ignorée.

## Messages d'erreur

| Message | Cause | Action |
|---|---|---|
| « Aucune source connectée » (code 2) | ni Strava ni Garmin | connecter une source ou `coach import` |
| « Strava refuse l'accès (401) » | autorisation révoquée ou scope insuffisant | `coach auth strava --reauthorize`, puis `--code` |
| « limite de requêtes Strava atteinte » | 100 requêtes en 15 min | relancer plus tard ; rien n'est perdu |
| « jetons Garmin expirés ou refusés » | jetons trop anciens | `coach auth garmin logout`, puis `login` par l'utilisateur |
| « bibliothèque garminconnect absente » | installation partielle | `install.sh` |
| « ignoré : fichier FIT de type … » | fichier de suivi, pas une activité | aucune |
| « sport deviné d'après la vitesse » | fichier sans type | vérifier, relancer avec `--sport` |
