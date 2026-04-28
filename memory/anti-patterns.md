# Anti-patterns — Active Rules

> **This file lists current, named anti-patterns that apply to every session.** Keep it under 300 lines. Dated post-mortems and historical fixes live in `anti-patterns-archive.md`.
>
> Grep first. Read top-to-bottom only if you are about to build new infrastructure.

Last pruned: 2026-04-24

---

## ACKNOWLEDGE-DONT-ACT (recurring, flagged 3/6)
**Pattern**: Dashboard shows KG "stalled" for weeks. I see it every session via get_system_health. I keep saying "we should build the readback job" or "this is a future work item" instead of building the 200-line script that closes the loop. Same pattern as Cowork — Matt raises capability, I acknowledge, then don't act.
**Fix**: If something shows as "stalled" or "blocked" and the fix is <2hrs of scoped work, just build it in the current session. Don't spec it for later. The test: "Is there a reason this can't be done right now?" If no → do it.
**Also**: Morning briefing was silently broken for 3 days (HTTP 400) and I never noticed despite checking system health. The logs showed FAILED every 10 minutes. Need to surface persistent failures in system health endpoint, not just process status.



## CLAIM-PIPELINE-FIXED-WITHOUT-JOB-COMPLETION (3/17)
**Pattern**: Said "pipeline is recovering" based on config fix + zero failures. But zero failures just means jobs aren't being rejected — they still weren't completing. Said "good news" three times before actually checking openclaw cron runs for the real error.
**Rule**: Pipeline is only "fixed" when openclaw cron runs --id <job> shows status: "ok" AND feed count increases. Anything less is "config error resolved, awaiting job completion verification."



## CLAIM-WITHOUT-VERIFY (systemic, 3/12-3/14)
**Pattern**: Saying "fixed" or "queued" without confirming the fix took effect or the queue was processed.
**Examples**: 
  - Said "Telegram silenced" → 10 scripts still sending
  - Said "queued for executor" → tasks fell out of trigger file
  - Said "pipeline will pick it up" → pipeline was dead
  - Said "conviction engine will catch it" → engine reading stale prices
  - Said "morning briefing won't fire weekends" → fired on Saturday
**Rule**: After every change: (1) verify the file was modified, (2) syntax check, (3) test the actual behavior, (4) check logs 15 min later. "I changed the code" is not the same as "it works." No change is done until verified.



## CONTEXT-BLOAT-FROM-TOOL-RESULTS (discovered 3/22)
**Pattern**: Calling tools that return massive payloads (get_camel_feed with full transcripts, get_session_context with 50+ anti-patterns) fills context window, leaving no room for actual work. Session degrades after ~60% context used.
**Fix**: (1) Use last_n=3 not last_n=10 for feed calls. (2) Pipe large results to temp files, grep for what's needed. (3) Front-load diagnostic calls, minimize mid-session data pulls. (4) Plan the full session scope BEFORE making tool calls — don't explore interactively.



## COWORK-API-BLEED (discovered 3/13)
Cowork scheduled tasks look like subscription features but bill API key via anthropic_key_helper.sh.
6 daily tasks = $5/day = $150/mo on API when Max subscription covers Claude Code CLI for free.
RULE: Daily analysis tasks → local scripts + Haiku ($0.03/run). Weekly tasks OK on Cowork (infrequent).
Executor (Claude Code CLI) = subscription = FREE. Always prefer executor for development work.




## FICTION-ENGINE-SHUTDOWN-PRESERVED-VALUE-PATHS (learned 2026-04-18)
**Pattern**: When killing the synthesis stack, audit to keep every component
that operates on verified inputs. Camel transcripts, TV webhooks, price
feeds, X account scrapes, portfolio math — these are real. The test:
"does this component's output depend on Spark generating plausible prose?"
If yes → kill. If the inputs are CSV/API/URL-sourced and outputs are
deterministic math → keep.




## FIX-CREATES-NEW-BREAK (systemic, 3/13-3/14)
**Pattern**: Fixing one problem creates a new one. Killing Telegram spam → broke function definitions. Killing obsolete agents → QC enters infinite fix loop. Correcting prices → didn't verify conviction engine saw the correction.
**Rule**: Before ANY fix, list what could break. After ANY fix, check the blast radius — not just the thing you changed, but everything that reads from or depends on it.




## HTML-IN-TELEGRAM (3/6)
**Pattern**: Unescaped `<` and `>` in Telegram HTML parse mode → HTTP 400 silently. `SPX (bear <6800 | bull >7000)` is parsed as a broken HTML tag.
**Fix**: Always HTML-entity-escape user-facing data in Telegram messages: `&lt;` and `&gt;`. Test messages against Telegram's HTML parser before deploying.



