#!/usr/bin/env python3
"""
OVERNIGHT SYNTHESIS — qwen3-32b
================================
Reads thesis ledger + recent transcripts, synthesizes cross-instrument
view via local 32B model. $0 cost. Writes to learning-feed + synthesis file.

Run: python3 ~/camel-overnight-synthesis.py
"""
import json, time, datetime, subprocess, sys
from pathlib import Path

HOME = Path.home()
LEDGER_PATH = HOME / ".openclaw/workspace/memory/camel-thesis-ledger.json"
TRANSCRIPT_DIR = HOME / ".openclaw/workspace/memory/camel-transcripts"
FEED = HOME / ".openclaw/workspace/memory/learning-feed.jsonl"
SYNTHESIS_OUT = HOME / ".openclaw/workspace/memory/camel-synthesis-latest.md"
LOCK_FILE = Path("/tmp/spark-active.lock")
OLLAMA_MODEL = "qwen3-32b-32k:latest"

def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def acquire_spark(owner="camel-synthesis", timeout=600):
    import os
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not LOCK_FILE.exists():
            LOCK_FILE.write_text(json.dumps({
                "owner": owner, "pid": os.getpid(),
                "acquired_at": time.time(),
                "acquired_iso": now_iso()
            }))
            return True
        # check staleness
        try:
            lock = json.loads(LOCK_FILE.read_text())
            pid = lock.get("pid")
            age = time.time() - lock.get("acquired_at", 0)
            try:
                os.kill(pid, 0)
                if age > 600:
                    print(f"  Evicting stale lock (age={age:.0f}s, pid={pid})")
                    LOCK_FILE.unlink()
                    continue
            except (ProcessLookupError, TypeError):
                print(f"  Evicting dead-process lock (pid={pid})")
                LOCK_FILE.unlink()
                continue
        except Exception:
            LOCK_FILE.unlink(missing_ok=True)
            continue
        print(f"  Lock held by {lock.get('owner','?')} (pid={lock.get('pid','?')} age={time.time()-lock.get('acquired_at',0):.0f}s) — waiting...")
        time.sleep(10)
    return False

def release_spark():
    LOCK_FILE.unlink(missing_ok=True)

def call_ollama(prompt, system=None, timeout=60, retries=2):
    """
    Stream qwen3-32b response to avoid single-response urllib timeout.
    timeout=60 applies per-chunk read (heartbeat), not total generation time.
    keep_alive=2h prevents model eviction mid-run.
    Retries on connection failure with 15s backoff.
    """
    import urllib.request, urllib.error, socket
    OLLAMA_URL = "http://10.0.0.143:11434/api/generate"
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": True,
        "keep_alive": "2h",
        "options": {"temperature": 0.3, "num_predict": 4096, "num_ctx": 32768}
    }
    if system:
        payload["system"] = system

    for attempt in range(retries + 1):
        if attempt > 0:
            print(f"  Retry {attempt}/{retries} after 15s...")
            time.sleep(15)
        try:
            data = json.dumps(payload).encode()
            req = urllib.request.Request(OLLAMA_URL, data=data,
                                          headers={"Content-Type": "application/json"})
            chunks = []
            total_tokens = 0
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                while True:
                    line = resp.readline()
                    if not line:
                        break
                    try:
                        chunk = json.loads(line.decode())
                        token = chunk.get("response", "")
                        chunks.append(token)
                        total_tokens += 1
                        if total_tokens % 300 == 0:
                            print(f"  ...{total_tokens} tokens", flush=True)
                        if chunk.get("done"):
                            dur = chunk.get("eval_duration", 0) / 1e9
                            tps = chunk.get("eval_count", 0) / max(dur, 1)
                            print(f"  Done: {chunk.get('eval_count',0)} tokens in {dur:.1f}s ({tps:.1f} tok/s)")
                            break
                    except json.JSONDecodeError:
                        continue
            result = "".join(chunks)
            if len(result) > 100:
                return result
            print(f"  Short response ({len(result)} chars) — retrying")
        except (urllib.error.URLError, socket.timeout, OSError) as e:
            print(f"  Ollama error attempt {attempt+1}: {e}")
            if attempt == retries:
                return f"ERROR: {e}"
    return "ERROR: all retries exhausted"

