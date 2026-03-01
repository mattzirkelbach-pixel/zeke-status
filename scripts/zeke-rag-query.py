#!/usr/bin/env python3
"""
zeke-rag-query.py — Block 3: RAG Query Helper
==============================================
Retrieves relevant context from ChromaDB before running synthesis or analysis.
This is the READ side of the RAG loop — called by queue tasks to pre-load context.

Usage:
  python3 ~/zeke-rag-query.py --query "gold cycle weekly timing" --n 5
  python3 ~/zeke-rag-query.py --query "TLT rate cuts" --collection feed_entries --n 3
  python3 ~/zeke-rag-query.py --instrument XAUUSD --type thesis --n 5
  python3 ~/zeke-rag-query.py --context-for "GLD entry timing at daily cycle low"

Returns JSON to stdout — designed to be called by spark-work-queue.py task runner
to inject relevant prior context into prompts before dispatching to Spark/Claude.
"""

import sys
import json
import argparse
import requests
from pathlib import Path

HOME = Path.home()
CHROMA_PATH = HOME / ".openclaw/chroma"
OLLAMA_URL = "http://localhost:11434"
EMBED_MODEL = "nomic-embed-text"

def embed_query(text: str) -> list[float] | None:
    try:
        r = requests.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={"model": EMBED_MODEL, "prompt": text[:4000]},
            timeout=20
        )
        if r.status_code == 200:
            return r.json().get("embedding")
        return None
    except:
        return None

def query_collection(col, query_embedding: list[float], n: int, where: dict | None = None) -> list[dict]:
    """Query a collection, return list of {text, metadata, distance}."""
    try:
        kwargs = {
            "query_embeddings": [query_embedding],
            "n_results": min(n, col.count() or 1),
            "include": ["documents", "metadatas", "distances"]
        }
        if where:
            kwargs["where"] = where
        results = col.query(**kwargs)
        
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        dists = results.get("distances", [[]])[0]
        
        return [
            {"text": d, "metadata": m, "distance": dist, "relevance": round(1 - dist, 3)}
            for d, m, dist in zip(docs, metas, dists)
            if d
        ]
    except Exception as e:
        return []

def get_context_for_prompt(query: str, n_per_collection: int = 3) -> dict:
    """
    Main function: given a query string, retrieve relevant context from all collections.
    Returns a dict suitable for injecting into a synthesis prompt.
    """
    import chromadb
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    
    emb = embed_query(query)
    if emb is None:
        return {"error": "Embedding failed", "context": [], "query": query}
    
    results = {"query": query, "context": [], "collection_stats": {}}
    
    collection_names = ["synthesis_outputs", "feed_entries", "thesis_ledger"]
    for cname in collection_names:
        try:
            col = client.get_collection(cname)
            stats = col.count()
            results["collection_stats"][cname] = stats
            if stats == 0:
                continue
            hits = query_collection(col, emb, n_per_collection)
            for h in hits:
                h["collection"] = cname
                results["context"].append(h)
        except Exception as e:
            results["collection_stats"][cname] = f"error: {e}"
    
    # Sort all results by relevance
    results["context"].sort(key=lambda x: x.get("relevance", 0), reverse=True)
    
    return results

def format_context_for_prompt(context_result: dict, max_chars: int = 3000) -> str:
    """Format RAG results into a string for injection into LLM prompts."""
    if not context_result.get("context"):
        return ""
    
    lines = ["=== PRIOR ZEKE CONTEXT (RAG retrieval) ==="]
    lines.append(f"Query: {context_result['query']}")
    lines.append("")
    
    chars_used = 0
    for i, item in enumerate(context_result["context"]):
        text = item["text"]
        meta = item.get("metadata", {})
        rel = item.get("relevance", 0)
        col = item.get("collection", "")
        
        source_label = {
            "synthesis_outputs": f"[Prior synthesis: {meta.get('source', '')}]",
            "feed_entries": f"[Feed: {meta.get('topic', '')} @ {meta.get('timestamp', '')[:10]}]",
            "thesis_ledger": f"[Thesis: {meta.get('video_title', '')} | {meta.get('instrument', '')} {meta.get('bias', '')}]"
        }.get(col, f"[{col}]")
        
        entry = f"{source_label} (relevance: {rel})\n{text}"
        if chars_used + len(entry) > max_chars:
            break
        lines.append(entry)
        lines.append("")
        chars_used += len(entry)
    
    lines.append("=== END PRIOR CONTEXT ===")
    return "\n".join(lines)

def main():
    parser = argparse.ArgumentParser(description="Zeke RAG Query")
    parser.add_argument("--query", "-q", help="Query string")
    parser.add_argument("--context-for", help="Get formatted context string for this topic (for prompt injection)")
    parser.add_argument("--instrument", help="Filter by instrument (XAUUSD, TLT, BTC, etc)")
    parser.add_argument("--collection", choices=["synthesis_outputs", "feed_entries", "thesis_ledger", "all"],
                       default="all", help="Which collection to search")
    parser.add_argument("--n", type=int, default=5, help="Results per collection")
    parser.add_argument("--format", choices=["json", "text", "prompt"], default="json",
                       help="Output format")
    parser.add_argument("--stats", action="store_true", help="Show collection stats only")
    args = parser.parse_args()

    import chromadb
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))

    if args.stats:
        out = {}
        for cname in ["synthesis_outputs", "feed_entries", "thesis_ledger"]:
            try:
                col = client.get_collection(cname)
                out[cname] = col.count()
            except:
                out[cname] = 0
        print(json.dumps(out, indent=2))
        return

    query = args.context_for or args.query
    if not query:
        print(json.dumps({"error": "Provide --query or --context-for"}))
        sys.exit(1)

    # Build instrument filter for thesis
    where = None
    if args.instrument:
        where = {"instrument": {"$contains": args.instrument}}

    if args.context_for:
        # Return formatted string for prompt injection
        result = get_context_for_prompt(query, n_per_collection=args.n)
        if args.format == "prompt":
            print(format_context_for_prompt(result))
        else:
            print(json.dumps(result, indent=2))
        return

    # Single collection or all
    emb = embed_query(query)
    if emb is None:
        print(json.dumps({"error": "Embedding failed"}))
        sys.exit(1)

    if args.collection == "all":
        result = get_context_for_prompt(query, n_per_collection=args.n)
        print(json.dumps(result, indent=2))
    else:
        try:
            col = client.get_collection(args.collection)
            hits = query_collection(col, emb, args.n, where=where)
            print(json.dumps({"collection": args.collection, "query": query, "results": hits}, indent=2))
        except Exception as e:
            print(json.dumps({"error": str(e)}))
            sys.exit(1)

if __name__ == "__main__":
    main()
