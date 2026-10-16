from ingest.alerts import new_alerts


def ac(db_flags=1, squawk="1234"):
    """Helper: a fake aircraft as it comes from the API."""
    return {
        "hex": "468078", "flight": "HAF354R", "dbFlags": db_flags, "squawk": squawk,
        "lat": 38.7, "lon": 23.6, "alt_baro": 21000, "gs": 250,
    }


def test_military_aircraft_alerts_only_once():
    sent = {}
    first = new_alerts([ac()], sent, now=1000)
    assert len(first) == 1
    assert "Military" in first[0]
    # 15 seconds later, same aircraft: no new message
    assert new_alerts([ac()], sent, now=1015) == []


def test_alert_again_after_cooldown():
    sent = {}
    new_alerts([ac()], sent, now=0)
    assert len(new_alerts([ac()], sent, now=7 * 3600)) == 1


def test_normal_aircraft_no_alert():
    assert new_alerts([ac(db_flags=None)], {}, now=0) == []


def test_emergency_squawk_alert():
    messages = new_alerts([ac(db_flags=None, squawk="7700")], {}, now=0)
    assert len(messages) == 1
    assert "7700" in messages[0]