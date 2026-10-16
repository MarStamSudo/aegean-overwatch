"""Rules and analysis on aircraft data: tags, flights, GNSS quality."""

from itertools import groupby

# readsb dbFlags is a bit field: each bit is a yes/no flag
FLAG_MILITARY = 1

# NIC below this value = degraded GNSS position integrity
LOW_NIC = 7

# A gap longer than this between two positions of the same aircraft = a new flight
FLIGHT_GAP_S = 20 * 60

# Loitering: at least this much turning (degrees) within this time window = an orbit
LOITER_WINDOW_S = 20 * 60
LOITER_MIN_TURN = 360
# Don't trust a turn measured across a gap longer than this
MAX_TURN_GAP_S = 120

EMERGENCY_SQUAWKS = {
    "7500": "hijack",
    "7600": "radio failure",
    "7700": "emergency",
}


def classify(aircraft):
    """Return a list of tags for one aircraft, e.g. ["military"] or ["emergency"]."""
    tags = []

    db_flags = aircraft.get("db_flags") or 0
    if db_flags & FLAG_MILITARY:
        tags.append("military")

    if aircraft.get("squawk") in EMERGENCY_SQUAWKS:
        tags.append("emergency")

    return tags


def emergency_reason(aircraft):
    """Human-readable reason for an emergency squawk, or None."""
    return EMERGENCY_SQUAWKS.get(aircraft.get("squawk"))


def split_flights(points, max_gap_s=FLIGHT_GAP_S):
    """Split the positions of ONE aircraft (sorted by ts) into separate flights.

    A new flight starts when:
    - there is a gap longer than max_gap_s between two positions, or
    - the callsign changes (a missing callsign is NOT a change).
    """
    flights = []
    current = []

    for p in points:
        if current:
            prev = current[-1]
            long_gap = p["ts"] - prev["ts"] > max_gap_s
            callsign_changed = bool(
                p.get("flight") and prev.get("flight") and p["flight"] != prev["flight"]
            )
            if long_gap or callsign_changed:
                flights.append(current)
                current = []
        current.append(p)

    if current:
        flights.append(current)
    return flights


def summarize_flight(icao, points):
    """One-line summary of a flight: who, when, how many positions, how many with low NIC."""
    callsign = next((p["flight"] for p in points if p.get("flight")), None)
    low_nic = sum(1 for p in points if p.get("nic") is not None and p["nic"] < LOW_NIC)
    return {
        "icao": icao,
        "flight": callsign,
        "start": points[0]["ts"],
        "end": points[-1]["ts"],
        "positions": len(points),
        "low_nic": low_nic,
    }

def turn_angle(from_deg, to_deg):
    """Signed smallest turn from one heading to another, in degrees (-180..180).
    Positive = right turn (clockwise), negative = left turn."""
    return (to_deg - from_deg + 540) % 360 - 180


def detect_loiters(points, window_s=LOITER_WINDOW_S, min_turn=LOITER_MIN_TURN):
    """Find orbits / holding patterns in ONE flight (positions sorted by ts).

    A position belongs to a loiter if, inside some window of window_s seconds
    that contains it, the aircraft turned at least min_turn degrees in total
    (signed: left and right turns cancel out, so zig-zags don't count).
    Returns a list of events: {"start", "end", "turn_deg", "lat", "lon"}.
    """
    n = len(points)
    if n < 2:
        return []

    # 1. Cumulative signed turn up to each position
    cum = [0.0] * n
    for k in range(1, n):
        prev, p = points[k - 1], points[k]
        turn = 0.0
        if (
            prev.get("track") is not None
            and p.get("track") is not None
            and p["ts"] - prev["ts"] <= MAX_TURN_GAP_S
        ):
            turn = turn_angle(prev["track"], p["track"])
        cum[k] = cum[k - 1] + turn

    # 2. Sliding window: mark every position inside a window with enough turning
    in_loiter = [False] * n
    i = 0
    for j in range(n):
        while points[j]["ts"] - points[i]["ts"] > window_s:
            i += 1
        if abs(cum[j] - cum[i]) >= min_turn:
            for k in range(i, j + 1):
                in_loiter[k] = True

    # 3. Merge consecutive marked positions into events
    events = []
    k = 0
    while k < n:
        if not in_loiter[k]:
            k += 1
            continue
        start = k
        while k < n and in_loiter[k]:
            k += 1
        segment = points[start:k]
        events.append({
            "start": segment[0]["ts"],
            "end": segment[-1]["ts"],
            "turn_deg": round(abs(cum[k - 1] - cum[start])),
            "lat": sum(p["lat"] for p in segment) / len(segment),
            "lon": sum(p["lon"] for p in segment) / len(segment),
        })
    return events

def find_loiter_events(rows):
    """Find orbits in the positions of MANY aircraft (rows sorted by icao, ts).

    Each event also carries its aircraft, callsign and the start/end of the
    whole flight it belongs to, so the map can show the full flight.
    Newest events first.
    """
    events = []
    for icao, points in groupby(rows, key=lambda r: r["icao"]):
        for flight in split_flights(list(points)):
            callsign = next((p["flight"] for p in flight if p.get("flight")), None)
            for event in detect_loiters(flight):
                events.append({
                    **event,
                    "icao": icao,
                    "flight": callsign,
                    "flight_start": flight[0]["ts"],
                    "flight_end": flight[-1]["ts"],
                })
    events.sort(key=lambda e: e["start"], reverse=True)
    return events

