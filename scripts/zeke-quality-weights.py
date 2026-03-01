#!/usr/bin/env python3
"""
zeke-quality-weights.py — Block 6: Quality-Driven Queue Optimization
=====================================================================
Reads feed-quality-scores.jsonl, aggregates by domain, then:
  - Boosts queue task priority for high-quality domains (+1)
  - Queues remediation tasks for low-quality domains (avg < 3.0)
  - Queues quality-audit tasks for declining domains (trend↓ + avg < 3.8)
  - Writes domain health state to quality-domain-health.json for dashboard

This closes the recursive loop:
  Feed entries → quality scores → domain health → queue priority adjustments
  → better tasks → better entries → higher scores

Run: python3 ~/zeke-quality-weights.py
Scheduled: com.zeke.quality-weights LaunchAgent (7:00am daily)

Output:
  - spark-work-queue.jsonl (priority adjustments on pending tasks)
  - quality-domain-health.json (domain health state for dashboard)
  - logs/quality-weights.log
"""

import json
import datetime
from pathlib import Path
from collections import defaultdict

HOME = Path.home()
MEM = HOME / ".openclaw/workspace/memory"
SCORES_FILE = MEM / "feed-quality-scores.jsonl"
QUEUE_FILE = MEM / "spark-work-queue.jsonl"
HEALTH_FILE = MEM / "quality-domain-health.json"
JOURNAL_FILE = MEM / "session-journal.jsonl"
LOG_FILE = HOME / "logs/quality-weights.log"

# Map all historical topic names to canonical domain names
TOPIC_TO_DOMAIN = {
    "treasury bonds and interest rates": "treasury-bonds",
    "treasury-bonds": "treasury-bonds",
    "treasurybonds": "treasury-bonds",
    "treasury auction calendar": "treasury-bonds",
    "fedwatch-rate-probabilities": "treasury-bonds",
    "macroalf-commentary": "treasury-bonds",
    "longevity research": "longevity",
    "longevity": "longevity",
    "ai agents and tool calling": "ai-agents",
    "ai-agents": "ai-agents",
    "tool-calling": "ai-agents",
    "multi-agent systems": "ai-agents",
    "self-improvement": "self-improvement",
    "compound-synthesis": "compound-synthesis",
    "camel-finance-cycle-analysis": "camel-finance",
    "camel finance: cycle trading theory": "camel-finance",
    "camel finance: hyperwave theory": "camel-finance",
    "camel finance: tradingview guide": "camel-finance",
    "camel finance: key u.s. economic": "camel-finance",
    "camel finance: understanding m": "camel-finance",
    "camel finance: trendline analy": "camel-finance",
    "camel finance: bitcoin": "camel-finance",
    "queue-research-xauusd": "camel-finance",
    "queue-analysis-spx": "camel-finance",
    "queue-research-tlt": "treasury-bonds",
    "queue-research-iren": "ai-agents",
    "options-flow-gld": "camel-finance",
    "options-flow-slv": "camel-finance",
}

# Thresholds
STRONG_THRESHOLD = 3.8    # avg >= this: boost pending tasks +1
WEAK_THRESHOLD = 3.0      # avg < this: queue remediation task
DECLINE_THRESHOLD = 3.8   # avg < this AND trend↓: queue quality-audit task
MIN_SAMPLES = 5           # need at least this many scored entries to act

# Priority adjustments
BOOST_AMOUNT = 1          # add to pending tasks from strong domains
MAX_PRIORITY = 10         # never exceed this

