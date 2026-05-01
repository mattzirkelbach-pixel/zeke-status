# Research synthesis — Zeke architecture vs. consensus best-practice

**Author:** Claude Code session at Matt's request, 2026-04-30
**Method:** Four parallel research agents on independent sources — Karpathy's corpus, Anthropic's published guidance, top OSS agent frameworks, high-rated GitHub configs + autonomous trading agents. Each agent worked from a structured brief comparing findings to Zeke's specific failures.
**Result:** Near-total convergence. The architectural failures Zeke exhibits are not novel; they are named anti-patterns with named solutions in the field.

## TL;DR

Zeke's failure modes — 600 findings/day with no consumer, recursive self-consultation, 5 memory layers / 1 compounds, self-grading 1.0 on n=4, 1 tombstone for 358 artifacts, 128 .bak files — are **textbook anti-patterns**. Karpathy, Anthropic's research team, and the maintainers of every major agent framework (LangGraph, Letta/MemGPT, mem0, MetaGPT, AutoGen, SWE-agent, Aider, TradingAgents, ai-hedge-fund) have all separately documented these failures and prescribed fixes. **Matt does not need to invent. He needs to copy.**

The architecture is also not all wrong. The capability registry concept, the local Mac Mini setup, the session-brief idea, the subagents-for-fresh-context pattern, the use of skills, and the harness-with-sub-harnesses approach all align with what the field considers right. **The fix is subtractive (kill the broken parts, copy the named-patterns) — not a rewrite from scratch.**

## The convergent verdict (what all four sources independently said)

### 1. The 600 findings/day with no consumer is a textbook anti-pattern

| Source | Phrasing |
|--------|----------|
| **Anthropic** | "Multi-agent systems consume ~15× more tokens than standard chat... For economic viability, multi-agent systems require tasks where the value is high enough to pay for the increased performance." Implicit answer: start with the consumer, work backward. |
| **Karpathy** | "Demo is works.any(), product is works.all()." 600 findings is works.any() — produces, nothing verifies. Prescription: shrink to verification-bounded throughput. |
| **GitHub trading agents** | TradingAgents (10k+ stars): every decision is *pending* until next same-ticker run, when it gets stamped with realized return + alpha vs. SPY. Memory only compounds because every entry eventually gets a real-world score. |
| **OSS frameworks** | MetaGPT (67k stars, ICLR 2025 oral): pub/sub `Environment` where messages with no subscribers are visibly logged warnings — converts sprawl from invisible into a debuggable metric. Freqtrade producer/consumer: typed signal bus with explicit contract. |

**Named solution:** Define the consumer first. If no consumer, the producer shouldn't run. For Zeke specifically: TradingAgents' realized-return reflection pattern is the most direct copy.

### 2. Recursive self-consultation (consult-claude.py consulting itself 67/67 times) is a known failure mode

| Source | Phrasing |
|--------|----------|
| **Karpathy** | "If you continue training on too much of your own stuff, you actually collapse... saying more and more of the same stuff." This is **model collapse**. |
| **Anthropic** | "Orchestrator-workers" is a strict tree: orchestrator delegates DOWN, workers do NOT consult UP. **No Anthropic-published precedent exists for an agent recursively consulting itself for novelty detection.** |
| **OSS frameworks** | LangGraph: hard `recursion_limit=25` (default), raises `GraphRecursionError`. AutoGen: `MaxMessageTermination` + `allow_repeat_speaker=False`. **Both frameworks have these limits because the bug was so common.** |
| **GitHub configs** | "PreToolUse `recursion-guard` hook" is a recognized pattern. |

**Named solution:** A depth counter on `consult-claude` calls + hard cap. Or replace consult-claude with bounded evaluator-optimizer (one Claude proposes, second Claude scores, max 2 iterations).

### 3. Five memory layers with stale facts is a known anti-pattern

| Source | Phrasing |
|--------|----------|
| **Anthropic** | One canonical persistent file + on-demand skills. "Compaction is event-driven, not cron-based" — regenerate when context fills, not every 15 minutes. |
| **Karpathy** | "These models don't have a distillation phase of taking what happened, analyzing it obsessively, thinking through it." Continuous re-summarization is the *opposite* of distillation. |
| **OSS frameworks** | Letta (22k stars): three strict tiers — **core** (in-context, hard size limit), **recall** (full log), **archival** (vector-indexed). Memory edits go through tool calls (`core_memory_replace`, `memory_insert`). The size limit forces compression and supersession. |
| **OSS frameworks** | mem0 community discussion: mem0's weakness is supersession — Zep is the framework that explicitly marks old facts as **temporally superseded** ("I moved to Shanghai" demotes "I live in Beijing"). Zeke has neither. |

