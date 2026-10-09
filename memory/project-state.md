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

### Cowork scheduled tasks die silently when Claude.app quits (added 2026-09-09)
2026-09-08 ~10:34Z the Claude desktop app stopped running. All four Cowork
scheduled tasks (cowork-trigger-processor, weekly-system-review,
video-transcript-analyzer, morning-alpha-briefing) run INSIDE that app and are
marked "Only on this computer", so all four stopped firing for ~24h with:
  - enabled=true on every task
  - recordedSkips = {} (nothing recorded)
  - no error anywhere, no alert
The Mac itself was healthy the whole time (up 1d15h, caffeinate holding
PreventSystemSleep) and the LOCAL LaunchAgent briefing sent normally at 10:30Z —
so machine-level watchdogs and the dead-man check both stayed green. Only the
missing morning-alpha-synthesis.md mtime revealed it.

**Detection:** `ps aux | grep -c "[C]laude.app/Contents/MacOS/Claude"` — 0 means
every Cowork scheduled task is dead regardless of what scheduled-tasks.json says.
Also compare each task's lastRunAt against its cron; stale lastRunAt with
enabled=true and no recordedSkips is the signature.
**Fix:** `open -a Claude` (works over Zeke MCP exec; app relaunches into the GUI
session). Verify the process survives ~60s, then confirm the next scheduled fire
actually lands — relaunching the app is not proof the scheduler resumed.
**ROOT CAUSE FOUND 2026-09-11: scripts/zombie-claude-killer.py is killing it.**
That LaunchAgent (com.zeke.zombie-claude-killer, every 1800s) SIGKILLs any
process at /Applications/Claude.app/Contents/MacOS/Claude matching
`etime > 2h AND state.startswith("R")` — a clause with NO CPU guard. `state=R`
in a ps sample just means the app was doing something at that instant, so every
healthy long-lived Claude.app qualifies. The TTY allowlist never protects the
GUI app (its ppid is 1, tty "??"). state/incidents/zombie-kills.jsonl shows 10
such kills since 2026-05-27, every one at 0.0-3.8% CPU — nowhere near the 50%
runaway it was built for (2026-05-03, a GUI proc stuck 64h at 100% CPU).
Confirmed kills behind the outages: 2026-09-08T11:38:56Z (pid 629) = the ~24h
gap, and 2026-09-11T10:39:14Z (pid 59293, 1.0% CPU, up 10h) five minutes after
that morning's brief completed.
FIX (not yet applied, awaiting Matt): the `state=R` clause in should_kill() is
redundant — the `cpu > 50` clause already catches the real runaway case. Either
drop it or require a CPU floor alongside it. Do NOT rebuild the script; it
carries a DO-NOT-REBUILD marker. py_compile after editing.

**Missed windows ARE caught up on relaunch** (corrected 2026-09-09, same day —
the original note here claimed the opposite and was wrong). Within ~1 minute of
`open -a Claude` at 11:09Z, all three due tasks fired at 11:10Z (trigger
processor, video analyzer, morning-alpha-briefing) and the synthesis was written
at 11:13Z, correctly dated 2026-09-09 with deltas against 9/8. Normal schedule
then resumed (11:30, 12:01). So relaunching promptly recovers the day rather
than conceding it — do not tell Matt a missed brief is lost without checking.

### Monday brief said "first run" for three weeks — fixed 2026-09-21
**CONFIRMED IN PRODUCTION Mon 2026-09-28** (first gap-3 morning since the fix):
the CHANGES block rendered 6 real deltas (GLD 6->7, SLV 6->7 + level, GDX
6->1, SILJ 6->7, SPX 6->7) instead of "first run". Suite still 47 OK. The 9/22-
9/25 deltas were gap-1 and did not exercise the fix; this one did. Note the
[:6] cap was hit by pure cycle-count aging again — five of six lines are
"N->N+1" — and BTC's -2.06% weekend move did not make the block. That is the
open follow-up (a), now observed in production rather than simulated.

