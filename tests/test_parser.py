"""Parser checked against the real values in the saved sample pages (see FIELD_MAP.md)."""
from __future__ import annotations

from datetime import date

import pytest
from conftest import load_sample

from player_extractor.models import Spell
from player_extractor.parser import canonical_player_url, parse_player, parse_squad_links, player_id_from_url

RUSSO = "player_wsl_star_alessia_russo.html"
BRONZE = "player_dual_nationality_lucy_bronze.html"
LITTLE = "player_long_career_kim_little.html"
SYME = "player_championship_emily_syme.html"
MCDONALD = "player_sparse_youth_neeve_mcdonald.html"


def parse(name: str, today: date):
    url, html = load_sample(name)
    return parse_player(html, url, today=today)


def spell(spells: list[Spell], club: str, from_season: str) -> Spell:
    for sp in spells:
        if sp.club == club and sp.from_season == from_season:
            return sp
    raise AssertionError(f"no spell {club} from {from_season} in {[(s.club, s.from_season, s.to_season) for s in spells]}")


# ---------------------------------------------------------------------------

def test_url_helpers():
    assert player_id_from_url("https://www.playmakerstats.com/player/alessia-russo/482425") == "482425"
    assert player_id_from_url("/player/emily-mutch/729112?epoca_id=156") == "729112"
    assert player_id_from_url("/player/kim-little/132319/career") == "132319"
    assert player_id_from_url("https://www.playmakerstats.com/team/arsenal/16654") is None
    assert canonical_player_url("/player/emily-mutch/729112?epoca_id=156") == "https://www.playmakerstats.com/player/emily-mutch/729112"
    assert canonical_player_url("https://www.playmakerstats.com/player/kim-little/132319/results?x=1") == "https://www.playmakerstats.com/player/kim-little/132319"


def test_russo(today):
    rec, spells = parse(RUSSO, today)
    assert rec.player_id == "482425"
    assert rec.url == "https://www.playmakerstats.com/player/alessia-russo/482425"
    assert (rec.first_name, rec.last_name) == ("Alessia", "Russo")
    assert rec.full_name == "Alessia Mia Teresa Russo"
    assert rec.known_as == "Alessia Russo"
    assert rec.date_of_birth == date(1999, 2, 8)
    assert rec.age_group == "Senior"
    assert rec.nationality == "English"
    assert rec.place_of_birth == "England"
    assert rec.primary_position == "ST"
    assert rec.secondary_positions is None
    assert rec.preferred_foot == "Right"
    assert (rec.height_cm, rec.weight_kg) == (175, 68)
    assert rec.current_club == "Arsenal"
    assert rec.contract_expiry is None
    assert rec.availability is None
    assert rec.market_value_gbp is None
    assert rec.agent is None and rec.homegrown is None
    assert rec.review_reasons == []
    assert not any("market value" in n for n in rec.notes)

    assert [(s.club, s.from_season, s.to_season) for s in spells] == [
        ("Chelsea", "2015/16", "2017"),
        ("North Carolina Tar Heels", "2017", "2018"),
        ("Manchester United", "2020/21", "2022/23"),
        ("Arsenal", "2023/24", "Now"),
    ]
    assert rec.has_current_season_club


def test_bronze_dual_nationality_and_contract(today):
    rec, spells = parse(BRONZE, today)
    assert (rec.first_name, rec.last_name) == ("Lucy", "Bronze")
    assert rec.full_name == "Lucia Roberta Tough Bronze"
    assert rec.known_as == "Lucy Bronze"
    assert rec.date_of_birth == date(1991, 10, 28)
    assert rec.nationality == "English / Portugal"
    assert rec.place_of_birth == "England"
    assert rec.primary_position == "RB"
    assert rec.secondary_positions == "CB"
    assert rec.preferred_foot == "Right"
    assert (rec.height_cm, rec.weight_kg) == (172, 65)
    assert rec.current_club == "Chelsea"
    assert rec.contract_expiry == date(2027, 6, 30)
    assert "contract month only" in rec.notes
    assert rec.availability == "Under contract"
    assert rec.review_reasons == []

    assert len(spells) == 10
    assert spell(spells, "Sunderland", "2007/08").to_season == "2009"
    assert spell(spells, "North Carolina Tar Heels", "2009").to_season == "2009"
    assert spell(spells, "Liverpool", "2012/13").to_season == "2014/15"
    assert spell(spells, "Manchester City", "2014/15").to_season == "2016/17"
    assert spell(spells, "OL Lyonnes", "2017/18").to_season == "2019/20"
    assert spell(spells, "Manchester City", "2019/20").to_season == "2021/22"
    assert spell(spells, "Barcelona", "2022/23").to_season == "2023/24"
    assert spell(spells, "Chelsea", "2024/25").to_season == "Now"


def test_little_stale_contract_market_value_and_loans(today):
    rec, spells = parse(LITTLE, today)
    assert (rec.first_name, rec.last_name) == ("Kim", "Little")
    assert rec.known_as == "Kim Little"
    assert rec.nationality == "Scottish"
    assert rec.primary_position == "CAM"
    assert rec.secondary_positions == "CM"
    assert (rec.height_cm, rec.weight_kg) == (163, 60)
    assert rec.current_club == "Arsenal"
    assert rec.contract_expiry == date(2026, 6, 30)
    # expired contract but still listed for 2026/27 -> blank + review
    assert rec.availability is None
    assert "contract date may be out of date" in rec.review_reasons
    # one market value, in euros -> £ blank, raw value in notes
    assert rec.market_value_gbp is None
    assert [n for n in rec.notes if n.startswith("market value")] == ["market value (site): 100 k €"]

    seattle = spell(spells, "Seattle Reign", "2022")
    assert seattle.loan_from == "Arsenal" and seattle.to_season == "2022"
    melbourne = spell(spells, "Melbourne City", "2016")
    assert melbourne.loan_from == "Seattle Reign"
    assert "loan from Arsenal (2022)" in rec.notes
    assert spell(spells, "Arsenal", "2022/23").to_season == "Now"
    assert spell(spells, "Hibernian", "2006/07").to_season == "2007/08"