**Named solution:** Letta's tier model + Zep's temporal supersession. Practically: collapse to one file with a hard size limit and tool-mediated rewrites.

### 4. Self-grading scorers (`hit_rate=1.0 on n=4` grading no_trade-correct-on-flat) is the canonical evaluation failure

| Source | Phrasing |
|--------|----------|
| **Anthropic** | "If you can't verify it, don't ship it." Verification needs an oracle the agent doesn't control. |
| **Karpathy** | RL is "sucking bits of supervision through a straw." Replace outcome-only grading with **process supervision** — a human (you) confirms each lesson before it enters the registry. |
| **GitHub trading agents** | TradingAgents grounds the score in realized return + alpha vs. SPY at T+N — not LLM self-grade. Lopez de Prado's **Deflated Sharpe Ratio** + walk-forward / purged CV is the canonical statistical gate. |
| **OSS frameworks** | SWE-bench (the gold standard): every patch must pass a **FAIL_TO_PASS** test (test that was failing must now pass) AND **PASS_TO_PASS** (regression guard). Zeke has only the PASS_TO_PASS half. **Without FAIL_TO_PASS, the gate is unforgeable.** |

**Named solution:** Adopt SWE-bench's two-set rule for the auto-fix loop. Adopt TradingAgents' realized-return reflection for the trading side. Both make the grade ungameable because the agent can't manipulate market truth or pre-existing failing tests.

### 5. 128 .bak files is hand-rolled rollback that has a better solution

| Source | Phrasing |
|--------|----------|
| **GitHub configs** | Aider (44k stars): every edit is a discrete git commit. Rollback = `git revert <sha>`. Free time-travel + audit trail. |
| **OSS frameworks** | LangGraph: every state mutation creates a checkpoint snapshot keyed by `(thread_id, checkpoint_id)`. `get_state_history` returns every checkpoint; you can rewind/fork. |

**Named solution:** Replace .bak files with git commits. Implement a thin "auto-commit per learning-loop apply" wrapper.

### 6. 1 tombstone for 358 artifacts (retirement path effectively unused) is a known smell

| Source | Phrasing |
|--------|----------|
| **GitHub configs** | "Tombstone is the default, not the exception." Every artifact has expiry or confirmation cadence. Without re-confirmation, confidence decays toward zero and the artifact auto-retires. |
| **Anthropic** | "If your CLAUDE.md is too long, Claude ignores half of it." Same principle applies to capability registry: signal dilution from accumulating artifacts. |
| **OSS frameworks** | MetaGPT: an artifact with zero subscribers is a candidate for retirement. The architecture surfaces it. |

**Named solution:** Nightly retire-job. Anything not touched in N days + zero subscribers + no recent reference → auto-tombstone. Signal-to-noise restored.

### 7. Three coordinators sharing JSON state (no message bus) is a known anti-pattern

| Source | Phrasing |
|--------|----------|
| **Anthropic** | "Multi-agent is wrong when agents share context heavily or have many dependencies." Either merge to one process with one source of truth, or split so they don't share state at all. |
| **OSS frameworks** | MetaGPT: shared `Environment` with explicit `publish_message` and `_watch` subscriptions. Zeke has neither — implicit JSON polling. |
| **OSS frameworks** | LangGraph: typed state object updated only via `update_state(values=..., as_node=...)`. Auditable, reversible, single source of truth. |

**Named solution:** Either MetaGPT's pub/sub or LangGraph's typed state with checkpoints. Both eliminate "who wrote this last and is it stale?" as a class of failure.

### 8. Pre-flight protocol in advisory memory rather than enforced

| Source | Phrasing |
|--------|----------|
| **Anthropic** | "Hooks are deterministic and guarantee the action happens. CLAUDE.md is advisory." |
| **GitHub configs** | High-rated repos (rulebricks/claude-code-guardrails, dwarvesf/claude-guardrails, blakecrosley.com — 95 hooks documented) all enforce critical rules via PreToolUse hooks. |

**Named solution:** Convert the pre-flight protocol from `feedback_zeke_preflight.md` text into SessionStart and PreToolUse hooks in `settings.json`. Past Claudes graded F for skipping pre-flight precisely because text rules are skippable.

