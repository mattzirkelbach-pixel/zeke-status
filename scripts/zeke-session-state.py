#!/usr/bin/env python3
"""
zeke-session-state.py — Fast context loader for Claude sessions
================================================================
Writes a compact machine-readable state file at the end of sessions.
Claude reads this FIRST instead of reconstructing from logs/journals.

Output: ~/.openclaw/workspace/memory/claude-session-state.json
Target size: <3KB — readable in one tool call, no reconstruction needed.

Usage:
  python3 ~/zeke-session-state.py          # generate state snapshot
  python3 ~/zeke-session-state.py --read   # print current state (human readable)

Run at END of every Claude session. Also runs nightly via LaunchAgent.
"""

import json
import datetime
import subprocess
from pathlib import Path

HOME = Path.home()
MEM = HOME / ".openclaw/workspace/memory"
STATE_FILE = MEM / "claude-session-state.json"
QUEUE_FILE = MEM / "spark-work-queue.jsonl"
FEED_FILE = MEM / "learning-feed.jsonl"
JOURNAL_FILE = MEM / "session-journal.jsonl"
HEALTH_FILE = MEM / "quality-domain-health.json"
TRADE_PLAN_FILE = MEM / "trade-plan.md"  # if exists
ANTI_PATTERNS_FILE = MEM / "anti-patterns.md"

def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def feed_stats():
    try:
        from collections import Counter
        c = Counter()
        with open(FEED_FILE) as f:
            lines = f.readlines()
        for line in lines:
            try:
                d = json.loads(line)
                t = d.get("topic", "unknown").lower()
                if "camel" in t or "cycle" in t:
                    c["camel-finance"] += 1
                elif "treasury" in t or "bond" in t or "macroalf" in t or "fedwatch" in t:
                    c["treasury-bonds"] += 1
                elif "longevity" in t:
                    c["longevity"] += 1
                elif "ai-agent" in t or "tool-call" in t:
                    c["ai-agents"] += 1
                elif "self-improve" in t:
                    c["self-improvement"] += 1
                elif "compound-synth" in t:
                    c["compound-synthesis"] += 1
                else:
                    c["other"] += 1
            except:
                pass
        return {"total": len(lines), "by_domain": dict(c.most_common())}
    except Exception as e:
        return {"error": str(e)}

def queue_stats():
    try:
        tasks = json.loads(QUEUE_FILE.read_text())
        pending = [t for t in tasks if t.get("status") == "pending"]
        done = [t for t in tasks if t.get("status") == "done"]
        top_pending = sorted(pending, key=lambda x: -x.get("priority", 0))[:3]
        return {
            "total": len(tasks),
            "pending": len(pending),
            "done": len(done),
            "top_pending": [
                {"p": t.get("priority"), "label": t.get("label", "")[:50], "inst": t.get("instrument", "")}
                for t in top_pending
            ]
        }
    except Exception as e:
        return {"error": str(e)}

def domain_health():
    try:
        d = json.loads(HEALTH_FILE.read_text())
        domains = d.get("domains", {})
        return {k: {"tier": v["tier"], "avg": v["avg"], "trend": v["trend"]}
                for k, v in domains.items()}
    except:
        return {}

def latest_journal():
    try:
        lines = JOURNAL_FILE.read_text().strip().split("\n")
        last = json.loads(lines[-1])
        return {
            "type": last.get("type"),
            "ts": last.get("timestamp", "")[:16],
            "summary": last.get("summary", "")[:120],
            "next_session": last.get("next_session", "")[:120]
        }
    except Exception as e:
        return {"error": str(e)}

def launchagent_summary():
    """Count active launchagents."""
    try:
        result = subprocess.run(
            ["launchctl", "list"],
            capture_output=True, text=True
        )
        zeke_agents = [l for l in result.stdout.split("\n") if "zeke" in l.lower()]
        return len(zeke_agents)
    except:
        return -1

def anti_pattern_summary():
    """Extract key anti-patterns as bullet list."""
    try:
        text = ANTI_PATTERNS_FILE.read_text()
        # Extract lines starting with - or *
        patterns = [l.strip() for l in text.split("\n")
                    if l.strip().startswith(("-", "*", "•")) and len(l.strip()) > 10]
        return patterns[:8]  # top 8 most recent anti-patterns
    except:
        return []

def system_health():
    """Quick health check without calling MCP."""
    try:
        health_file = MEM / "system-health.json"
        if health_file.exists():
            d = json.loads(health_file.read_text())
            return {"feed": d.get("feed_count"), "spark": d.get("spark_status"), "ts": d.get("updated_at", "")[:16]}
    except:
        pass
    return {}