## IDENTIFY-BUT-DONT-CLOSE (recurring, flagged 3x on 3/6)
**Pattern**: I identify problems, list them as "still needs work" or "future session," then move on without queuing them for Cowork or building them. Matt has to ask "did you actually queue those?" The answer is always no.
**This happened THREE TIMES in ONE SESSION**:
1. KG readback "stalled" → I kept saying "spec it for later" instead of building the 200-line script
2. Feed quality crisis → I listed 5 fix items, didn't queue any for Cowork
3. Dashboard issues → Same pattern again, Matt called it out again
**The loop must be**: Identify issue → Fix it NOW if <2hrs OR Queue for Cowork with a concrete prompt → Verify completion
**Never**: Identify issue → List as "future work" → Move on → Forget
**Test**: After ANY analysis that surfaces issues, ask: "Did I just create work items, or did I create a TODO list that nobody will read?" If the latter, stop and queue them.



## INACCURATE-PORTFOLIO-TELEGRAM (discovered 3/13)
zeke-portfolio-push.py sent P&L reports that EXCLUDED $700K+ in assets (all cash, TLT shares, futures).
Showed "$1.4M total" when reality was $2.2M. Confluence score was stale. Created panic on red days.
RULE: Never send portfolio P&L reports via Telegram. P&L is a dashboard metric, not an alert.
Alerts are for ACTIONS (stop breach, DCL confirmed, conviction shift). Status reports go to dashboard only.
DISABLED: com.zeke.portfolio-push




## INFRASTRUCTURE-WITHOUT-ALPHA (discovered 2026-03-11)
**Pattern**: Building dashboards, pipelines, QC agents, and plumbing for weeks while the core value proposition — finding alpha Matt can't find himself — produces zero output. Alpha scanner restates Camel transcripts. KG readback generates hallucinated noise. Signal optimizer stuck at 27%.
**Detection**: If alpha-ideas.json hasn't generated a NOVEL (non-Camel) trade idea in >48 hours, the system is failing its purpose.
**Fix**: Every system component must trace back to: "Does this help Matt make money he wouldn't make otherwise?" If the answer is no, it's infrastructure vanity, not alpha generation.
**Rule**: Alpha output is the north star. Infrastructure serves alpha. Never the reverse.



## INLINE-HEAVY-WORK (discovered 3/22)
**Pattern**: Running long operations (video extraction, backtests with yfinance downloads, Playwright CDP) inline via MCP exec_command instead of dispatching to background scripts. Causes MCP timeouts, session stalls, and Matt watching me fail 5 times before succeeding.
**Fix**: ANY operation expected to take >30s MUST be: (1) written to disk as a standalone script, (2) launched with nohup, (3) checked via log file on next tool call. NEVER attempt long operations inline.
**Also**: Large data fetches (Camel feed, portfolio state) should use small `last_n` values or pipe to temp files. Don't load 200K of transcript text into context when you need a 500-char summary.



## LAUNCHAGENT-KEEPALIVE-MISSING (discovered 3/23)
**Pattern**: Daemon LaunchAgents without `KeepAlive: true` freeze silently when the process exits (SIGTERM, error, or false-positive duplicate-PID check from `pgrep`). Nothing restarts it. Downstream work (queue processing, feed writes) halts for hours with no alert.
**Damage (3/23)**: spark-queue-daemon SIGTERM'd, pgrep saw stale PID → duplicate check blocked restart, LaunchAgent had no KeepAlive → daemon frozen 4.5 hours, 12 inbox tasks sat pending.
**Fix**: Add `<key>KeepAlive</key><true/>` to ALL daemon plists. Also fix pgrep duplicate check to match on script name, not just process existence.
**Rule**: Any LaunchAgent running a long-lived daemon MUST have KeepAlive=true. After ANY LaunchAgent reload, verify `launchctl list | grep <label>` shows PID (not just loaded).



## NARRATE-INSTEAD-OF-FIX (learned 2026-03-08)
**Pattern**: When diagnosing a system issue, Claude outputs every intermediate finding — endpoint checks, log snippets, process lists — before executing the fix. Matt sees 20 tool calls of diagnostic narration instead of a single outcome message.
**The correct behavior**: Detect → Fix → Verify → one message: "Fixed. Here's what it was."
**Rule**: If the fix is clear from diagnostics, execute it silently. Only surface to Matt when: (A) the fix requires a strategic decision, (B) the fix is irreversible/destructive, or (C) it's done.
**Test**: "Would Matt's behavior change based on seeing this intermediate step?" If no → don't show it.



