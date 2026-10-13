import json
from pathlib import Path

import httpx
from shapely.geometry import shape, Point

HEADERS = {"User-Agent": "aegean-overwatch/0.1 (+https://github.com/MarStamSudo/aegean-overwatch)"}
URL = "https://api.adsb.lol/v2/point/38.3/25.0/250"
GEOJSON_PATH = Path(__file__).parent.parent / "data" / "aegean.geojson"

# 1. Load the Aegean polygon (once, before the request)
with open(GEOJSON_PATH, encoding="utf-8") as f:
    aegean = shape(json.load(f)["features"][0]["geometry"])

# 2. Fetch aircraft
response = httpx.get(URL, headers=HEADERS, timeout=10)
response.raise_for_status()
aircraft_list = response.json().get("ac", [])

# 3. Filter and print
with_position = 0
inside = 0

for aircraft in aircraft_list:
    lat = aircraft.get("lat")
    lon = aircraft.get("lon")
    if lat is None or lon is None:
        continue
    with_position += 1

    if not aegean.contains(Point(lon, lat)):
        continue
    inside += 1

    icao = aircraft.get("hex")
    flight = (aircraft.get("flight") or "").strip() or "-"
    alt_baro = aircraft.get("alt_baro")
    print(f"{icao}  {flight:<8}  {alt_baro:>6}  {lat:.3f}, {lon:.3f}")

# 4. Summary
print(f"Aircraft found: {len(aircraft_list)} | with position: {with_position} | inside Aegean: {inside}")