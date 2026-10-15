from analysis import classify, detect_loiters, emergency_reason, split_flights, summarize_flight, turn_angle

def test_normal_aircraft_has_no_tags():
    aircraft = {"db_flags": 0, "squawk": "1234"}
    assert classify(aircraft) == []


def test_military_flag():
    aircraft = {"db_flags": 1, "squawk": "1234"}
    assert classify(aircraft) == ["military"]


def test_military_flag_combined_with_other_bits():
    # 3 = military (1) + interesting (2)
    aircraft = {"db_flags": 3}
    assert "military" in classify(aircraft)


def test_interesting_but_not_military():
    # 2 = interesting only, NOT military
    aircraft = {"db_flags": 2}
    assert "military" not in classify(aircraft)


def test_emergency_squawk():
    aircraft = {"db_flags": 0, "squawk": "7700"}
    assert classify(aircraft) == ["emergency"]
    assert emergency_reason(aircraft) == "emergency"


def test_hijack_squawk_reason():
    assert emergency_reason({"squawk": "7500"}) == "hijack"


def test_missing_fields_do_not_crash():
    # Real data is dirty: fields can be missing or None
    assert classify({}) == []
    assert classify({"db_flags": None, "squawk": None}) == []

    # --- Flight splitting ---

def p(ts, flight="AEE602", nic=8):
    """Helper: a fake position."""
    return {"ts": ts, "flight": flight, "nic": nic}


def test_continuous_positions_are_one_flight():
    points = [p(0), p(15), p(30), p(45)]
    assert len(split_flights(points)) == 1


def test_long_gap_starts_new_flight():
    # 30 minutes between the 2nd and 3rd position
    points = [p(0), p(15), p(15 + 30 * 60), p(15 + 30 * 60 + 15)]
    flights = split_flights(points)
    assert len(flights) == 2
    assert len(flights[0]) == 2
    assert len(flights[1]) == 2


def test_short_gap_does_not_split():
    # 5 minutes gap: still the same flight
    points = [p(0), p(5 * 60)]
    assert len(split_flights(points)) == 1


def test_callsign_change_starts_new_flight():
    points = [p(0, "AEE602"), p(15, "AEE602"), p(30, "AEE603")]
    assert len(split_flights(points)) == 2


def test_missing_callsign_does_not_split():
    points = [p(0, "AEE602"), p(15, None), p(30, "AEE602")]
    assert len(split_flights(points)) == 1


def test_no_points_no_flights():
    assert split_flights([]) == []


def test_summarize_flight():
    points = [p(100, None, 8), p(115, "QTR85Y", 0), p(130, "QTR85Y", 0)]
    summary = summarize_flight("06a063", points)
    assert summary == {
        "icao": "06a063",
        "flight": "QTR85Y",
        "start": 100,
        "end": 130,
        "positions": 3,
        "low_nic": 2,
    }

    # --- Loitering ---

def tp(ts, track):
    """Helper: a fake position with a heading."""
    return {"ts": ts, "track": track, "lat": 38.0, "lon": 25.0}


def test_turn_angle_simple():
    assert turn_angle(90, 120) == 30    # right
    assert turn_angle(120, 90) == -30   # left


def test_turn_angle_wraps_around_north():
    assert turn_angle(350, 10) == 20    # 20 right, NOT 340 left
    assert turn_angle(10, 350) == -20


def test_straight_flight_is_not_loiter():
    points = [tp(i * 15, 90) for i in range(80)]  # 20 minutes heading east
    assert detect_loiters(points) == []


def test_full_circle_is_loiter():
    # turning 30 degrees right every 15 s: 13 turns = 390 degrees in ~3 minutes
    points = [tp(i * 15, (i * 30) % 360) for i in range(14)]
    events = detect_loiters(points)
    assert len(events) == 1
    assert events[0]["turn_deg"] == 390


def test_zigzag_is_not_loiter():
    # right 60, left 60, right 60... the turns cancel out
    points = [tp(i * 15, 60 if i % 2 == 0 else 120) for i in range(80)]
    assert detect_loiters(points) == []


def test_slow_turn_outside_window_is_not_loiter():
    # 30 degrees every 2 minutes: only 300 degrees fit in any 20-minute window
    points = [tp(i * 120, (i * 30) % 360) for i in range(20)]
    assert detect_loiters(points) == []


def test_missing_track_does_not_crash():
    points = [{"ts": i * 15, "track": None, "lat": 38.0, "lon": 25.0} for i in range(10)]
    assert detect_loiters(points) == []