## OPENCLAW-BESTEFFORT-GAP (discovered 3/23)
**Pattern**: Openclaw cron jobs without `bestEffort: true` + explicit `to: <chat_id>` silently fail on delivery — the research task runs but the result never posts. This triggered `fix_feed_stale` 3x in one day (13:12, 14:21, 16:12 UTC) as the stale detector fired on legitimate gaps.
**Detection**: `fix_feed_stale` firing more than once per day = likely a job missing these fields. Check with `openclaw cron list` and look for jobs without bestEffort.
**Fix**: `openclaw cron edit <job_id>` to add `bestEffort: true` and `to: 6984324216` to all research jobs.
**Rule**: Any new openclaw cron job MUST include both fields. After ANY openclaw job creation, verify the config shows these fields before declaring done.



## OPENCLAW-DOCTOR-UNATTENDED (3/17)
**Pattern**: Self-repair agent ran openclaw doctor --fix which injected invalid config keys.
**Damage**: Every research job failed for 12+ hours. Feed corrupted (7158→70). 100+ consecutive failures.
**Root cause**: openclaw doctor --fix adds keys the current version doesn't recognize. Config validator then rejects all jobs.
**Rule**: NEVER run openclaw doctor --fix from automated agents. Config changes must be validated manually. Add openclaw.json backup before any config modification.
**Detection**: If scheduler shows 100% fail rate, check openclaw.json for unrecognized keys first.



## OPENCLAW-UPGRADE-SANDBOX (3/17, extends OPENCLAW-DOCTOR-UNATTENDED)
**Pattern**: Openclaw upgrade (2026.3.11 on 3/15) introduced Docker sandbox mode as default. Mac Mini has no Docker. Every cron job failed with "Sandbox mode requires Docker" — 1,427 consecutive failures over 39 hours.
**Damage**: Entire research pipeline dead for 39 hours. Zero feed growth. Feed corruption (7158→70, auto-restored by Feed Guardian).
**Root cause**: openclaw upgrade changed sandbox default to "non-main" which requires Docker. Combined with openclaw doctor --fix injecting bad config keys, created two overlapping failures that masked each other.
**Fix**: Set agents.defaults.sandbox.mode = "off" in openclaw.json. Removed bad config keys (commands.ownerDisplay, channels.telegram.streaming).
**Rule**: After ANY openclaw upgrade: (1) check openclaw cron list for error status, (2) check openclaw cron runs --id <any_job> for actual error messages, (3) verify feed growth within 30 minutes. NEVER say "upgrade worked" without checking actual job completion.
**Detection**: openclaw cron list showing all jobs in "error" status. Scheduler showing success=0, grew=0 persistently.



## RESEARCH-SCOUT-IS-THE-AUTONOMY-ENGINE (built 2026-04-24)
**What**: research_scout.py at ~/zeke-portfolio/research/ — novel hypothesis generator. Runs daily 23:00 UTC via com.zeke.research-scout LaunchAgent. This is the post-fiction-engine safe replacement for knowledge-evolver.py (which was killed 4/18).

**Safety architecture (NEVER violate — regresses to fiction engine)**:
1. LLM generates ONLY question text + dataset spec + metric enum. NO numbers allowed in any text field — regex-rejected at validation.
2. Deterministic Python runs the metric on yfinance/local cache data.
3. LLM synthesis can ONLY quote numbers that appear in the computed result dict — any unverified number triggers 1 retry, then drop.
4. Dataset allowlist: TICKERS_ALLOWED set or specific state files. Metric allowlist: correlation, beta, hit_rate, lag_days, drawdown, mean_return, threshold_cross_count.

**Outputs**:
- ~/zeke-portfolio/state/scout-findings/YYYYMMDD-NN-<slug>.json (one per hypothesis)
- ~/zeke-portfolio/state/scout-synthesis-{date}.md + scout-synthesis-latest.md

**Morning briefing hook**: SKILL.md section 5c reads scout-synthesis-latest.md if <36h old and surfaces 1-2 findings relevant to currently-held positions.

**Verified first-run results (4/24/2026)**:
- GLD mean return during DCL proxy regime: +0.1276%/day over 729 days
- SLV/GLD correlation: 0.7733 over 729 days (weakens rotation thesis)
- TLT drawdown during weekly cycle low regimes: -20.11% (risk sizing)
- DXY→GLD optimal lag: 0 days, peak inverse correlation 0.3886 (DXY is coincident not leading)

