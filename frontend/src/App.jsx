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
// Also break the line when there is a long gap in the data.
function buildSegments(points) {
  const segments = [];
  let current = null;

  for (let i = 1; i < points.length; i++) {
    const prev = points[i - 1];
    const p = points[i];

    if (p.ts - prev.ts > MAX_GAP_S) {
      current = null;
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
  return new Date(ts * 1000).toLocaleString("en-GB", {
    day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit",
  });
}

function flightKey(f) {
  return `${f.icao}-${f.start}`;
}

// Listens for clicks on the empty map and reports them
function MapClickHandler({ onMapClick }) {
  useMapEvents({ click: onMapClick });
  return null;
}

// Zooms the map to a track, once per track (only when that track's data has arrived)
function FitToTrack({ points, fitKey }) {
  const map = useMap();
  const fitted = useRef(null);
  useEffect(() => {
    if (fitKey && points.length > 1 && fitted.current !== fitKey) {
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

function HistoryPanel({ selectedFlight, onSelect, hours, onHoursChange }) {
  const [q, setQ] = useState("");
  const [flights, setFlights] = useState([]);

  // Search 300 ms after the user stops typing (debounce)
  useEffect(() => {
    const id = setTimeout(() => {
      fetch(`${API_URL}/api/history/flights?hours=${hours}&q=${encodeURIComponent(q)}`)
        .then((res) => (res.ok ? res.json() : []))
        .then(setFlights)
        .catch(() => setFlights([]));
    }, 300);
    return () => clearTimeout(id);
  }, [q, hours]);

  const selectedKey = selectedFlight ? flightKey(selectedFlight) : null;

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

      <div className="small">{flights.length} flights</div>

      <ul className="results">
        {flights.map((f) => {
          const key = flightKey(f);
          const lowPct = Math.round((100 * f.low_nic) / f.positions);
          const minutes = Math.max(1, Math.round((f.end - f.start) / 60));
          return (
            <li key={key} className={key === selectedKey ? "active" : ""} onClick={() => onSelect(f)}>
              <div className="row">
                <strong>{f.flight || "-"}</strong>
                <span>{f.icao}</span>
              </div>
              <div className="row small">
                <span>{formatTime(f.start)} – {formatTime(f.end)} ({minutes} min)</span>
                <span className={lowPct > 0 ? "bad" : ""}>{lowPct}% low NIC</span>
              </div>
            </li>
          );
        })}
        {flights.length === 0 && <li className="empty">No flights found</li>}
      </ul>
    </aside>
  );
}

export default function App() {
  const [mode, setMode] = useState("live"); // "live" or "history"
  const [aircraft, setAircraft] = useState([]);
  const [selected, setSelected] = useState(null);             // live: selected aircraft (icao)
  const [selectedFlight, setSelectedFlight] = useState(null); // history: selected flight
  const [track, setTrack] = useState({ key: null, points: [] });
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

  // Which track to show: one flight (history) or the last hour of an aircraft (live)
  let trackKey = null;
  let trackUrl = null;
  if (mode === "history" && selectedFlight) {
    trackKey = flightKey(selectedFlight);
    trackUrl = `${API_URL}/api/aircraft/${selectedFlight.icao}/track?start=${selectedFlight.start}&end=${selectedFlight.end}`;
  } else if (mode === "live" && selected) {
    trackKey = selected;
    trackUrl = `${API_URL}/api/aircraft/${selected}/track?minutes=60`;
  }

  // Load the track (and refresh it in live mode as new data arrives)
  const liveTick = mode === "live" ? aircraft : null;
  useEffect(() => {
    if (!trackUrl) {
      setTrack({ key: null, points: [] });
      return;
    }
    let cancelled = false; // becomes true if the selection changes before the answer arrives

    fetch(trackUrl)
      .then((res) => (res.ok ? res.json() : []))
      .then((rows) => {
        if (!cancelled) setTrack({ key: trackKey, points: rows });
      })
      .catch(() => {
        if (!cancelled) setTrack({ key: trackKey, points: [] });
      });

    return () => {
      cancelled = true;
    };
  }, [trackKey, trackUrl, liveTick]);

  function switchMode(newMode) {
    setMode(newMode);
    setSelected(null);
    setSelectedFlight(null);
  }

  const segments = buildSegments(track.points);
  const lastPoint = track.points.length > 0 ? track.points[track.points.length - 1] : null;
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
            selectedFlight={selectedFlight}
            onSelect={setSelectedFlight}
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
          {mode === "history" && <FitToTrack points={track.points} fitKey={track.key} />}

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