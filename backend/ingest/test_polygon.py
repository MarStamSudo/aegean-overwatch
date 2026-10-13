import json
from pathlib import Path

from shapely.geometry import shape, Point

GEOJSON_PATH = Path(__file__).parent.parent / "data" / "aegean.geojson"

with open(GEOJSON_PATH, encoding="utf-8") as f:
    data = json.load(f)

print(data["features"][0]["geometry"]["type"])

# Build a shapely polygon from the GeoJSON geometry
aegean = shape(data["features"][0]["geometry"])

# Known test points (GeoJSON / shapely order: lon, lat)
naxos = Point(25.38, 37.10)
izmir = Point(27.14, 38.42)

print(f"Naxos inside: {aegean.contains(naxos)}")
print(f"Izmir inside: {aegean.contains(izmir)}")