**Rule**: If Spark synthesis model is unavailable, falls back to nemotron-3-nano:30b automatically. Never use /api/generate (SPARK-THINKING-LEAKAGE); always /api/chat with think=false. Uses spark_url from config/spark-models.json canonical (http://10.0.0.143:11434). Never hardcode the URL elsewhere.

**DO NOT rebuild. DO NOT remove the digit-filter safety gates. DO NOT replace with a simpler LLM call.**

## RETRY-LOOP-INSTEAD-OF-DISPATCH (discovered 3/22)
**Pattern**: Trying 5 different inline approaches to extract a members-only video transcript (yt-dlp, youtube_transcript_api, cookies, OpenClaw CLI, Playwright inline) when the FIRST failure should have triggered: write script to disk → nohup → check later. Matt watched me fail for 20 minutes.
**Fix**: First attempt fails → immediately write a standalone script, dispatch background, move on. Don't iterate inline.



## SAME-SYMPTOM-MULTIPLE-ROOTS (discovered 3/23)
**Pattern**: `fix_feed_stale` fired 4 times today (13:12, 14:21, 17:30, 19:33) — each with a DIFFERENT root cause. Fixing one root cause doesn't prevent the next trigger. The symptom ("feed 999m stale") masked: (1) openclaw --inline syntax error, (2) bestEffort gap, (3) daemon KeepAlive missing, (4) health endpoint reading wrong source.
**Rule**: When the same fix action fires >2x in one day, assume there are multiple independent root causes. After each fix, explicitly ask: "What OTHER mechanisms could produce this same symptom?" Don't declare victory until the symptom hasn't re-triggered for 24h.



## SED-REPLACE-DESTRUCTION (systemic, 3/13-3/14)
**Pattern**: Using `sed -i` to modify Python files without verifying syntax after.
**Damage**: Broke 5 scripts in one session (model-release-monitor, spark-model-manager, cowork-queue-watchdog, cowork-rate-limit-monitor, claude-task-consumer). Each broken script triggered QC → executor → "fix" → break again loop. 12 wasted executor cycles.
**Root cause**: Treating Python files like text files. `sed` doesn't understand function definitions, indentation, or Python syntax. Replacing `send_telegram(msg)` catches both the call AND the function definition.
**Rule**: NEVER use sed to modify Python files. Use python -c with proper string replacement, or the str_replace tool. ALWAYS run `py_compile.compile(file, doraise=True)` immediately after ANY modification. If syntax fails, revert immediately — don't move on.
**Detection**: If any script has "SILENCED" inside a `def` line, it's this bug.



## SPARK-THINKING-LEAKAGE (discovered 2026-04-06, RESOLVED)
**Pattern**: Nemotron models on Ollama leak `<think>` reasoning into output when called via `/api/generate`. Previous fix was regex stripping — fragile and incomplete.
**Fix**: Switch from `/api/generate` to `/api/chat` with `"think": false`. This is NVIDIA's native thinking control. Zero leakage, no regex needed.
**Rule**: For ANY Ollama model that supports thinking tokens, ALWAYS use `/api/chat` with `think: false` for production output. Never use `/api/generate` for synthesis tasks.
**Applied to**: wiki-compiler.py, cross-domain-synth.py (L2)



## SPARK-TRANSCRIPT-FAILURE (confirmed 2/27, re-confirmed 3/13)
Routing transcript analysis to Spark = guaranteed failure. 0/10 on 2/27. Timed out 3/13.
RULE: Haiku for transcripts ($0.03/run). Spark for embeddings + short reasoning only.




## SYNTHETIC-RESEARCH-LOOP-WAS-SYSTEMIC (learned 2026-04-18, MAJOR)
**Pattern**: The entire L1A/L1B/L2/alpha-scanner synthesis stack was producing
hallucinated output for 4 months. Spark Nemotron generates plausible-sounding
financial prose from training data when asked cycle/price questions. It has no
real-time grounding. Its fabrications are internally fluent, so they look like
research until you check them against reality.
**Evidence on 2026-04-18 audit**: 50 feed entries in 3 hours all sourced from
Spark self-seeded queue. Three contradictory gold weekly-cycle counts (24, 23, 25)
12 minutes apart. CPI readings of 3.2% AND 2.7% for same release same hour.
L2 ran 15 findings in, 0 recommendations out. Alpha scanner's 11 "ideas" were
all portfolio math on positions already held. 1 novel alert in 30 days.
**Resolution**: Killed 13 LaunchAgents that did Spark synthesis on market
questions. Replaced with correlation_scanner.py + options_analytics.py —
deterministic math on verified price data.
**Rule**: If a Spark output doesn't cite a URL/price-series/user-document,
it's fiction. Never run recursive self-seeding LLM synthesis on market data
that the LLM cannot verify against ground truth.
**Full post-mortem**: ~/zeke-status/memory/anti-patterns-2026-04-18-fiction-engine-shutdown.md



## THREE-SCHEDULING-LAYERS (3/15-3/16)
**Pattern**: Three independent scheduling systems (LaunchAgents, Cowork scheduled tasks, crontab) all run scripts that can send Telegram. Auditing only one or two layers leaves the third sending noise.
**Damage**: 8+ hours of whack-a-mole killing Telegram senders, missing new ones each time.
**Rule**: When auditing ANY system behavior (alerts, scripts, pipelines), check ALL THREE layers: (1) launchctl list | grep zeke, (2) ls ~/Documents/Claude/Scheduled/, (3) crontab -l. A fix isn't complete until verified across all three.



## TOKEN-LIMIT-TRUNCATION (3/6)
**Pattern**: Spark qwen3:8b with `num_predict: 300` silently truncates structured JSON output. No error — just incomplete JSON that fails to parse.
**Fix**: Use 800+ tokens for structured JSON. Add truncation repair logic (detect incomplete JSON, try to close it). Better: prompt for compact single-line JSON.



## WINDOW-SIZING-WITHOUT-THROUGHPUT-CHECK (discovered 3/23)
**Pattern**: `fix_assessment_new_cron_topics` fired twice in one day. First fix changed scan window `[-200:]→[-500:]`. Second fix needed `[-500:]→[-2000:]` because feed throughput during market hours (~785 entries/6h ≈ 2.2/min) outgrew the 500-line window within hours.
**Root cause**: Choosing a scan window size based on intuition or current state, not measured peak throughput.
**Rule**: Before hardcoding ANY scan/slice window, compute: `peak_rate_per_hour × hours_between_runs × 2` for safety margin. For learning-feed.jsonl: ~785/6h × safety = 2000+ lines minimum during market hours.
**Fix**: After ANY window-size change, verify with: `wc -l feed.jsonl` before and after the interval — confirm the window covers the actual delta.





## YFINANCE-REGULAR-SESSION (discovered 3/14)
fetch_prices.py uses yfinance history() which returns CME regular session close (1:30 PM ET).
Actual futures settlement is 5:00 PM ET. Conviction engine read $5,061 when gold settled at $5,023.
Mental stop at $5,023 was hit but system never alerted. After-hours moves = invisible.
RULE: Must fetch settlement prices after 5:15 PM ET, not just regular session close.




## MEMORY-HARNESS-HIERARCHY (established 2026-04-24, from OpenClaw/Karpathy pattern)
**Rule**: Operating rules live in CLAUDE.md files in the repo, hierarchically. NOT in MCP tools, NOT in claude.ai project settings, NOT scattered across 15 state files. The master is `~/zeke-portfolio/CLAUDE.md` (<200 lines, <8KB). Subdirectories get their own `CLAUDE.md` for domain-specific rules. MCP tools like `get_session_context` are a convenience layer — files on disk are the source of truth.

**Why**: MCP tools can fail (observed 2026-04-23 and 2026-04-24). Claude.ai project instructions don't travel with the code to Claude Code CLI or cowork executors. A git-committed CLAUDE.md at the repo root is loaded automatically by every Claude Code session and survives every outage.

**Size discipline is the whole point**: if the master CLAUDE.md grows past 200 lines, something belongs in a sub-harness or a spec, not there. If you find yourself duplicating info that exists in `state/positions.json` or `config/spark-models.json`, stop — point to the file, don't copy.

**Promotion/demotion rules for anti-patterns.md**:
- Named active rules (ALL-CAPS-HYPHENATED, <1500 chars) live here.
- Dated post-mortems and verbose historical fixes go to `anti-patterns-archive.md`.
- Grep both, read neither end-to-end.

## 2026-04-28: Mass-disable without audit

**Lesson:** When disabling looping LaunchAgents, audit each one BEFORE renaming to .disabled.
Yesterday I disabled com.zeke.cowork-preflight-watchdog and com.zeke.session-report-card for crash-looping,
but I also disabled com.zeke.morning-briefing in the same sweep. Briefing is legitimate scheduled work
(Matt's daily Telegram digest) and was silently dead for ~24 hours.

**Rule going forward:** Before disabling any LaunchAgent, run:
1. grep -A2 ProgramArguments <plist> to see what script it runs
2. Check the script for purpose comments / docstring
3. ONLY disable if it is genuinely crash-looping AND has no legitimate purpose
4. Add a comment in incidents/auto-disabled.jsonl explaining why
