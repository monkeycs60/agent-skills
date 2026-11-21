# Engines, calls, quotas and pricing

## Tier 0: free, use it up first

| Need | Tool | Cost |
|---|---|---|
| Docs for a library, framework, SDK, CLI | **Context7**, never web search for this | free |
| Reddit threads and subreddits | MCP `reddit-mcp-buddy` | free |
| Read a page whose URL you already have | `WebFetch` | tokens only |
| Simple factual question, one expected answer | native `WebSearch` | included in the subscription |

A technical docs question often stops at tier 0.

## Tier 1: search engines

### Parallel Search, the reference engine

```bash
curl -s -X POST https://api.parallel.ai/v1/search \
  -H "x-api-key: $PARALLEL_API_KEY" -H "Content-Type: application/json" \
  -d '{"objective":"...","search_queries":["...","..."],"mode":"advanced"}'
```

- Results carry a **publication date**: that is what makes the freshness filter real.
- Community pass restricted to Reddit and Hacker News:

```json
"advanced_settings": {
  "source_policy": {
    "include_domains": ["reddit.com", "news.ycombinator.com"]
  }
}
```

API pitfalls: `max_results` is rejected at the root; `processor` and `max_chars_per_result` are deprecated in favour of `mode` and `excerpts.max_chars_per_result`. The MCP endpoint is `search.parallel.ai/mcp`, never `mcp.parallel.ai`.

### The other engines, for what they do best

| Tool | Its strength |
|---|---|
| **Firecrawl search** | Native freshness `--tbs qdr:h/d/w/m`, categories `--categories github,research,pdf`, geography `--location` / `--country`, `--scrape` returns the full content in one call. Good for a GitHub repo, a paper, a French-language or very fresh topic |
| **Exa** | The only **semantic** engine: searches by meaning. Signature move: `findSimilar` from a URL. Filters by category (`research paper`, `github`, `news`, `company`, `pdf`, `tweet`) and by date. Good for a poorly named field, competitors, a family of sources |
| **Tavily** (MCP `tavily`) | Short excerpts filtered by relevance, a ranking different from Parallel's. To cross-check a doubtful result or widen a field that is too narrow |
| **Firecrawl agent** | Natural-language synthesis over a fixed set of URLs (`--urls`), `--max-credits` required. To compare a precise point across 3 to 5 known pages |

Exa directly, when the `exa` MCP is not enough:

```bash
# semantic search, dated results
curl -s -X POST https://api.exa.ai/search \
  -H "x-api-key: $EXA_API_KEY" -H "Content-Type: application/json" \
  -d '{"query":"...","type":"auto","numResults":10,
       "startPublishedDate":"<YYYY-MM-DD>",
       "contents":{"text":{"maxCharacters":800}}}'

# start from a URL and find the same family of content
curl -s -X POST https://api.exa.ai/findSimilar \
  -H "x-api-key: $EXA_API_KEY" -H "Content-Type: application/json" \
  -d '{"url":"https://...","numResults":10}'
```

Reflex: when you find an excellent source, pass its URL to `findSimilar` rather than rephrasing a query.

### Firecrawl CLI

npm package `firecrawl-cli` (`npm i -g firecrawl-cli`); with nvm, it is only on the PATH under the Node version that installed it. Help: `firecrawl <command> --help`.

## Tier 2: heavy reading

| Need | Tool | Cost |
|---|---|---|
| Ingest a site, a whole doc, a full blog | `firecrawl crawl` / `firecrawl map` | Firecrawl credits |
| Cleanly extract 10 to 100 already identified URLs | Parallel Extract | $0.001 per URL |

## Tier 3: Parallel Task, the contrarian

```bash
curl -s -X POST https://api.parallel.ai/v1/tasks/runs \
  -H "x-api-key: $PARALLEL_API_KEY" -H "Content-Type: application/json" \
  -d '{"input":"<detailed objective + source and date constraints>",
       "processor":"core",
       "task_spec":{"output_schema":{"type":"text","description":"<expected format>"}}}'
```

Fetch by polling `/v1/tasks/runs/<id>` then `/result`, in the background (`run_in_background` + a polling script). The `parallel-task` MCP (`createDeepResearch`, `getStatus`, `getResultMarkdown`) does the same.

| Processor | Use | Cost per run |
|---|---|---|
| `base` | factual question | $0.010 |
| `core` | comparison, 1 to 5 min | $0.025 |
| `pro` | real market study | $0.100 |
| `ultra` → `ultra8x` | never without the user's approval | $0.30 → $2.40 |

## Monthly free quotas

| Provider | Free quota | Then |
|---|---|---|
| Context7, Reddit MCP, WebFetch | unlimited in practice | |
| Parallel | 5,000 requests + $5 of credits | $0.005 per `advanced` search |
| Exa | $10 of credits, about 1,400 searches | $7 / 1,000 searches, $1 / 1,000 content pages |
| Firecrawl | 1,000 credits, 2 credits per batch of 10 results, about 500 searches | subscription, rate depends on the tier |
| Tavily | 1,000 credits | $0.008 per credit |

## Parallel unit pricing

| Call | Cost |
|---|---|
| Search `turbo` / `fast` | $0.001 |
| Search `basic` / `advanced` | $0.005 |
| Results beyond 10 | $0.001 / 1,000 |
| Extract | $0.001 per URL |
| Task `base` / `core` / `pro` | $0.010 / $0.025 / $0.100 |
| Task `ultra` → `ultra8x` | $0.30 → $2.40 |
| Responses `low` / `medium` / `high` | $0.010 / $0.050 / $0.250 |

Failed runs are not billed. To compute the real cost of a study, count the calls actually billed, not validation errors.

## Rotating a key

Edit the key file loaded by the shell. Codex MCP servers read environment variables; Claude Code's keep their own copy in `~/.claude.json`, to be updated with `claude mcp remove <name> -s user` then `claude mcp add`.
