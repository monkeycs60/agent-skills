# Capturer l'écran réel de l'app

`node $S/capturer.js recette.json` ouvre une page dans un navigateur sans interface, la prépare,
la photographie (PNG, `dsf` fois la taille du viewport) et écrit à côté un JSON : cadre des éléments
choisis (`boites`) et styles calculés d'éléments témoins (`styles`, pour remplir `charte.css`).

**Données fictives uniquement** : serveur local, démo ou préproduction, jamais un compte réel.

## Recette

Seuls `url` et `sortie` sont obligatoires. Un chemin relatif (`url` local, `sortie`) se lit depuis
le dossier de la recette.

```json
{
  "url": "http://localhost:5173/login",
  "viewport": [1440, 900], "dsf": 2, "lang": "fr-FR", "theme": "light",
  "sortie": "assets/ecran-reel-fr.png",
  "attente": 1500,
  "cookies": [{ "name": "session", "value": "...", "domain": "localhost" }],
  "localStorage": { "onboardingVu": "1" },
  "fermer": "^(OK|Plus tard|Tout accepter|Suivant|Fermer)$",
  "etapes": [
    { "saisir": { "selecteur": "input[type=email]", "texte": "demo@example.com" } },
    { "cliquer": "Se connecter" },
    { "attendre": "/dashboard/.test(location.href)" },
    { "aller": "http://localhost:5173/invitations" },
    { "pause": 1500 },
    { "masquer": ".bandeau-cookies" },
    { "js": "document.querySelector('input').focus()" }
  ],
  "boites": { "zoneLien": "document.querySelector('#lien')", "itemMenu": "largeurMin(feuille(/^Inviter$/), 120)" },
  "styles": { "boutonPrincipal": "document.querySelector('button[type=submit]')", "itemActif": "feuille(/^Tableau de bord$/)" }
}
```

| Clé | Effet |
|---|---|
| `url` | Adresse `http(s)://`, `file://`, ou chemin local (avec `?lang=...` éventuel) |
| `attente` | Pause après chargement, polices et images prêtes (défaut 1 500 ms en http, 0 pour un fichier) |
| `fermer` | Expression régulière des boutons qui ferment carrousels, nouveautés et bandeaux ; appliquée après chaque étape |
| `cliquer` | Texte exact d'un bouton ou d'un lien, `/expression régulière/`, ou sélecteur CSS préfixé par `css:` |
| `attendre` | Expression JavaScript attendue vraie (25 s au plus) |
| `boites`, `styles` | Expressions JavaScript qui rendent un élément ; aides : `feuille(re)` (feuille du DOM dont le texte correspond), `ancetreFond(el, 'rgb(...)')`, `largeurMin(el, px)` |

Une session est nécessaire et les cookies ne suffisent pas : se connecter avec le navigateur de
l'agent s'il en a un, ou par les `etapes` (saisir, cliquer, attendre).

## Du JSON au film

Les cadres sont en pixels CSS du viewport. Le film affiche la capture dans `#real` à 1 120 px de
large : échelle `1120 / viewport[0]`, origine (400, 306) dans le monde. `cadresCapture()` de
`modele/film.html` lit `assets/ecran-reel-<lang>.json` et pose tout seul :
- l'état `RING` de la forme (cadre final) sur `boites.zoneLien`, 7 px de marge ;
- l'anneau `#ring2` sur `boites.itemMenu`, 5 px de marge.

Garder ces deux noms de boîte, ou adapter `cadresCapture()`. Le film ouvert depuis le disque
(`file://`) ne lit pas le JSON et garde les cadres écrits dans `ST` : seul le rendu par `render.js`
fait foi.

Une capture par langue : `"lang"` de la recette et `?lang=` de l'app s'il existe, sortie
`ecran-reel-<lang>.png`.