def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def log(msg):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    LOG_FILE.parent.mkdir(exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def normalize_topic(raw_topic: str) -> str:
    """Map raw topic string to canonical domain name."""
    t = raw_topic.lower().strip()
    # Exact match first
    if t in TOPIC_TO_DOMAIN:
        return TOPIC_TO_DOMAIN[t]
    # Prefix match for long Camel Finance topic names
    for key, canon in TOPIC_TO_DOMAIN.items():
        if t.startswith(key[:15]) and len(key) > 10:
            return canon
    return t  # unknown — keep as-is, will appear in health report

def load_scores() -> dict:
    """Load and aggregate quality scores by canonical domain."""
    domain_scores = defaultdict(list)
    if not SCORES_FILE.exists():
        log("WARN: No feed-quality-scores.jsonl found")
        return {}
    with open(SCORES_FILE) as f:
        for line in f:
            try:
                d = json.loads(line.strip())
                raw = d.get("topic", "unknown")
                canon = normalize_topic(raw)
                score = d.get("score", 0)
                if 1 <= score <= 5:
                    domain_scores[canon].append(score)
            except:
                pass
    return dict(domain_scores)

def compute_health(domain_scores: dict) -> dict:
    """Compute health metrics per domain."""
    health = {}
    for domain, scores in domain_scores.items():
        if len(scores) < MIN_SAMPLES:
            continue
        avg = sum(scores) / len(scores)
        # Recent trend: last 20% of entries vs overall avg
        n_recent = max(5, len(scores) // 5)
        recent = scores[-n_recent:]
        recent_avg = sum(recent) / len(recent)
        trend = "up" if recent_avg > avg + 0.1 else ("down" if recent_avg < avg - 0.1 else "flat")

        if avg >= STRONG_THRESHOLD:
            tier = "STRONG"
        elif avg >= WEAK_THRESHOLD:
            tier = "OK"
        else:
            tier = "WEAK"

        health[domain] = {
            "avg": round(avg, 2),
            "recent_avg": round(recent_avg, 2),
            "trend": trend,
            "n": len(scores),
            "tier": tier,
            "computed_at": now_iso()
        }
    return health

def load_queue() -> list:
    if not QUEUE_FILE.exists():
        return []
    try:
        return json.loads(QUEUE_FILE.read_text())
    except:
        return []

def save_queue(tasks: list):
    QUEUE_FILE.write_text(json.dumps(tasks, indent=2))

def domain_for_task(task: dict) -> str:
    """Map task instrument/label to a canonical domain."""
    instrument = task.get("instrument", "").upper()
    label = task.get("label", "").lower()
    source = task.get("source", "").lower()
    if any(x in instrument for x in ["TLT", "TMF", "RATES", "BOND"]):
        return "treasury-bonds"
    if "macroalf" in label or "fedwatch" in label or "treasury auction" in label:
        return "treasury-bonds"
    if any(x in instrument for x in ["XAUUSD", "GLD", "XAGUSD", "SLV", "GDX", "SILJ", "SPX", "IBIT", "BTC", "IREN", "BITF"]):
        return "camel-finance"
    if "macro" in instrument.lower():
        return "treasury-bonds"
    return "general"

def queue_task(tasks: list, label: str, prompt: str, priority: int, instrument: str, source: str):
    """Add task if not already present."""
    if any(t.get("label") == label for t in tasks):
        return False
    tasks.append({
        "id": f"qw_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}",
        "priority": priority,
        "task_type": "research",
        "instrument": instrument,
        "label": label,
        "description": prompt,
        "prompt_template": prompt,
        "source": source,
        "context_refs": [],
        "created_at": now_iso(),
        "status": "pending",
        "completed_at": None,
        "output_path": None
    })
    return True

def write_journal(entry: dict):
    entry["timestamp"] = now_iso()
    with open(JOURNAL_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")

def main():
    log("=" * 60)
    log("zeke-quality-weights.py — Block 6")
    log("=" * 60)

    # 1. Load and aggregate scores
    domain_scores = load_scores()
    if not domain_scores:
        log("No scores found. Run zeke-quality-scorer.py first.")
        return

    # 2. Compute health per domain
    health = compute_health(domain_scores)
    log(f"Domain health computed ({len(health)} domains with {MIN_SAMPLES}+ samples):")
    for domain, h in sorted(health.items(), key=lambda x: x[1]["avg"]):
        arrow = {"up": "↑", "down": "↓", "flat": "→"}[h["trend"]]
        log(f"  [{h['tier']:<6}] {domain:<25} avg={h['avg']:.2f} recent={h['recent_avg']:.2f} {arrow}  n={h['n']}")

    # 3. Save domain health file for dashboard
    HEALTH_FILE.write_text(json.dumps({"computed_at": now_iso(), "domains": health}, indent=2))
    log(f"Saved domain health → {HEALTH_FILE.name}")

    # 4. Load queue, apply adjustments
    tasks = load_queue()
    pending = [t for t in tasks if t.get("status") == "pending"]
    log(f"Queue: {len(tasks)} total, {len(pending)} pending")

    boosts = 0
    remediation_added = 0
    audit_added = 0

    for domain, h in health.items():
        tier = h["tier"]
        trend = h["trend"]

        # STRONG domain: boost pending tasks mapped to this domain
        if tier == "STRONG":
            for task in pending:
                if domain_for_task(task) == domain:
                    old_p = task["priority"]
                    task["priority"] = min(old_p + BOOST_AMOUNT, MAX_PRIORITY)
                    if task["priority"] != old_p:
                        boosts += 1
                        log(f"  BOOST {domain}: task '{task['label'][:40]}' {old_p}→{task['priority']}")

        # WEAK domain: queue remediation task
        if tier == "WEAK":
            label = f"Quality remediation: {domain} avg={h['avg']:.2f} — improve source quality"
            prompt = (
                f"Domain '{domain}' has an average quality score of {h['avg']:.2f}/5.0 "
                f"(n={h['n']}, trend={h['trend']}). This is below the acceptable threshold of {WEAK_THRESHOLD}. "
                f"Analyze: (1) What types of findings is this domain producing that score poorly? "
                f"(2) What are better sources or query strategies for this domain? "
                f"(3) Write 2-3 example high-quality findings (score 4-5) that this domain SHOULD be producing. "
                f"(4) Output specific recommendations to improve the research job prompt for this domain."
            )
            added = queue_task(tasks, label, prompt, priority=7, instrument=domain.upper(), source="quality-weights")
            if added:
                remediation_added += 1
                log(f"  REMEDIATION queued: {domain} (avg={h['avg']:.2f})")

        # DECLINING domain (OK tier but trending down): queue audit task
        if tier == "OK" and trend == "down":
            label = f"Quality audit: {domain} declining ({h['avg']:.2f}→{h['recent_avg']:.2f})"
            prompt = (
                f"Domain '{domain}' quality is declining: overall avg={h['avg']:.2f}, "
                f"recent avg={h['recent_avg']:.2f} (last {max(5,h['n']//5)} entries). "
                f"Diagnose: (1) Are recent entries becoming repetitive or lower-value? "
                f"(2) Has the source material quality changed? "
                f"(3) What specific changes to the research approach would reverse the decline? "
                f"Output 3 concrete improvements."
            )
            added = queue_task(tasks, label, prompt, priority=6, instrument=domain.upper(), source="quality-weights")
            if added:
                audit_added += 1
                log(f"  AUDIT queued: {domain} ({h['avg']:.2f}↓{h['recent_avg']:.2f})")

    # 5. Save updated queue
    save_queue(tasks)
    log(f"Queue updated: {boosts} boosts, {remediation_added} remediation tasks, {audit_added} audit tasks")

    # 6. Journal the run
    write_journal({
        "session_id": "quality-weights-auto",
        "type": "QUALITY_WEIGHTS_RUN",
        "summary": f"Block 6 quality-weights run: {len(health)} domains evaluated",
        "domain_health": {d: {"tier": h["tier"], "avg": h["avg"], "trend": h["trend"]} for d, h in health.items()},
        "actions": {"boosts": boosts, "remediation_tasks": remediation_added, "audit_tasks": audit_added}
    })
    log("Journal updated.")
    log("=" * 60)

if __name__ == "__main__":
    main()
