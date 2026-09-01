# Zeke Project State — Current Reality
# SINGLE SOURCE OF TRUTH. Updated every major session.
# Last updated: 2026-05-31 (Confluence Engine + on-demand Analyst built — see section below; prior refresh 2026-05-08)

## INCIDENT 2026-07-04: Morning briefing outage fixed (21 days, since 2026-06-08)
com.zeke.morning-briefing LaunchAgent had fallen out of launchd (plist found renamed to
.retired-20260601). A stale sandboxed Cowork task (~/Documents/Claude/Scheduled/morning-alpha-briefing,
supposed to have been disabled back in March per the original migration spec) partially covered the
gap once on 2026-06-12 but its sandbox can't shell out to alert_dispatcher, so no Telegram send
happened; it then went silent too. Fix: restored the plist + `launchctl bootstrap gui/501`, disabled
the stale Cowork task. Verified via --dry-run + one isolated test Telegram send. Real morning_briefing_daily
cooldown untouched — next real send expected Monday 2026-07-06 06:30 ET. Watch launchctl list after
any future reboot to confirm it stays loaded (a separate system-wide launchd issue is being tracked
independently by Matt).

## Portfolio (positions.json @ 2026-05-08)

### E*TRADE brokerage ($266,437 — 3/25 snapshot)
Cash $161,228. Positions $60,208. Total YTD pnl on positions: **-$40,165**.
- GLD $470C x5 Dec26 (cb $27,920, mv $11,025, pnl -$16,895)
- GLD $500C x1 Dec26 (cb $4,222, mv $1,465, pnl -$2,757)
- GLD $430C x3 Dec26 (cb $12,450, mv $11,232, pnl -$1,218)
- SLV $80C x28 Jan27 (cb $47,415, mv $26,740, pnl -$20,675)
- SLV $65C x10 Jan27 (cb $14,000, mv $15,380, pnl +$1,380)
- Plus futures positions — see `etrade_brokerage.positions` in positions.json for full list

### Robinhood 401k (17 positions, 3/11 snapshot)
- **TLT calls:** $101C x3150 ($110K mv), $90C x850 ($131K mv), $95C x400 ($28K mv)
- **TLT shares:** 1,868 sh ($160K mv)
- **TMF $50C x725** ($54K mv)
- **GLD calls:** $480C x25 ($53K), $395C x5 ($32K), $460C x10 ($28K)
- **Miners:** GDX $100C x95 ($106K), SILJ $34C x375 ($203K), SILJ $27C x25 ($20K)
- **SLV $80C x75** Jun27 ($94K)
- **IBIT $48C x500** Jun26 ($71K)
- **PPLT $175C x10** ($30K)

### Robinhood brokerage
- KEEL $2C x50 May26 ($10K mv) — lightened from 100 → 50 on 4/22, letting remainder ride on BTC catch-bid

### Closed since last project-state update
- **NOW position closed weeks before 2026-04-22.** Per persistent fact in SESSION_BRIEF.

## Cycle state (cycle_state.json @ 2026-05-07 21:00 UTC)
- **XAUUSD:** day 25 of daily cycle, weekly cycle week 4
- **Last DCL:** 2026-04-24 @ $4,099.125 (signal received 4/28). DCL **NOT confirmed**
- **Last WCL:** 2026-04-10 @ $3,886.465 (NOT confirmed)
- **HCL above prior:** TRUE
- **Camel last update:** 2026-03-25 (stale by 6 weeks — needs refresh): "Phase: approaching_low. LONG. early signs of true cycle low bottom"
- **Camel trade plan (stale):** "Two drives down: drive 1 done, drive 2 = undercut to new lower low (probable). Then reverse, cross bullish, break trendline. 10-SMA will be ~5080 by confirmation. Hard invalidation = wherever this DCL low forms."

## Trading framework
- **Exit window:** May–June 2026 before 8yr half-cycle top. 401k miners exit first. Spec: [exit-playbook-2026-may-june.md](~/zeke-portfolio/specs/exit-playbook-2026-may-june.md) (4/21).
- **DCL deploy gate:** Anti-FOMO — entries require DCL confirmation (swing low + SMA reclaim + day 18+). No alert = wait.
- **Tax:** E*TRADE Section 1256 ONLY for new options (GLD/SLV qualify; GDX/SILJ do NOT). Robinhood 401k tax-deferred.

