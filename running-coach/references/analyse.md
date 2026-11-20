# Analyser une séance ou une semaine

## Grille d'un compte rendu de séance
`coach analyze` fournit les chiffres ; la réponse à l'utilisateur les interprète, dans cet ordre :
1. Verdict en une ou deux phrases : la séance a-t-elle rempli son rôle (récupérer, construire l'endurance, travailler le seuil…) ?
2. Contexte : séance prévue au plan ce jour-là, phase, fatigue avant la séance (TSB de la veille).
3. Lecture de la structure : splits km par km ou tours ; repérer échauffement, bloc, récupérations, retour au calme, dérive en fin de sortie.
4. Métriques : TRIMP, temps par zone, EF et découplage pour les sorties en endurance.
5. Comparaison avec les séances du même type (tableau « Séances comparables ») : allure à FC égale, EF.
6. Impact sur la charge : CTL, ATL et TSB avant et après.
7. Conséquence pour la suite : ce que cela change à la prochaine séance.

## Formules

| Mesure | Calcul |
|---|---|
| TRIMP (Banister) | Σ durée (min) × r × k × e^(b·r), avec r = (FC − FC repos) / (FC max − FC repos) borné à [0, 1] ; k = 0,64, b = 1,92 (hommes) ; k = 0,86, b = 1,67 (femmes). Intégré seconde par seconde quand l'enregistrement existe, sinon sur la FC moyenne. FC repos absente : 55. Sans FC : 1,2 par minute de course (0,9 vélo, 0,8 renforcement, 1 autre), marqué « estimé ». |
| CTL (forme de fond) | CTL(j) = CTL(j−1) + (TRIMP(j) − CTL(j−1)) / 42 |
| ATL (fatigue) | ATL(j) = ATL(j−1) + (TRIMP(j) − ATL(j−1)) / 7 |
| TSB (fraîcheur) | CTL(j−1) − ATL(j−1) : la forme au matin, avant la séance du jour |
| Départ des séries | CTL = ATL = TRIMP quotidien moyen des 28 premiers jours de données, pour ne pas supposer un athlète parti de zéro |
| Splits | coupure exacte à chaque kilomètre par interpolation ; temps en mouvement seulement (vitesse ≥ 0,8 m/s, trous de plus de 30 s exclus) ; sinon tours automatiques de 1 km |
| EF (efficience) | vitesse (m/min) / FC moyenne, sur les km complets hors premier km ; footings et sorties longues seulement |
| Découplage | (EF 1re moitié − EF 2de moitié) / EF 1re moitié × 100 ; au moins 6 km et 40 min hors premier km |

Les valeurs de TRIMP dépendent du profil : modifier FC max, FC repos ou sexe recalcule tout l'historique.

## Lecture des indicateurs

| Indicateur | Repères |
|---|---|
| TSB | > +15 très frais (désentraînement si cela dure) ; +5 à +15 frais, bon avant une course ; −10 à +5 équilibre ; −25 à −10 fatigue d'entraînement normale en bloc ; < −25 fatigue élevée, alléger ; < −30 repos |
| Découplage | < 5 % endurance solide à cette allure ; 5-10 % correct ; > 10 % allure trop rapide pour la durée, chaleur, déshydratation ou base aérobie à construire |
| EF | ne se compare qu'entre footings proches (terrain, chaleur) ; une hausse sur 4 à 8 semaines signale un progrès aérobie |
| Temps par zone | footing ou sortie longue : plus de 20-25 % au-dessus de Z2 = trop rapide ; semaine : environ 80 % en Z1-Z2 |
| Volume | hausse de 10-15 % par semaine au plus ; une semaine allégée (−20 à −30 %) toutes les 3 ou 4 semaines |

## Détection de structure
Sur les km complets. « Rapide » = allure ≤ 92 % du 3e quartile des allures de la séance, plus rapide que 1,12 × allure seuil si elle est connue, et FC au moins en Z3 si elle est mesurée. « Longue » = au moins `long_run_min_minutes` (75 min par défaut).

| Libellé | Critère | Type |
|---|---|---|
| `Fractionné N×D` | tours manuels : au moins 3 tours rapides (> 108 % de la vitesse médiane des tours) alternés avec des tours lents ; D = distance ou durée la plus régulière | qualité |
| `Tempo/seuil` | bloc continu d'au moins 3 km rapides, ou séance entière à l'allure seuil, ou au moins 3 km en Z4 | qualité |
| `Allure spécifique continue` | séance entière entre seuil et allure marathon, au moins 6 km | qualité |
| `Progressif` | km rapides groupés en fin de séance | qualité |
| `Fractionné` | au moins 3 km rapides non contigus | qualité |
| `Accélérations` | 1 ou 2 km rapides isolés | footing |
| `Sortie longue`, `Sortie longue progressive`, `Sortie longue avec bloc` | longue, sans, avec km rapides en fin, avec bloc | sortie longue |
| `Footing`, `Récupération` | sans km rapide ; FC médiane en Z1 pour la récupération | footing |
| `Séance soutenue`, `Sortie longue soutenue`, `Court` | résumé seulement (pas de splits) : FC moyenne en Z3 ou plus ; moins de 3 km | selon le cas |

Un fractionné court (200-400 m) dilué dans des splits au km ressemble à un footing irrégulier : les tours manuels ou la FC le révèlent. Faute de tours, le dire plutôt que d'affirmer.

## Bilan de semaine (`coach week`)
Lire dans l'ordre : volume face à l'objectif et à la moyenne des 4 semaines précédentes, nombre de séances de qualité (1 à 2), sortie longue (25 à 35 % du volume), répartition d'intensité, adhérence au plan, évolution du TSB. Conclure par une à trois priorités pour la semaine suivante.

## Pièges de mesure
- Résumé seulement (`detail` 0) : ni splits ni structure fine. `coach sync --details 50` ou l'import du FIT d'origine complète l'analyse.
- Tours automatiques : ils se coupent sur un point GPS, donc un peu au-delà de 1 000 m ; le dernier tour est partiel.
- Capteur optique au poignet : pics de FC aberrants au départ ou par temps froid ; une FC max isolée très au-dessus du profil est probablement un artefact.
- Tapis de course : distance de la montre souvent fausse de 5 à 10 % ; juger sur la FC.
- Chaleur, dénivelé, vent : la FC monte à allure égale ; ne pas conclure à une perte de forme sur une seule séance.
- Altitude GPS bruitée : le dénivelé est lissé (seuil de 3 m) et reste approximatif.
