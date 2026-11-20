# Mouvement : comment un film est construit

## Le moteur (`modele/moteur.js`, à ne pas modifier)

- Charte : `couleur('--brand')` rend une variable de `charte.css` en `[r, g, b, a]` pour `trA` ;
  `alpha(c, a)` en fait une chaîne `rgba` ; `logos()` remplit les `<img data-logo="clair|fonce">` ;
  `policesCharte()` liste les polices à attendre. **Aucune couleur en dur** dans le film : en CSS,
  `var(--brand)` et `color-mix(in srgb, var(--brand) 20%, transparent)` pour une transparence.
  Dans un attribut SVG (`fill`, `stroke`), `var()` ne marche pas : passer par `style="fill:var(--brand)"`.

- `sp(t, t0, 'ressort')` : progression 0 à 1 d'un ressort parti à `t0`.
- `tr(t, v0, [[instant, valeur, ressort], ...])` : une valeur qui change **plusieurs fois** de
  cible. Un ressort par changement, jamais de redémarrage : le mouvement reste continu, et
  n'importe quelle image se calcule seule, sans simuler les précédentes.
- `trA` : pareil pour une couleur `[r, g, b, a]`.
- `io(t, entree, sortie)` : visibilité d'un élément.
- `enter(t, entree, sortie, options)` : entrée et sortie standard d'un décor (monte, se précise,
  s'efface en flou).
- `imp(t, t0, amplitude)` : secousse amortie. Négative pour un clic (la forme s'enfonce),
  positive pour une pulsation de succès.
- `put(el, {x, y, s, r, o, blur})`, `words(el)` (titre découpé en mots), `demarrer({...})`.

Ressorts : `snap` (boutons, icônes), `ui` (interface, par défaut), `def` (cartes, la forme),
`heavy` (plein écran, sans rebond), `play` (pastilles, rebond visible), `cam` (caméra, lent),
`soft` (fondus). **Léger rebond sur l'interface, aucun sur les grands textes.** Jamais de courbe
d'animation classique (ease-in-out) : c'est ce qui donne l'effet « diaporama ».

## La forme unique

1. **Lister ses états** dans `ST` : position, taille, rayon, un par étape.
   Exemple du modèle : `FULL` (plein écran), `CHIP` (bouton Rejoindre puis pastille), `MENU`, `INPUT`,
   `LINK`, `STICKER` (ligne de lien dans la messagerie), `RING`.
2. **Enchaîner les états** dans `GEO` : `[instant, 'ETAT', ressort]`. Couleur de fond dans
   `BG_KEYS`, bordure, halo et ombre dans leurs propres suites de clés.
3. **Chaque état a son contenu** : un calque par état (`#cChip`, `#cMenu`...), de taille fixe
   égale à celle de l'état, qui apparaît **après** l'arrivée de la forme et disparaît **avant**
   son départ (ressort `snap` en sortie).
4. **Passage de relais** : quand la forme quitte un élément qui doit rester à l'écran (le champ URL
   reste pendant que le lien apparaît), une **copie fixe** identique apparaît à la même image
   (`#inputS`), et la forme repart. Le spectateur ne voit aucune coupure.
5. **Couleurs de transition** : passer de `--brand` à `--success-bg` traverse souvent un gris terne. Faire
   atterrir la forme dans un décor **déjà présent**, et changer la couleur pendant l'atterrissage.
6. Fin : la forme se pose en **cadre** sur la vraie capture (`cadresCapture()` lit le JSON de
   capture, voir `capture.md`), puis s'élargit en plein écran `--brand`.

## Rythme

- Grille de 0,5 s (120 battements par minute) : les changements tombent sur la grille, une musique
  pourra être ajoutée plus tard sans remonter le film.
- Accroche : 3 s maximum, trois mots-phrases qui montent sur les battements, un mot surligné.
- Une étape : 3 à 5 s. Une idée par étape, une légende par étape (titre + une ligne).
- Une étape peut changer de sous-titre en cours (`SUBS`) quand l'action change de sens.
- Fin : environ 2,5 s de plein écran `--brand` avec logo, titre et pastille « La doc complète ».
- Total : environ 7 s par étape, pauses comprises. Le film de référence fait 36,7 s pour 5 étapes.

