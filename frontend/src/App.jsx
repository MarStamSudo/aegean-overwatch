import { useEffect, useRef, useState } from "react";
import { MapContainer, TileLayer, CircleMarker, Popup, Polyline, useMap, useMapEvents } from "react-leaflet";
import "leaflet/dist/leaflet.css";

const API_URL = "http://127.0.0.1:8000";
const REFRESH_MS = 15000;
const LOW_NIC = 7;      // same threshold as the backend
const MAX_GAP_S = 600;  // break the track line if there is no data for 10 minutes

const COLOR_GPS_OK = "#38bdf8";
const COLOR_GPS_BAD = "#ef4444";

// Marker color by priority: emergency > military > normal
function markerColor(a) {
  if (a.tags?.includes("emergency")) return "#ef4444"; // red
  if (a.tags?.includes("military")) return "#f97316";  // orange
  return "#22c55e";                                     // green
}

// Split a track into colored pieces: blue where GPS is OK, red where it is degraded.
// Also break the line when there is a long gap in the data (e.g. two separate flights).
function buildSegments(points) {
  const segments = [];
  let current = null;

  for (let i = 1; i < points.length; i++) {
    const prev = points[i - 1];
    const p = points[i];

    if (p.ts - prev.ts > MAX_GAP_S) {
      current = null; // gap: start a new line later
      continue;
    }

    const degraded = p.nic != null && p.nic < LOW_NIC;
    const color = degraded ? COLOR_GPS_BAD : COLOR_GPS_OK;

    if (!current || current.color !== color) {
      current = { color, positions: [[prev.lat, prev.lon]] };
      segments.push(current);
    }
    current.positions.push([p.lat, p.lon]);
  }
  return segments;
}

function formatTime(ts) {
  return new Date(ts * 1000).toLocaleString("el-GR", {
    day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit",
  });
}

// Listens for clicks on the empty map and reports them
function MapClickHandler({ onMapClick }) {
  useMapEvents({ click: onMapClick });
  return null;
}

// Zooms the map to a track, once per selected aircraft
function FitToTrack({ points, fitKey }) {
  const map = useMap();
  const fitted = useRef(null);
  useEffect(() => {
    if (points.length > 1 && fitted.current !== fitKey) {
      map.fitBounds(points.map((p) => [p.lat, p.lon]), { padding: [40, 40] });
      fitted.current = fitKey;
    }
  }, [points, fitKey, map]);
  return null;
}

// Tells Leaflet to recalculate its size when the layout changes (panel opens/closes)
function ResizeOnChange({ trigger }) {
  const map = useMap();
  useEffect(() => {
    map.invalidateSize();
  }, [trigger, map]);
  return null;
}

function HistoryPanel({ selected, onSelect, hours, onHoursChange }) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState([]);

  // Search 300 ms after the user stops typing (debounce)
  useEffect(() => {
    const id = setTimeout(() => {
      fetch(`${API_URL}/api/history/aircraft?hours=${hours}&q=${encodeURIComponent(q)}`)
        .then((res) => (res.ok ? res.json() : []))
        .then(setResults)
        .catch(() => setResults([]));
    }, 300);
    return () => clearTimeout(id);
  }, [q, hours]);

  return (
    <aside className="panel">
      <input
        className="search"
        placeholder="Search callsign or ICAO..."
        value={q}
        onChange={(e) => setQ(e.target.value)}
      />
      <select value={hours} onChange={(e) => onHoursChange(Number(e.target.value))}>
        <option value={6}>Last 6 hours</option>
        <option value={24}>Last 24 hours</option>
        <option value={72}>Last 3 days</option>
        <option value={168}>Last 7 days</option>
      </select>

      <div className="legend">
        <span><i style={{ background: COLOR_GPS_OK }} />GPS OK</span>
        <span><i style={{ background: COLOR_GPS_BAD }} />GPS degraded (NIC &lt; {LOW_NIC})</span>
      </div>

      <ul className="results">
        {results.map((r) => {
          const lowPct = Math.round((100 * r.low_nic) / r.positions);
          return (
            <li
              key={r.icao}
              className={r.icao === selected ? "active" : ""}
              onClick={() => onSelect(r.icao)}
            >
              <div className="row">
                <strong>{r.flight || "-"}</strong>
                <span>{r.icao}</span>
              </div>
              <div className="row small">
                <span>{formatTime(r.first_seen)} – {formatTime(r.last_seen)}</span>
                <span className={lowPct > 0 ? "bad" : ""}>{lowPct}% low NIC</span>
              </div>
            </li>
          );
        })}
        {results.length === 0 && <li className="empty">No aircraft found</li>}
      </ul>
    </aside>
  );
}

