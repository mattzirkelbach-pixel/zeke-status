
## 2026-08-18 — morning_briefing v2 rebuild (telegram-push-notifications)
Matt flagged the 08-18 6:30 send as garbage (after the NaN-price fix earlier
the same morning). Root problems found and fixed in scripts/morning_briefing.py
(deployed to mini ~/zeke-portfolio/scripts/, committed there as c825a4e):
- Deferred digest deduped on first-90-chars of message — ALL-CLEAR lines differ
  by gold price, so 11 near-duplicates passed and round-robin filled 4+ slots.
  Now: digit-stripped normalize_key, ALL-CLEARs collapse to one counted line.
- Raw HTML fragments rendered ("<b>PRE-MARKET…" chopped at 150 chars). Now
  HTML-stripped + word-boundary truncation everywhere.
- Filler sections ("No new hypotheses today.", "No imminent political
  catalysts.") rendered daily. Now empty sections render nothing.
- OTM watch pushed closed AMZN $265C ("EXIT still recommended", stale
  "expires in 18d") — now filtered against positions.json closed/qty=0.
- "day 155/36-44 PAST WINDOW" → "count stale (155d)"; a count 3x past the
  window is a broken anchor, not information.
- Camel theses chopped mid-word at 120 chars → sentence/word-safe 220.
- NEW core section SETUPS & TRIGGERS: deterministic engine (CF signals with
  age filter 1D≤21d/1W≤60d, price vs 10-SMA, day-18 confirmation gate,
  overnight top-signal fires promoted with holdings context). Every line ends
  with an action verb (WAIT / NO CHASE / VERIFY / EXIT-REVIEW / WATCH).
- POSITION RISK from options-risk-dashboard.json (15 CRITICAL surfaced) in
  place of "E*Trade: 5 positions".
Tests: 17 in tests/test_morning_briefing_v2.py (run on mini, all pass).
Anti-pattern reinforced: never dedupe alert text on a raw prefix — normalize
out numbers first. Never render a section that says "nothing to say".
