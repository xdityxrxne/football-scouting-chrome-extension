from __future__ import annotations

from datetime import date

import pytest

from player_extractor import config, derive

# --- age group ---------------------------------------------------------------

@pytest.mark.parametrize("dob,expected", [
    (date(2012, 1, 1), "U15"),
    (date(2011, 11, 15), "U15"),   # turns 15 tomorrow
    (date(2011, 11, 14), "U18"),   # 15th birthday today
    (date(2008, 11, 15), "U18"),   # turns 18 tomorrow
    (date(2008, 11, 14), "U21"),   # 18 today
    (date(2005, 11, 15), "U21"),   # turns 21 tomorrow
    (date(2005, 11, 14), "Senior"),  # 21 today
    (date(1990, 6, 29), "Senior"),
])
def test_age_group(dob, expected):
    assert derive.age_group(dob, date(2026, 11, 14)) == expected


def test_age_group_blank_dob():
    assert derive.age_group(None, date(2026, 11, 14)) is None


# --- dates & seasons ---------------------------------------------------------

def test_parse_date():
    assert derive.parse_date("1999-02-08 (27 -yrs-old)") == date(1999, 2, 8)
    assert derive.parse_date("04/07/2023") == date(2023, 7, 4)
    assert derive.parse_date("-") is None
    assert derive.parse_date("") is None
    assert derive.parse_date("1999-13-40") is None


def test_season_formatting():
    assert derive.format_season("2026/27") == "2026/27"
    assert derive.format_season("2026/2027") == "2026/27"
    assert derive.format_season("2026-27") == "2026/27"
    assert derive.format_season("1999/00") == "1999/00"
    assert derive.format_season("2018") == "2018"
    assert derive.format_season("") is None
    assert derive.format_season("abc") is None


def test_current_season():
    assert derive.current_season(date(2026, 11, 14)) == "2026/27"
    assert derive.current_season(date(2026, 6, 30)) == "2025/26"
    assert derive.current_season(date(2026, 7, 1)) == "2026/27"
    assert derive.season_is_current("2026/27", date(2026, 11, 14))
    assert derive.season_is_current("2026", date(2026, 11, 14))
    assert not derive.season_is_current("2025/26", date(2026, 11, 14))


# --- contract & availability -------------------------------------------------

def test_contract_month_only():
    assert derive.parse_contract_expiry("2027/06") == (date(2027, 6, 30), "contract month only")
    assert derive.parse_contract_expiry("2024/02") == (date(2024, 2, 29), "contract month only")
    assert derive.parse_contract_expiry("2026-12-31") == (date(2026, 12, 31), None)
    assert derive.parse_contract_expiry("-") == (None, None)
    d, note = derive.parse_contract_expiry("soon")
    assert d is None and "not understood" in note


def test_availability_rules():
    today = date(2026, 11, 14)
    assert derive.availability(date(2027, 6, 30), True, today) == ("Under contract", None)
    assert derive.availability(date(2026, 11, 14), False, today) == ("Under contract", None)   # expires today
    assert derive.availability(date(2026, 6, 30), False, today) == ("Available", None)
    assert derive.availability(date(2026, 6, 30), True, today) == (None, "contract date may be out of date")
    assert derive.availability(None, True, today) == (None, None)


# --- positions ---------------------------------------------------------------

def test_position_mapping():
    assert derive.map_position("Striker") == ("ST", None)
    assert derive.map_position("right back") == ("RB", None)
    assert derive.map_position("Defender") == (None, "position too generic: Defender")
    assert derive.map_position("Sweeper") == (None, "position not mapped: Sweeper")
    assert derive.map_position(None) == (None, None)


def test_map_positions_primary_and_secondary():
    primary, secondary, notes = derive.map_positions(["Attacking Midfielder", "Centre Midfielder", "Forward"])
    assert primary == "CAM"
    assert secondary == "CM"
    assert notes == ["secondary position too generic: Forward"]
    primary, secondary, notes = derive.map_positions(["Defender"])
    assert primary is None and secondary is None
    assert notes == ["primary position too generic: Defender"]


def test_all_mapped_codes_are_valid():
    assert set(config.POSITION_MAP.values()) <= set(config.POSITION_CODES)


# --- nationality / birthplace / foot ----------------------------------------

def test_nationality_labels():
    assert derive.join_nationalities(["England"]) == "English"
    assert derive.join_nationalities(["England", "Portugal"]) == "English / Portugal"
    assert derive.join_nationalities(["Scotland", "Scotland"]) == "Scottish"
    assert derive.join_nationalities(["Northern Ireland"]) == "Northern Irish"
    assert derive.join_nationalities([]) is None


def test_place_of_birth():
    assert derive.place_of_birth("England (Taunton)") == "Taunton, England"
    assert derive.place_of_birth("England") == "England"
    assert derive.place_of_birth(None) is None


def test_preferred_foot():
    assert derive.preferred_foot("Right") == ("Right", None)
    assert derive.preferred_foot("both") == ("Both", None)
    assert derive.preferred_foot("Head") == (None, "preferred foot not understood: Head")


# --- units -------------------------------------------------------------------

def test_height_weight():
    assert derive.split_height_weight("175 cm / 68 kg") == (175, 68)
    assert derive.split_height_weight("172 cm / -") == (172, None)     # missing weight
    assert derive.split_height_weight("- / 60 kg") == (None, 60)
    assert derive.split_height_weight(None) == (None, None)
    assert derive.height_cm("1.75 m") == 175
    assert derive.height_cm("5 ft 9 in") == 175
    assert derive.weight_kg("150 lbs") == 68


# --- market value ------------------------------------------------------------

def test_market_value(monkeypatch):
    assert derive.parse_market_value("100 k €") == (100000, "EUR")
    assert derive.parse_market_value("£2.5M") == (2500000, "GBP")
    assert derive.market_value_gbp("100 k €") == (None, "market value (site): 100 k €")
    assert derive.market_value_gbp("£250 k") == (250000, None)
    assert derive.market_value_gbp(None) == (None, None)
    monkeypatch.setattr(config, "MARKET_VALUE_EUR_TO_GBP_RATE", 0.85)
    assert derive.market_value_gbp("100 k €") == (85000, "market value converted from 100 k € at 0.85")


# --- names -------------------------------------------------------------------

def test_name_split():
    assert derive.split_display_name("Daphne van Domselaar") == ("Daphne", "van Domselaar")
    assert derive.split_display_name("Lucy Bronze") == ("Lucy", "Bronze")
    assert derive.split_display_name("Ronaldinho") == (None, "Ronaldinho")
    assert derive.name_split_note("Lucia Roberta Tough Bronze", "Bronze") is None
    assert derive.name_split_note("Alessia Mia Teresa Russo", "Russo") is None
    assert derive.name_split_note("Maria Jose Silva Santos", "Silva") == "check name split"


# --- missing / review --------------------------------------------------------

def test_missing_and_review():
    row = {f: "x" for f in config.MISSING_TRACKED_FIELDS}
    assert derive.missing_fields(row) == []
    assert derive.needs_review(row, []) is False
    row["Weight (kg)"] = None
    assert derive.missing_fields(row) == ["Weight (kg)"]
    row["Homegrown"] = None
    row["Agent"] = None
    assert derive.missing_fields(row) == ["Weight (kg)"]   # never-published fields are not reported
    assert derive.needs_review(row, []) is False         # weight is not a key field
    row["Date of birth"] = ""
    assert derive.needs_review(row, []) is True
    assert derive.needs_review({f: "x" for f in config.MISSING_TRACKED_FIELDS}, ["anything"]) is True
