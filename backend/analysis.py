"""Rules that tag aircraft as interesting (military, emergency, ...)."""

# readsb dbFlags is a bit field: each bit is a yes/no flag
FLAG_MILITARY = 1

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