#!/usr/bin/env python3
"""Mission Control API server — serves dashboard + live data from local files."""
import http.server, json, os, socketserver
from pathlib import Path
from datetime import datetime

PORT = 3335
BASE = Path(__file__).parent
MEMORY = Path.home() / ".openclaw/workspace/memory"

def _read_json(p):
    try: return json.loads(Path(p).read_text())
    except: return {}

def _read_jsonl(p):
    entries = []
    try:
        for line in Path(p).read_text().splitlines():
            try:
                d = json.loads(line.strip())
                if isinstance(d, dict):
                    entries.append(d)
            except: pass
    except: pass
    return entries

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(BASE), **kw)

    def do_GET(self):
        if self.path == "/api/diagnostic":
            self._json(self._diagnostic())
        elif self.path == "/api/journal":
            self._json(self._journal())
        elif self.path == "/api/queue":
            self._json(self._queue())
        elif self.path == "/api/domains":
            self._json(self._domains())
        elif self.path == "/api/feed":
            self._json(self._feed())
        elif self.path == "/api/cycles":
            self._json(self._cycles())
        elif self.path == "/api/health":
            self._json({"status": "ok", "ts": datetime.now().isoformat()})
        else:
            super().do_GET()

    def _json(self, data):
        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def _diagnostic(self):
        return _read_json(BASE / "diagnostic.json")

    def _journal(self):
        entries = _read_jsonl(BASE / "memory/session-journal.jsonl")
        return {"entries": entries[-30:], "total": len(entries)}

    def _queue(self):
        q = _read_json(MEMORY / "spark-work-queue.jsonl")
        if isinstance(q, list):
            statuses = {}
            for t in q:
                if isinstance(t, dict):
                    s = t.get("status", "unknown")
                    statuses[s] = statuses.get(s, 0) + 1
            pending = [t for t in q if isinstance(t, dict) and t.get("status") == "pending"]
            return {"total": len(q), "statuses": statuses, "pending": pending[:20]}
        return {"total": 0, "statuses": {}, "pending": []}

    def _domains(self):
        dom_dir = MEMORY / "domains"
        domains = []
        if dom_dir.exists():
            for f in sorted(dom_dir.iterdir()):
                if f.suffix == ".md" and f.stem != "README":
                    content = f.read_text()[:500]
                    domains.append({"name": f.stem, "size": f.stat().st_size,
                                    "preview": content[:200]})
        return {"domains": domains, "count": len(domains)}

    def _feed(self):
        return _read_json(BASE / "status.json")

    def _cycles(self):
        return _read_jsonl(BASE / "cycle-history.jsonl")[-20:]

    def log_message(self, fmt, *args):
        pass  # quiet

if __name__ == "__main__":
    with socketserver.TCPServer(("", PORT), Handler) as s:
        s.allow_reuse_address = True
        print(f"Mission Control server on :{PORT}")
        s.serve_forever()
