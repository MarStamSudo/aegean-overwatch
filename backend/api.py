import sqlite3

from analysis import classify, emergency_reason
from analysis import LOW_NIC, classify
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from ingest.db import DB_PATH

app = FastAPI(title="Aegean Overwatch API")

# Allow the React dev server (Vite runs on port 5173) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["GET"],
)


def query(sql, params=()):
    """Run a read-only query and return a list of dicts."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


@app.get("/api/health")
def health():
    """Simple check that the API is running."""
    return {"status": "ok"}


@app.get("/api/aircraft/latest")
def latest_positions(seconds: int = 120):
    """Latest known position of every aircraft seen in the last N seconds (one row per aircraft)."""
    rows = query("""
        SELECT *
        FROM positions
        WHERE id IN (
            SELECT MAX(id)
            FROM positions
            WHERE ts >= strftime('%s', 'now') - ?
            GROUP BY icao
        )
        ORDER BY icao
    """, (seconds,))

    for row in rows:
        row["tags"] = classify(row)
        row["emergency_reason"] = emergency_reason(row)
    return rows


@app.get("/api/aircraft/{icao}/track")
def aircraft_track(icao: str, minutes: int = 60):
    """All positions of one aircraft in the last N minutes, oldest first."""
    rows = query("""
        SELECT ts, lat, lon, alt_baro, gs, track, nic, nac_p
        FROM positions
        WHERE icao = ? AND ts >= strftime('%s', 'now') - ? * 60
        ORDER BY ts
    """, (icao.lower(), minutes))
    if not rows:
        raise HTTPException(status_code=404, detail="No positions for this aircraft")
    return rows

# aircraft history
@app.get("/api/history/aircraft")
def history_aircraft(hours: int = 24, q: str = ""):
    """Aircraft seen in the last N hours, most GNSS-degraded first.
    Optional search by callsign or ICAO (partial match)."""
    q = q.strip()
    return query("""
        SELECT icao,
               MAX(flight)   AS flight,
               COUNT(*)      AS positions,
               SUM(nic < ?)  AS low_nic,
               MIN(ts)       AS first_seen,
               MAX(ts)       AS last_seen
        FROM positions
        WHERE ts >= strftime('%s', 'now') - ? * 3600
          AND (? = '' OR icao LIKE ? OR flight LIKE ?)
        GROUP BY icao
        ORDER BY low_nic DESC, last_seen DESC
        LIMIT 100
    """, (LOW_NIC, hours, q, f"%{q.lower()}%", f"%{q.upper()}%"))