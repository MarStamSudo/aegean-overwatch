import sqlite3

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
    """Latest known position of every aircraft seen in the last N seconds."""
    return query("""
        SELECT p.*
        FROM positions p
        JOIN (
            SELECT icao, MAX(ts) AS max_ts
            FROM positions
            WHERE ts >= strftime('%s', 'now') - ?
            GROUP BY icao
        ) last
        ON p.icao = last.icao AND p.ts = last.max_ts
        ORDER BY p.icao
    """, (seconds,))


@app.get("/api/aircraft/{icao}/track")
def aircraft_track(icao: str, minutes: int = 60):
    """All positions of one aircraft in the last N minutes, oldest first."""
    rows = query("""
        SELECT ts, lat, lon, alt_baro, gs, track
        FROM positions
        WHERE icao = ? AND ts >= strftime('%s', 'now') - ? * 60
        ORDER BY ts
    """, (icao.lower(), minutes))
    if not rows:
        raise HTTPException(status_code=404, detail="No positions for this aircraft")
    return rows