`build_changes()` in scripts/morning_briefing.py gated the delta baseline on
`(date.today() - bdate).days > 2`. The brief skips weekends (is_weekend()) but
NOT market holidays, so every Monday's baseline was Friday's = 3 days ->
"• no baseline (first run)" on 2026-09-07 (Labor Day, script still ran),
09-14 and 09-21; 08-31 was the genuine first run. Every Tue-Fri rendered real
deltas (12/12). Introduced in commit 3ff53ca (2026-09-05).
FIX: threshold 2 -> 4 (3 = weekend; 4 = one day of slack for a failed Friday
send, since the snapshot is only written after a successful send). Sentinel
text and the "CHANGES SINCE YESTERDAY" header are byte-identical — both are
matched by scripts/brief_scorecard.py gate_changes_block(). Backups:
scripts/morning_briefing.py.bak-20260921-074954-firstrun and the tests file.
Added 3 tests to TestChangesBlock (gap 3 and 4 must render deltas, gap 5 must
say first run); suite 44 -> 47, all green; red/green verified. NOT committed —
the working copy carries 5 other uncommitted hunks that are Matt's.
WHY IT HID FOR 3 WEEKS: (1) the scorecard rubric accepts "no baseline (first
run)" as a valid CHANGES block, so Monday briefs scored 100; (2) the daily
cloud check-in verified the brief SENT and never read it. Verify content,
not delivery: on a Tue-Fri, "first run" in state/morning-alpha.md is a
regression; on a Monday after 09-28 it means this fix failed.
FOLLOW-UPS (real, not done — need their own tests): (a) diffs[:6] cap fills
with pure cycle-count aging on Mondays (GLD 1->2, SLV 10->2 ...) and DROPPED
BTC's +8% weekend move in a simulated patched 09-21 brief — skip diffs where
new.day - old.day == trading_days_between(), or raise the cap when gap > 1;
(b) the snapshot carries no price, so a weekend price move is never a
"change" — add per-ticker last_close + a "moved >2% since baseline" line if
Monday is meant to answer "what changed over the weekend".

## Cowork scheduled tasks moved to cloud Routines (2026-09-28, found 2026-09-29)
- 2026-09-28 21:21Z: Claude.app (2.9939.4, relaunched 15:00 local) migrated all four
  local Cowork tasks to cloud Routines via `sweep` (`migratedToRemote` in
  scheduled-tasks.json, all `enabled:false` locally). Those four cloud copies
  (trig_011YbLVzMjp7L6asnJZRYT8A morning, trig_01XRzNSYG3nwtRgknHUmp4v3 processor,
  trig_01XqUDowYhfoYpsqU7rh68tk video, trig_01TKpZpt4uedwDaNsb4CJ9Nq weekly) were
  then DISABLED at 21:51-21:54Z and replaced by four new "(cloud, Zeke MCP)"
  Routines created via http_api (creator Matt):
    trig_017eKrFriZ6S1EV5YU8qp4rE  Morning alpha briefing   CRON_TZ=America/Indianapolis 30 6 * * 1-5
    trig_019un1ZgtXAhE58K51cSqsZP  Cowork trigger processor CRON_TZ=America/Indianapolis 21 */6 * * *
    trig_01DMavjPuDDXaWyxmBMveAyR  Video transcript analyzer CRON_TZ=America/Indianapolis 30 11 * * *
    trig_01GvnRarZkttF7ZX6gLEubUF  Weekly system review     CRON_TZ=America/Indianapolis 0 20 * * 0
- Prompts were rewritten with an "Execution environment (cloud routine since
  2026-09-28)" header: sandbox has nothing local; the Mini is reached only via the
  Zeke_MCP connector (exec_command / read_file / write_file). Morning brief still
  writes ONLY state/morning-alpha-synthesis.md; local morning_briefing.py LaunchAgent
  still owns Telegram.
- First cloud run: 2026-09-29 10:32:52Z -> 10:34:22Z SUCCEEDED, synthesis mtime
  06:34 local matches. Ran on claude-sonnet-5-5 (session cse_019wW8sjfX3Fx48itjJ5dv43,
  cost $0.50, 97k ctx). The Routine's model field is EMPTY, so the Opus 5 choice
  Matt set on the local task on 9/12 did NOT carry over. Trigger processor is
  pinned to claude-sonnet-5-5 explicitly.
