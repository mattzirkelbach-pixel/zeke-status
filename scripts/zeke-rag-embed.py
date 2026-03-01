#!/usr/bin/env python3
"""
zeke-rag-embed.py — Block 3: RAG Feedback Loop (Embed Side)
============================================================
Embeds Zeke's own synthesis outputs, feed entries, and thesis ledger
back into ChromaDB so every subsequent synthesis/analysis starts with
"what did I conclude about this last time?"

This is what separates accumulating information from compounding intelligence.

Runtime: ~/zeke-rag-venv/bin/python3 (Python 3.13, ChromaDB 1.x compatible)
Embedding: ollama nomic-embed-text (local, $0 cost)
Storage: ~/.openclaw/chroma (persistent PersistentClient)

Called by:
  - LaunchAgent: com.zeke.rag-embed (daily at 5:30am, after synthesis)
  - spark-work-queue.py: task_type="embed"
  - Manual: python3 ~/zeke-rag-embed.py [--full-backfill]

Collections:
  synthesis_outputs   — daily synthesis + camel synthesis markdown files
  feed_entries        — learning-feed.jsonl entries (financial topics only)
  thesis_ledger       — camel finance thesis entries per video
"""

import sys
import json
import hashlib
import argparse
import requests
import traceback
from pathlib import Path
from datetime import datetime, timezone, timedelta

# ── Paths ──
HOME = Path.home()
CHROMA_PATH = HOME / ".openclaw/chroma"
MEMORY_PATH = HOME / ".openclaw/workspace/memory"
FEED_PATH = MEMORY_PATH / "learning-feed.jsonl"
THESIS_PATH = HOME / "zeke-portfolio/data/thesis-ledger.jsonl"
SYNTHESIS_PATHS = [
    MEMORY_PATH / "daily-synthesis.md",
    MEMORY_PATH / "camel-synthesis-latest.md",
    MEMORY_PATH / "cross-domain-synthesis.md",
]
STATE_FILE = HOME / ".zeke-rag-embed-state.json"
LOG_FILE = HOME / "logs/rag-embed.log"
OLLAMA_URL = "http://localhost:11434"
EMBED_MODEL = "nomic-embed-text"

# ── Logging ──
def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        LOG_FILE.parent.mkdir(exist_ok=True)
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except:
        pass

# ── Ollama embedding ──
def embed_text(text: str) -> list[float] | None:
    """Call ollama nomic-embed-text, return embedding vector."""
    try:
        r = requests.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={"model": EMBED_MODEL, "prompt": text[:8000]},
            timeout=30
        )
        if r.status_code == 200:
            return r.json().get("embedding")
        log(f"WARN embed HTTP {r.status_code}: {r.text[:100]}")
        return None
    except Exception as e:
        log(f"WARN embed error: {e}")
        return None

def embed_batch(texts: list[str]) -> list[list[float] | None]:
    """Embed a list of texts, returning list of embeddings (or None on failure)."""
    results = []
    for i, t in enumerate(texts):
        emb = embed_text(t)
        results.append(emb)
        if (i + 1) % 10 == 0:
            log(f"  Embedded {i+1}/{len(texts)}...")
    return results

# ── State management (track what's already embedded) ──
def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text())
    except:
        return {"embedded_hashes": [], "last_run": None, "total_embedded": 0}

def save_state(state: dict):
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    STATE_FILE.write_text(json.dumps(state, indent=2))

