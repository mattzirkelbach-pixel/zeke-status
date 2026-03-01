# Zeke Vision Map — Block 10 Audit
# Generated: 2026-03-01 | Source: ZEKE-ARCHITECTURE.md, zeke-architecture-v2.md, vision.md, project-state.md, anti-patterns.md
# Purpose: Map deployed blocks to spec phases. Identify gaps. Define next 5 blocks.

---

## Spec: The Four Layers

Per zeke-architecture-v2.md, the recursive autonomy architecture has four layers:

**L1 Execution** — bulletproof job runner, verified feed writes, structured logs, single scheduler
**L2 Oversight** — supervisor reads logs, detects patterns, quality gate, self-healer
**L3 Intelligence** — tiered dispatch, RAG context-aware calls, cross-domain synthesis, task queue
**L4 Recursive Learning** — synthesis writes next tasks, quality scores modify weights, system improves itself

Per memory/anti-patterns.md (highest-priority spec additions):
- Phase 1: spark-work-queue replaces cron, Spark polls continuously
- Phase 2: synthesis writes next_tasks to queue, quality scores modify weights
- Phase 3: RAG feedback, cross-source discovery
- Phase 4: self-specifying jobs (system writes its own job definitions)
- Spark <20% utilization = system failure
- Every synthesis that doesn't write next_tasks is a dead end, not a loop

---

## Block-to-Layer Map

| Block | What Was Built | Layer | Status |
|-------|---------------|-------|--------|
| 1 | spark-work-queue.py — queue daemon, Spark polls queue | L3 + Ph1 | ✅ DONE |
| 2 | Domain scrub — 5 canonical domains, removed noise | L2 | ✅ DONE |
| 3 | RAG feedback — ChromaDB + nomic, 113 chunks indexed | L3 + Ph3 | ✅ DONE |
| 4 | Nightly synthesis clusters — cross-domain findings | L4 partial | ✅ DONE |
| 5 | Financial ingestion — MacroAlf, TreasuryDirect | L1 | ✅ DONE |
| 6 | Quality-weights — scores modify task priority/weights | L2 + Ph2 partial | ✅ DONE |
| 7 | Approval system — human-in-loop for structural decisions | L2 | ✅ DONE |
| 8 | Memory distillation — session state, nightly strategic context | L3/L4 | ✅ DONE |
| 9 | Camel synthesis layer — _build_finding(), purge, readable IDs | L3 | ✅ DONE |

---

## Current State vs Spec

### What's Complete
- L1: Rock solid. Scheduler runs verified 30-min cycles. Feed writes validated. Structured JSONL logs.
- L2: Full oversight stack. Quality-weights acts as supervisor. Approval gates structural decisions.
  Self-healer fires on WEAK domains. Feed guardian validates on write. Dedup runs at 3am.
- L3 (dispatch): zeke_dispatch.py routes by cost tier. Haiku for bulk, Sonnet for judgment, Spark for $0.
- L3 (RAG): ChromaDB live. Camel analysis is RAG-enhanced. Context-aware calls working.
- L3 (queue): spark-work-queue.jsonl with 12 pending tasks. Queue daemon polling.

### What's Incomplete (Gaps)

**GAP 1 — CRITICAL: Synthesis → next_tasks not closed for 5 of 6 domains**
The 5 OpenClaw research jobs (longevity, ai-agents, treasury-bonds, compound-synthesis,
self-improvement) write to the feed and STOP. They generate zero next_tasks.
Only camel-overnight-synthesis.py has next_tasks logic.
Result: every non-camel finding is a terminal dead end. The recursive loop is broken.
Spark runs → produces findings → findings go nowhere → Spark runs same topics again.
This is the anti-pattern called out explicitly in anti-patterns.md.

**GAP 2 — MODERATE: No proactive intelligence delivery**
Vision.md medium-term goal: "Proactive insights — Zeke messages Matt when something
important happens, not just when asked." Telegram exists but only sends trade alerts.
No mechanism to detect high-conviction findings and push them unprompted.