## What Zeke is doing RIGHT (don't lose this)

All four sources independently confirmed these as correct choices:

| Zeke component | Why it's right |
|---|---|
| **Capability registry** (`artifacts/index.jsonl`) | Letta and LangGraph would pay to retrofit something like this. Add subscriber counts and the retirement path will use itself. |
| **Local Mac Mini + DGX setup** | Karpathy explicitly: "OpenAI got this wrong because they focused early codex / agent efforts on cloud deployments instead of simply localhost." Praises Claude Code as "first convincing demonstration of what an LLM Agent looks like." |
| **Persistent SESSION_BRIEF** | Anthropic's compaction pattern, just executed on wrong cadence (cron not event-driven) and wrong write semantics (append not replace). The concept is sound. |
| **Subagents for fresh context** | wshobson/agents (76+ specialized subagents) is the canonical pattern. This very research session used 4 parallel subagents. |
| **Skills (zeke-trading-analyst, zeke-system-ops)** | Matches Anthropic's "load on demand" pattern explicitly. |
| **Harness with sub-harnesses** (CLAUDE.md per domain) | Aligns with high-star repos. Just needs pruning to <80 lines. |
| **Auto-fix pipeline** (extract→propose→gate→apply→grade→rollback) | SWE-bench-style is exactly this. Just missing the FAIL_TO_PASS half. |

## Sequenced action plan (sourced)

Each step has a named pattern, a star-count-validated source, and an expected outcome.

### Tier 0 — already deployed today (this session)
- ✅ Fix #1: claude CLI on learning PATH
- ✅ Fixes #2-4: tz-aware datetime, HERE→_ORCH_DIR, auditor Label
- ✅ Fix #1.5: gate ACCEPT_PROGRESS
- ✅ Throttle: research_engine 30→1/hr (96% reduction)
- ✅ Spec written: `specs/research-to-edges-wiring.md`

### Tier 1 — high-confidence subtractive moves (low risk, low effort, high leverage)
**Half a day each.**

1. **Prune CLAUDE.md harness to <80 lines** — Source: HumanLayer convention, awesome-claude-md (3k stars). Today's is 122 lines + 6KB. Remove things Anthropic's own docs say belong in skills or hooks. Acceptance: `wc -l ~/zeke-portfolio/CLAUDE.md` returns ≤80.

2. **Convert pre-flight protocol to SessionStart hook** — Source: Anthropic best-practices docs ("hooks deterministic, CLAUDE.md advisory"). The rule "read harness, find_capability, audit 3 layers" goes in `settings.json` as a hook. Past Claudes won't be able to skip it. Acceptance: hook fires on `Edit` to any `*.py`.

3. **Add `recursion_limit` on consult-claude.py** — Source: LangGraph default 25, AutoGen `allow_repeat_speaker=False`. A counter in the call envelope. Hard fail past N. Acceptance: synthetic test sends 26 nested calls, gets `RecursionError`.

4. **Replace .bak files with git commits in learning loop** — Source: Aider (44k stars). Auto-commit each `apply()` rather than write `.bak`. Acceptance: `git log learning/policy.md` shows incremental commits; `find . -name "*.bak"` returns 0 in `learning/`.

5. **Kill dead memory layers** — Source: Anthropic ("one canonical + on-demand skills"). Delete `~/.openclaw/workspace/memory/` daily files (32 days dead) and `~/Documents/Claude/` (empty of human notes). Acceptance: those paths gone or marked deprecated.

### Tier 2 — high-confidence additive moves (medium risk, medium effort)
**1-3 days each.**

6. **Adopt TradingAgents' realized-return reflection memory** — Source: TauricResearch/TradingAgents (10k+ stars). Every alpha_v3 decision becomes a *pending* entry. Next same-asset cycle: stamp with realized return + alpha vs. SPY + one-paragraph reflection. Replaces `edge-weights.json` (which is grading no_trade-on-flat). Acceptance: file `state/decision-reflections.jsonl` has at least 1 stamped entry showing realized return.

7. **Add FAIL_TO_PASS gate to learning loop** — Source: SWE-bench Verified (OpenAI canonical benchmark). Currently the loop accepts on PASS_TO_PASS only. Add: every accepted lesson must reference at least one previously-failing assertion that now passes. Acceptance: gate decision schema includes `fail_to_pass_evidence` field; rejects diff that doesn't satisfy.

