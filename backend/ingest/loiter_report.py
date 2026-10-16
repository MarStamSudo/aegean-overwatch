"""Report: aircraft that flew orbits or holding patterns (>= 360 degrees of turning within 20 minutes)."""
import sqlite3
import sys
import time

from analysis import find_loiter_events
from ingest.db import DB_PATH

HOURS = int(sys.argv[1]) if len(sys.argv) > 1 else 24

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
rows = [dict(r) for r in conn.execute("""
    SELECT icao, flight, ts, lat, lon, track
    FROM positions
    WHERE ts >= strftime('%s', 'now') - ? * 3600
    ORDER BY icao, ts
""", (HOURS,))]
conn.close()

events = sorted(find_loiter_events(rows), key=lambda e: e["start"])

print(f"Loiter events in the last {HOURS} hours: {len(events)}\n")
for e in events:
    start = time.strftime("%d/%m %H:%M", time.localtime(e["start"]))
    minutes = max(1, round((e["end"] - e["start"]) / 60))
    print(f"  {start}  {e['icao']}  {e['flight'] or '-':<8}  {minutes:>3} min"
          f"  turned {e['turn_deg']:>4} deg  around {e['lat']:.2f}, {e['lon']:.2f}")