import httpx

HEADERS = { "User-Agent": "aegean-overwatch/0.1 (+https://github.com/MarStamSudo/aegean-overwatch)" }

URL = "https://api.adsb.lol/v2/point/38.3/25.0/250"

response = httpx.get(URL, headers=HEADERS, timeout=10)
print(response.status_code)
print(response.text)