def content_hash(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()[:12]

# ── ChromaDB setup ──
def get_client_and_collections():
    import chromadb
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    
    synthesis_col = client.get_or_create_collection(
        name="synthesis_outputs",
        metadata={"description": "Zeke's own synthesis outputs — daily + camel + cross-domain"}
    )
    feed_col = client.get_or_create_collection(
        name="feed_entries",
        metadata={"description": "Learning feed entries — financial topics prioritized"}
    )
    thesis_col = client.get_or_create_collection(
        name="thesis_ledger",
        metadata={"description": "Camel Finance thesis ledger — per-video conviction signals"}
    )
    return client, synthesis_col, feed_col, thesis_col

# ── Embed synthesis files ──
def embed_synthesis(col, state: dict, force=False) -> int:
    count = 0
    embedded_hashes = set(state.get("embedded_hashes", []))
    
    for path in SYNTHESIS_PATHS:
        if not path.exists():
            continue
        text = path.read_text().strip()
        if len(text) < 100:
            continue
        
        h = content_hash(text)
        if h in embedded_hashes and not force:
            log(f"  Skip {path.name} (already embedded, hash={h})")
            continue
        
        # Chunk large files into ~1000 char segments with overlap
        chunks = chunk_text(text, chunk_size=1000, overlap=150)
        log(f"  Embedding {path.name}: {len(chunks)} chunks...")
        
        for i, chunk in enumerate(chunks):
            emb = embed_text(chunk)
            if emb is None:
                continue
            doc_id = f"synthesis_{path.stem}_{h}_{i}"
            try:
                col.upsert(
                    ids=[doc_id],
                    embeddings=[emb],
                    documents=[chunk],
                    metadatas=[{
                        "source": path.name,
                        "chunk": i,
                        "total_chunks": len(chunks),
                        "hash": h,
                        "embedded_at": datetime.now(timezone.utc).isoformat(),
                        "type": "synthesis"
                    }]
                )
                count += 1
            except Exception as e:
                log(f"  WARN upsert error: {e}")
        
        embedded_hashes.add(h)
        log(f"  ✓ {path.name}: {len(chunks)} chunks embedded")
    
    state["embedded_hashes"] = list(embedded_hashes)
    return count

# ── Embed feed entries (financial topics only, recent) ──
FINANCIAL_TOPICS = {
    "camel-finance", "camel finance", "treasury-bonds", "treasury bonds",
    "gold", "silver", "gld", "slv", "xauusd", "bitcoin", "btc", "ibit",
    "iren", "tlt", "gdx", "silj", "spx", "fedwatch", "fed", "rate",
    "cycle", "options", "position", "trade", "market"
}

def is_financial_topic(entry: dict) -> bool:
    topic = (entry.get("topic") or "").lower()
    finding = (entry.get("finding") or entry.get("insight") or "").lower()
    return any(kw in topic or kw in finding[:200] for kw in FINANCIAL_TOPICS)

def embed_feed(col, state: dict, days_back=14, force=False) -> int:
    if not FEED_PATH.exists():
        log("  Feed file not found, skipping")
        return 0
    
    count = 0
    embedded_hashes = set(state.get("embedded_hashes", []))
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
    
    entries = []
    with open(FEED_PATH) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except:
                continue
            # Date filter
            try:
                ts = datetime.fromisoformat(e.get("timestamp", "").replace("Z", "+00:00"))
                if ts < cutoff and not force:
                    continue
            except:
                pass
            if not is_financial_topic(e):
                continue
            entries.append(e)
    
    log(f"  Feed: {len(entries)} financial entries from last {days_back} days")
    
    new_entries = []
    for e in entries:
        text = (e.get("finding") or e.get("insight") or "").strip()
        if len(text) < 50:
            continue
        h = content_hash(text)
        if h in embedded_hashes and not force:
            continue
        new_entries.append((e, text, h))
    
    log(f"  Feed: {len(new_entries)} new entries to embed")
    
    for e, text, h in new_entries:
        emb = embed_text(text)
        if emb is None:
            continue
        doc_id = f"feed_{h}"
        try:
            col.upsert(
                ids=[doc_id],
                embeddings=[emb],
                documents=[text],
                metadatas=[{
                    "topic": e.get("topic", ""),
                    "timestamp": e.get("timestamp", ""),
                    "hash": h,
                    "embedded_at": datetime.now(timezone.utc).isoformat(),
                    "type": "feed_entry"
                }]
            )
            embedded_hashes.add(h)
            count += 1
        except Exception as ex:
            log(f"  WARN feed upsert: {ex}")
    
    state["embedded_hashes"] = list(embedded_hashes)
    return count

# ── Embed thesis ledger ──
def embed_thesis(col, state: dict, force=False) -> int:
    if not THESIS_PATH.exists():
        log(f"  Thesis ledger not found at {THESIS_PATH}, skipping")
        return 0
    
    count = 0
    embedded_hashes = set(state.get("embedded_hashes", []))
    
    entries = []
    with open(THESIS_PATH) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except:
                continue
    
    log(f"  Thesis ledger: {len(entries)} entries")
    
    for e in entries:
        # Build a rich text representation of the thesis entry
        parts = []
        if e.get("video_title"):
            parts.append(f"Video: {e['video_title']}")
        if e.get("thesis"):
            parts.append(f"Thesis: {e['thesis']}")
        if e.get("conviction"):
            parts.append(f"Conviction: {e['conviction']}")
        if e.get("instrument"):
            parts.append(f"Instrument: {e['instrument']}")
        if e.get("bias"):
            parts.append(f"Bias: {e['bias']}")
        if e.get("key_levels"):
            parts.append(f"Key levels: {e['key_levels']}")
        if e.get("cycle_position"):
            parts.append(f"Cycle position: {e['cycle_position']}")
        
        text = " | ".join(parts)
        if len(text) < 30:
            continue
        
        h = content_hash(text)
        if h in embedded_hashes and not force:
            continue
        
        emb = embed_text(text)
        if emb is None:
            continue
        
        doc_id = f"thesis_{h}"
        try:
            col.upsert(
                ids=[doc_id],
                embeddings=[emb],
                documents=[text],
                metadatas=[{
                    "video_title": str(e.get("video_title", "")),
                    "instrument": str(e.get("instrument", "")),
                    "conviction": str(e.get("conviction", "")),
                    "bias": str(e.get("bias", "")),
                    "date": str(e.get("date") or e.get("published_at") or ""),
                    "hash": h,
                    "embedded_at": datetime.now(timezone.utc).isoformat(),
                    "type": "thesis"
                }]
            )
            embedded_hashes.add(h)
            count += 1
        except Exception as ex:
            log(f"  WARN thesis upsert: {ex}")
    
    state["embedded_hashes"] = list(embedded_hashes)
    return count

# ── Text chunking ──
def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 150) -> list[str]:
    """Split text into overlapping chunks."""
    if len(text) <= chunk_size:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        # Try to break at sentence boundary
        if end < len(text):
            last_period = chunk.rfind(". ")
            if last_period > chunk_size * 0.6:
                chunk = chunk[:last_period + 1]
                end = start + last_period + 1
        chunks.append(chunk.strip())
        start = end - overlap
    return [c for c in chunks if len(c) > 50]

