import { useEffect, useState } from "react";
import { MapContainer, TileLayer, CircleMarker, Popup, Polyline, useMapEvents } from "react-leaflet";
import "leaflet/dist/leaflet.css";

const API_URL = "http://127.0.0.1:8000";
const REFRESH_MS = 15000;

// Listens for clicks on the empty map and reports them
function MapClickHandler({ onMapClick }) {
  useMapEvents({ click: onMapClick });
  return null;
}

export default function App() {
  const [aircraft, setAircraft] = useState([]);
  const [selected, setSelected] = useState(null);
  const [track, setTrack] = useState([]);

  // Load the latest positions now, then every 15 seconds
  useEffect(() => {
    async function load() {
      try {
        const res = await fetch(`${API_URL}/api/aircraft/latest`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        setAircraft(await res.json());
      } catch (err) {
        console.error("Failed to load aircraft:", err);
      }
    }
    load();
    const id = setInterval(load, REFRESH_MS);
    return () => clearInterval(id);
  }, []);

  // When an aircraft is selected, load its track (and refresh it with new data)
  useEffect(() => {
    if (!selected) {
      setTrack([]);
      return;
    }
    fetch(`${API_URL}/api/aircraft/${selected}/track?minutes=60`)
      .then((res) => (res.ok ? res.json() : []))
      .then((rows) => setTrack(rows.map((p) => [p.lat, p.lon])))
      .catch(() => setTrack([]));
  }, [selected, aircraft]);

  return (
    <div className="app">
      <header className="topbar">
        AEGEAN OVERWATCH
        <span>{aircraft.length} aircraft</span>
      </header>

      <MapContainer center={[38.5, 25.0]} zoom={7} className="map">
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <MapClickHandler onMapClick={() => setSelected(null)} />

        {track.length > 1 && (
          <Polyline positions={track} pathOptions={{ color: "#38bdf8", weight: 2 }} />
        )}

        {aircraft.map((a) => {
          const isSelected = a.icao === selected;
          return (
              <CircleMarker
              key={a.icao}
              center={[a.lat, a.lon]}
              radius={isSelected ? 7 : 5}
              bubblingMouseEvents={false}
              pathOptions={{ color: isSelected ? "#facc15" : "#22c55e", fillOpacity: 0.9 }}
              eventHandlers={{ click: () => setSelected(a.icao) }}
            >
              <Popup>
                <strong>{a.flight || "-"}</strong> ({a.icao})<br />
                Altitude: {a.on_ground ? "ground" : `${a.alt_baro ?? "-"} ft`}<br />
                Speed: {a.gs != null ? `${Math.round(a.gs)} kt` : "-"}
              </Popup>
            </CircleMarker>
          );
        })}
      </MapContainer>
    </div>
  );
}