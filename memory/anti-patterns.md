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
