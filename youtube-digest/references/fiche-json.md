# Format de `fiche.json`

`scripts/report.py` lit `~/.local/share/youtube/<id>/fiche.json` et en fait `rapport.html`. Tous les textes sont en français. Ils acceptent `code`, **gras**, *italique* et [lien](https://…), rien d'autre. `t` est un nombre de secondes, pris dans les liens `?t=` de la transcription.

```json
{
  "en_une_phrase": "De quoi parle la vidéo et pour qui.",
  "verdict": {
    "avis": "regarder | survoler | passer",
    "texte": "Pourquoi, en deux ou trois phrases.",
    "moments": [{"t": 38, "label": "La démo"}]
  },
  "points_cles": [{"t": 190, "titre": "Titre court", "texte": "Une ou deux phrases."}],
  "schemas": [{"titre": "Qui parle à qui", "mermaid": "flowchart LR\n  A[Client] -->|JSON-RPC| B[Serveur]", "legende": "Ce qu'il faut retenir du schéma."}],
  "etapes": [{"titre": "Étape", "texte": "Quoi faire.", "code": "npx …", "langage": "bash", "t": 383}],
  "ressources": [{"url": "https://…", "titre": "Article compagnon", "apport": "Ce qu'il apporte en plus de la vidéo.", "lu": true}],
  "commentaires": {
    "resume": "Une phrase sur le ton général des commentaires.",
    "points": [{"type": "correction | alerte | alternative | question | avis", "texte": "Ce qui est dit.", "auteur": "@pseudo", "likes": 46}]
  },
  "angles_morts": [{"t": 519, "texte": "Ce qui est montré sans être dit, et où le trouver."}]
}
```

## Ce qui est obligatoire
- `en_une_phrase`, `verdict` et `commentaires.resume` : toujours, même si les commentaires ne sont que des remerciements ; le dire alors en une phrase, avec `points` vide.
- `points_cles` : 5 à 10, chacun avec `t`.
- `etapes` : seulement pour un tuto. Le `code` vient de l'article ou du dépôt lu, sinon de la transcription. Ne jamais l'inventer : un code reconstitué le dit dans `texte`.
- `ressources` : chaque lien utile de la transcription, avec `lu: true` pour ceux réellement lus.
- `angles_morts` : seulement ce qu'aucune ressource n'a comblé.

## Schémas
- En faire un dès que la vidéo décrit un processus, une installation, une architecture ou un échange entre composants. Il en faut un ou deux, trois au plus.
- `flowchart LR` pour une architecture ou un pipeline, `flowchart TD` pour des étapes avec des choix, `sequenceDiagram` pour un protocole ou des appels entre services.
- Libellés courts, `<br>` pour couper une ligne, guillemets autour d'un libellé qui contient des parenthèses, des deux-points ou une barre oblique.
- Un schéma qui ne se rend pas apparaît en source dans le rapport : `report.py` donne `schemas_failed`. Corriger la syntaxe et relancer.