def build_state():
    state = {
        "generated_at": now_iso(),
        "version": 3,

        # === BLOCKS COMPLETE (recursive autonomy spec) ===
        "blocks": {
            "complete": [1, 2, 3, 4, 5, 6],
            "next": 7,
            "block7_summary": "pending-approval.json + Cowork wiring for human-in-the-loop decisions"
        },

        # === SYSTEM STATE ===
        "feed": feed_stats(),
        "queue": queue_stats(),
        "domain_health": domain_health(),
        "launchagents_active": launchagent_summary(),
        "system": system_health(),

        # === LAST SESSION ===
        "last_journal": latest_journal(),

        # === CAMEL FINANCE CORPUS ===
        "camel_corpus": {
            "transcripts_processed": 28,
            "instruments_in_ledger": 75,
            "key_theses": {
                "XAUUSD": {"direction": "bullish", "strength": 0.962, "based_on": 10},
                "XAGUSD": {"direction": "bullish", "strength": 0.975, "based_on": 6},
                "TLT": {"direction": "bullish", "strength": 0.956, "based_on": 6},
                "SPX": {"direction": "bearish", "strength": 0.75, "based_on": 18},
                "BTC": {"direction": "bearish", "strength": 0.638, "based_on": 17},
            },
            "note": "Thesis ledger in camel-thesis-ledger.json. Corpus = YT transcripts (28) + course chapters (cycle theory PDF). Quality avg 2.8 for camel-finance-cycle-analysis = verbatim chunks not synthesized findings."
        },

        # === ACTIVE POSITIONS (snapshot — verify with get_portfolio_state) ===
        "positions_snapshot": {
            "note": "Stale — always call get_portfolio_state for live data",
            "GLD_calls": "Dec 2026 $470C 2x $500C 1x (filled 2/24)",
            "TLT": "650x $90C + 300x $95C + 3150x $101C exp 1/15/27 + ~1868sh avg $88.36",
            "IBIT": "$48C Jun2026 401k $177.5K basis — needs BTC >$85K",
            "IREN": "$50C May2026 401k $152K basis — theta cliff mid-April",
            "BITF": "$2C 5/15/26 100x",
            "SILJ": "$30C 25x 401k",
            "GDX": "$95C 10x 401k"
        },

        # === CRITICAL RULES (anti-patterns compressed) ===
        "critical_rules": [
            "TASK SIZING: >30min or >3 components = split. One piece, commit, journal, repeat.",
            "MEMORY: Update journal + anti-patterns + context files after structural changes.",
            "NO FOMO: No SLV entry without daily cycle low confirmation (swing low + SMA reclaim + day 18+).",
            "SECTION 1256: GLD/SLV options in E*TRADE taxable. GDX/SILJ/miners in 401k only.",
            "EVERY new research = queue task, NOT cron. Synthesis must generate next_tasks.",
            "Spark <20% utilized = system failure.",
            "Pull data before answering. No guessing prices or positions.",
            "Camel finance corpus: INTENT = extract cycle theory + conviction scoring, not verbatim chunks.",
            "Quality scorer topic normalization critical — map aliases to canonical domains.",
            "Feed is append-only. Never overwrite. Guardian enforces this."
        ],

        # === TONIGHT'S AUTONOMOUS SCHEDULE ===
        "autonomous_schedule": {
            "05:00": "3-cluster nightly synthesis (Gold/Silver → Rates/Bonds → Crypto+Alignment)",
            "05:30": "RAG embed (synthesis → ChromaDB)",
            "06:15": "Financial ingestion (MacroAlf RSS, TreasuryDirect, FedWatch/Yahoo via Spark)",
            "07:00": "Quality-weights run (domain health → queue priority adjustments)"
        },

        # === HOW TO START NEXT SESSION ===
        "session_start_protocol": [
            "1. Read this file FIRST (claude-session-state.json) — already done if you're reading this",
            "2. Call get_latest_prices + get_portfolio_state ONLY if doing trade analysis",
            "3. Call get_active_signals ONLY if evaluating entry/exit triggers",
            "4. Do NOT read scheduler logs, feed files, or briefing docs unless specifically needed",
            "5. Do NOT call get_system_health unless troubleshooting",
            "6. Jump to the task. Context is loaded."
        ]
    }
    return state

def main():
    import sys
    state = build_state()
    STATE_FILE.write_text(json.dumps(state, indent=2))
    size = STATE_FILE.stat().st_size
    print(f"Session state written → {STATE_FILE.name} ({size:,} bytes)")
    print(f"  Feed: {state['feed'].get('total')} entries")
    print(f"  Queue: {state['queue'].get('pending')} pending / {state['queue'].get('total')} total")
    print(f"  LaunchAgents: {state['launchagents_active']}")
    print(f"  Last session: {state['last_journal'].get('summary','?')[:70]}")

    if "--read" in sys.argv:
        print("\n=== FULL STATE ===")
        print(json.dumps(state, indent=2))

if __name__ == "__main__":
    main()
