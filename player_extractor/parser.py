"""
parse_player(html, url) -> (PlayerRecord, [Spell, ...])

Pure: no network, no files. Tolerant of missing sections: anything not found is None.
All selectors and label texts come from config.py.
"""
from __future__ import annotations

import logging
import re
from datetime import date

from bs4 import BeautifulSoup, Tag

from . import config, derive
from .models import PlayerRecord, Spell

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------

def player_id_from_url(url: str) -> str | None:
    m = re.search(config.PLAYER_URL_PATTERN, url or "")
    return m.group(1) if m else None


def team_id_from_url(url: str) -> str | None:
    m = re.search(config.TEAM_URL_PATTERN, url or "")
    return m.group(1) if m else None


def canonical_player_url(url: str) -> str:
    """Strip query/fragment and sub-pages: .../player/slug/123/results?x -> https://site/player/slug/123"""
    m = re.search(r"(/player/[^/?#]+/\d+)", url or "")
    if not m:
        return url
    return config.SITE_BASE_URL + m.group(1)


# ---------------------------------------------------------------------------
# Profile card
# ---------------------------------------------------------------------------

def _text(el: Tag | None) -> str | None:
    return derive.clean(el.get_text(" ", strip=True)) if el is not None else None


def _row_values(row: Tag) -> list[str]:
    """All values in a profile row (one per .card-data__value), using the .text child when present."""
    values: list[str] = []
    for v in row.select(config.SEL_PROFILE_VALUE):
        inner = v.select_one(config.SEL_PROFILE_VALUE_TEXT)
        t = _text(inner if inner is not None else v)
        if t:
            values.append(t)
    if not values:
        # value may be inline text without a value span
        label = row.select_one(config.SEL_PROFILE_LABEL)
        label_text = _text(label) or ""
        whole = _text(row) or ""
        rest = derive.clean(whole[len(label_text):]) if whole.startswith(label_text) else derive.clean(whole)
        if rest:
            values.append(rest)
    return values


def read_profile(soup: BeautifulSoup) -> dict[str, list[str]]:
    """Profile card as {label (lower-case): [values...]}."""
    card = soup.select_one(config.SEL_PROFILE_CARD)
    result: dict[str, list[str]] = {}
    if card is None:
        log.warning("profile card not found")
        return result
    for row in card.select(config.SEL_PROFILE_ROW):
        label = _text(row.select_one(config.SEL_PROFILE_LABEL))
        if not label:
            continue
        result[label.lower()] = _row_values(row)
    return result


def _lookup(profile: dict[str, list[str]], labels: tuple[str, ...]) -> list[str]:
    """Values for the first profile label that equals or starts with one of `labels`."""
    for key, values in profile.items():
        for lab in labels:
            if key == lab or key.startswith(lab + " ") or key.startswith(lab + "/") or key.startswith(lab + " /"):
                return values
    return []


def _first(values: list[str]) -> str | None:
    return values[0] if values else None


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

def read_display_name(soup: BeautifulSoup) -> str | None:
    name_el = soup.select_one(config.SEL_DISPLAY_NAME)
    if name_el is None:
        h1 = soup.select_one("h1")
        return _text(h1)
    for num in name_el.select(config.SEL_SHIRT_NUMBER):
        num.decompose()
    return _text(name_el)


def read_header_club(soup: BeautifulSoup) -> str | None:
    header = soup.select_one(config.SEL_HEADER)
    if header is None:
        return None
    link = header.select_one(config.SEL_HEADER_TEAM_LINK)
    return _text(link)


def read_market_value(soup: BeautifulSoup) -> str | None:
    return _text(soup.select_one(config.SEL_MARKET_VALUE))


# ---------------------------------------------------------------------------
# Career table -> spells
# ---------------------------------------------------------------------------

def _career_rows(soup: BeautifulSoup) -> list[dict[str, str | None]]:
    """Raw rows (newest first) from the club career table: season, club, club_id, loan_from."""
    body = soup.select_one(config.SEL_CAREER_BODY)
    if body is None:
        return []
    table: Tag | None = None
    for section in body.select(config.SEL_CAREER_SECTION):
        if (_text(section) or "").lower() == config.CAREER_SECTION_CLUBS:
            table = section.find_next_sibling(config.SEL_CAREER_TABLE.split(".")[0])
            break
    if table is None:
        table = body.select_one(config.SEL_CAREER_TABLE)
    if table is None:
        return []

    rows: list[dict[str, str | None]] = []
    last_season: str | None = None
    for tr in table.select("tbody tr"):
        tds = tr.find_all("td", recursive=False)
        if len(tds) < 3:
            continue
        season_raw = _text(tds[1])
        season = derive.format_season(season_raw) if season_raw else last_season
        if season_raw and season is None:
            log.warning("season not understood: %r", season_raw)
            continue
        last_season = season
        team_cell = tds[2]
        link = team_cell.select_one(config.SEL_CAREER_TEAM_LINK)
        club = _text(link) if link is not None else _text(team_cell.select_one(config.SEL_PROFILE_VALUE_TEXT))
        if not club:
            continue
        club_id = team_id_from_url(link["href"]) if link is not None and link.has_attr("href") else None
        cell_text = team_cell.get_text(" ", strip=True)
        loan_from = None
        if config.CAREER_LOAN_MARKER in cell_text:
            brackets = [derive.clean(s.get_text()) for s in team_cell.find_all("span")]
            brackets = [b.strip("[]") for b in brackets if b and b.startswith("[")]
            # the squad label ("[Women]") comes first; the parent club is the other bracket
            others = [b for b in brackets if b.lower() not in {"women", "men"} and "universit" not in b.lower()]
            loan_from = others[-1] if others else (link.get("title", "").replace("Loan - ", "").strip() or "loan")
        rows.append({"season": season, "club": club, "club_id": club_id, "loan_from": loan_from})
    return rows