# ── Summary ──
def print_collection_stats(synthesis_col, feed_col, thesis_col):
    log(f"\n  ChromaDB state:")
    log(f"    synthesis_outputs: {synthesis_col.count()} chunks")
    log(f"    feed_entries:      {feed_col.count()} entries")
    log(f"    thesis_ledger:     {thesis_col.count()} entries")
    log(f"    Total:             {synthesis_col.count() + feed_col.count() + thesis_col.count()} documents")

# ── Main ──
def main():
    parser = argparse.ArgumentParser(description="Zeke RAG Embed — Block 3")
    parser.add_argument("--full-backfill", action="store_true", help="Embed all feed entries regardless of age")
    parser.add_argument("--force", action="store_true", help="Re-embed even if hash already seen")
    parser.add_argument("--synthesis-only", action="store_true", help="Only embed synthesis files")
    parser.add_argument("--stats", action="store_true", help="Just print collection stats")
    args = parser.parse_args()

    log("=" * 60)
    log("zeke-rag-embed.py — Block 3 RAG Feedback Loop")
    log("=" * 60)

    # Check ollama
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        models = [m["name"] for m in r.json().get("models", [])]
        if not any("nomic" in m for m in models):
            log("ERROR: nomic-embed-text not found in ollama. Run: ollama pull nomic-embed-text")
            sys.exit(1)
        log(f"✓ Ollama: {EMBED_MODEL} available")
    except Exception as e:
        log(f"ERROR: Cannot reach ollama: {e}")
        sys.exit(1)

    # Get ChromaDB collections
    try:
        client, synthesis_col, feed_col, thesis_col = get_client_and_collections()
        log(f"✓ ChromaDB at {CHROMA_PATH}")
    except Exception as e:
        log(f"ERROR: ChromaDB init failed: {e}")
        traceback.print_exc()
        sys.exit(1)

    if args.stats:
        print_collection_stats(synthesis_col, feed_col, thesis_col)
        return

    state = load_state()
    total = 0

    # Embed synthesis outputs
    log("\n[1/3] Synthesis outputs...")
    n = embed_synthesis(synthesis_col, state, force=args.force)
    log(f"  → {n} new chunks embedded")
    total += n

    if not args.synthesis_only:
        # Embed feed entries
        days = 90 if args.full_backfill else 14
        log(f"\n[2/3] Feed entries (last {days} days, financial topics)...")
        n = embed_feed(feed_col, state, days_back=days, force=args.force)
        log(f"  → {n} new entries embedded")
        total += n

        # Embed thesis ledger
        log("\n[3/3] Thesis ledger...")
        n = embed_thesis(thesis_col, state, force=args.force)
        log(f"  → {n} new thesis entries embedded")
        total += n

    state["total_embedded"] = state.get("total_embedded", 0) + total
    save_state(state)

    print_collection_stats(synthesis_col, feed_col, thesis_col)
    log(f"\n✓ Done. {total} new documents embedded this run.")
    log(f"  Total ever embedded: {state['total_embedded']}")
    log("=" * 60)

if __name__ == "__main__":
    main()
