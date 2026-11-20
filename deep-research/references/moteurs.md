# Moteurs, appels, quotas et tarifs

## Palier 0 : gratuit, à épuiser en premier

| Besoin | Outil | Coût |
|---|---|---|
| Doc d'une librairie, framework, SDK, CLI | **Context7**, jamais la recherche web pour ça | gratuit |
| Fils et sous-forums Reddit | MCP `reddit-mcp-buddy` | gratuit |
| Lire une page dont on a déjà l'URL | `WebFetch` | tokens seuls |
| Question factuelle simple, une seule réponse attendue | `WebSearch` natif | inclus dans l'abonnement |

Une question de doc technique s'arrête souvent au palier 0.

## Palier 1 : moteurs de recherche

### Parallel Search, moteur de référence

```bash
curl -s -X POST https://api.parallel.ai/v1/search \
  -H "x-api-key: $PARALLEL_API_KEY" -H "Content-Type: application/json" \
  -d '{"objective":"...","search_queries":["...","..."],"mode":"advanced"}'
```

- Les résultats portent une **date de publication** : c'est ce qui rend le filtre de fraîcheur réel.
- Passe communautaire restreinte à Reddit et Hacker News :

```json
"advanced_settings": {
  "source_policy": {
    "include_domains": ["reddit.com", "news.ycombinator.com"]
  }
}
```

Pièges de l'API : `max_results` est refusé à la racine ; `processor` et `max_chars_per_result` sont dépréciés au profit de `mode` et `excerpts.max_chars_per_result`. L'endpoint MCP est `search.parallel.ai/mcp`, jamais `mcp.parallel.ai`.

### Les autres moteurs, pour ce qu'ils font de mieux

| Outil | Sa force |
|---|---|
| **Firecrawl search** | Fraîcheur native `--tbs qdr:h/d/w/m`, catégories `--categories github,research,pdf`, géographie `--location` / `--country`, `--scrape` ramène le contenu complet en un appel. Bon pour un dépôt GitHub, un papier, un sujet francophone ou très frais |
| **Exa** | Seul moteur **sémantique** : cherche par le sens. Signature : `findSimilar` à partir d'une URL. Filtres par catégorie (`research paper`, `github`, `news`, `company`, `pdf`, `tweet`) et par date. Bon pour un champ mal nommé, des concurrents, une famille de sources |
| **Tavily** (MCP `tavily`) | Extraits courts filtrés par pertinence, classement différent de Parallel. Pour croiser un résultat douteux ou élargir un champ trop étroit |
| **Firecrawl agent** | Synthèse en langage naturel sur un jeu d'URL imposé (`--urls`), `--max-credits` obligatoire. Pour comparer un point précis sur 3 à 5 pages connues |

Exa en direct, quand le MCP `exa` ne suffit pas :

```bash
# recherche sémantique, résultats datés
curl -s -X POST https://api.exa.ai/search \
  -H "x-api-key: $EXA_API_KEY" -H "Content-Type: application/json" \
  -d '{"query":"...","type":"auto","numResults":10,
       "startPublishedDate":"<AAAA-MM-JJ>",
       "contents":{"text":{"maxCharacters":800}}}'

# partir d'une URL et trouver la même famille de contenu
curl -s -X POST https://api.exa.ai/findSimilar \
  -H "x-api-key: $EXA_API_KEY" -H "Content-Type: application/json" \
  -d '{"url":"https://...","numResults":10}'
```

Réflexe : quand une source excellente est trouvée, passer son URL à `findSimilar` plutôt que reformuler une requête.

### CLI Firecrawl

Paquet npm `firecrawl-cli` (`npm i -g firecrawl-cli`) ; avec nvm, il n'est dans le PATH que sous la version de Node qui l'a installé. Aide : `firecrawl <commande> --help`.

## Palier 2 : lecture lourde

| Besoin | Outil | Coût |
|---|---|---|
| Avaler un site, une doc entière, un blog complet | `firecrawl crawl` / `firecrawl map` | crédits Firecrawl |
| Extraire proprement 10 à 100 URL déjà identifiées | Parallel Extract | 0,001 $ par URL |

## Palier 3 : Parallel Task, le contradicteur

```bash
curl -s -X POST https://api.parallel.ai/v1/tasks/runs \
  -H "x-api-key: $PARALLEL_API_KEY" -H "Content-Type: application/json" \
  -d '{"input":"<objectif détaillé + contraintes de sources et de dates>",
       "processor":"core",
       "task_spec":{"output_schema":{"type":"text","description":"<format attendu>"}}}'
```

Récupération par polling sur `/v1/tasks/runs/<id>` puis `/result`, en tâche de fond (`run_in_background` + script de polling). Le MCP `parallel-task` (`createDeepResearch`, `getStatus`, `getResultMarkdown`) fait la même chose.

| Processeur | Usage | Coût par run |
|---|---|---|
| `base` | question factuelle | 0,010 $ |
| `core` | comparatif, 1 à 5 min | 0,025 $ |
| `pro` | vraie étude de marché | 0,100 $ |
| `ultra` → `ultra8x` | jamais sans accord de l'utilisateur | 0,30 $ → 2,40 $ |

## Quotas gratuits mensuels

| Fournisseur | Quota gratuit | Puis |
|---|---|---|
| Context7, Reddit MCP, WebFetch | illimité en pratique | |
| Parallel | 5 000 requêtes + 5 $ de crédits | 0,005 $ par recherche `advanced` |
| Exa | 10 $ de crédits, soit ~1 400 recherches | 7 $ / 1 000 recherches, 1 $ / 1 000 pages de contenu |
| Firecrawl | 1 000 crédits, 2 crédits par tranche de 10 résultats, soit ~500 recherches | abonnement, taux selon le palier |
| Tavily | 1 000 crédits | 0,008 $ le crédit |

## Tarifs Parallel à l'unité

| Appel | Coût |
|---|---|
| Search `turbo` / `fast` | 0,001 $ |
| Search `basic` / `advanced` | 0,005 $ |
| Résultats au-delà de 10 | 0,001 $ / 1 000 |
| Extract | 0,001 $ par URL |
| Task `base` / `core` / `pro` | 0,010 $ / 0,025 $ / 0,100 $ |
| Task `ultra` → `ultra8x` | 0,30 $ → 2,40 $ |
| Responses `low` / `medium` / `high` | 0,010 $ / 0,050 $ / 0,250 $ |

Les runs échoués ne sont pas facturés. Pour chiffrer le coût réel d'une étude, compter les appels effectivement facturés, pas les erreurs de validation.

## Rotation d'une clé

Éditer le fichier de clés chargé par le shell. Les serveurs MCP de Codex lisent les variables d'environnement ; ceux de Claude Code gardent leur copie dans `~/.claude.json`, à mettre à jour par `claude mcp remove <nom> -s user` puis `claude mcp add`.
