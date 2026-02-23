#!/usr/bin/env python3
"""
Zeke Quality Scorer + Insight Detector
Runs every 15 min alongside status push.
- Scores recent feed entries for novelty/depth
- Detects genuinely novel insights
- Sends to Telegram if truly noteworthy
- Writes quality metrics to status dir
"""
import json, hashlib, re
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import Counter
import urllib.request

FEED = Path.home() / ".openclaw/workspace/memory/learning-feed.jsonl"
STATUS = Path.home() / "zeke-status"
QUALITY_FILE = STATUS / "quality-metrics.json"
SENT_INSIGHTS = STATUS / "sent-insights.json"

TELEGRAM_TOKEN = "8320091698:AAEDPuqw9o-14aI04cYHP-ByxzsTz2LktvY"
TELEGRAM_CHAT = "6984324216"

# Insight scoring criteria
DEPTH_SIGNALS = [
    'study', 'found that', 'research shows', 'published', 'peer-reviewed',
    'data suggests', 'evidence', 'clinical trial', 'meta-analysis',
    'according to', 'paper', 'journal', 'significant', 'correlation',
    'mechanism', 'pathway', 'breakthrough', 'novel', 'first time',
    'contrary to', 'surprisingly', 'challenges the', 'paradigm'
]
SHALLOW_SIGNALS = [
    'is important', 'plays a role', 'may help', 'could potentially',
    'further research needed', 'it is known', 'generally accepted',
    'various factors', 'many studies', 'some researchers'
]

# Matt's high-priority topics
PRIORITY_TOPICS = ['treasury', 'tlt', 'bond', 'yield', 'interest rate', 'longevity', 'rapamycin']


def score_entry(entry):
    """Score 1-5 based on depth, specificity, novelty signals."""
    finding = str(entry.get('finding', entry.get('insight', entry.get('content', ''))))
    topic = str(entry.get('topic', '')).lower()
    score = 2.5  # baseline

    fl = finding.lower()

    # Depth signals
    depth_hits = sum(1 for s in DEPTH_SIGNALS if s in fl)
    score += min(depth_hits * 0.3, 1.2)

    # Shallow penalties
    shallow_hits = sum(1 for s in SHALLOW_SIGNALS if s in fl)
    score -= min(shallow_hits * 0.3, 1.0)

    # Specificity: numbers, percentages, dates = good
    numbers = len(re.findall(r'\d+\.?\d*%|\$\d+|\d{4}(?:\s|$)', finding))
    score += min(numbers * 0.2, 0.8)

    # Length: very short = shallow, moderate = good, very long = padding
    words = len(finding.split())
    if words < 20: score -= 0.5
    elif words > 40 and words < 120: score += 0.3
    elif words > 200: score -= 0.3

    # Source citations
    if any(s in fl for s in ['http', 'www.', '.com', '.org', '.gov']):
        score += 0.3

    # Priority topic bonus
    if any(p in topic for p in PRIORITY_TOPICS):
        score += 0.3

    return max(1.0, min(5.0, round(score, 1)))


def is_novel(entry, recent_entries):
    """Check if this finding says something genuinely new vs recent entries."""
    finding = str(entry.get('finding', ''))[:150].lower()
    topic = entry.get('topic', '')

    # Compare against recent same-topic entries
    same_topic = [e for e in recent_entries if e.get('topic') == topic]

    for prev in same_topic[-10:]:
        prev_f = str(prev.get('finding', ''))[:150].lower()
        # Simple word overlap check
        words_new = set(finding.split())
        words_old = set(prev_f.split())
        if len(words_new) < 5:
            return False
        overlap = len(words_new & words_old) / len(words_new)
        if overlap > 0.6:
            return False  # Too similar

    return True


def telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = json.dumps({"chat_id": TELEGRAM_CHAT, "text": msg}).encode()
    try:
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=15)
        return True
    except:
        return False


def main():
    if not FEED.exists():
        return

    entries = []
    for line in FEED.read_text().strip().split('\n'):
        if line.strip():
            try:
                entries.append(json.loads(line))
            except:
                pass

    if not entries:
        return

    # Score all entries
    scores = []
    topic_scores = Counter()
    topic_counts = Counter()

    for e in entries:
        s = score_entry(e)
        scores.append(s)
        topic = e.get('topic', 'unknown')
        topic_scores[topic] += s
        topic_counts[topic] += 1

    # Compute metrics
    avg = sum(scores) / len(scores) if scores else 0
    topic_avgs = {}
    for t in topic_counts:
        topic_avgs[t] = round(topic_scores[t] / topic_counts[t], 1)

    recent_30 = scores[-30:] if len(scores) >= 30 else scores
    recent_avg = sum(recent_30) / len(recent_30) if recent_30 else 0

    quality_5 = len([s for s in scores if s >= 4.0])
    quality_1 = len([s for s in scores if s <= 1.5])

    metrics = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_entries": len(entries),
        "avg_quality": round(avg, 2),
        "recent_30_avg": round(recent_avg, 2),
        "high_quality_count": quality_5,
        "low_quality_count": quality_1,
        "topic_averages": dict(sorted(topic_avgs.items(), key=lambda x: -x[1])),
        "score_distribution": {
            "1-2": len([s for s in scores if s < 2]),
            "2-3": len([s for s in scores if 2 <= s < 3]),
            "3-4": len([s for s in scores if 3 <= s < 4]),
            "4-5": len([s for s in scores if s >= 4])
        }
    }

    QUALITY_FILE.write_text(json.dumps(metrics, indent=2))

    # ── Insight detection on NEW entries (last 15 min) ──
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(minutes=20)).isoformat()

    # Load sent insights to avoid re-sending
    sent = set()
    if SENT_INSIGHTS.exists():
        try:
            sent = set(json.loads(SENT_INSIGHTS.read_text()))
        except:
            pass

    new_insights = []
    for e in entries[-15:]:  # Check last 15 entries
        ts = e.get('timestamp', '')
        if ts < cutoff:
            continue

        score = score_entry(e)
        if score < 3.5:
            continue

        finding = str(e.get('finding', ''))
        fhash = hashlib.md5(finding[:100].encode()).hexdigest()
        if fhash in sent:
            continue

        if not is_novel(e, entries):
            continue

        new_insights.append((e, score, fhash))

    # Send top insight to Telegram (max 1 per run to avoid spam)
    if new_insights:
        best = max(new_insights, key=lambda x: x[1])
        e, score, fhash = best
        topic = e.get('topic', 'unknown')
        finding = str(e.get('finding', ''))[:300]

        # Only send if score >= 4.0 OR it's a priority topic with score >= 3.5
        is_priority = any(p in topic.lower() for p in PRIORITY_TOPICS)
        if score >= 4.0 or (is_priority and score >= 3.5):
            msg = f"💡 [{topic}] (quality: {score}/5)\n\n{finding}"
            if telegram(msg):
                sent.add(fhash)
                SENT_INSIGHTS.write_text(json.dumps(list(sent)[-500:]))  # Keep last 500

if __name__ == "__main__":
    main()
