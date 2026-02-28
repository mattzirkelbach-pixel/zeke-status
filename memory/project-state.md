# Zeke Project State — Current Reality
# This file is the SINGLE SOURCE OF TRUTH for project state.
# Updated every session. NOT append-only — overwritten with current facts.
# Read this FIRST in every conversation via get_session_context.
# Last updated: 2026-02-28T03:55:00Z

## Infrastructure Status

### Scheduler & Pipeline
- **Scheduler**: Running (PID alive), 30-min daytime cycles, overnight research
- **Camel Pipeline v3**: Tiered dispatch (fetch=$0, analyze=Haiku $0.003/chunk). Proven 8/10 vs Ollama 0/10.
- **Spark Lock**: `~/spark_lock.py` — advisory lock. Scheduler + pipeline + self-repair all use it.
- **Quality Scorer**: Runs every 3h. Feed deduped and stable.
- **Dashboard**: http://100.64.219.70:3334 — temporal decay LIVE (14d half-life, staleness at 45d)
- **Mission Control**: https://mattzirkelbach-pixel.github.io/zeke-status/ — v12, compute arch + 4-layer autonomy

### Compute Architecture (NEW — 2/28)
- **Architecture doc**: ~/zeke-compute-architecture.md (definitive reference)
- **Dispatch engine**: ~/zeke_dispatch.py — routes tasks to cheapest capable tier
- **Key insight**: Spark = knowledge layer + background processor, NOT cheap API replacement
- **Tiers**: L0 Python($0) → L1 Vector/RAG(planned,$0) → L2 Triage(8B,$0) → L3 API(Haiku/Sonnet) → L4 Batch(32B overnight,$0)
- **Budget**: $2/day cap. Haiku $1, Sonnet $0.50, Opus $0.25. File: ~/.zeke-dispatch-budget.json
- **HIGHEST PRIORITY**: ChromaDB + nomic embeddings for RAG (Phase 1 of implementation)

### Known Issues
- CF web crawl stalled at 8/34 lessons — needs restart
- YouTube IP-blocking after ~20 bulk fetches (expected, use delays)
- qwen3-32b still hot (29.1GB VRAM) — should be on-demand only per new architecture

### Cron Schedule (14 jobs)
- guardian (1min), watchdog (10min), mcp-watchdog (5min), status-push (5min)
- snapshots (15min), feed-guardian (15min), quality-scorer (3h)
- self-repair (30min), camel-pipeline-v2 (6h), dedup (3am), session-purge (4am)
- nightly-synthesis (5am), price-fetch (6am), trade-alerts v2 (10min weekdays)

## Autonomy Layers (The Recursive Learning Vision)

### L1: Execution — DEPLOYED
Scheduler runs 30-min cycles. Cron triggers 14 jobs. Fire-and-forget pipelines.
Data flows: fetch transcripts → analyze → ingest → feed. Deterministic, reliable.

### L2: Oversight — DEPLOYED
Self-repair detects and fixes failures. Watchdog monitors MCP/Spark health.
Feed guardian validates data quality. Quality scorer audits entries.
System heals itself without human intervention.

### L3: Intelligence — IN PROGRESS
Tiered dispatch routes work to optimal compute. Haiku extracts structured data.
Camel Finance analysis produces thesis-level insights. Temporal decay weights recency.
NEXT: ChromaDB RAG layer makes every API call context-aware.

### L4: Recursive Learning — PLANNED
The system improves itself. Overnight batch (32B, $0) re-analyzes Haiku output.
Feedback loop: API output → embed → vector DB → enriches next API call.
Cross-source synthesis: transcripts + lessons + feed = compound knowledge.
Thesis ledger tracks conviction over time. Conflicts surface automatically.
**This is the goal: each cycle makes the next cycle smarter.**

## Trading Position Context
- Phase 1 active: GLD Dec26 $470C(2x)/$500C(1x)
- Tranche 2 PENDING: waiting DCL confirmation
- SLV entry PENDING: same DCL trigger, separate capital
- Alert engine v2 live on Telegram
- TLT LEAPS: 4100 contracts, Jan 2027 expiry, rate cut thesis

## Memory Architecture
| Layer | What | Persistence |
|-------|------|-------------|
| 1. Project Memory | 10 key-value slots | Anthropic auto-loads |
| 2. GitHub Memory | This file + journal + anti-patterns | git push |
| 3. Local Files | Feed, transcripts, thesis ledger | Mac Mini filesystem |
| 4. MCP Context | Reads 2+3 at session start | Read-only aggregation |

### Session Start Protocol
Every new conversation MUST:
1. Call `get_session_context` (loads layers 2-4)
2. Read THIS FILE for current project state
3. Check compute budget status if running dispatches
4. Checkpoint to this file + journal before session ends
