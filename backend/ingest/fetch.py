import json
import sys
import time
from pathlib import Path

import httpx
from shapely.geometry import shape, Point

import db

# Let this script import analysis.py from the backend/ folder (one level up)
sys.path.insert(0, str(Path(__file__).parent.parent))
import alerts  # noqa: E402  (must come after the path change)

HEADERS = {"User-Agent": "aegean-overwatch/0.1 (+https://github.com/MarStamSudo/aegean-overwatch)"}
GEOJSON_PATH = Path(__file__).parent.parent / "data" / "aegean.geojson"
POLL_INTERVAL = 15  # seconds between polling rounds

# Center of the Aegean and radius in nautical miles (max 250 for all sources)
LAT, LON, RADIUS_NM = 38.3, 25.0, 250

SOURCES = [
    {"name": "adsb.lol",       "enabled": True,  "url": f"https://api.adsb.lol/v2/point/{LAT}/{LON}/{RADIUS_NM}"},
        {"name": "airplanes.live", "enabled": False, "url": f"https://api.airplanes.live/v2/point/{LAT}/{LON}/{RADIUS_NM}"},  # API key for feeders only
    {"name": "adsb.fi",        "enabled": True,  "url": f"https://opendata.adsb.fi/api/v3/lat/{LAT}/lon/{LON}/dist/{RADIUS_NM}"},
]


def load_polygon(path):
    """Read the GeoJSON file and return a shapely polygon."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return shape(data["features"][0]["geometry"])


def fetch_source(url):
    """Call one ADS-B API and return its list of aircraft."""
    response = httpx.get(url, headers=HEADERS, timeout=10)
    response.raise_for_status()
    data = response.json()
    return data.get("ac") or data.get("aircraft") or []


def merge_aircraft(results):
    """Merge aircraft lists from several sources.

    The same aircraft (same hex) can appear in many sources.
    We keep the report with the freshest position (smallest seen_pos).
    """
    merged = {}
    for aircraft_list in results:
        for aircraft in aircraft_list:
            icao = (aircraft.get("hex") or "").lower()
            if not icao:
                continue
            aircraft["hex"] = icao

            current = merged.get(icao)
            if current is None or aircraft.get("seen_pos", 999) < current.get("seen_pos", 999):
                merged[icao] = aircraft
    return list(merged.values())


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

    active = [s for s in SOURCES if s.get("enabled", True)]
    names = ", ".join(s["name"] for s in active)
    print(f"Aegean Overwatch started. Sources: {names}. Every {POLL_INTERVAL}s. Press Ctrl+C to stop.")

    # Alerts: remember what we already sent, so we don't repeat it every 15 seconds
    sent_alerts = {}
    if alerts.enabled():
        alerts.send_telegram("✅ Aegean Overwatch collector started")
        print("Telegram alerts: ON")
    else:
        print("Telegram alerts: OFF (no TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID in backend/.env)")

    try:
        while True:
            now = time.strftime("%H:%M:%S")

            # 1. Ask every active source; one failing source must not stop the others
            results = []
            stats = []
            for source in active:
                try:
                    aircraft_list = fetch_source(source["url"])
                    results.append(aircraft_list)
                    stats.append(f"{source['name']}: {len(aircraft_list)}")
                except httpx.HTTPError as error:
                    stats.append(f"{source['name']}: FAILED")
                    print(f"[{now}] {source['name']} error: {error}")

            # 2. Merge, filter, store
            merged = merge_aircraft(results)
            inside = filter_aegean(merged, aegean)
            written = db.insert_positions(conn, inside, int(time.time()))
            print(f"[{now}] {' | '.join(stats)} -> merged: {len(merged)} | Aegean: {len(inside)} | saved: {written}")

            # 3. Alerts for military aircraft and emergency squawks
            for message in alerts.new_alerts(inside, sent_alerts, int(time.time())):
                alerts.send_telegram(message)

            time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        print("\nStopped by user.")
    finally:
        conn.close()

if __name__ == "__main__":
    main()