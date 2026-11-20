---
name: deep-research
description: "Multi-engine web research (Parallel, Exa, Tavily, Firecrawl) with dated sources checked against primary sources, delivered as a standalone HTML report. Use for a study, a comparison, a state of the art, a tool or company review, or a \"what is the best X\" question."
---

# Recherche intensive

Produire une étude sourcée et datée sur un sujet mouvant, en évitant les deux pièges qui ruinent une recherche web : le contenu périmé republié comme neuf, et le marketing déguisé en comparatif. Le livrable est un document HTML autonome dans `~/Downloads`, pas une réponse de chat.

## Avant de commencer
- Clés `$PARALLEL_API_KEY`, `$EXA_API_KEY`, `$FIRECRAWL_API_KEY`, `$TAVILY_API_KEY` : dans l'environnement (par exemple un fichier `keys.env` chargé par le profil du shell). Jamais de clé en dur dans un script.
- Serveurs MCP : `parallel-search`, `parallel-task`, `exa`, `tavily`, `reddit-mcp-buddy`, Context7. CLI `firecrawl` en shell.
- Budget : de l'ordre de 0,10 $ par étude. Au-delà de **0,75 $**, s'arrêter et demander à l'utilisateur en disant ce qui est dépensé et ce que coûterait la suite. Ce seuil ne vise que le palier 3 (Parallel Task, Responses).

## Le protocole en cinq temps

### 1. Cadrer avant de chercher
Fixer et annoncer dans le document :
- **La fenêtre temporelle.** Par défaut rien de plus vieux que 3 mois ; 6 semaines sur un sujet rapide (modèles, pricing, outils IA) ; jusqu'à un an sur un sujet stable (méthodo, droit, science).
- **La question de décision.** Ce que l'utilisateur fera du résultat. Sans décision derrière, on produit un catalogue.
- **Ce qui rendrait la réponse fausse.** Le vérifier en priorité.

### 2. Lancer le contradicteur en tâche de fond
Sur une question de fond, lancer un run Parallel Task **avant** de chercher soi-même, et travailler pendant qu'il tourne. Processeur : `base` pour un fait, `core` pour un comparatif, `pro` pour une étude de marché ; jamais au-dessus sans accord de l'utilisateur. Appel et polling : [references/moteurs.md](references/moteurs.md).

### 3. Faire sa propre passe en croisant les moteurs
Ne jamais dépendre d'un seul moteur : chacun voit un web différent. Aucun moteur n'est conditionné à un seuil ; croiser dès que le sujet le mérite.

| Palier | Outils | Quand |
|---|---|---|
| 0, gratuit | Context7, `reddit-mcp-buddy`, `WebFetch`, `WebSearch` | d'abord ; une question de doc technique s'arrête souvent là |
| 1, moteurs | **Parallel Search** (référence, par lui qu'on commence), Exa, Tavily, `firecrawl search` | selon ce que le sujet demande |
| 2, lecture lourde | `firecrawl crawl` / `map`, Parallel Extract | site ou doc entière, lot d'URL connues |
| 3, payant à l'unité | Parallel Task, Responses | le contradicteur ; seul poste qui pèse sur le budget |

Toujours au moins une passe Parallel restreinte à `reddit.com` et `news.ycombinator.com` : c'est là qu'est le signal d'usage réel. Écarter ce qui sort de la fenêtre temporelle, et dire quand une source clé est trop vieille.

Ces signaux appellent un moteur de plus :
1. Moins de quatre sources distinctes dans la fenêtre temporelle.
2. Tous les résultats convergent vers le même article ou se citent en boucle (signature SEO).
3. Une contradiction reste non tranchée après lecture des sources primaires.
4. Sujet de niche, non anglophone, ou daté à l'heure près.

Un désaccord entre deux moteurs est une information, pas un problème.

### 4. Arbitrer les désaccords à la source primaire
L'étape qui fait la valeur du livrable, et celle qu'on est tenté de sauter. Quand le rapport délégué et la passe manuelle divergent, ni l'un ni l'autre n'a raison par défaut : lire la page officielle.

Hiérarchie des sources :
1. Page de pricing, changelog, annonce officielle du fournisseur
2. Benchmark indépendant et reproductible, méthodologie publiée
3. Documentation technique
4. Retour d'usage communautaire daté
5. (en dessous, rien qui puisse porter un chiffre)
6. Article de comparaison, billet de blog, agrégateur

**Aucun chiffre du document ne vient du niveau 6** : un chiffre sans source primaire datée reste hors du document.

### 5. Écrire le document
HTML autonome dans `/tmp` (CSS et JS inclus), copié dans `~/Downloads/` et ouvert dans Chrome. Structure :
1. **Verdict** : la recommandation en un paragraphe, avant toute donnée
2. **Ce qui a bougé** : les faits datés qui invalident les réponses d'hier
3. **Les données** : tableaux comparatifs, une ligne de lecture par ligne
4. **Recommandations par cas d'usage**, dont une ligne pour le cas de l'utilisateur
5. **Signal terrain** : citations Reddit et HN, avec leur limite
6. **Fiabilité** : contradictions rencontrées, tranchées ou non, durée de vie du document
7. **Sources** : primaires, datées, avec ce qui a servi à quoi

## Règles non négociables
- **Jamais une seule source.** Au minimum : le moteur principal, une passe Reddit et HN, et la page officielle pour chaque chiffre.
- **Ne jamais rogner sur les moteurs ou les requêtes pour économiser** : à volume normal, les paliers 0 à 2 restent dans les quotas gratuits ; c'est le résultat qu'on abîme, pas la facture.
- **Signaler le marketing.** Blog d'un acteur premier de son propre comparatif, SEO généré qui place un inconnu en tête : le nommer dans le document plutôt que l'ignorer.
- **Dater la durée de vie** du document et dire ce qu'il faudra revérifier.
- **Ne jamais lisser une contradiction.** Non tranchée, elle s'écrit telle quelle ; jamais de moyenne inventée.
- **Reconnaître ses erreurs.** Quand le rapport délégué corrige la passe manuelle, le dire et corriger le document.
- **Wording** : jamais de tiret cadratin ni de point-virgule dans le texte du livrable. Tables pour tout ce qui est comparable. Bloc `TODO` en fin de réponse.
- Coût réel de l'étude en fin de réponse si l'utilisateur le demande, en ne comptant que les appels facturés.

## Claude Code et Codex
Ce fichier est le protocole canonique, partagé entre Claude Code et Codex : un prompt Codex `/recherche-intensive` peut simplement renvoyer ici. Toute modification du protocole se fait ici.

| | Claude Code | Codex |
|---|---|---|
| Serveurs MCP | dans `~/.claude.json` | les mêmes dans `~/.codex/config.toml`, via `bearer_token_env_var` |
| Doc de librairie | Context7 | pas de Context7 : `openaiDeveloperDocs` pour OpenAI, sinon doc officielle en direct |
| Moteur en plus | | MCP `brave-search` |

## Références (à lire seulement si l'étape l'exige)
- [references/moteurs.md](references/moteurs.md) (`~/.claude/skills/deep-research/references/moteurs.md`) : appels `curl` Parallel, Exa et Task, pièges d'API, force de chaque moteur, flags Firecrawl et chemin du CLI, quotas gratuits, tarifs Parallel, rotation des clés. À lire avant le premier appel d'API ou pour chiffrer un coût.
