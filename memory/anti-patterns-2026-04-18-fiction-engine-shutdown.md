# Anti-Pattern: SYNTHETIC-RESEARCH-LOOP-WAS-SYSTEMIC (learned 2026-04-18)

## What I discovered
Ran the auditor against the system on 2026-04-18 after Matt pushed back that 4 months
of 24/7 operation had produced almost no value. Numbers were damning:

- 36,319 Spark queue tasks "completed" lifetime, 0 failed — and on inspection the
  content was mutually-contradictory hallucinations of gold at $1,948 / $2,325 /
  $2,345 in entries written 12 minutes apart (actual GLD spot $445.93).
- Spark generated CPI readings of BOTH 3.2% (above 3.0% consensus) AND 2.7% (matching
  consensus, first sub-3% since Feb 2021) for March 2026 — same release, opposite
  directions, same hour.
- 10Y yield cited as 4.38%, 4.392%, 4.25%, 4.389% in one evening of queue output.
- L2 cross-domain synthesis latest run: 15 findings in, 0 recommendations out,
  1 discarded. Had been running nightly for weeks producing nothing.
- Alpha scanner's 11 "ideas": all were portfolio math on positions already held.
  Zero novel tickers. Zero non-Camel ideas.
- In 3 weeks of dispatcher uptime, 63 alerts sent. Only 1 was tagged
  alpha_high_conviction — and that was a pandas 20-day-high screen on crude oil
  (not novel).
- Self-assessment graded A 24 runs in a row because grader measured process
  uptime, not decision quality (UPTIME-WITHOUT-VALUE from 3/25 was still in force).

## Root cause
Spark Nemotron-3-Nano generates plausible-sounding financial prose from training
data when asked "what is gold's cycle day today." It has no real-time data,
no price lookup, no citation layer. Its fabrications are internally fluent,
which made them look like research. The queue daemon auto-seeded new tasks
when idle, compounding the fiction loop. wiki-compiler then ingested the
fiction and L2 read the compiled fiction as fact. Feedback loops
(alpha-feedback) ran against this base — they were adjusting weights on noise.

The 4/8 anti-pattern SYNTHETIC-NOISE-AS-KNOWLEDGE caught one source
(queue-research-general). It should have been generalized — every Spark
synthesis task without a citation layer produces this same class of
hallucinated output.

## What I killed (2026-04-18)
13 LaunchAgents (plists moved to ~/Library/LaunchAgents/.fiction-engine-disabled-20260418/):
- com.zeke.spark-queue (self-seeding hallucination daemon)
- com.zeke.knowledge-evolver (L1B)
- com.zeke.cross-domain-synth (L2)
- com.zeke.signal-optimizer (L1A, plateaued at 39% optimizing fake signals)
- com.zeke.kg-readback (already flagged hallucinated noise)
- com.zeke.rag-embed (embedding the fiction)
- com.zeke.wiki-compiler (compiling fiction into "knowledge")
- com.zeke.overnight-deep (deep Spark synthesis = more fiction)
- com.zeke.super-prewarm (pre-warming 120B for synthesis we're killing)
- com.zeke.infra-scout
- com.zeke.alpha-scanner
- com.zeke.alpha-feedback
- com.zeke.camel-backtester (was good, but dependent on dead pipeline)

4 live daemon processes killed via pkill.
2 cron jobs removed (zeke-queue-refill, zeke-content-reactor).
GPU utilization dropped 93% -> 0% in 3 minutes and stayed honest.

## What I kept (these actually produce value)
- com.zeke.camel-yt-pipeline-v2, camel-yt-posts, camel-daily-video-scanner,
  camel-x-monitor, camel-twin — ingest REAL external source data
- com.zeke.price-watcher, option-quotes, tv-cycle-reader, tv-webhook — real
  price data paths
- com.zeke.conviction-engine, bleed-detector, qc-agent, system-auditor,
  feed-guardian — operate on verified inputs
- com.zeke.mcp-server, mcp-watchdog, scheduler, unified-api, watchdog,
  cowork-executor, bi-hourly-assessment, boot-recovery, spark-model-manager,
  openclaw-browser, members-video-extractor — plumbing
- All 3 cloud Routines (trig_01TfKX..., trig_013id9Ti..., trig_01Qtrcb...)

## What I built to replace the fiction engine
Two deterministic quant tools — verified price data in, math out, zero hallucination surface:

1. /Users/zekezirk/zeke-portfolio/analytics/correlation_scanner.py
   LaunchAgent com.zeke.correlation-scanner, weekdays 17:30 local.
   13 tickers × 3 windows (30/60/90d) rolling correlations.
   Alerts when |30d - 90d| >= 0.30 or sign flips on stable pairs.
   Writes state/correlation-matrix.json + dispatches STATUS alerts.

2. /Users/zekezirk/zeke-portfolio/analytics/options_analytics.py
   LaunchAgent com.zeke.options-analytics, weekdays 09:45 + 16:15 local.
   Full BSM Greeks + breakeven probability + theta cliff for all 21 option
   positions. First production run immediately surfaced 2 CRITICAL alerts
   that 4 months of Spark "research" never flagged:
   - IBIT $48C: 61 DTE, 19% BE probability, down 46%
   - GLD $500C: down 78% from cost, 9% BE probability
   Writes state/options-risk-dashboard.json + dispatches CRITICAL alerts.
   morning_briefing.py now reads this file and shows the alerts in the
   OPTIONS RISK section (between CAMEL THESIS and ACTIVE SIGNALS).

## Rule going forward
**Every future analytics component must trace back to verifiable inputs.**
If a Spark synthesis task's output can't cite a URL, price series, or
user-supplied document, it's fiction. Feed entries sourced from
`spark-queue/bg_*` or `spark-queue/followup_*` are presumed hallucinated
unless proven otherwise. Wiki-compiler filter for queue-research-general
should be extended to queue-research-* globally.

## Detection
Count entries in learning-feed.jsonl last 24h where source starts with
"spark-queue/" AND topic starts with "queue-research-". If > 50% of new
entries match, the fiction loop has been reactivated somewhere — kill it.

## What I will NOT do again
- Build a "research" pipeline whose output is LLM prose on market questions
  without a grounding source. If the Spark GPU needs work to do, give it
  math on verified price series, not prose about cycles.
- Let a self-seeding queue daemon run unattended. The "always keep Spark busy"
  goal was wrong. Spark busy on verified quant work = value. Spark busy on
  self-generated narrative = fiction compounding at 70 tok/s.
- Let self-assessment grade A based on uptime. Need VALUE metric: did any
  output change a decision in the last 24h? If no → grade capped at C.
