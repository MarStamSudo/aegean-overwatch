"""Quick health report of the collected data."""
import sqlite3

from db import DB_PATH

conn = sqlite3.connect(DB_PATH)

total, first, last, aircraft = conn.execute("""
    SELECT COUNT(*),
           datetime(MIN(ts), 'unixepoch', 'localtime'),
           datetime(MAX(ts), 'unixepoch', 'localtime'),
           COUNT(DISTINCT icao)
    FROM positions
""").fetchone()

print(f"Rows:            {total}")
print(f"Unique aircraft: {aircraft}")
print(f"First position:  {first}")
print(f"Last position:   {last}")

print("\nRows per hour (last 24h):")
for hour, rows in conn.execute("""
    SELECT strftime('%Y-%m-%d %H:00', ts, 'unixepoch', 'localtime') AS hour, COUNT(*)
    FROM positions
    WHERE ts >= strftime('%s', 'now') - 24 * 3600
    GROUP BY hour
    ORDER BY hour
"""):
    print(f"  {hour}  {rows:>6}  {'#' * (rows // 200)}")

size_mb = DB_PATH.stat().st_size / 1024 / 1024
print(f"\nDatabase size:   {size_mb:.1f} MB")
conn.close()