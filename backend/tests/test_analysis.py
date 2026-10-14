from analysis import classify, emergency_reason


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