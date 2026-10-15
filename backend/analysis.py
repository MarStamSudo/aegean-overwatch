"""Rules and analysis on aircraft data: tags, flights, GNSS quality."""


# readsb dbFlags is a bit field: each bit is a yes/no flag
FLAG_MILITARY = 1

# NIC below this value = degraded GNSS position integrity
LOW_NIC = 7

# A gap longer than this between two positions of the same aircraft = a new flight
FLIGHT_GAP_S = 20 * 60

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

