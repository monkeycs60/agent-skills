---
name: deep-research
description: "Multi-engine web research (Parallel, Exa, Tavily, Firecrawl) with dated sources checked against primary sources, delivered as a standalone HTML report. Use for a study, a comparison, a state of the art, a tool or company review, or a \"what is the best X\" question."
---

# Deep research

Produce a sourced, dated study on a fast-moving topic while avoiding the two traps that ruin web research: stale content republished as new, and marketing dressed up as a comparison. The deliverable is a standalone HTML document in `~/Downloads`, not a chat answer.

Answer the user, and write every report or deliverable, in the language of the user's request, whatever the language of this skill's files.

## Before you start
- Keys `$PARALLEL_API_KEY`, `$EXA_API_KEY`, `$FIRECRAWL_API_KEY`, `$TAVILY_API_KEY`: in the environment (for example a `keys.env` file loaded by the shell profile). Never hard-code a key in a script.
- MCP servers: `parallel-search`, `parallel-task`, `exa`, `tavily`, `reddit-mcp-buddy`, Context7. `firecrawl` CLI in the shell.
- Budget: around $0.10 per study. Above **$0.75**, stop and ask the user, stating what has been spent and what the rest would cost. This threshold only covers tier 3 (Parallel Task, Responses).

## The five-step protocol

### 1. Frame before searching
Set and state in the document:
- **The time window.** By default nothing older than 3 months; 6 weeks on a fast topic (models, pricing, AI tools); up to a year on a stable topic (methodology, law, science).
- **The decision question.** What the user will do with the result. Without a decision behind it, you produce a catalogue.
- **What would make the answer wrong.** Check that first.

### 2. Start the contrarian in the background
On a substantive question, start a Parallel Task run **before** searching yourself, and keep working while it runs. Processor: `base` for a fact, `core` for a comparison, `pro` for a market study; never higher without the user's approval. Call and polling: [references/engines.md](references/engines.md).

### 3. Do your own pass, crossing engines
Never depend on a single engine: each one sees a different web. No engine is gated behind a threshold; cross them as soon as the topic deserves it.

| Tier | Tools | When |
|---|---|---|
| 0, free | Context7, `reddit-mcp-buddy`, `WebFetch`, `WebSearch` | first; a technical docs question often stops here |
| 1, engines | **Parallel Search** (the reference, start with it), Exa, Tavily, `firecrawl search` | as the topic requires |
| 2, heavy reading | `firecrawl crawl` / `map`, Parallel Extract | a whole site or doc, a batch of known URLs |
| 3, pay per call | Parallel Task, Responses | the contrarian; the only line that weighs on the budget |

Always run at least one Parallel pass restricted to `reddit.com` and `news.ycombinator.com`: that is where real usage signal lives. Drop what falls outside the time window, and say when a key source is too old.

These signals call for one more engine:
1. Fewer than four distinct sources within the time window.
2. All results converge on the same article or cite each other in a loop (SEO signature).
3. A contradiction remains unresolved after reading the primary sources.
4. Niche topic, non-English, or dated to the hour.

A disagreement between two engines is information, not a problem.

### 4. Settle disagreements at the primary source
The step that gives the deliverable its value, and the one you are tempted to skip. When the delegated report and the manual pass diverge, neither is right by default: read the official page.

Source hierarchy:
1. Vendor pricing page, changelog, official announcement
2. Independent, reproducible benchmark with published methodology
3. Technical documentation
4. Dated community usage report
5. (below this, nothing that can carry a number)
6. Comparison article, blog post, aggregator

**No number in the document comes from level 6**: a number without a dated primary source stays out of the document.

### 5. Write the document
Standalone HTML in `/tmp` (CSS and JS inline), copied to `~/Downloads/` and opened in Chrome. Structure:
1. **Verdict**: the recommendation in one paragraph, before any data
2. **What changed**: the dated facts that invalidate yesterday's answers
3. **The data**: comparison tables, one reading line per row
4. **Recommendations by use case**, including one line for the user's case
5. **Field signal**: Reddit and HN quotes, with their limits
6. **Reliability**: contradictions met, settled or not, the document's shelf life
7. **Sources**: primary, dated, with what each one was used for

## Non-negotiable rules
- **Never a single source.** At minimum: the main engine, a Reddit and HN pass, and the official page for every number.
- **Never cut engines or queries to save money**: at normal volume, tiers 0 to 2 stay within free quotas; cutting damages the result, not the bill.
- **Call out marketing.** A vendor's blog ranking itself first in its own comparison, generated SEO putting an unknown on top: name it in the document instead of ignoring it.
- **Date the document's shelf life** and say what will need rechecking.
- **Never smooth over a contradiction.** Unresolved, it is written as is; never an invented average.
- **Own your mistakes.** When the delegated report corrects the manual pass, say so and fix the document.
- **Wording**: never an em dash or a semicolon in the deliverable's text. Tables for everything comparable. `TODO` block at the end of the reply.
- Real cost of the study at the end of the reply if the user asks, counting only billed calls.

## Claude Code and Codex
This file is the canonical protocol, shared between Claude Code and Codex: a Codex prompt `/recherche-intensive` can simply point here. Any change to the protocol is made here.

| | Claude Code | Codex |
|---|---|---|
| MCP servers | in `~/.claude.json` | the same ones in `~/.codex/config.toml`, via `bearer_token_env_var` |
| Library docs | Context7 | no Context7: `openaiDeveloperDocs` for OpenAI, otherwise official docs directly |
| Extra engine | | MCP `brave-search` |

## References (read only when the step requires it)
- [references/engines.md](references/engines.md) (`~/.claude/skills/deep-research/references/engines.md`): Parallel, Exa and Task `curl` calls, API pitfalls, each engine's strength, Firecrawl flags and CLI path, free quotas, Parallel pricing, key rotation. Read before the first API call or to estimate a cost.