def build_ledger_summary(ledger):
    instruments = ledger.get("instruments", {})
    lines = []
    # Sort by based_on desc
    ranked = []
    for name, data in instruments.items():
        active = data.get("active_thesis") or {}
        based_on = active.get("based_on", 0)
        if based_on >= 2:
            ranked.append((name, data, active, based_on))
    ranked.sort(key=lambda x: x[3], reverse=True)

    for name, data, active, based_on in ranked:
        direction = active.get("direction", "?")
        strength = active.get("strength", 0)
        last_obs = active.get("last_observation", "")[:120]
        last_vid = active.get("last_video", "")
        lines.append(f"- {name}: {direction.upper()} (strength={strength:.2f}, n={based_on}) — \"{last_obs}\" [{last_vid}]")

    return "\n".join(lines)

def get_recent_transcripts(n=8):
    """Get the n most recently analyzed transcripts for context."""
    files = sorted(TRANSCRIPT_DIR.glob("*.json"),
                   key=lambda f: f.stat().st_mtime, reverse=True)[:n]
    summaries = []
    for f in files:
        try:
            doc = json.loads(f.read_text())
            analysis = doc.get("analysis", {})
            title = doc.get("title", "unknown")
            date = doc.get("date", "?")
            bias = analysis.get("overall_bias", analysis.get("bias", "?"))
            summary = analysis.get("summary", "")[:200]
            instruments = analysis.get("instruments_discussed",
                          analysis.get("instruments", []))[:6]
            summaries.append(f"### {title} ({date})\nBias: {bias} | Instruments: {', '.join(instruments)}\n{summary}")
        except Exception:
            continue
    return "\n\n".join(summaries)

def run_cluster_pass(pass_num, label, prompt, system_prompt, prior_context=""):
    """Run one cluster synthesis pass. Returns result string or ERROR."""
    full_prompt = prompt
    if prior_context:
        full_prompt = f"=== PRIOR CLUSTER SYNTHESIS ===\n{prior_context[:3000]}\n=== END PRIOR ===\n\n{prompt}"
    print(f"[SYNTHESIS] Pass {pass_num}/3: {label} (~{len(full_prompt)} chars)")
    result = call_ollama(full_prompt, system=system_prompt, timeout=300)
    if result.startswith("ERROR"):
        print(f"[SYNTHESIS] Pass {pass_num} failed: {result}")
    else:
        print(f"[SYNTHESIS] Pass {pass_num} done ({len(result)} chars)")
    return result