## Laisser le temps de lire (pauses)

Règle, vérifiée sur le film de référence : **chaque texte reste affiché, en entier et immobile, au
moins 0,4 s + 0,3 s par mot**. Un sous-titre de 8 mots demande 2,8 s. Compter à partir du moment où
le texte est **entièrement** apparu, jusqu'au début de sa sortie.

Pour tenir la règle sans ralentir les mouvements (qui perdraient leur vivacité), le modèle **met le
film en pause** aux instants où tout est posé :

```js
const HOLDS = [[2.0, 1.0], [3.6, .5], ...];   // [instant du film sans pauses, durée de la pause]
function hold(T) { let acc = 0; for (const [a, d] of HOLDS) { if (T < a + acc) return T - acc; if (T < a + acc + d) return a; acc += d; } return T - acc; }
function paint(T) { const t = hold(T); const u = warp(t); paintBase(u, T); scene1(t, u); }
```

- Pendant une pause, tout ce qui raconte se fige ; **le fond continue** (halos, trame, respiration de
  la caméra), ainsi que tout ce qui oscille en permanence (illustration qui flotte, curseur texte,
  pulsations) : ces éléments utilisent le temps ambiant `tReel`, jamais `t`.
- Placer une pause **après** la fin des effets brefs : une onde de clic figée en pleine expansion
  fait un cercle suspendu.
- Placer la pause **avant** la sortie de la légende, quand la forme et le décor sont arrivés.
- Vérifier avec une planche prise au milieu de chaque pause : chaque image doit être complète et
  immobile.

## Allonger une scène sans tout décaler (retouche)

Un film porte une centaine de repères de temps. Pour allonger une scène, ne pas les décaler à la
main : insérer du temps avec `warp()`, comme dans le modèle, où la scène 1 (Rejoindre, En attente,
Membre) a reçu 1,2 s de plus que le reste du film.

```js
const INS_A = 4.3, INS_D = 1.2;   // à 4,3 s, on insère 1,2 s
const warp = (t) => t <= INS_A ? t : (t <= INS_A + INS_D ? INS_A : t - INS_D);
function paint(t) { const u = warp(t); paintBase(u, t); scene1(t, u); }
```

- `paintBase(u, tReel)` : tout le film, sur le temps décalé. Le fond (halos, trame, respiration de
  la caméra) utilise `tReel`, sinon il se fige pendant l'insertion.
- `scene1(t, u)` : la scène allongée, racontée en temps réel. Elle **écrase** ce que la base
  dessine pendant l'insertion, et doit **converger vers l'état de la base** à `INS_A + INS_D`,
  instant où la base reprend la main. Choisir `INS_A` à un moment où la base est immobile.
- Les calques créés pour la scène allongée doivent être masqués hors de sa fenêtre.

## Caméra

- `camFx`, `camFy`, `camZ` avec le ressort `cam`, plus une respiration imperceptible
  (`0.012 * sin(t * 0.35)`).
- Zoomer (1,15 à 1,2) **uniquement** sur le moment clé. Avant de zoomer, effacer ce qui glisserait
  sous la bande de légende.
- Le curseur est dans le monde, mais contre-mis à l'échelle (`/ camZ`) pour garder la même taille.

## Curseur et clics

- Segments visibles (`CUR`) : il apparaît, se déplace avec `def`, clique, puis disparaît. Il n'est
  jamais là quand il ne sert à rien.
- Chaque clic : le curseur s'enfonce (`imp` négatif), une onde de la couleur `--brand` s'étend, et l'élément cliqué
  réagit sur la même image (couleur, `imp` sur la forme).
- Viser à côté du libellé, jamais dessus.

## Textes

- Titres : mots masqués qui montent un par un (`words`, décalage de 0,045 s).
- Texte tapé : révélation par caractères avec une courbe qui ralentit à la fin, curseur texte qui
  clignote. Texte collé : balayage de gauche à droite en 0,25 s (plus juste qu'une frappe).
- Un texte long dans une zone : ajuster la taille à l'initialisation (boucle dans `init()`).