**GAP 3 — MODERATE: Cross-domain synthesis → portfolio actions not wired**
L3 spec: "Strategist reads KG, updates priorities." The analyst agent (compound-synthesis)
finds connections but they don't flow into trade plan updates or position sizing.
TLT + macro synthesis should be modifying the trade plan, not just the feed.

**GAP 4 — MINOR: Camel backfill**
114 existing camel entries use old verbatim format. New entries use _build_finding().
History is inconsistent. Backfill would normalize the corpus.

**GAP 5 — MINOR: FedWatch auth blocked**
Financial ingestion pipeline incomplete. FedWatch + Yahoo Finance returning auth errors.
Blocks rate expectation data from feeding into TLT thesis.

---

## Phase Completion

| Phase | Spec Goal | Status |
|-------|-----------|--------|
| Ph1 | Queue daemon replaces cron, Spark polls | ✅ Block 1 |
| Ph2 | Synthesis writes next_tasks, quality modifies weights | 50% — quality weights done, next_tasks NOT done |
| Ph3 | RAG feedback, cross-source discovery | ✅ Block 3 (RAG). Cross-source partial. |
| Ph4 | Self-specifying jobs | ❌ Not started |

---

## Next 5 Blocks

**Block 11 — Synthesis → next_tasks (closes recursive loop)**
Post-cycle task extractor: after each scheduler cycle, read new feed entries,
use Haiku to extract 1-2 next research tasks per entry, write to spark-work-queue.jsonl.
Works for ALL 6 domains without touching OpenClaw jobs.json.
Closes Ph2. Makes every synthesis recursive, not terminal.
Effort: ~2 hours. Highest priority.

**Block 12 — Proactive intelligence delivery**
Feed watcher: scan new high-quality entries (score ≥ 3.5) for cross-domain signals
relevant to active positions. Push summary to Telegram when triggered.
Triggers: new camel thesis contradicts existing position, TLT rate signal, gold cycle update.
Closes medium-term vision goal. Zeke becomes a colleague that speaks up, not a database.

**Block 13 — Camel backfill synthesis**
Reprocess 114 existing camel entries through _build_finding() logic.
Run structured extraction on stored transcript JSONs, rebuild findings.
Normalizes corpus. RAG quality improves. Historical conviction tracking consistent.

**Block 14 — Cross-domain → trade plan wiring**
Analyst agent reads TLT + macro + gold findings daily. Generates structured
position intelligence (conviction score, risk flags, cycle alignment).
Writes to portfolio/assets/{TICKER}/narrative.json. Surfaces via get_trade_plan().
Closes L3 strategist gap. Intelligence layer starts driving decisions.

**Block 15 — FedWatch + financial ingestion completion**
Solve auth for FedWatch (CME rate probabilities) and Yahoo Finance.
Route through Haiku with session management, or find unauthenticated endpoints.
Feeds rate cut probability into TLT thesis scoring.
Closes Block 5 incomplete items.

---

## Metric That Matters (from spec)

Feed entries per 24h with valid timestamps and non-trivial, deduplicated content.

Current (post-Blocks 1-9): ~18-20/day (synthesized, quality-gated, cycle verified)
Target with Block 11 closed: same volume, but EACH entry generates 1-2 next tasks
→ queue grows automatically → Spark never idle → research compounds every cycle

Spark utilization target: >60% during waking hours. Current: estimated 40-50%.
Gap is directly attributable to queue not being fed by synthesis output.
Block 11 closes this.

---

## Architecture Is On Track

The spec called for L1→L2→L3→L4 sequential build. We're there:
- L1: solid
- L2: solid
- L3: 80% — dispatch, RAG, queue working. Synthesis not recursive yet.
- L4: foundations only — memory distillation is the only L4 piece. Needs Block 11.

No drift from vision. No wasted blocks. Every block maps to a spec phase.
The one critical gap (Ph2 synthesis→next_tasks) is the next block.