def _season_sort_key(season: str) -> int:
    return int(season[:4])


def build_spells(rows: list[dict[str, str | None]], today: date) -> list[Spell]:
    """Merge consecutive same-club seasons (rows newest first) into spells, oldest first."""
    spells: list[Spell] = []
    for row in reversed(rows):           # oldest first
        same = (
            spells
            and spells[-1].club_id == row["club_id"]
            and spells[-1].club == row["club"]
            and spells[-1].loan_from == row["loan_from"]
        )
        if same:
            spells[-1].to_season = row["season"] or spells[-1].to_season
        else:
            spells.append(Spell(
                club=row["club"] or "",
                club_id=row["club_id"],
                from_season=row["season"] or "",
                to_season=row["season"] or "",
                loan_from=row["loan_from"],
            ))
    for sp in spells:
        if derive.season_is_current(sp.to_season, today):
            sp.to_season = "Now"
    return spells


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def parse_player(html: str, url: str, today: date | None = None) -> tuple[PlayerRecord, list[Spell]]:
    """
    Parse one saved player page. `today` is injectable for tests (defaults to date.today()).
    Never raises on missing sections; unknown values are None and explained in record.notes.
    """
    today = today or date.today()
    soup = BeautifulSoup(html, "lxml")
    url = canonical_player_url(url)
    rec = PlayerRecord(player_id=player_id_from_url(url) or "", url=url)
    if not rec.player_id:
        rec.review_reasons.append("player id not found in URL")

    profile = read_profile(soup)

    # --- names
    display = read_display_name(soup)
    rec.full_name = _first(_lookup(profile, config.LABEL_FULL_NAME)) or display
    rec.first_name, rec.last_name = derive.split_display_name(display or rec.full_name)
    rec.known_as = display
    note = derive.name_split_note(rec.full_name, rec.last_name)
    if note:
        rec.review_reasons.append(note)

    # --- dates
    dob_raw = _first(_lookup(profile, config.LABEL_DOB))
    rec.date_of_birth = derive.parse_date(dob_raw)
    if dob_raw and rec.date_of_birth is None:
        rec.review_reasons.append(f"date of birth not understood: {dob_raw}")
    rec.age_group = derive.age_group(rec.date_of_birth, today)

    # --- nationality / birthplace
    rec.nationality = derive.join_nationalities(_lookup(profile, config.LABEL_NATIONALITY))
    rec.place_of_birth = derive.place_of_birth(_first(_lookup(profile, config.LABEL_BIRTHPLACE)))

    # --- positions
    raw_positions = _lookup(profile, config.LABEL_POSITION)
    rec.primary_position, rec.secondary_positions, pos_notes = derive.map_positions(raw_positions)
    rec.review_reasons.extend(pos_notes)

    # --- foot, height, weight
    rec.preferred_foot, note = derive.preferred_foot(_first(_lookup(profile, config.LABEL_FOOT)))
    if note:
        rec.review_reasons.append(note)
    hw_raw = " ".join(_lookup(profile, config.LABEL_HEIGHT_WEIGHT))
    rec.height_cm, rec.weight_kg = derive.split_height_weight(hw_raw)

    # --- club & contract
    rec.current_club = _first(_lookup(profile, config.LABEL_CURRENT_CLUB)) or read_header_club(soup)
    rec.contract_expiry, note = derive.parse_contract_expiry(_first(_lookup(profile, config.LABEL_CONTRACT)))
    if note:
        (rec.notes if note == "contract month only" else rec.review_reasons).append(note)

    # --- fields the site may add one day
    rec.agent = _first(_lookup(profile, config.LABEL_AGENT))
    rec.homegrown = _first(_lookup(profile, config.LABEL_HOMEGROWN))

    # --- market value
    rec.market_value_gbp, note = derive.market_value_gbp(read_market_value(soup))
    if note:
        rec.notes.append(note)

    # --- career
    spells = build_spells(_career_rows(soup), today)
    rec.has_current_season_club = any(sp.to_season == "Now" for sp in spells)
    for sp in spells:
        if sp.loan_from:
            rec.notes.append(f"loan from {sp.loan_from} ({sp.from_season})")

    # --- availability (needs career info)
    rec.availability, note = derive.availability(rec.contract_expiry, rec.has_current_season_club, today)
    if note:
        rec.review_reasons.append(note)

    return rec, spells


def is_player_page(html: str) -> bool:
    """True only if the HTML contains the player profile card (so challenge/error pages are rejected)."""
    return BeautifulSoup(html, "lxml").select_one(config.SEL_PROFILE_CARD) is not None


def is_team_page(html: str) -> bool:
    return BeautifulSoup(html, "lxml").select_one(config.SEL_SQUAD_BODY) is not None


# ---------------------------------------------------------------------------
# Squad page
# ---------------------------------------------------------------------------

def parse_squad_links(html: str) -> list[str]:
    """Canonical player URLs from a team page's squad list, in page order, de-duplicated."""
    soup = BeautifulSoup(html, "lxml")
    body = soup.select_one(config.SEL_SQUAD_BODY)
    if body is None:
        return []
    seen: list[str] = []
    for a in body.select(config.SEL_SQUAD_PLAYER_LINK):
        href = a.get("href", "")
        if not player_id_from_url(href):
            continue
        url = canonical_player_url(href)
        if url not in seen:
            seen.append(url)
    return seen
