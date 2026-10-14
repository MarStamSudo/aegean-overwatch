import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "aegean.db"


def connect():
    """Open (or create) the database file and return a connection."""
    return sqlite3.connect(DB_PATH)


def init_db(conn):
    """Create the table and index if they don't exist yet."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS positions (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            ts        INTEGER NOT NULL,   -- unix time (seconds)
            icao      TEXT    NOT NULL,
            flight    TEXT,
            lat       REAL    NOT NULL,
            lon       REAL    NOT NULL,
            alt_baro  INTEGER,
            on_ground INTEGER NOT NULL,   -- 1 = on the ground, 0 = airborne
            gs        REAL,
            track     REAL,
            squawk    TEXT,
            nic       INTEGER,
            nac_p     INTEGER,
            db_flags  INTEGER
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_positions_icao_ts ON positions (icao, ts)")
    conn.commit()


def to_row(aircraft, ts):
    """Convert one aircraft dict from the API into a tuple for the table."""
    alt = aircraft.get("alt_baro")
    on_ground = 1 if alt == "ground" else 0
    alt_baro = alt if isinstance(alt, int) else None

    return (
        ts,
        aircraft["hex"],
        (aircraft.get("flight") or "").strip() or None,
        aircraft["lat"],
        aircraft["lon"],
        alt_baro,
        on_ground,
        aircraft.get("gs"),
        aircraft.get("track"),
        aircraft.get("squawk"),
        aircraft.get("nic"),
        aircraft.get("nac_p"),
        aircraft.get("dbFlags"),
    )


def insert_positions(conn, aircraft_list, ts):
    """Insert one row per aircraft. Returns how many rows were written."""
    rows = [to_row(a, ts) for a in aircraft_list]
    conn.executemany("""
        INSERT INTO positions
            (ts, icao, flight, lat, lon, alt_baro, on_ground, gs, track, squawk, nic, nac_p, db_flags)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows)
    conn.commit()
    return len(rows)