def test_syme_birthplace_generic_secondary_and_loan(today):
    rec, spells = parse(SYME, today)
    assert (rec.first_name, rec.last_name) == ("Emily", "Syme")
    assert rec.known_as == "Emily Syme"              # always the header display name
    assert rec.date_of_birth == date(2000, 7, 23)
    assert rec.place_of_birth == "Taunton, England"
    assert rec.primary_position == "CAM"
    assert rec.secondary_positions is None           # "Forward" is generic
    assert "secondary position too generic: Forward" in rec.review_reasons
    assert rec.preferred_foot is None
    assert rec.height_cm is None and rec.weight_kg is None
    assert rec.current_club == "Bristol City"

    sheff = spell(spells, "Sheffield United", "2021/22")
    assert sheff.loan_from == "Aston Villa"
    assert spell(spells, "Aston Villa", "2019/20").to_season == "2021/22"
    assert spell(spells, "Bristol City", "2022/23").to_season == "Now"
    assert spell(spells, "Bristol City", "2016/17").to_season == "2017/18"


def test_mcdonald_sparse_youth(today):
    rec, spells = parse(MCDONALD, today)
    assert (rec.first_name, rec.last_name) == ("Neeve", "McDonald")
    assert rec.date_of_birth is None
    assert rec.age_group is None
    assert rec.primary_position is None
    assert "primary position too generic: Defender" in rec.review_reasons
    assert rec.current_club == "Bristol City"
    assert rec.contract_expiry is None and rec.availability is None
    assert [(s.club, s.from_season, s.to_season) for s in spells] == [("Bristol City", "2026/27", "Now")]


def test_spell_merging_mixed_season_formats(today):
    """A spell may span a YYYY/YY season and a calendar-year season (US leagues); rows arrive newest first."""
    from player_extractor.parser import build_spells
    rows = [
        {"season": "2009/10", "club": "Sunderland", "club_id": "1", "loan_from": None},
        {"season": "2009", "club": "North Carolina", "club_id": "2", "loan_from": None},
        {"season": "2009", "club": "Sunderland", "club_id": "1", "loan_from": None},   # continuation row (blank season on site)
        {"season": "2007/08", "club": "Sunderland", "club_id": "1", "loan_from": None},
    ]
    spells = build_spells(rows, today)
    assert [(s.club, s.from_season, s.to_season) for s in spells] == [
        ("Sunderland", "2007/08", "2009"),
        ("North Carolina", "2009", "2009"),
        ("Sunderland", "2009/10", "2009/10"),
    ]
    # the same club on loan is a separate spell, and the current season becomes "Now"
    rows = [
        {"season": "2026/27", "club": "Arsenal", "club_id": "3", "loan_from": None},
        {"season": "2025", "club": "Seattle", "club_id": "4", "loan_from": "Arsenal"},
        {"season": "2025", "club": "Arsenal", "club_id": "3", "loan_from": None},
    ]
    spells = build_spells(rows, today)
    assert [(s.club, s.from_season, s.to_season, s.loan_from) for s in spells] == [
        ("Arsenal", "2025", "2025", None),
        ("Seattle", "2025", "2025", "Arsenal"),
        ("Arsenal", "2026/27", "Now", None),
    ]
    # a calendar-year season equal to this year also counts as current
    spells = build_spells([{"season": "2026", "club": "Seattle", "club_id": "4", "loan_from": None}], today)
    assert spells[0].to_season == "Now"


def test_page_type_detection():
    from player_extractor.parser import is_player_page, is_team_page
    assert is_player_page(load_sample(RUSSO)[1])
    assert not is_team_page(load_sample(RUSSO)[1])
    assert is_team_page(load_sample("team_arsenal_women.html")[1])
    challenge = "<html><head><title>Just a moment...</title></head><body><h1>www.playmakerstats.com</h1><div id='challenge-running'></div></body></html>"
    assert not is_player_page(challenge) and not is_team_page(challenge)


def test_runner_rejects_non_profile_page(tmp_path):
    import pytest as _pytest

    from player_extractor.excel_store import PlayerStore
    from player_extractor.runner import NotAPlayerPage, RunSummary, process_html
    store = PlayerStore(tmp_path / "p.xlsx")
    with _pytest.raises(NotAPlayerPage):
        process_html(store, "https://www.playmakerstats.com/player/x/1", "<html><h1>www.playmakerstats.com</h1></html>", RunSummary("t", tmp_path))
    assert store.players == []


def test_parser_tolerates_empty_html(today):
    rec, spells = parse_player("<html><body><p>nothing</p></body></html>", "https://www.playmakerstats.com/player/x/1", today=today)
    assert rec.player_id == "1"
    assert rec.first_name is None and rec.current_club is None
    assert spells == []


@pytest.mark.parametrize("name,expected_count,must_include", [
    ("team_arsenal_women.html", 28, "https://www.playmakerstats.com/player/alessia-russo/482425"),
    ("team_bristol_city_women.html", 31, "https://www.playmakerstats.com/player/neeve-mcdonald/3697506"),
])
def test_squad_links(name, expected_count, must_include):
    _, html = load_sample(name)
    links = parse_squad_links(html)
    assert len(links) == expected_count
    assert len(set(links)) == len(links)
    assert must_include in links
    assert all("?" not in u for u in links)