8. **Pub/sub message bus or LangGraph-style typed state** — Source: MetaGPT (67k stars) for pub/sub; LangGraph (30k stars) for typed state. Either pattern. Single source of truth replaces three coordinators sharing JSON. Acceptance: a published artifact with zero subscribers logs a visible warning.

### Tier 3 — speculative (high effort, requires Matt's product judgment)
**Multi-week. Spec first.**

9. **Backtest gate (Lopez de Prado walk-forward + Deflated Sharpe)** — Source: arxiv 2512.12924, Alpha-Agent. Already specced at `~/zeke-portfolio/specs/research-to-edges-wiring.md`. This is the second half of the "research engine produces value" question. Don't start until #6 is in place.

10. **Letta-style memory tiers with size limits** — Source: Letta docs. More invasive than Tier 1 #1; touches the curator. Defer until Tier 1 + 2 land.

## What Matt should NOT do

These came up in the research as cautionary signals:

- **Don't start by writing a brand-new orchestrator.** Karpathy: "use Claude Code as the agent loop, don't write your own." OpenAI Swarm was abandoned within 12 months precisely because hand-rolled minimal orchestration without persistence rotted.
- **Don't migrate to mem0 expecting supersession.** Community write-ups explicitly call mem0 weak on this. Zep is the right reference if going that direction; Letta is the right reference for in-context tier semantics.
- **Don't keep the research engine running at any volume until it has a consumer + gate.** All four sources independently said: producer without consumer is pure waste.
- **Don't add more components.** The fix is subtractive. The research engine has a throttle (1/hr) — leave it there until #6 lands.

## Sources

### Karpathy
- [2025 LLM Year in Review](https://karpathy.bearblog.dev/year-in-review-2025/)
- [Dwarkesh interview: AGI is a decade away](https://www.dwarkesh.com/p/andrej-karpathy)
- [Software 3.0 / YC AI Startup School](https://www.latent.space/p/s3)
- [nanochat repo](https://github.com/karpathy/nanochat)
- [Cognitive core tweet](https://x.com/karpathy/status/1938626382248149433)
- [RL credit assignment](https://x.com/karpathy/status/1944435412489171119)

### Anthropic
- [Building Effective AI Agents](https://www.anthropic.com/research/building-effective-agents)
- [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- [How we built our multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system)
- [Best Practices for Claude Code](https://code.claude.com/docs/en/best-practices)
- [Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
- [Anthropic Cookbook agent patterns](https://github.com/anthropics/anthropic-cookbook/tree/main/patterns/agents)

### OSS frameworks
- [LangGraph](https://github.com/langchain-ai/langgraph) — 30.9k stars
- [Letta (formerly MemGPT)](https://github.com/letta-ai/letta) — 22.4k stars
- [mem0](https://github.com/mem0ai/mem0) — 54.5k stars
- [AutoGen](https://github.com/microsoft/autogen) — 57.6k stars (now in maintenance mode)
- [MetaGPT](https://github.com/geekan/MetaGPT) — 67.6k stars, ICLR 2025 oral
- [SWE-agent](https://github.com/SWE-agent/SWE-agent) — 19.1k stars
- [SWE-bench Verified](https://openai.com/index/introducing-swe-bench-verified/)
- [Aider](https://github.com/aider-AI/aider) — 44.2k stars

### Trading agents
- [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents) — 10k+ stars
- [virattt/ai-hedge-fund](https://github.com/virattt/ai-hedge-fund) — 51k stars
- [Freqtrade producer/consumer](https://www.freqtrade.io/en/2022.12/producer-consumer/)
- [Lopez de Prado: Deflated Sharpe Ratio](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551)
- [arxiv 2512.12924 — Hypothesis-Driven Trading](https://arxiv.org/html/2512.12924v1)
- [Reflexion (Shinn et al. 2023)](https://arxiv.org/abs/2303.11366)

### Claude Code configs
- [josix/awesome-claude-md](https://github.com/josix/awesome-claude-md) — 3k stars
- [wshobson/agents](https://github.com/wshobson/agents) — 76+ specialized subagents
- [HumanLayer claudecode best practices](https://rosmur.github.io/claudecode-best-practices/)
- [rulebricks/claude-code-guardrails](https://github.com/rulebricks/claude-code-guardrails)
- [dwarvesf/claude-guardrails](https://github.com/dwarvesf/claude-guardrails)
- [Claude Code hooks guide](https://code.claude.com/docs/en/hooks-guide)

### Lethal trifecta
- [Simon Willison's writeup](https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/) (Karpathy-endorsed)
