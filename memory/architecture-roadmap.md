# Zeke Architecture Roadmap
# Single source of truth for architectural decisions, tradeoffs, upgrade triggers.
# Updated: 2026-03-01 | Read before structural changes. Push to GitHub after updates.

---

## Decision Log

### [2026-03-01] Queue Daemon: Cron (10-min) vs Persistent Daemon

DECISION: Cron mode. NOT persistent daemon.

WHY NOW:
- No launchd service configured yet for spark-work-queue.py
- Queue depth rarely exceeds 8-10 tasks — 10-min delay wastes nothing
- Cron is self-healing: crash = next tick restarts automatically
- Single-instance guard handles overlap

TRADEOFF ACCEPTED:
- Priority-10 signals may wait up to 10 minutes
- Acceptable because: trade alerts have their own 10-min cron, no sub-minute requirements yet

UPGRADE TRIGGER — switch to persistent launchd daemon when:
- Queue regularly has >20 pending tasks (Spark being starved by gaps)
- Real-time market triggers added (WebSocket price feeds, options flow)
- DCL confirmation false-negative due to cron gap
- Phase 2 real-time ingestion requires continuous polling

HOW TO UPGRADE WHEN READY:
1. Create ~/Library/LaunchAgents/com.zeke.spark-queue.plist
2. Set RunAtLoad=true, KeepAlive=true, ThrottleInterval=60
3. Remove the */10 crontab entry
4. Verify single-instance guard still works under launchd restart behavior

---

### [2026-03-01] Multi-Domain Research Architecture

CONTEXT: Matt adds research domains as his interests/projects expand.
System must scale to N domains without manual scheduler edits.

CURRENT STATE (fragile):
- domains/*.md knowledge files exist and are populated [OK]
- OpenClaw research jobs per domain exist [OK]
- Scheduler HARDCODES job names (lines 222-236 zeke-scheduler.py) [PROBLEM]
- No registry — jobs.json + scheduler.py + domains/ must sync manually [PROBLEM]
- All domains run every 2h regardless of quality score (72 entries/day) [PROBLEM]
- No domain field in feed entries or queue tasks [PROBLEM]

TARGET ARCHITECTURE:
- domains/registry.json = single source of truth
- Scheduler reads registry dynamically — add domain = add to registry only
- Queue tasks tagged with domain field
- Per-domain daily entry cap (default 3/day, config per domain)
- Per-domain quality weight: <5/10 avg = reduced priority/frequency
- Synthesis generates per-domain task outputs

UPGRADE TRIGGER: Adding domain #7. Do NOT add without registry migration.

DOMAIN ADDITION PROTOCOL (once registry built):
1. Add entry to registry.json (name, job_id, daily_cap, quality_weight)
2. Create domains/{name}.md
3. Create OpenClaw job
4. No scheduler edit needed

INPUT CHANNELS FOR NEW DOMAINS:
- Claude.ai chat: "Add X as research domain" (manual now, automated Phase 2)
- Telegram: /domain add X (PLANNED Phase 2)
- Autonomous: synthesis identifies gap -> pending-approval.json (PLANNED Phase 4)
- Queue self-gen: already live for research sub-tasks

ACTIVE DOMAINS:
  treasury-bonds | every 2h | 23KB domain file | ~5/10 quality
  longevity      | every 2h | 7KB domain file  | ~3.3/10 quality
  ai-agents      | every 2h | 3KB domain file  | ~3.3/10 quality
  self-improvement | every 2h | 3KB domain file | ~3.3/10 quality
  tool-calling   | every 2h | no domain file   | ~3.3/10 quality
  camel-finance  | 6h pipeline | thesis ledger  | ~8/10 quality

NOTE on 2026-03-01 feed dedup: Removed 2,041 low-quality repetitive entries.
Domain *.md knowledge files intact. Jobs regenerate quality entries.
KEY MENTAL MODEL: Feed = staging pipeline. Domain files = accumulated expertise.
Graduation from feed -> domain file is the missing supervisor step.

---

## Phase Roadmap

PHASE 1 — Work Queue Foundation (Week 1, 2026-03-01)

Day 1 [DONE]: spark-work-queue.py
  - Cron mode, single-instance guard, 8 task types, self-gen
  - 2 tasks complete, 1 auto-follow-up generated

Day 2 [IN PROGRESS]: Synthesis -> Task Generation
  - camel-overnight-synthesis.py: after synthesis -> write domain-tagged queue tasks
  - All tasks get domain field from day 1
  - ALSO: domains/registry.json (required before domain #7)

Day 3: Financial Ingestion (queue-fed, NOT cron)
  - FedWatch daily scrape
  - MacroAlf/Lyn Alden RSS extract
  - GLD/SLV options flow (barchart.com)
  - TLT auction calendar (Treasury.gov)

PHASE 2 — Self-Direction (Days 4-7)

  - Domain quality weighting: <5/10 -> reduce freq, >7/10 -> increase + spawn follow-ups
  - Persistent daemon upgrade (if trigger conditions met above)
  - qwen3-32b nightly instrument clusters:
      Pass 1: Gold/Silver | Pass 2: Rates/Bonds | Pass 3: Crypto | Pass 4: Cross-cluster
      Each pass feeds the next. Cost $0. Quality 10x monolithic.
  - Spark utilization panel in Mission Control (target >60%)

PHASE 3 — Compounding Intelligence (Weeks 2-3)

  - RAG feedback: embed synthesis outputs to ChromaDB, each synthesis reads prior conclusions
  - Cross-source discovery: thesis findings -> auto-search -> new sources -> ingestion pipeline
  - Temporal drift: conviction trend tracking, alert if thesis drops >0.15 over 2 weeks
  - Feed graduation: supervisor job that promotes feed entries to domain files (the missing piece)

PHASE 4 — Recursive Autonomy (Month 2)

  - Self-specifying jobs: system drafts specs -> pending-approval.json -> Matt reviews weekly
  - Full compound loop: overnight synthesis -> tasks -> Spark processes -> evening synthesis -> repeat

---

## Key Anti-Patterns (multi-domain specific)

- NEVER add domain by editing scheduler.py. Use registry.json once built.
- NEVER same frequency for all domains. Quality score drives frequency.
- NEVER let domains run 12x/day without quality gate. That's how feed bloats to 2,454.
- NEVER delete domain *.md files. They are expertise, not cache.
- NEVER confuse feed (staging) with domain files (knowledge). Graduate, don't accumulate.

---

## Metrics

  Spark utilization: ~30% now -> 60% target
  Queue avg pending: 6 now -> 15-25 target
  Self-generated task ratio: 12% now -> 80% target
  Synthesis quality avg: 3.3-8/10 (domain split) -> 7/10 all domains
  Domain count: 6 now -> unlimited (registry-driven)
  Time to add domain: 30 min manual -> 5 min with registry
