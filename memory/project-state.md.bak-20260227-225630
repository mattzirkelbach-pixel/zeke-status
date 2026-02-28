# Zeke Project State — Current Reality
# This file is the SINGLE SOURCE OF TRUTH for project state.
# Updated every session. NOT append-only — overwritten with current facts.
# Read this FIRST in every conversation via get_session_context.
# Last updated: 2026-02-27T20:30:00Z

## Infrastructure Status

### Scheduler & Pipeline
- **Scheduler**: Running (PID alive), 30-min daytime cycles, overnight research
- **Camel Pipeline v2**: Cron every 6h. Has chunking, thesis ledger, spark lock, try/except resilience
- **Spark Lock**: `~/spark_lock.py` — advisory lock. Scheduler + pipeline + self-repair all use it.
- **Quality Scorer**: Runs every 3h. Was flagging duplicate camel entries (FIXED: feed deduped 2/27)
- **Dashboard**: http://100.64.219.70:3334 — temporal decay LIVE (14d half-life, staleness at 45d)

### Known Issues
- Camel v2 backfill dedup bug: `--backfill N` was reprocessing all videos. FIXED 2/27 (now only `--reprocess` forces re-analysis)
- Instrument name normalization needed in dashboard (Dixie vs DXY, etc.)
- osascript Chrome control needs "Allow JavaScript from Apple Events" enabled

### Cron Schedule (14 jobs)
- guardian (1min), watchdog (10min), mcp-watchdog (5min), status-push (5min)
- snapshots (15min), feed-guardian (15min), quality-scorer (3h)
- self-repair (30min), camel-pipeline-v2 (6h), dedup (3am), session-purge (4am)
- nightly-synthesis (5am), price-fetch (6am), trade-alerts v2 (10min weekdays)

## Active Work Streams

### 1. Camel Finance 50-Video Backfill
- **Status**: RUNNING autonomously (launched 2/27 ~8:12PM ET)
- **Monitor**: `tail -f /tmp/camel-backfill-50.log`
- **Expected duration**: 8-12 hours
- **When done**: Check `grep -c "Written to feed" /tmp/camel-backfill-50.log` for count

### 2. Camel Finance Website Crawl
- **Status**: BLOCKED — needs Chrome "Allow JS from Apple Events" setting
- **Script ready**: `~/camel-site-crawler.py` (osascript-based, autonomous)
- **Two-phase**: `python3 ~/camel-site-crawler.py` (crawl) then `--ingest` (process via Spark)
- **Content available**: 6 courses, live charts, video search tool, cycle marker
- **Matt must**: Be logged in to camelfinance.co.uk in Chrome

### 3. Temporal Decay (Dashboard)
- **Status**: DONE — live in server.py `_get_camel_data()`
- **Config**: 14-day half-life, 45-day staleness threshold
- **Affects**: bias_summary (weighted scores), thesis_summary (weighted strength), trade_calls (age/stale flags)

### 4. Feed Quality
- **Status**: Improved after dedup (1608→1590 lines, 18 duplicate camel entries removed)
- **Root cause**: v1/v2 URL format mismatch + backfill reprocessing bug
- **Both fixed**: Normalized to youtube/{ID}, backfill skip logic corrected

## Trading Position Context
- Phase 1 active: GLD Dec26 $470C(2x)/$500C(1x)
- Tranche 2 PENDING: waiting DCL confirmation
- SLV entry PENDING: same DCL trigger, separate capital
- Alert engine v2 live on Telegram
- Cycle state: ~day 21-22 of 22-28, DCL imminent but NOT confirmed

## Memory Architecture
This is Claude's memory system — how I (Claude) maintain continuity between conversations.
COMPLETELY SEPARATE from Camel Finance temporal decay (which is dashboard data weighting).

| Layer | What | Persistence | Scalability Risk |
|-------|------|-------------|-----------------|
| 1. Project Memory | 10 key-value slots | Anthropic auto-loads | FULL — no room for growth |
| 2. GitHub Memory | This file + journal + anti-patterns | git push, web-fetchable | Journal needs compaction strategy |
| 3. Local Files | Feed, transcripts, thesis ledger | Mac Mini filesystem | Robust — append-only |
| 4. MCP Context | Reads 2+3 at session start | Read-only aggregation | Limited to last 3 journal entries |

### Session Start Protocol
Every new conversation MUST:
1. Call `get_session_context` (loads layers 2-4)
2. Read THIS FILE for current project state
3. Check backfill/crawler status if relevant
4. Checkpoint to this file + journal before session ends or at midpoints
