import httpx



HEADERS = { "User-Agent": "aegean-overwatch/0.1 (+https://github.com/MarStamSudo/aegean-overwatch)" }

URL = "https://api.adsb.lol/v2/point/38.3/25.0/250"

response = httpx.get(URL, headers=HEADERS, timeout=10)
response.raise_for_status()


data = response.json()
aircraft_list = data.get("ac", [])

print(f"Aircrafts that have been found: {len(aircraft_list)}")

for aircraft in aircraft_list:
    lat = aircraft.get("lat")
    lon = aircraft.get("lon")
    if lat is None or lon is None:
        continue
    hex_air = aircraft.get("hex")
    flight = (aircraft.get("flight") or "").strip() or "-"
    alt_baro = aircraft.get("alt_baro")
    print(f"This aircraft is in: {flight}, {hex_air}, {alt_baro}, {lat}, {lon}")