## Compute
- **Mac Mini orchestrator** + **DGX Spark GB10** (128GB, GPU NVIDIA GB10).
- **Spark inference:** nemotron-3-super:120b loaded. Health OK (GPU 0% idle, 35°C). Recurring **HTTP 503** on overnight-deep tasks 3+4 (correlation + portfolio-opt) — **unfixed**.
- **Model router:** `config/spark-models.json` + `spark_models.py`. ALL scripts use `get_model()`. nemotron-3-super primary, qwen3:8b fast, qwen3-32b-32k fallback, nomic-embed-text embedding.
- **Claude Code:** v2.1.132, latest 2.1.133 (1 behind, autofix wired 2026-05-06).

## Pipeline state (nightly-assessment grade A through 2026-05-08 09:00 UTC)
- **Openclaw scheduler:** RUNNING (uptime 3,426 min = 57h). Gateway running.
- **Feed:** 41,805 lines, 50/50 clean recent, 58% actionable, junk 2%. Updated 1.7 min ago.
- **L1B:** dispatched 15, ingested 22, GOOD quality.
- **Spark queue:** 36,338 done, 0 failed, 775 pending, 0% echo rate.
- **Cron topics:** gold-cycle, oil-tlt, btc-spx-macro all DISABLED at openclaw level (intentional? — flagged by auditor).
- **Cowork executor:** IDLE. Pending tasks: 0.
- **Research engine:** UP. 3,714 tests run today, 3,714 findings written, 3,066 followups. **Throttled to 1/hr (was 30/hr) pending edge-wiring spec review.**

## What was BUILT 2026-05-31 — Confluence Engine + on-demand Analyst (Opus session)
Full detail: `~/.openclaw/workspace/memory/2026-05-31.md` + artifact registry + plan `~/.claude/plans/woolly-painting-dolphin.md`. Validation ledger: `state/confluence-validation-ledger.json`.

| Capability | Path | Status |
|---|---|---|
| Cycle WHEN layer | decisions/cycle_window.py | LIVE — price-cycle timing WEAK (~20-25% in window); cross-check only |
| Fib/pitchfork WHERE | decisions/fib_pitchfork.py | anchor bug fixed (`median_sane`); Fib math verified |
| Live CF indicator (vision) | decisions/cf_vision_extract.py | LIVE — re-points to ANY ticker; replaces DEAD DOM scraper |
| Confluence Engine (fusion) | decisions/confluence_engine.py | SHADOW (no alerts) — Camel+CF+price+fib tiered |
| On-demand dossier | decisions/assess_ticker.py | any ticker → cycle+Fib ladder+2%/6% sizing |
| Autonomous analyst note | decisions/analyst_note.py | LOCAL stack (Nemotron synth), ZERO Opus; `--notify`→Telegram |
| End-to-end runner | decisions/confluence_refresh.py | one-command pipeline |
| Two-way invocation | orchestrator/edge-telegram-listener.py | `note <TICKER>` → spawns analyst_note --notify (still draft-marked) |

KEY FACTS: Cycles are UNIVERSAL (playbook `~/.openclaw/workspace/references/camel-finance-cycle-theory.pdf` p19) — CF indicator re-points to any ticker. Design principle (Matt): iterate on the LOCAL stack (Spark/Nemotron + Haiku + deterministic + yfinance), reserve Opus for novel judgment — don't peg Claude. LLMs fumble arithmetic → deterministic engine numbers are authoritative. ROGUE alert path: `~/zeke-cycle-engine.py detect --alert` (crontab, 30min) bypasses alert_dispatcher (no cooldown/kill-switch, lookback=2) — Phase-4 cleanup target. Everything is SHADOW (no live alerts) pending Phase-2 out-of-sample backtest → arming bar. NEXT: register listener, universe sector-screen, Phase-2 backtest → arm → schedule.

## What was BUILT 2026-04-18 → 2026-05-08

| Capability | Path | Status |
|---|---|---|
| Deterministic research scout | `research/research_scout.py` | LIVE since 4/24 |
| Zombie Claude killer | `scripts/zombie-claude-killer.py` | LIVE since 5/3, fired 5/7 |
| Decision reflections store | `orchestrator/decision_reflections.py` | BUILT, **NOT WIRED to alpha_v3** |
| Claude-code drift autofix | (in capabilities checker) | LIVE since 5/6 |
| Learning loop budget gate | `learning/loop.py` `_budget_ok()` | LIVE since 5/7 — gate held overnight (3 defers @ 122% block) |
| Edge wiring spec | `specs/research-to-edges-wiring.md` | DRAFT, awaiting review |
| Exit playbook | `specs/exit-playbook-2026-may-june.md` | WRITTEN 4/21, ready |

## What was KILLED 2026-04-18+
13 fiction-engine LaunchAgents (synthesis stack hallucinating numbers). Inaccurate-portfolio-push (showed $1.4M when reality $2.2M). Duplicate morning-briefing.

