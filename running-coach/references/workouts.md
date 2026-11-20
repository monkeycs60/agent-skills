# Séances structurées sur la montre (Garmin Connect)

Une séance créée dans Garmin Connect et planifiée au calendrier arrive sur la montre à la synchronisation suivante. Les autres marques ne sont pas prises en charge : leur donner la description texte.

## Commandes
| Commande | Effet |
|---|---|
| `coach workout push <fichier.json \| -> --date AAAA-MM-JJ --dry-run` | valide, affiche le résumé et le JSON envoyé, n'envoie rien |
| `coach workout push <fichier.json \| -> --date AAAA-MM-JJ` | crée la séance dans le compte puis la planifie ; sans `--date`, elle reste dans la bibliothèque |
| `coach workout list` | séances du compte (id, nom) |
| `coach workout delete <id>` | supprime une séance du compte |
| `coach next --spec` | séance proposée par `coach next`, au format ci-dessous |

Toujours `--dry-run` d'abord, montrer le résumé à l'utilisateur et n'envoyer qu'après son accord : la commande écrit dans son compte.

## Format
```json
{
  "name": "VMA 6x800m",
  "description": "Bloc VMA",
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

| Élément | Valeurs |
|---|---|
| `kind` | `warmup`, `cooldown`, `interval` (effort, ou course continue), `recovery`, `rest`, `repeat` |
| fin d'étape, exactement une | `dur` (`"mm:ss"`, `"h:mm:ss"` ou secondes), `dist` (mètres), `lap` (`true` : jusqu'à l'appui sur Tour) |
| `target`, facultatif | `{"pace": ["m:ss", "m:ss"]}` en min/km, dans n'importe quel ordre ; `{"hr": [bas, haut]}` en bpm ; `{"open": true}` ou absent : libre |
| `repeat` | `times` (entier ≥ 1) et `steps` ; pas de `repeat` dans un `repeat` |

- Cibles tirées de `coach profile` : FC de la zone visée, allures de la table.
- Une fourchette d'allure de 10 s/km évite que la montre sonne sans arrêt ; une cible FC convient mieux aux footings et aux sorties longues.
- Une sortie longue s'écrit en une étape `interval` avec `dist` et une cible FC de Z2 ; une fin à allure objectif en seconde étape.
