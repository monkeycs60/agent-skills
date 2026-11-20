# Le vrai Chrome de l'utilisateur

En mode par défaut, `ab` s'attache au Chrome déjà ouvert par l'utilisateur (`--auto-connect` d'agent-browser) et travaille dans un onglet réservé à la conversation (`--pin-tab`). L'agent hérite de toutes les connexions de ce profil : aucun identifiant à saisir, aucun cookie à exporter.

## Mise en route, une fois par machine

1. Chrome 144 ou plus récent, ouvert avec le profil dont les connexions servent.
2. L'utilisateur ouvre `chrome://inspect/#remote-debugging` et autorise le débogage à distance. Chrome publie alors son port de débogage dans son dossier de profil, où `ab` le retrouve seul.
3. Première commande d'une conversation : Chrome affiche une demande d'autorisation de connexion. L'utilisateur la valide, puis l'agent relance la commande.

Ne pas contourner cette demande ni reprendre le profil d'une autre personne. Si Chrome manque, l'utilisateur l'installe depuis https://www.google.com/chrome/.

## Quand Chrome redemande l'autorisation

Chaque conversation ouvre sa propre connexion. Chrome peut donc redemander l'autorisation :

- à la première commande de chaque nouvelle conversation ;
- après un redémarrage de Chrome ;
- après une heure sans commande dans la conversation, quand agent-browser a fermé sa connexion.

Après un redémarrage de Chrome, la commande suivante se reconnecte d'elle-même, sans intervention de l'agent une fois l'autorisation donnée.

## Ce que voit l'utilisateur

- L'onglet de l'agent s'ouvre dans la fenêtre Chrome active et y passe au premier plan. Chaque nouvelle conversation en ouvre un de plus.
- `ab close` ferme cet onglet et lui seul. `ab` ne ferme jamais Chrome ni les onglets de l'utilisateur.
- Le focus clavier et la fenêtre active ne sont pas protégés : selon le système, l'ouverture de l'onglet ou un clic de l'agent peut ramener Chrome devant. Prévenir l'utilisateur avant un long parcours en vrai Chrome, ou passer en mode isolé si ses connexions ne servent pas.

## Clics lents : l'onglet de l'agent est en arrière-plan

Chrome ne peint pas un onglet caché. Dès qu'un autre onglet passe devant celui de l'agent dans la même fenêtre (l'utilisateur change d'onglet, une autre conversation ouvre le sien), chaque clic de l'agent attend environ 5 s, contre quelques dizaines de millisecondes au premier plan. `fill`, `press`, `snapshot`, `read` et `screenshot` restent rapides.

Remèdes, du plus simple au plus sûr :

- une seule conversation à la fois en vrai Chrome ;
- l'utilisateur détache l'onglet de l'agent dans sa propre fenêtre : l'onglet actif de chaque fenêtre visible reste peint ;
- mode isolé pour tout ce qui n'exige pas ses connexions ;
- pour une vidéo, garder l'onglet de l'agent au premier plan pendant toute la prise.

## Option avancée : un Chrome dédié aux agents (`AB_CDP`)

Un second Chrome, avec son propre profil, évite les demandes d'autorisation et laisse intact le Chrome principal. L'utilisateur s'y connecte une fois aux sites utiles ; les connexions y restent.

```bash
google-chrome --user-data-dir="$HOME/.chrome-agents" --remote-debugging-port=9222
open -na "Google Chrome" --args --user-data-dir="$HOME/.chrome-agents" --remote-debugging-port=9222
AB_CDP=9222 ab open https://example.com
```

La première ligne vaut pour Linux, la deuxième pour macOS. Chrome ignore `--remote-debugging-port` sur le profil par défaut : le dossier `--user-data-dir` doit être distinct. Tant que ce port est ouvert, tout programme local peut piloter ce profil et lire ses cookies : réserver ce Chrome aux comptes que l'utilisateur accepte d'y exposer. `AB_CDP` accepte aussi une URL `ws://…` vers un relais CDP de son choix.

## Pannes

| Symptôme | Cause | Action |
|---|---|---|
| `No running Chrome instance found`, suivi du conseil de `ab` | Chrome fermé, ou débogage à distance non autorisé | Demander à l'utilisateur d'ouvrir Chrome et de vérifier `chrome://inspect/#remote-debugging`. Si ses connexions ne servent pas : `AB_ISOLATED=1`. |
| La première commande échoue ou attend | Demande d'autorisation affichée dans Chrome | Prévenir l'utilisateur, attendre son clic, relancer. |
| `tab_gone` | L'onglet de l'agent a été fermé | `ab` en rouvre un vierge à la commande suivante : refaire `open`. Si l'erreur persiste : `ab tab new about:blank`. |
| Chaque clic prend environ 5 s | Onglet de l'agent en arrière-plan | Voir « Clics lents » ci-dessus. |
| `Unknown ref` | Refs périmées après navigation | `ab snapshot -i`, puis utiliser les nouvelles refs. |
| Toute autre erreur inattendue | Installation ou démon en mauvais état | `AB_ISOLATED=1 ab doctor`. |
