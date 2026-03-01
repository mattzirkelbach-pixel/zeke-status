#!/usr/bin/env python3
"""
zeke-memory-distill.py — Nightly operational memory distillation (Block 8)
Reads OpenClaw daily .md files + session journal + anti-patterns.
Distills into claude-strategic-context.md via Haiku.
Run nightly at 4:45am (before synthesis).
"""

import json, datetime, subprocess, glob, os
from pathlib import Path

HOME = Path.home()
MEM = HOME / ".openclaw/workspace/memory"
OUTPUT = MEM / "claude-strategic-context.md"
BACKUP_DIR = HOME / "zeke-backups/memory-distill"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

def log(msg):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")

def backup_existing():
    if OUTPUT.exists():
        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = BACKUP_DIR / f"claude-strategic-context.{ts}.md"
        backup.write_text(OUTPUT.read_text())
        log(f"Backed up → {backup.name}")

def collect_daily_mds(days_back=30):
    cutoff = datetime.date.today() - datetime.timedelta(days=days_back)
    files = sorted(MEM.glob("2026-*.md"))
    recent = []
    for f in files:
        try:
            parts = f.stem.split("-")
            file_date = datetime.date(int(parts[0]), int(parts[1]), int(parts[2]))
            if file_date >= cutoff:
                recent.append((file_date, f))
        except (ValueError, IndexError):
            pass
    return recent

def collect_journal(days_back=30):
    journal = MEM / "session-journal.jsonl"
    if not journal.exists():
        return []
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days_back)
    entries = []
    for line in journal.read_text().strip().split("\n"):
        try:
            e = json.loads(line)
            ts_str = e.get("timestamp", "")
            if ts_str:
                ts = datetime.datetime.fromisoformat(ts_str)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=datetime.timezone.utc)
                if ts >= cutoff:
                    entries.append(e)
        except:
            pass
    return entries

def collect_anti_patterns():
    ap = MEM / "anti-patterns.md"
    return ap.read_text()[:3000] if ap.exists() else ""

def collect_state():
    ss = MEM / "claude-session-state.json"
    if not ss.exists():
        return {}
    try:
        return json.loads(ss.read_text())
    except:
        return {}

def find_claude():
    paths = sorted(glob.glob(str(HOME / "Library/Application Support/Claude/claude-code/*/claude")))
    return paths[-1] if paths else None

def main():
    log("=" * 60)
    log("zeke-memory-distill.py — Block 8")
    log("=" * 60)

    daily_mds = collect_daily_mds(days_back=30)
    journal = collect_journal(days_back=30)
    anti_patterns = collect_anti_patterns()
    state = collect_state()

    log(f"Sources: {len(daily_mds)} daily .md files | {len(journal)} journal entries")

    if not daily_mds and not journal:
        log("No source material — exiting")
        return

    backup_existing()

    # Build daily md text
    daily_text = ""
    for date, fpath in daily_mds[-14:]:
        content = fpath.read_text()[:1500]
        daily_text += f"\n### {date} ({fpath.name})\n{content}\n"

    # Build journal text
    journal_text = ""
    for e in journal[-10:]:
        journal_text += f"\n### {e.get('timestamp','')[:16]} — {e.get('type','')}\n"
        journal_text += f"Summary: {e.get('summary','')}\n"
        done = e.get('completed', e.get('completed_today', []))
        if done:
            journal_text += f"Done: {', '.join(str(x) for x in done[:4])}\n"
        if e.get('next_session'):
            journal_text += f"Next: {str(e.get('next_session',''))[:150]}\n"

    blocks = state.get('blocks', {})
    state_text = f"""Blocks complete: {blocks.get('complete', [])}
Next: Block {blocks.get('next')} — {blocks.get('block7_summary', '')}
Feed entries: {state.get('feed', {}).get('total', '?')}
Queue pending: {state.get('queue', {}).get('pending', '?')}
Approvals pending: {state.get('pending_approvals', {}).get('pending', 0)}
Last session: {state.get('last_journal', {}).get('summary', '?')}"""

    prompt = f"""INSTRUCTION: Output ONLY raw markdown. No preamble, no commentary, no "I've synthesized" wrapper. Start directly with the markdown heading. This output will be written verbatim to a file.

You are a memory distillation engine for Zeke, an autonomous trading intelligence system.
Synthesize the sources below into claude-strategic-context.md content.
Requirements: 800-1200 words, dense operational markdown, machine-optimized for fast loading.

Output these sections in order:
# Zeke Strategic Context
Last distilled: {datetime.date.today()}

## System Architecture
## Active Positions  
## Trading Rules
## Autonomous Schedule
## Critical Anti-Patterns
## What's Next

Rules: dense facts, no narrative, compress anti-patterns to rule+consequence only.

=== CURRENT STATE ===
{state_text}

=== OPENCLAW DAILY FILES (last 14 days) ===
{daily_text or "None in range."}

=== SESSION JOURNAL ===
{journal_text or "None in range."}

=== ANTI-PATTERNS ===
{anti_patterns or "None."}

Write the updated claude-strategic-context.md now:"""

    claude_bin = find_claude()
    if not claude_bin:
        log("ERROR: claude binary not found")
        return

    log(f"Distilling via Haiku... (prompt: {len(prompt):,} chars)")
    result = subprocess.run(
        [claude_bin, "-p", "--model", "claude-haiku-4-5-20251001", prompt],
        capture_output=True, text=True, timeout=120,
        env={**os.environ, "HOME": str(HOME)}
    )

    if result.returncode != 0 or not result.stdout.strip() or len(result.stdout.strip()) < 300:
        log(f"Distillation failed (rc={result.returncode}, output={len(result.stdout)} chars)")
        if result.stderr:
            log(f"STDERR: {result.stderr[:300]}")
        return

    content = result.stdout.strip()
    OUTPUT.write_text(content)
    log(f"Written → {OUTPUT.name} ({len(content):,} chars)")

    # Journal entry
    journal_file = MEM / "session-journal.jsonl"
    entry = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "session_id": f"memory-distill-{datetime.date.today()}",
        "type": "MEMORY_DISTILL",
        "summary": f"Distillation complete. {len(daily_mds)} daily files + {len(journal)} journal entries → strategic-context updated.",
        "output_chars": len(content)
    }
    with open(journal_file, "a") as f:
        f.write(json.dumps(entry) + "\n")

    # Regenerate session state
    subprocess.run(["python3", str(HOME / "zeke-session-state.py")], capture_output=True)
    log("Session state regenerated. Done.")

if __name__ == "__main__":
    main()