- Consequences: zombie-claude-killer / Claude.app liveness no longer affects
  scheduled work; local scheduled-tasks.json + local-agent-mode-sessions are
  obsolete for health checks. Health = get_trigger last_run on the four IDs above.
- Stale text in the new processor prompt: says local executor runs "every 60s"
  and gates on heartbeat age < 5 min; executor is 300s since 8/31, so the cloud
  sweep will sometimes judge the local worker stuck. Harmless unless tasks pending.

## Mac down 12h overnight 10/7-10/8; morning brief missed (2026-10-08)
- Last zeke-status commit 2026-10-07 18:23 ET; reboot 2026-10-08 06:22 ET (`last reboot`),
  no clean shutdown entry, no panic report. 4th hang-class incident (Jun 29, Aug 15-16,
  Sep 21-22 issue #11, now). Cause not determined from logs.
- Dead-man Routine WORKED: issue #13 opened 00:05Z (102 min), 3 comments to 03:05Z.
  It did NOT auto-close after recovery: its prompt says "age<=60 -> output OK and STOP"
  before the step that closes an open issue, so recovery-close never runs. Close by hand.
- Brief impact: com.zeke.morning-briefing is StartCalendarInterval 06:30 with no catch-up;
  user session came up ~06:36 (caffeinate/Claude assertions), so the 06:30 slot was
  missed (launchctl runs=0, never exited). No Telegram brief, no morning-alpha.md,
  brief-state-yesterday.json still 10/7. Cloud synthesis Routine fired 06:33 ET while
  the Mini was still booting: 11s run, 494 output tokens, wrote nothing, status SUCCEEDED
  (SUCCEEDED = session finished, not "did the job"). brief_scorecard sent CRITICAL
  "NO BRIEF TO GRADE" 07:08 ET. Absence watchdog (09:00/09:35/10:05/11:05 ET) only alerts,
  never re-runs the brief. Recovery = run scripts/morning_briefing.py by hand (no --force
  needed when nothing sent today) then fire_trigger trig_017eKrFriZ6S1EV5YU8qp4rE.
- Pipeline otherwise recovered post-boot: premarket brief 07:01 ET, price scan 07:08 ET,
  dead-man/watchdog OK, cowork-executor running fscan_20261008_haiku55 (queued by the
  frontier scan Matt resumed 07:12 ET; routine now on claude-fable-5-1, issue #14).

## ROOT CAUSE of the 10/7-10/8 outage: power event, not a hang (2026-10-08 evening)
- The DGX Spark's `last -x` shows system boots at 2026-10-06 21:53, 2026-10-08 06:22 and
  2026-10-08 19:14 ET. The Mini rebooted 2026-10-08 06:22 ET too: both boxes came back
  in the same minute, so the 18:23 ET 10/7 -> 06:22 ET 10/8 gap was a power loss (or a
  shared strip/UPS trip), not a Mini wedge. Treat "both machines reboot together" as
  the power signature in future incidents. There is no auto-catch-up for calendar
  LaunchAgents after a power cycle (see 10/8 entry above).
- Spark evening outage 10/8: last good Ollama contact 17:08 ET (super-prewarm), fail
  at 18:38 ET, research engine "unreachable" from 18:11 ET and "Host is down" 19:18 ET.
  CAUTION: ~/logs/super-prewarm.log stamps LOCAL time with a trailing "Z", so its
  "17:08:48Z" is 17:08 ET; do not read it as UTC;
  no NetworkManager carrier events in the Spark journal for that window, so the Spark
  hung rather than losing link. Matt rebooted it 19:14 ET; link up 19:23 ET; from the
  Mini: ARP ok, ping 4 ms, ssh 22 + Ollama 11434 open, autossh tunnel restored, by
  19:26 ET. Ollama listens on *:11434 (not localhost-only). After the reboot only
  nomic-embed-text was loaded; super-prewarm kicked by hand 19:3x ET.
- Diagnosing the Spark from the Mini: the MCP exec shell has no /sbin,/usr/sbin in PATH
  (use /sbin/ping, /sbin/ifconfig, /usr/sbin/arp -an). Mini is 10.0.0.125 on en1; Spark
  is 10.0.0.143 MAC 4c:bb:47:2e:70:27, hostname spark-7027, ssh user zirkai (key auth
  works). spark_url lives in config/spark-models.json and is also hardcoded in 7 .py
  files (boot-recovery, kg-readback, model-release-monitor, spark-model-manager,
  spark_models, system-auditor, zeke-unified-api); a DHCP reservation on the router
  (10.0.0.1) for that MAC is the cheap protection. nvidia-smi on the GB10 reports
  memory as [N/A] (unified memory) - do not gate on it.
- Spark sshd logs "Invalid user zekezirk from 10.0.0.125" at 19:24/19:25 ET: some Mini
  process sshes to the Spark without specifying user zirkai and fails silently. Not yet
  located.
- Workflow note: the first outage-sweep workflow (13:5xZ) died on the account's 5-hour
  usage limit ("session limit, resets 15:20 UTC") after writing the synthesis; rerun at
  23:2xZ. Subagent fan-outs share Matt's plan quota - check headroom before big sweeps.

## 10/8 outage sweep result (workflow, 15 agents, verified) and synthesis correction
- Only slots lost to the power loss: btc-trailing-monitor 21:00 10/7 (superseded by 10/8
  runs), nightly-reflection 02:30, claude-code-updater 03:00, embed-capability-index 03:30,
  sprawl-audit 04:00, camel-posts-backup 04:10, system-auditor 05:00, conviction-backtest
  Thu 05:00, fix-monitor 05:30, tombstone-sweep 05:45, briefing-prestage 05:45,
  premarket-scan 06:00 (+ morning-briefing 06:30, recovered). Every other calendar and
  interval job, all 17 daemons, openclaw gateway/tunnel/dashboard and ttyd ran or came
  back normally; boot-recovery.py only checks Funnel + restarts CDP, no catch-up role.
- Kicked by hand 20:12 ET 10/8 after two-agent verification (read-only probes, no
  Telegram): system-auditor (exit 0, state/system-audit.json) and conviction-backtest
  (exit 0, state/conviction-backtest.json; otherwise nightly-assessment would hit its 168h
  FAILED threshold Mon). Left for their 10/9 slots: the rest. premarket-scan must NOT be
  kicked late: its 720-min cooldown lapses and it sends a dated PRE-MARKET Telegram.
- wiki-compiler's 18:39 ET run lost 7 feed entries (6 for bond-thesis.md) to the Spark
  outage and advanced its cursor past them; openclaw gateway cron agents timed out
  18:25 ET and retried at 20:00 ET. scheduler had one boot-race fail (treasury-bonds
  06:36 ET). TV delivered new DCL labels 20:01Z 10/8: TLT $76.43 and GDX $84.36
  (daily_day_tv reset to 1 for both).
- Synthesis written 13:50Z had two wrong decision lines, found by the fact-checker and
  fixed 23:5xZ (file now 10,116 chars, rechecked pass/pass): (1) SPX kill line was given as
  the 10-SMA $7,731; the real alpha_v3 kill is a close under $7,177.63 (-8% from the
  $7,801.77 entry; SESSION_BRIEF.json + morning-alpha.md). (2) "TLT $78 stop" is not an
  armed rule anywhere (no TLT exit rule; the only $78 stop on file is silver's); it is
  the bottom of Camel's 78-80 sweep zone carried as a floor since the 9/29 synthesis.
  Lesson for the cloud synthesis prompt: cite kill/stop levels only from decisions.jsonl,
  SESSION_BRIEF open_decisions or morning-alpha.md, never from prior syntheses.
- Account 5-hour usage limit can kill subagent fan-outs mid-flight ("session limit,
  resets 15:20 UTC" on 10/8); the producer had already written its file. Check headroom
  before big workflows and treat ROUTINE_RUN_STATUS_SUCCEEDED as "session ended", not
  "job done".
