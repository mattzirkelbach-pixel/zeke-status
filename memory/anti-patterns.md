
## Claude Code Version Hardcoding (learned 2026-02-28)
- **NEVER hardcode claude-code version paths** like `claude-code/2.1.45/claude` — breaks silently on every update
- **Python**: use `sorted(glob.glob(str(HOME / "Library/Application Support/Claude/claude-code/*/claude")))[-1]`
- **Bash**: use `$(ls -d "$HOME/Library/Application Support/Claude/claude-code/"*/claude 2>/dev/null | sort -V | tail -1)`
- Both self-repair.py and nightly-synthesis.sh now use dynamic lookup — do NOT revert to hardcoded paths

## Pipeline Merge Protocol (learned 2026-02-28)
- **BEFORE merging/deprecating any pipeline**: read the full file, state what you confirmed, document it explicitly — not just internally
- **BEFORE any structural change**: snapshot jobs.json + crontab to dated .bak files
- **State files must be reconciled BEFORE merge**: if two pipelines tracked state separately, audit both and unify into canonical file FIRST
- **Deprecated files stay on disk** with header comment marking them deprecated — never silently delete

## Canonical Memory Update is NON-OPTIONAL (learned 2026-02-28)
- **Every session that makes structural changes** MUST write to session-journal.jsonl AND anti-patterns.md
- **ecosystem-audit.md alone is not sufficient** — the scheduled agents (kg-extractor, system-doctor) read session-journal and anti-patterns, not the audit file
- **If it's not in the journal, the next Claude won't know it happened**
- Treat memory writes as mandatory final step, same as releasing the Spark lock in a finally block

## Assessment-Before-Action is Partner Behavior (learned 2026-02-28)
- **Never act on a merge/deprecation without stating the pre-action assessment out loud**
- The assessment is: what does this file do, who calls it, what state does it own, what will break if removed
- Matt should be able to read the assessment and catch errors before execution, not after
- This is not a prompt — it is default behavior for any intelligent partner

## Vision/Execution Disconnect (learned 2026-03-01)
- **vision.md had the right destination (Feb 19): "conceive, design, build, test, deploy without human intervention"**
- **The operational roadmap in claude-strategic-context.md diverged to tactical features — no connection to vision**
- **Each session built features without asking: does this advance the autonomy architecture?**
- Fix: Start EVERY session by reading recursive-autonomy-spec.md. Every task should be mappable to a Phase in that spec. If it's not, ask why.
- Fix: If you're building a cron job, stop. Ask: should this be a queue task instead?

## Spark Idle = System Failure (learned 2026-03-01)
- **Spark at <20% utilization = 19-20 hours/day of free GPU capacity doing nothing**
- **The system "waiting" for the next cron tick while Spark is idle is the same as sleeping on the job**
- Correct model: Spark should be ALWAYS running the highest-priority task in the queue
- Idle Spark means: either queue is empty (a bug) or tasks are clock-driven not queue-driven (an architecture failure)
- Never add a new cron job for research/analysis work. Add a queue entry type instead.

## Synthesis Must Generate Next Tasks (learned 2026-03-01)
- **Every synthesis that doesn't write its next tasks to the queue is a dead end, not a loop**
- Tonight's Camel synthesis identified "find other cycle traders" — that should have been automatic, not a human observation
- Every synthesis output must include a `next_tasks` section that writes to spark-work-queue.jsonl
- If synthesis is terminal, it's not recursive. It's just an expensive feed entry.

## MCP Transport: Streamable HTTP IS LIVE — DO NOT RE-RECOMMEND (learned 2026-03-01)
- **server.py line 1022: `mcp.run(transport="streamable-http")` — DONE. Feb 2026.**
- SSE was replaced. Ping keepalive was replaced. This is not a future fix. It is current reality.
- When MCP drops: it is a Spark resource-starvation event, not a transport bug. Server self-recovers once inference completes (~60s).
- **NEVER suggest "migrate to Streamable HTTP" or "add SSE keepalive" — both already in production.**
- Known remaining issue: Claude.ai client-side SSE race condition on reconnect (Anthropic bug #10525). Not fixable by us.
- Recovery: wait ~60s, retry. Delete/re-add in Settings is last resort only.

## Session Journal Discipline Failure (learned 2026-03-01)
- **Session journal had 2 entries for weeks of work. Major architecture decisions were not captured.**
- Anti-patterns file is not enough — it captures lessons but not decisions
- The journal is how the next Claude session knows what architectural state it inherits
- Every session that makes a structural decision (not just file change) needs a journal entry with: what decided, why, what comes next
