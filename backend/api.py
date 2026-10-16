import sqlite3
from itertools import groupby

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from analysis import classify, emergency_reason, split_flights, summarize_flight
from ingest.db import DB_PATH

from analysis import classify, emergency_reason, find_loiter_events, split_flights, summarize_flight

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
def aircraft_track(icao: str, minutes: int = 60, start: int | None = None, end: int | None = None):
    """Positions of one aircraft, oldest first.
    With start/end (unix seconds): exactly that time window (one flight).
    Otherwise: the last N minutes."""
    if start is not None and end is not None:
        rows = query("""
            SELECT ts, lat, lon, alt_baro, gs, track, nic, nac_p
            FROM positions
            WHERE icao = ? AND ts BETWEEN ? AND ?
            ORDER BY ts
        """, (icao.lower(), start, end))
    else:
        rows = query("""
            SELECT ts, lat, lon, alt_baro, gs, track, nic, nac_p
            FROM positions
            WHERE icao = ? AND ts >= strftime('%s', 'now') - ? * 60
            ORDER BY ts
        """, (icao.lower(), minutes))

    if not rows:
        raise HTTPException(status_code=404, detail="No positions for this aircraft")
    return rows


@app.get("/api/history/flights")
def history_flights(hours: int = 24, q: str = ""):
    """Flights seen in the last N hours, most GNSS-degraded first.
    Optional search by callsign or ICAO (partial match)."""
    q = q.strip()
    rows = query("""
        SELECT icao, flight, ts, nic
        FROM positions
        WHERE ts >= strftime('%s', 'now') - ? * 3600
          AND (? = '' OR icao LIKE ? OR flight LIKE ?)
        ORDER BY icao, ts
    """, (hours, q, f"%{q.lower()}%", f"%{q.upper()}%"))

    flights = []
    for icao, points in groupby(rows, key=lambda row: row["icao"]):
        for flight_points in split_flights(list(points)):
            flights.append(summarize_flight(icao, flight_points))

    flights.sort(key=lambda f: (f["low_nic"], f["end"]), reverse=True)
    return flights[:200]

@app.get("/api/history/loiters")
def history_loiters(hours: int = 24):
    """Orbits / holding patterns in the last N hours, newest first."""
    rows = query("""
        SELECT icao, flight, ts, lat, lon, track
        FROM positions
        WHERE ts >= strftime('%s', 'now') - ? * 3600
        ORDER BY icao, ts
    """, (hours,))
    return find_loiter_events(rows)