## Memory layers
- **session-journal.jsonl** (2.5MB): 509 sessions since 4/18, 499 graded A. Updated through today.
- **learning-log.jsonl** (336KB): 880 entries. Updated through today.
- **anti-patterns.md** (32KB): 9 new patterns since 4/18. Updated 2026-05-07.
- **learning/lessons.jsonl**: 1,510 entries. **learning/applied.jsonl**: 877 as of 5/8 10:04 (was 859 at 5/8 00:24 — 18 applied overnight).
- **~/.openclaw/workspace/memory/ daily files: DEAD since 2026-03-29** (40 days). Agents claim to read these but they're stale. **Unfixed.**
- **SESSION_BRIEF.md**: 53KB, regenerated 2026-05-08 10:11 UTC. Persistent facts loaded.

## Alerts
- **Telegram bot dead 2026-05-07 (`@Zekevonz_bot` deleted/blocked at Telegram level).** New bot pending — Matt creating via BotFather, will drop new token via claude.ai. Swap helper: `~/zeke-portfolio/scripts/swap-telegram-bot.py`.
- 5 senders authorized: conviction-engine, dcl_go_nogo, bleed-detector, morning_briefing, feed-guardian.
- Alert lockdown lifted 2026-05-07 20:24 (config: `state/alert-config.json` `lockdown=false`).

## Known unfixed issues (truth, not aspiration)
1. **Research findings being consumed.** Step 2 extractor live: 44 candidates from 3,527 findings (full corpus). Operator CLI ready: `python3 ~/zeke-portfolio/orchestrator/edge-review.py list`. Spec Steps 5-7 (track-record, auto-gate eval) deferred until first 5 edges approved.
2. **Camel cycle data PARTIAL FIX 2026-05-08:** XAUUSD/BTC/SPX/TLT updated 10:49-10:52Z; XAGUSD/SLV/GDX/SILJ still stale (not in today's 5 videos). `com.zeke.video-analyzer.plist` re-enabled (was disabled — root cause). Self-heals every 6h going forward.
3. **Spark 503 on overnight-deep correlation/portfolio-opt** for 2+ days running. Tasks 1-2 work; tasks 3-4 timeout.
4. **Decision reflections not wired** to alpha_v3 — built 4/30, sitting unconnected. Edge wiring is the bigger lever.
5. **Openclaw memory layer dead 40 days** — `~/.openclaw/workspace/memory/`.
6. **morning-briefing-state.json says last_sent: 2026-03-23** (5+ weeks stale) while dispatcher fires daily — file just stopped being written. Cosmetic; no impact on actual sends.
7. **Sprawl: 122 dormant scripts** flagged for removal in 2026-05-08 sprawl audit. 24 duplicates.
8. **Budget tracker calibration error fixed 2026-05-08:** prior version over-counted by ~2.5x (combined_pct = sonnet+opus, max_200 quota). Now unified `messages_per_5h=500` matching UI. Throttle gate was over-deferring during entire 2026-05-07 session.

## Control planes — who can change what (added 2026-08-31)

Two separate paths reach this Mac. Confusing them wasted a full session on 2026-08-31.

**A. Cloud/remote Claude session (claude.ai/code) → Zeke MCP over Tailscale.**
Tools: `exec_command`, `read_file`, `write_file`, `tail_log`, `restart_service`, etc.
CAN: read/write any file, edit scripts + plists, `launchctl` load/unload/kickstart,
restart services, rotate logs, run python/git. Everything shell-reachable.
CANNOT: click anything. No screen, no GUI, no computer-use tools in that session.

**B. Local Claude desktop app session on the Mac.**
2026-08-31: Matt enabled computer control + screen recording for the desktop app.
This grants GUI control to sessions running IN THAT APP — not to cloud sessions.
Use this path for anything that only exists as app UI state.

**GUI-only settings (path B required — a cloud session cannot reach these):**
- Scheduled-task model picker (Edit scheduled task → model dropdown). Default resolves
  to the app's default model, which was **Fable 5** — that is why every Cowork
  scheduled task ran on Fable and all four died together when the Fable weekly cap
  hit 100% on 2026-08-31.
- Scheduled-task Permissions ("Manually approve" vs pre-approved tools).
- Plan usage page (Settings → Usage). Weekly caps are **per model tier**: on
  2026-08-31 Fable read 100% used while All-models read 58%. A tier can be dead
  while the account has headroom — check the per-model bar, not just the total.

**Practical rule:** if a fix is a file, a script, a plist or a service → cloud session
handles it end to end. If the fix is a dropdown or a toggle → it needs the local app
(path B) or Matt's hands. Say which one up front instead of promising a remote fix.
