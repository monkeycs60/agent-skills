# Boucle d'autocritique

Le premier rendu n'est jamais le bon : ne montrer la vidéo qu'après cette boucle.

## Signature : vérifier qu'aucun élément ne manque, dans cet ordre

1. **Accroche** : plein écran `--brand` avec reflet, trois phrases très courtes en police de titre
   900 qui montent sur les battements, un mot surligné sur un bandeau `--accent`, un pictogramme
   au trait à droite.
2. **La forme se rétracte** et devient le premier objet de l'histoire, puis ne quitte plus l'écran.
3. **Une étape, une légende** en haut à gauche (pastille numérotée, titre, sous-titre), barre de
   progression en bas.
4. **Décors fidèles à l'app** : libellés du code, couleurs de la charte, curseur qui clique à côté
   des libellés, onde au clic, ressorts à léger rebond.
5. **Un prérequis se raconte** (demander, en attente, validé).
6. **Le moment « waouh »** : zoom caméra doux, texte qui s'écrit.
7. **Ce qui se passe hors de l'app** se montre sur son vrai support, sans logo de tiers.
8. **La vraie capture** dans une fenêtre, la forme posée en cadre sur l'élément clé.
9. **Fin** : plein écran `--brand`, logo `--logo-fonce`, titre, pastille vers la doc.
10. **Pauses de lecture** partout où un texte doit être lu, le fond restant vivant.
11. **Kit YouTube** si la vidéo va sur YouTube (`youtube.md`).

## Quelles images regarder

1. **Planche des moments clés** : une image au milieu de chaque étape, plus l'accroche et la fin
   (12 à 16 images, `render.js planche`).
2. **Planche des transitions** : une image 0,1 à 0,3 s après **chaque** départ de la forme et
   **chaque** changement de décor. Les défauts se cachent là.
3. **Une image en pleine taille** au moment clé (dans le dossier des images, `still-XXXXX.jpg`)
   pour juger la netteté et les chevauchements.

## Grille de notation, sur 10 par image

| Critère | Question |
|---|---|
| Lisibilité | Tout se lit-il à 800 px de large ? Rien sous 22 px ? |
| Une idée | Voit-on une seule chose importante, ou deux qui se disputent ? |
| Justesse | Libellés identiques au code ? Rien d'inventé côté interface ? |
| Charte | Couleurs, polices, rayons et logo sont-ils ceux de l'app ? Une personne de l'équipe reconnaîtrait-elle son produit ? |
| Composition | Équilibre avec la bande de légende ? Rien de coupé par le bord ? |
| Continuité | La forme est-elle toujours identifiable ? Aucun élément qui surgit ou flotte ? |

Écrire les **trois pires défauts**, les corriger, refaire une planche. S'arrêter quand toutes les
images sont à 8 ou plus.

## Défauts déjà rencontrés (les chercher d'abord)

- Icône posée du mauvais côté (`left:0` imposé par `.a`), alors que le curseur clique de l'autre.
- Curseur posé sur le libellé qu'il clique.
- Décor trop petit pour être lu (une carte de 800 x 210 ne se lit plus : 900 x 240 au moins).
- Filet résiduel quand un titre sort de son masque : l'estomper pendant la sortie.
- Forme qui arrive avant son décor : faire entrer le décor d'abord.
- Contenu de la forme encore visible pendant le changement de scène suivant.
- Couleur terne pendant un changement de teinte (`--brand` vers `--success-bg`).
- Décor qui glisse sous la légende pendant un zoom.
- Pastille qui survit à sa carte : son contenu doit disparaître, et la forme partir, avec la carte.
- Élément invisible parce qu'il est dessiné **sous** la forme (le doigt sous la ligne de lien
  blanche) : vérifier l'ordre dans le HTML avant de toucher aux couleurs.
- Action qui se passe hors de l'app montrée dans un décor qui ressemble à l'app.
- Texte qui part avant d'avoir pu être lu (règle : 0,4 s + 0,3 s par mot, immobile).
- Texte qui déborde de son conteneur après un changement de libellé (un domaine plus long dans la
  ligne de lien) : après toute retouche de texte, regarder l'image en pleine taille.
- Pause posée pendant un effet bref (onde de clic, étincelles) : l'effet se fige à l'écran.
- Annotation qui interprète un paramètre d'URL (« Votre profil » sous un paramètre qui ne désigne
  pas toujours le profil) ou qui mentionne une option absente du lien montré. Relire chaque
  annotation en se demandant : est-ce vrai pour **tous** les comptes, pas seulement sur la démo ?

## Après l'encodage

`render.js verifier` compare six images décodées du MP4 aux mêmes images rendues à nouveau
(`outils.md`). Attendu : écart moyen autour de 1, écart ponctuel de 1 à 3 sur les aplats, jusqu'à 12
sur le bord d'un texte de couleur vive (sous-échantillonnage des couleurs, normal). Un écart moyen
au-dessus du seuil (3 avec ffmpeg, 5 avec le lecteur du navigateur), ou de 10 **sur un aplat**,
signale un problème de matrice ou de plage de couleurs : la commande sort alors en erreur. Regarder aussi `image-decodee-*.png` en pleine taille.
