"""Exploratory report: signs of GNSS (GPS) interference in the collected data."""
import sqlite3

from db import DB_PATH

LOW_NIC = 7        # NIC below this = degraded position integrity
CELL_SIZE = 0.5    # grid cell size in degrees (~55 km)
MIN_SAMPLES = 200  # ignore grid cells with too little data

conn = sqlite3.connect(DB_PATH)


def section(title):
    print(f"\n=== {title} ===")


# 1. Distribution of NIC values
section("1. NIC values (how many positions have each value)")
total_with_nic = conn.execute("SELECT COUNT(*) FROM positions WHERE nic IS NOT NULL").fetchone()[0]
missing = conn.execute("SELECT COUNT(*) FROM positions WHERE nic IS NULL").fetchone()[0]
for nic, count in conn.execute("""
    SELECT nic, COUNT(*) FROM positions
    WHERE nic IS NOT NULL
    GROUP BY nic ORDER BY nic
"""):
    pct = 100 * count / total_with_nic
    print(f"  NIC {nic:>2}: {count:>7}  ({pct:5.1f}%)  {'#' * int(pct)}")
print(f"  (no NIC reported: {missing})")


# 2. Which aircraft have low NIC? (one aircraft with bad equipment is NOT jamming)
section(f"2. Aircraft with most low-NIC positions (NIC < {LOW_NIC})")
for icao, flight, total, low in conn.execute("""
    SELECT icao, MAX(flight), COUNT(*), SUM(nic < ?)
    FROM positions
    WHERE nic IS NOT NULL
    GROUP BY icao
    HAVING SUM(nic < ?) > 0
    ORDER BY SUM(nic < ?) DESC
    LIMIT 10
""", (LOW_NIC, LOW_NIC, LOW_NIC)):
    print(f"  {icao}  {flight or '-':<8}  low {low:>5} of {total:>5}  ({100 * low / total:5.1f}%)")


# 3. Where? Group positions into grid cells
section(f"3. Grid cells ({CELL_SIZE} deg) with highest share of low NIC")
print("  cell (lat, lon)      positions   low   low%   distinct aircraft affected")
for cell_lat, cell_lon, total, low, aircraft in conn.execute("""
    SELECT CAST(lat / ? AS INTEGER) * ? AS cell_lat,
           CAST(lon / ? AS INTEGER) * ? AS cell_lon,
           COUNT(*),
           SUM(nic < ?),
           COUNT(DISTINCT CASE WHEN nic < ? THEN icao END)
    FROM positions
    WHERE nic IS NOT NULL
    GROUP BY cell_lat, cell_lon
    HAVING COUNT(*) >= ?
    ORDER BY 1.0 * SUM(nic < ?) / COUNT(*) DESC
    LIMIT 10
""", (CELL_SIZE, CELL_SIZE, CELL_SIZE, CELL_SIZE, LOW_NIC, LOW_NIC, MIN_SAMPLES, LOW_NIC)):
    print(f"  ({cell_lat:5.1f}, {cell_lon:5.1f})   {total:>9}  {low:>5}  {100 * low / total:5.1f}%   {aircraft}")


# 4. When? Share of low NIC per hour
section("4. Low NIC per hour")
for hour, total, low, aircraft in conn.execute("""
    SELECT strftime('%Y-%m-%d %H:00', ts, 'unixepoch', 'localtime') AS hour,
           COUNT(*),
           SUM(nic < ?),
           COUNT(DISTINCT CASE WHEN nic < ? THEN icao END)
    FROM positions
    WHERE nic IS NOT NULL
    GROUP BY hour ORDER BY hour
""", (LOW_NIC, LOW_NIC)):
    print(f"  {hour}  {low:>5} of {total:>6}  ({100 * low / total:5.1f}%)  aircraft: {aircraft}")

conn.close()