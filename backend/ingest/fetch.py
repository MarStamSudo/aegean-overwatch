import json
import time
import db
from pathlib import Path

import httpx
from shapely.geometry import shape, Point

HEADERS = {"User-Agent": "aegean-overwatch/0.1 (+https://github.com/MarStamSudo/aegean-overwatch)"}
URL = "https://api.adsb.lol/v2/point/38.3/25.0/250"
GEOJSON_PATH = Path(__file__).parent.parent / "data" / "aegean.geojson"
POLL_INTERVAL = 15


def load_polygon(path):
    """Read the GeoJSON file and return a shapely polygon."""
    with open(path, encoding="utf-8") as f:          
        data = json.load(f)
    return shape(data["features"][0]["geometry"])


def fetch_aircraft():
    """Call the API and return the list of aircraft (list of dicts)."""
    response = httpx.get(URL, headers=HEADERS, timeout=10)   
    response.raise_for_status()
    return response.json().get("ac", [])


def filter_aegean(aircraft_list, polygon):
    """Return only aircraft that have a position and are inside the polygon."""
    result = []
    for aircraft in aircraft_list:                   
        lat = aircraft.get("lat")
        lon = aircraft.get("lon")
        if lat is None or lon is None:
            continue
        if not polygon.contains(Point(lon, lat)):
            continue
        result.append(aircraft)
    return result


def format_aircraft(aircraft):
    """Return one readable line describing an aircraft."""
    icao = aircraft.get("hex")                       
    flight = (aircraft.get("flight") or "").strip() or "-"
    alt_baro = aircraft.get("alt_baro")
    alt_text = "-" if alt_baro is None else str(alt_baro)
    lat = aircraft["lat"]
    lon = aircraft["lon"]
    return f"{icao}  {flight:<8}  {alt_text:>6}  {lat:.3f}, {lon:.3f}"


def main():
    aegean = load_polygon(GEOJSON_PATH)
    conn = db.connect()
    db.init_db(conn)
    print(f"Aegean Overwatch started. Polling every {POLL_INTERVAL}s. Press Ctrl+C to stop.")

    try:
        while True:
            now = time.strftime("%H:%M:%S")
            try:
                aircraft_list = fetch_aircraft()
                inside = filter_aegean(aircraft_list, aegean)
                written = db.insert_positions(conn, inside, int(time.time()))
                print(f"[{now}] found: {len(aircraft_list)} | inside Aegean: {len(inside)} | saved: {written}")
            except httpx.HTTPError as error:
                print(f"[{now}] request failed, will retry: {error}")

            time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        print("\nStopped by user.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()