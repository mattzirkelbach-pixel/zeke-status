
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

## Dashboard Must Reflect System State (learned 2026-03-01)
- **Every major session that changes system architecture MUST rebuild index.html**
- The dashboard at https://mattzirkelbach-pixel.github.io/zeke-status/ is Matt's primary GUI when not in chat
- If the dashboard doesn't reflect current state, Matt is flying blind between sessions
- Protocol: after memory sync, update index.html sections for: autonomy layers, system health, domain count, known blockers
- Push to GitHub = deploy. Dashboard serves from GitHub Pages immediately.

## LaunchAgent Hygiene (learned 2026-03-01)
- **Ghost plists (pointing to missing/archived scripts) accumulate silently and show in macOS System Settings as duplicates**
- Run audit: compare all plist ProgramArguments targets against filesystem — any MISSING = remove and unload
- .bak files in ~/Library/LaunchAgents/ should NEVER exist — macOS tries to load them, fails, shows as duplicates
- RunAtLoad=true on one-shot tasks (backfill, deploys) causes exit code 1 at login — use StartInterval instead
- Cleanup protocol: unload → move to zeke-backups/ → journal the removal

## FDA = Permanent Autonomy Unlock (learned 2026-03-01)
- **python3.14 + claude-code need Full Disk Access or they generate TCC permission dialogs constantly**
- python3 prompts kTCCServiceSystemPolicyAppData every ~few minutes = the approval queue at the Mac mini
- Fix is permanent: System Settings → Privacy & Security → Full Disk Access → add python3 + claude-code
- FDA covers ALL sub-services: AppData, SysAdminFiles, Downloads, Documents, Desktop, MediaLibrary
- After granting: 0 TCC prompts. The queue disappears.
- Confirmed grants 2026-03-01: python3.14, claude-code, node, sshd-keygen-wrapper, terminal, claude-desktop

## Cowork Integration Points (learned 2026-03-01)
- **Cowork is the central tab in claude.ai** — not a separate app to install
- Best integration: pending-approval.json pattern (Phase 4) — queue autonomous decisions for remote review
- Second fit: file management layer — archiving synthesis outputs, organizing zeke-backups/, graduated domain files
- Does NOT replace Python pipeline — Cowork handles human-in-the-loop touchpoints, Python handles data flow
- Claude Code on the right panel in claude.ai = the execution agent for agentic tasks

## Machine-Readable vs Human-Readable — File Creation Rule (learned 2026-03-01)
- **Before creating any file, ask: who reads this — a human or a machine?**
- Machine-consumed → JSON, JSONL, structured fields. Never markdown prose.
- Human-consumed → markdown only if the human explicitly asked for it
- **NEVER create a markdown "vision" or "audit" file unless Matt requests it**
- The correct output for a spec audit is: (1) verbal summary to Matt in chat, (2) maybe a JSON field update in project-state.md, (3) a feed entry if it's a finding
- Creating a 7KB markdown file that nothing reads = documentation theater = pure bloat
- Every file created adds to context load, compaction pressure, and maintenance surface
- Default: do the work in-context, surface the key finding to Matt, write to an existing structured file only if persistence is needed

## MCP Tool Call Size Limit (learned 2026-03-01)
- MCP rejects large payloads. Never write 150+ line files via write_file in one call.
- Correct: exec_command with python3 -c for targeted edits, or write to /tmp then move.
- Timeout = almost always payload size, not network.

## Signal Urgency Tiers - No Throttle on CRITICAL (learned 2026-03-01)
- CRITICAL (urgency=3): always fires, zero rate limit. DCL confirm, hard stop, cycle failure.
- WATCH (urgency=2): 4h cooldown per type, max 5/day.
- INFO (urgency=1): 24h cooldown, max 2/day.
- Design signals algorithmically for ANY instrument, not just current positions.
- Feed-discovered patterns must be able to surface new signals Matt did not define.

## One Block Per Session Boundary (learned 2026-03-01)
- ONE queue task per execution boundary. Full stop.
- After any block: verify syntax + dry-run, write journal, git commit, THEN stop.
- If user asks to "run next block" mid-conversation: do it, then surface results, then stop.
- Chaining blocks without committing journal = guaranteed crash and orphaned state
- The signal that context is getting long: MCP starts timing out. That is the hard stop.
- Recovery from crash: read session-journal.jsonl + check what files exist before touching anything.