export default function App() {
  const [mode, setMode] = useState("live"); // "live" or "history"
  const [aircraft, setAircraft] = useState([]);
  const [selected, setSelected] = useState(null);
  const [track, setTrack] = useState([]);
  const [hours, setHours] = useState(24);

  // Live: load the latest positions now, then every 15 seconds
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

  // Load the track of the selected aircraft (last hour in live mode, longer in history mode)
  useEffect(() => {
    if (!selected) {
      setTrack([]);
      return;
    }
    const minutes = mode === "history" ? hours * 60 : 60;
    fetch(`${API_URL}/api/aircraft/${selected}/track?minutes=${minutes}`)
      .then((res) => (res.ok ? res.json() : []))
      .then(setTrack)
      .catch(() => setTrack([]));
  }, [selected, mode, hours, aircraft]);

  function switchMode(newMode) {
    setMode(newMode);
    setSelected(null);
  }

  const segments = buildSegments(track);
  const lastPoint = track.length > 0 ? track[track.length - 1] : null;
  const militaryCount = aircraft.filter((a) => a.tags?.includes("military")).length;
  const emergencyCount = aircraft.filter((a) => a.tags?.includes("emergency")).length;

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          AEGEAN OVERWATCH
          <nav className="tabs">
            <button className={mode === "live" ? "active" : ""} onClick={() => switchMode("live")}>Live</button>
            <button className={mode === "history" ? "active" : ""} onClick={() => switchMode("history")}>History</button>
          </nav>
        </div>
        {mode === "live" && (
          <span>
            {aircraft.length} aircraft · {militaryCount} military · {emergencyCount} emergency
          </span>
        )}
      </header>

      <div className="content">
        {mode === "history" && (
          <HistoryPanel
            selected={selected}
            onSelect={setSelected}
            hours={hours}
            onHoursChange={setHours}
          />
        )}

        <MapContainer center={[38.5, 25.0]} zoom={7} className="map">
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <ResizeOnChange trigger={mode} />
          {mode === "live" && <MapClickHandler onMapClick={() => setSelected(null)} />}
          {mode === "history" && <FitToTrack points={track} fitKey={selected} />}

          {segments.map((s, i) => (
            <Polyline key={i} positions={s.positions} pathOptions={{ color: s.color, weight: 3 }} />
          ))}

          {mode === "live" &&
            aircraft.map((a) => {
              const isSelected = a.icao === selected;
              return (
                <CircleMarker
                  key={a.icao}
                  center={[a.lat, a.lon]}
                  radius={isSelected ? 7 : 5}
                  bubblingMouseEvents={false}
                  pathOptions={{ color: isSelected ? "#facc15" : markerColor(a), fillOpacity: 0.9 }}
                  eventHandlers={{ click: () => setSelected(a.icao) }}
                >
                  <Popup>
                    <strong>{a.flight || "-"}</strong> ({a.icao})<br />
                    Altitude: {a.on_ground ? "ground" : `${a.alt_baro ?? "-"} ft`}<br />
                    Speed: {a.gs != null ? `${Math.round(a.gs)} kt` : "-"}<br />
                    GPS integrity (NIC): {a.nic ?? "-"}
                    {a.tags?.includes("military") && (<><br /><strong>Military aircraft</strong></>)}
                    {a.emergency_reason && (<><br /><strong>Squawk {a.squawk}: {a.emergency_reason}</strong></>)}
                  </Popup>
                </CircleMarker>
              );
            })}

          {mode === "history" && lastPoint && (
            <CircleMarker
              center={[lastPoint.lat, lastPoint.lon]}
              radius={6}
              pathOptions={{ color: "#facc15", fillOpacity: 0.9 }}
            />
          )}
        </MapContainer>
      </div>
    </div>
  );
}