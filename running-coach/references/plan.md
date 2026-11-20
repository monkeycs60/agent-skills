# Plan d'entraînement et prochaine séance

## Format de `~/.config/running-coach/plan.json`
Facultatif. Sans plan, `coach next` applique les règles génériques plus bas.

```json
{
  "name": "Semi de printemps",
  "start": "2027-01-04",
  "weeks": {
    "2027-W01": {"phase": "Base", "km": 32, "sessions": [
      {"day": "tue", "type": "quality", "priority": 1, "desc": "Fartlek 10 × 1 min", "km": 9},
      {"day": "thu", "type": "easy", "priority": 3, "desc": "Footing 40 min", "km": 7},
      {"day": "sun", "type": "long", "priority": 1, "desc": "Sortie longue 14 km en Z2", "km": 14}
    ]},
    "2027-W02": {"phase": "Base", "km": 34, "sessions": [
      {"day": "tue", "type": "quality", "priority": 1, "desc": "Seuil 3 × 8 min",
       "spec": {"name": "Seuil 3x8'", "steps": [
         {"kind": "warmup", "dur": "15:00"},
         {"kind": "repeat", "times": 3, "steps": [
           {"kind": "interval", "dur": "8:00", "target": {"pace": ["4:50", "5:00"]}},
           {"kind": "recovery", "dur": "2:00"}]},
         {"kind": "cooldown", "dur": "10:00"}]}}
    ]}
  }
}
```

| Champ | Contenu |
|---|---|
| `start` | début du plan ; `coach recap` part de cette date |
| `weeks` | clé `AAAA-Wnn` (semaine ISO, lundi → dimanche) |
| `phase`, `km` | libellé affiché (remplace la phase calculée) et volume visé de la semaine |
| `day` | `mon` … `sun` (ou `lun` … `dim`) |
| `type` | `easy`, `long`, `quality`, `race`, `rest` |
| `priority` | 1 séance clé, 2 importante, 3 facultative (défaut 2) |
| `desc` | texte montré à l'utilisateur |
| `km` | distance prévue ; donne la séance montre des footings et sorties longues |
| `spec` | séance structurée, même format que `coach workout push` (exemple en semaine 2027-W02), reprise par `coach next --spec` |

`coach plan` valide le fichier et affiche la semaine en cours.

## Rattachement des séances réalisées
- Sortie longue : la plus longue course de la semaine, quel que soit le jour, si elle est classée longue ou atteint 75 % des `km` prévus.
- Qualité : une course de type qualité à un jour près, sinon n'importe quelle course de qualité restante de la semaine.
- Footing : une course restante à un jour près.
- Statuts : fait, manqué (jour passé), aujourd'hui, à venir, repos.

## Logique de `coach next`
Si l'utilisateur a déjà couru aujourd'hui, la proposition vaut pour demain. Premier cas qui s'applique :
1. aucune course enregistrée : footing de 40 min pour calibrer ;
2. jour de l'objectif : course ; moins de 4 jours après : repos ; jusqu'à 14 jours après : footings de récupération ;
3. TSB < −30 : repos ;
4. plan présent pour la semaine : séance du jour (repos s'il n'y a rien), remplacée par un footing si TSB < −25 pour une séance dure, décalée d'un jour si c'est une séance de qualité et que la veille a été dure ; une séance clé manquée est signalée avec la consigne de rattrapage ;
5. sorties de la semaine déjà faites (`runs_per_week`) : repos ;
6. séance dure la veille (qualité ou longue) : récupération de 30 à 40 min, repos si TSB < −20 ;
7. semaine de course : activation à J−3 ou J−2, repos à J−1, sinon footing court avec accélérations ;
8. sortie longue pas faite et jour de sortie longue atteint : sortie longue (repoussée si TSB < −20) ;
9. qualité à faire (1 par semaine, 2 en développement et spécifique à partir de 5 sorties), dernière séance dure il y a 2 jours ou plus, TSB ≥ −20, et demain n'est pas le jour de la sortie longue : séance selon la phase ;
10. sinon footing, dimensionné sur le volume restant de la semaine hors sortie longue.

| Phase (selon la date de l'objectif) | Séance de qualité proposée |
|---|---|
| Base (plus de 16 semaines) ou Entretien (sans objectif) | fartlek, ou seuil en entretien |
| Développement (16 à 9 semaines) | VMA et seuil en alternance |
| Spécifique (8 semaines à l'affûtage) | allure objectif ; sortie longue avec fin à allure objectif pour semi et marathon |
| Affûtage (3 semaines marathon, 2 sinon) | allure objectif en volume réduit ; sortie longue à 65 % |
| Semaine de course | activation |

Dimensionnement : seuil 2, 3 ou 4 × 10 min et VMA 5 × 800 m, 5 × 1 000 m ou 6 × 1 000 m selon que le volume visé est sous 30, sous 50 ou au-delà de 50 km ; sortie longue = plus grande valeur entre 10 km, 30 % du volume et la plus longue sortie des 4 dernières semaines (+1 km en développement et spécifique), plafonnée à 14, 18, 22 ou 32 km pour un objectif 5 km, 10 km, semi ou marathon.

`coach next` est une proposition de départ : l'ajuster à ce que l'utilisateur rapporte (sommeil, douleur, chaleur, agenda) et le dire.

## Écrire un plan avec l'utilisateur
- Partir du volume actuel (`coach recap`), pas du volume rêvé ; progression de 10 % par semaine au plus, une semaine allégée toutes les 3 ou 4 semaines.
- Une ou deux séances de qualité par semaine, jamais deux jours de suite ; la sortie longue à 25-35 % du volume hebdomadaire.
- Affûtage : 2 semaines (3 pour un marathon), volume réduit de 30 à 50 %, intensité conservée.
- Allures et FC tirées de `coach profile` ; écrire une `spec` pour les séances de qualité que l'utilisateur veut sur sa montre.
- Après écriture : `coach plan` pour valider, puis `coach next` pour vérifier la proposition du jour.