def main():
    print(f"[SYNTHESIS] Starting — {now_iso()}")

    # Load ledger
    ledger = json.loads(LEDGER_PATH.read_text())
    ledger_summary = build_ledger_summary(ledger)
    recent_transcripts = get_recent_transcripts(8)

    conflicts = ledger.get("conflicts", [])
    conflict_summary = ""
    if conflicts:
        recent_conflicts = conflicts[-10:]
        conflict_lines = []
        for c in recent_conflicts:
            conflict_lines.append(
                f"- {c.get('instrument','?')}: was {c.get('prev_direction','?')} → now {c.get('new_direction','?')} ({c.get('video_title','?')})"
            )
        conflict_summary = "RECENT THESIS CONFLICTS (direction changes):\n" + "\n".join(conflict_lines)

    print(f"[SYNTHESIS] Ledger: {len(ledger.get('instruments',{}))} instruments | Conflicts: {len(conflicts)}")
    print(f"[SYNTHESIS] Waiting for Spark lock...")

    if not acquire_spark("camel-synthesis", timeout=600):
        print("[SYNTHESIS] Could not acquire Spark lock — aborting")
        sys.exit(1)

    print(f"[SYNTHESIS] Lock acquired — running qwen3-32b synthesis")

    try:
        system_prompt = """You are Zeke, a financial intelligence system specializing in cycle theory and macro trading.
You analyze Camel Finance's research to extract actionable intelligence for a concentrated macro portfolio.
Be direct, specific, and quantitative where possible. No hedging language. Focus on what matters for trade timing."""

        shared_header = f"""You have analyzed {len(list(TRANSCRIPT_DIR.glob('*.json')))} Camel Finance videos.

## THESIS LEDGER STATE
{ledger_summary}

{conflict_summary}

## RECENT VIDEO SUMMARIES (last 8)
{recent_transcripts}
"""

        # === PASS 1: Gold/Silver cluster ===
        pass1_prompt = shared_header + """
## CLUSTER: GOLD / SILVER / MINERS

Analyze only this cluster. Cover:
1. GOLD CYCLE POSITION: What week of the 22-26 week cycle? Current daily cycle day?
2. SILVER THESIS: Strength of conviction, "VIOLENT move" timing — when and what triggers it?
3. MINERS (GDX/SILJ): Are they leading or lagging gold? Confirmation status?
4. GLD ENTRY TIMING: Specific criteria for tranche 2 entry — what must happen first?
5. KEY LEVELS: Support/resistance to watch. Invalidation levels.
6. CONVICTION SCORE: 1-10 for gold bull thesis. Reasons for any discount.

Portfolio: GLD Dec26 $470C (2x) + $500C (1x), SILJ $30C Jan27 (25x), GDX $95C Dec26 (10x).
Be specific. Reference video titles where relevant."""

        pass1 = run_cluster_pass(1, "Gold/Silver/Miners", pass1_prompt, system_prompt)
        if pass1.startswith("ERROR"):
            sys.exit(1)

        # === PASS 2: Rates/Bonds cluster (fed with Pass 1 context) ===
        pass2_prompt = shared_header + """
## CLUSTER: RATES / BONDS / MACRO

Analyze only this cluster. Cover:
1. FED TRAJECTORY: What is Camel's read on rate cut timing? Next cut probability?
2. 10Y YIELD: Current level vs key thresholds (4.0%, 4.4%). Direction?
3. TLT THESIS: Does Camel support the Treasury bull trade? Timing for duration bid?
4. DXY: Dollar cycle — bull or bear? Implications for gold and bonds?
5. MACRO REGIME: Recession risk, credit conditions, risk-on vs risk-off signal?
6. ALIGNMENT: Does the rates thesis support or conflict with the gold thesis from Pass 1?

Portfolio: TLT LEAPS Jan27 ($90C 650x, $95C 300x, $101C 3150x, 1868 shares @ $88.36), TMF $50C Jan27 (575x).
Be specific. Reference actual yield levels and Fed calendar."""

        pass2 = run_cluster_pass(2, "Rates/Bonds/Macro", pass2_prompt, system_prompt, prior_context=pass1)
        if pass2.startswith("ERROR"):
            print("[SYNTHESIS] Pass 2 failed — continuing with pass 1 only")
            pass2 = ""

        # === PASS 3: Crypto + Cross-cluster alignment ===
        pass3_prompt = shared_header + """
## CLUSTER: CRYPTO + CROSS-CLUSTER PORTFOLIO ALIGNMENT

Part A — Crypto:
1. BTC CYCLE: What cycle week/phase? Is Camel bullish or cautious?
2. IBIT $48C Jun26: Needs BTC >$85K by June. Is this achievable on current thesis?
3. IREN $50C May26: AI/data center angle — any catalysts in Camel's macro view?
4. MINERS (crypto): BITF $2C May26 — relevant signals?

Part B — Cross-cluster alignment:
5. PORTFOLIO ALIGNMENT SCORE: 1-10 overall. How well do Gold + Rates + Crypto clusters align?
6. BIGGEST RISK: What single development would most damage the portfolio?
7. ACTIONABLE SIGNALS: Top 3 triggers to watch this week across all positions.

8. NEXT_TASKS_JSON: Output a JSON array of 3-5 follow-up tasks on a single line:
NEXT_TASKS_JSON:[{"task":"...","domain":"camel-finance","priority":7,"rationale":"..."}]
Priority: 9=time-critical, 7=post-synthesis, 5=routine, 3=background."""

        prior_both = (pass1[:1500] + "\n\n---\n\n" + pass2[:1500]) if pass2 else pass1[:2000]
        pass3 = run_cluster_pass(3, "Crypto + Cross-cluster", pass3_prompt, system_prompt, prior_context=prior_both)
        if pass3.startswith("ERROR"):
            print("[SYNTHESIS] Pass 3 failed — using passes 1+2 only")
            pass3 = ""

        # Combine all passes into final synthesis
        result = f"## CLUSTER 1: Gold / Silver / Miners\n\n{pass1}\n\n---\n\n## CLUSTER 2: Rates / Bonds / Macro\n\n{pass2}\n\n---\n\n## CLUSTER 3: Crypto + Portfolio Alignment\n\n{pass3}"

        # Write synthesis file
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M ET")
        output = f"# Camel Finance Synthesis (3-Cluster) — {ts}\n\n"
        output += f"*qwen3-32b | {len(list(TRANSCRIPT_DIR.glob('*.json')))} videos | {len(ledger.get('instruments',{}))} instruments*\n\n"
        output += result

        SYNTHESIS_OUT.write_text(output)
        print(f"[SYNTHESIS] Written to {SYNTHESIS_OUT}")

        # --- Parse NEXT_TASKS_JSON from pass3 (cross-cluster alignment pass) ---
        parse_source = pass3 if pass3 else result
        next_tasks = []
        try:
            for line in parse_source.split("\n"):
                if line.strip().startswith("NEXT_TASKS_JSON:"):
                    raw = line.strip()[len("NEXT_TASKS_JSON:"):].strip()
                    next_tasks = json.loads(raw)
                    print(f"[SYNTHESIS] Parsed {len(next_tasks)} next tasks from synthesis")
                    break
        except Exception as e:
            print(f"[SYNTHESIS] Could not parse NEXT_TASKS_JSON: {e}")

        # Write next tasks to queue
        if next_tasks:
            queue_path = HOME / ".openclaw/workspace/memory/spark-work-queue.jsonl"
            existing = json.loads(queue_path.read_text()) if queue_path.exists() else []
            existing_labels = {t.get("label","") for t in existing}
            added = 0
            for task in next_tasks:
                label = task.get("task","")[:80]
                if label in existing_labels:
                    print(f"[SYNTHESIS] Skipping duplicate task: {label[:50]}")
                    continue
                queue_entry = {
                    "id": f"synthesis_{now_iso().replace(':','').replace('-','')[:15]}_{added}",
                    "priority": task.get("priority", 6),
                    "task_type": "research",
                    "domain": task.get("domain", "camel-finance"),
                    "label": label,
                    "prompt": label,
                    "rationale": task.get("rationale",""),
                    "source": "camel-overnight-synthesis",
                    "context_refs": ["camel-synthesis-latest.md", "camel-thesis-ledger.json"],
                    "created_at": now_iso(),
                    "status": "pending",
                    "completed_at": None,
                    "output_path": None
                }
                existing.append(queue_entry)
                existing_labels.add(label)
                added += 1
            if added:
                queue_path.write_text(json.dumps(existing, indent=2))
                print(f"[SYNTHESIS] Wrote {added} new tasks to queue")

        # --- Write to feed (domain-tagged, strip NEXT_TASKS_JSON line) ---
        clean_result = "\n".join(
            l for l in result.split("\n")
            if not l.strip().startswith("NEXT_TASKS_JSON:")
        )
        feed_entry = {
            "timestamp": now_iso(),
            "topic": "camel-synthesis-overnight",
            "domain": "camel-finance",
            "finding": clean_result[:500],
            "source": "qwen3-32b-synthesis",
            "full_path": str(SYNTHESIS_OUT),
            "instruments_covered": len(ledger.get("instruments", {})),
            "videos_analyzed": len(list(TRANSCRIPT_DIR.glob("*.json"))),
            "next_tasks_generated": len(next_tasks)
        }
        with open(FEED, "a") as f:
            f.write(json.dumps(feed_entry) + "\n")

        print(f"[SYNTHESIS] Feed entry written (domain=camel-finance, {len(next_tasks)} tasks queued)")
        print(f"\n{'='*60}")
        print(result[:1500])
        print(f"{'='*60}")
        print(f"\n[SYNTHESIS] Complete — {now_iso()}")

    finally:
        release_spark()
        time.sleep(5)

if __name__ == "__main__":
    main()
