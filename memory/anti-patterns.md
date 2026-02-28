# Zeke Anti-Patterns — What NOT To Do
> Hard-won lessons. Read before every destructive operation.
> Updated: 2026-02-26

## Deletion & Modification
- **NEVER delete cron jobs without checking scheduler mapping.** Scheduler dispatches by name (lines 221-240). Deleting a job from jobs.json while scheduler still references it = zero feed growth for that topic. (Broke this 2/26 — caused emergency restoration.)
- **NEVER patch prompts incrementally.** Accumulated edits make prompts incoherent. Always rewrite the full prompt from scratch. (Broke this multiple times pre-2/22.)
- **NEVER use the `write` tool with local models.** They overwrite entire files instead of appending. Use `exec` with `>>` only. (Caused 3+ feed wipes.)
- **NEVER give local models more than 6 tools.** They degrade: parameter mangling, hallucinated tool names, broken JSON. (Proved empirically.)
- **NEVER use `set -e` in bash orchestrators.** First timeout kills entire script. (Caused 7.5 hours zero feed growth.)
- **NEVER type complex Python through ttyd.** Bash 3.2 mangles quotes, heredocs, indentation. Write downloadable scripts instead. (Multiple deploy failures 2/22.)

## Assumptions
- **NEVER assume backup is pre-change.** The rebuild script made its backup AFTER deleting jobs. Always verify backup contents before relying on it.
- **NEVER assume MCP connector is alive.** It drops silently (Anthropic bug). Server stays healthy — fix is remove/re-add in Settings. Design memory to work WITHOUT MCP.
- **NEVER assume `$(date)` works in OpenClaw prompts.** OpenClaw interpolates shell expressions. Use model's own time awareness or exec commands.
- **NEVER use qwen3:32b directly.** It has 2048 default context and hangs. Always use qwen3-32b-32k (custom 32k context).

## Process
- **NEVER deploy without verifying.** Every change needs: valid syntax check, process alive check, feed count check. (Multiple "it works" declarations that didn't.)
- **NEVER build orchestrators on unverified operations.** Verify the individual operation works first, then wrap it.
- **NEVER send Claude Code prompts that assume prior context.** Every `claude -p` must be fully self-contained with complete specs.
- **NEVER declare victory without testing.** HTML render, JSON parse, process checks. Always verify.

## Architecture
- **NEVER make MCP the only path to critical data.** Use GitHub (web_fetch) as reliable backup. MCP is convenience, not foundation.
- **NEVER store sensitive data (tokens, keys) in GitHub-pushed directories.** Keep in ~/.zeke-telegram.env with chmod 600.
- **Gateway must restart after jobs.json or openclaw.json changes.** Also purge sessions directory.

## MCP Connector Stability
- **SSE keepalive is required.** MCP SDK omits EventSourceResponse ping param. Fix: monkey-patch ping=15. (2/26)
- **Track issues:** #20335, #18557, #1026, #15232, #5826, anthropics/claude-ai-mcp#5
- **SSE being deprecated** in favor of Streamable HTTP. Migrate when claude.ai support stabilizes.


## OpenClaw cron job field names (learned 2/26 evening)
- NEVER use `payload.prompt` — OpenClaw ignores it completely
- ALWAYS use `payload.message` — this is the only field OpenClaw reads for cron job prompts
- `delivery.mode` must be `"none"` for research jobs. `"announce"` requires a target config or job fails with "delivery target is missing"
- When rewriting jobs.json, ALWAYS check existing working jobs for the correct field structure before writing new ones

## Gateway freezing from concurrent jobs (learned 2/26 evening)  
- Multiple openclaw-cron processes running simultaneously will freeze the gateway
- Guardian may crash-loop (restart every 60s) if scheduler dies on startup
- Fix: kill all openclaw processes, purge sessions, let guardian restart cleanly

## Trading Discipline (learned 2/27 — the FOMO lesson)
- **NEVER chase a move without DCL confirmation.** SLV up 0.5% triggered FOMO on 2/27. The alert engine exists to replace emotion with data. If Telegram hasn't said "pull the trigger" → the answer is WAIT.
- **NEVER enter before cycle day 18.** Gold daily cycle is 22-28 days. Entries before day 18 have no timing edge and increase drawdown risk.
- **DCL confirmation requires ALL of:** (1) swing low formed, (2) close above 10d SMA after being below it, (3) cycle day 18+. Missing any one = no entry.
- **NEVER let "it's going up" override the system.** The pullback you're waiting for (early March per Camel) will give you cheaper calls AND confirmed cycle structure. Buying on a green day saves nothing.
- **SLV entry is SEPARATE capital from GLD.** Never reduce GLD allocation to fund SLV. Both fire on same trigger (gold DCL), both go in E*TRADE (1256).
- **No hedging decisions without pulling full data first.** Don't react to a single price move. Pull prices → portfolio → cycle state → trade plan → THEN decide.
- **Size with conviction, not anxiety.** FOMO-driven entries are undersized (rushed) or oversized (compensating). Planned entries have pre-set allocations.

## Spark Contention (2026-02-27)
- Multiple consumers (scheduler, camel pipeline, self-repair) hit Ollama with no coordination
- Ollama queues internally but jobs can timeout waiting
- FIX: spark_lock.py advisory lock with PID-alive checks and 10min staleness
- All Spark consumers must acquire/release lock around inference calls

## Feed Deduplication (2026-02-27)
- v1 pipeline used `https://youtube.com/watch?v=ID`, v2 used `youtube/ID`
- Same video appeared 3-6x in feed, poisoning quality scores
- FIX: Normalize all camel sources to `youtube/{VIDEO_ID}` format
- Pipeline now does dedup check before writing

## MCP Timeout Pattern (2026-02-27)
- MCP exec_command has 30s timeout - NOT for long-running processes
- Pattern: write script → make executable → `bash script.sh &` → return immediately
- For multi-hour jobs: write to research-queue.jsonl or add one-shot cron entry
- NEVER try to babysit a long process through sequential MCP calls
