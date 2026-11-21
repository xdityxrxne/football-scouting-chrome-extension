"""
Derived-field rules. Pure functions, no I/O.

Every function takes raw text / values and returns a normalised value or None.
"Uncertain" outcomes are reported back to the caller as notes, never guessed.
"""
from __future__ import annotations

import re
from datetime import date

from . import config

# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def clean(text: str | None) -> str | None:
    """Collapse whitespace; return None for blank or placeholder values like '-'."""
    if text is None:
        return None
    t = re.sub(r"\s+", " ", str(text)).strip()
    if t.lower() in config.EMPTY_VALUE_MARKERS:
        return None
    return t


# ---------------------------------------------------------------------------
# Dates, age, season
# ---------------------------------------------------------------------------

_ISO_DATE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
_DMY_DATE = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")


def parse_date(text: str | None) -> date | None:
    """'1999-02-08 (27 -yrs-old)' -> date(1999, 2, 8). Also accepts dd/mm/yyyy."""
    t = clean(text)
    if not t:
        return None
    m = _ISO_DATE.search(t)
    if m:
        y, mo, d = (int(g) for g in m.groups())
    else:
        m = _DMY_DATE.search(t)
        if not m:
            return None
        d, mo, y = (int(g) for g in m.groups())
    try:
        return date(y, mo, d)
    except ValueError:
        return None


def age_on(dob: date, today: date) -> int:
    years = today.year - dob.year
    if (today.month, today.day) < (dob.month, dob.day):
        years -= 1
    return years


def age_group(dob: date | None, today: date) -> str | None:
    """U15 if under 15, U18 if under 18, U21 if under 21, else Senior. None if no DOB."""
    if dob is None:
        return None
    age = age_on(dob, today)
    for limit, label in config.AGE_GROUPS:
        if age < limit:
            return label
    return config.AGE_GROUP_DEFAULT


def current_season(today: date) -> str:
    """The football season containing `today`, formatted YYYY/YY (season starts in July)."""
    start_year = today.year if today.month >= config.SEASON_START_MONTH else today.year - 1
    return format_season(f"{start_year}/{start_year + 1}")


_SEASON_SPLIT = re.compile(r"^(\d{4})\s*[/\-–]\s*(\d{2,4})$")
_SEASON_YEAR = re.compile(r"^\d{4}$")


def format_season(text: str | None) -> str | None:
    """Normalise '2026/2027', '2026-27', '2026/27' -> '2026/27'. A plain year '2018' stays '2018'."""
    t = clean(text)
    if not t:
        return None
    if _SEASON_YEAR.match(t):
        return t
    m = _SEASON_SPLIT.match(t)
    if not m:
        return None
    start = int(m.group(1))
    end_part = m.group(2)
    end = int(end_part) if len(end_part) == 4 else (start // 100) * 100 + int(end_part)
    if end < start:
        end += 100
    return f"{start}/{end % 100:02d}"


def season_is_current(season: str | None, today: date) -> bool:
    """True if a season string is the season we are in now ('2026/27' or the calendar year '2026')."""
    if not season:
        return False
    if _SEASON_YEAR.match(season):
        return int(season) == today.year
    return season == current_season(today)


def end_of_month(year: int, month: int) -> date:
    if month == 12:
        return date(year, 12, 31)
    from datetime import timedelta
    return date(year, month + 1, 1) - timedelta(days=1)


_CONTRACT_YM = re.compile(r"^(\d{4})\s*/\s*(\d{1,2})$")


def parse_contract_expiry(text: str | None) -> tuple[date | None, str | None]:
    """
    '2027/06' -> (2027-06-30, 'contract month only').
    A full date is accepted too. Returns (None, None) when blank; (None, note) when unreadable.
    """
    t = clean(text)
    if not t:
        return None, None
    m = _CONTRACT_YM.match(t)
    if m:
        y, mo = int(m.group(1)), int(m.group(2))
        if 1 <= mo <= 12:
            return end_of_month(y, mo), "contract month only"
        return None, f"contract value not understood: {t}"
    d = parse_date(t)
    if d:
        return d, None
    return None, f"contract value not understood: {t}"


def availability(contract_expiry: date | None, has_current_season_club: bool, today: date) -> tuple[str | None, str | None]:
    """
    Returns (availability, note).
    future expiry -> 'Under contract'
    past expiry and no current-season club -> 'Available'
    past expiry but still listed for the current season -> blank + note (date may be stale)
    no expiry -> blank
    """
    if contract_expiry is None:
        return None, None
    if contract_expiry >= today:
        return "Under contract", None
    if has_current_season_club:
        return None, "contract date may be out of date"
    return "Available", None


# ---------------------------------------------------------------------------
# Positions
# ---------------------------------------------------------------------------

def map_position(raw: str | None) -> tuple[str | None, str | None]:
    """
    Site position name -> code. Returns (code, note).
    Unknown or generic names give (None, note-with-raw-value).
    """
    t = clean(raw)
    if not t:
        return None, None
    key = t.lower()
    if key in config.GENERIC_POSITIONS:
        return None, f"position too generic: {t}"
    code = config.POSITION_MAP.get(key)
    if code in config.POSITION_CODES:
        return code, None
    return None, f"position not mapped: {t}"


def map_positions(raw_values: list[str]) -> tuple[str | None, str | None, list[str]]:
    """First value -> primary, rest -> secondary (comma-separated). Returns (primary, secondary, notes)."""
    notes: list[str] = []
    primary = None
    secondary: list[str] = []
    for i, raw in enumerate(raw_values):
        code, note = map_position(raw)
        if note:
            notes.append(("primary " if i == 0 else "secondary ") + note)
        if i == 0:
            primary = code
        elif code:
            secondary.append(code)
    return primary, (", ".join(secondary) or None), notes


# ---------------------------------------------------------------------------
# Nationality, birthplace, foot
# ---------------------------------------------------------------------------

def nationality_label(country: str | None) -> str | None:
    t = clean(country)
    if not t:
        return None
    return config.NATIONALITY_MAP.get(t.lower(), t)


def join_nationalities(countries: list[str]) -> str | None:
    labels = [lab for lab in (nationality_label(c) for c in countries) if lab]
    seen: list[str] = []
    for lab in labels:
        if lab not in seen:
            seen.append(lab)
    return config.NATIONALITY_JOINER.join(seen) or None


_BIRTHPLACE = re.compile(r"^(?P<country>[^()]+?)\s*(?:\((?P<town>[^()]+)\))?$")


def place_of_birth(text: str | None) -> str | None:
    """'England (Taunton)' -> 'Taunton, England'; 'England' -> 'England'."""
    t = clean(text)
    if not t:
        return None
    m = _BIRTHPLACE.match(t)
    if not m:
        return t
    country = m.group("country").strip()
    town = (m.group("town") or "").strip()
    return f"{town}, {country}" if town else country


_FOOT_MAP = {"right": "Right", "left": "Left", "both": "Both", "either": "Both", "two-footed": "Both"}


def preferred_foot(text: str | None) -> tuple[str | None, str | None]:
    t = clean(text)
    if not t:
        return None, None
    val = _FOOT_MAP.get(t.lower())
    if val:
        return val, None
    return None, f"preferred foot not understood: {t}"


# ---------------------------------------------------------------------------
# Height / weight
# ---------------------------------------------------------------------------

_CM = re.compile(r"(\d{2,3})\s*cm", re.I)
_KG = re.compile(r"(\d{2,3})\s*kg", re.I)
_FT_IN = re.compile(r"(\d)\s*(?:ft|')\s*(\d{1,2})?\s*(?:in|\")?", re.I)
_LBS = re.compile(r"(\d{2,3})\s*(?:lbs?|pounds)", re.I)
_M = re.compile(r"(\d)[.,](\d{2})\s*m\b", re.I)


def height_cm(text: str | None) -> int | None:
    t = clean(text)
    if not t:
        return None
    m = _CM.search(t)
    if m:
        return int(m.group(1))
    m = _M.search(t)
    if m:
        return int(round(float(f"{m.group(1)}.{m.group(2)}") * 100))
    m = _FT_IN.search(t)
    if m:
        inches = int(m.group(1)) * 12 + int(m.group(2) or 0)
        return int(round(inches * 2.54))
    return None


def weight_kg(text: str | None) -> int | None:
    t = clean(text)
    if not t:
        return None
    m = _KG.search(t)
    if m:
        return int(m.group(1))
    m = _LBS.search(t)
    if m:
        return int(round(int(m.group(1)) * 0.45359237))
    return None


def split_height_weight(text: str | None) -> tuple[int | None, int | None]:
    """'175 cm / 68 kg' -> (175, 68). Either side may be missing."""
    t = clean(text)
    if not t:
        return None, None
    return height_cm(t), weight_kg(t)


# ---------------------------------------------------------------------------
# Market value
# ---------------------------------------------------------------------------

_MV = re.compile(r"(?P<cur>[£€$])?\s*(?P<num>\d+(?:[.,]\d+)?)\s*(?P<mult>[kKmM])?\s*(?P<cur2>[£€$]|EUR|GBP|USD)?")


def parse_market_value(text: str | None) -> tuple[int | None, str | None]:
    """'100 k €' -> (100000, 'EUR'); '£2.5M' -> (2500000, 'GBP'). (None, None) when blank/unreadable."""
    t = clean(text)
    if not t:
        return None, None
    m = _MV.search(t)
    if not m or not m.group("num"):
        return None, None
    amount = float(m.group("num").replace(",", "."))
    mult = (m.group("mult") or "").lower()
    if mult == "k":
        amount *= 1_000
    elif mult == "m":
        amount *= 1_000_000
    cur_raw = m.group("cur") or m.group("cur2") or ""
    currency = {"£": "GBP", "€": "EUR", "$": "USD"}.get(cur_raw, cur_raw.upper() or None)
    return int(round(amount)), currency


def market_value_gbp(text: str | None) -> tuple[int | None, str | None]:
    """
    £ value if the site shows pounds; otherwise None plus a note with the raw value.
    EUR is converted only when config.MARKET_VALUE_EUR_TO_GBP_RATE is set.
    """
    t = clean(text)
    if not t:
        return None, None
    amount, currency = parse_market_value(t)
    if amount is None:
        return None, f"market value not understood: {t}"
    if currency == "GBP":
        return amount, None
    rate = config.MARKET_VALUE_EUR_TO_GBP_RATE
    if currency == "EUR" and rate:
        return int(round(amount * rate)), f"market value converted from {t} at {rate}"
    return None, f"market value (site): {t}"


# ---------------------------------------------------------------------------
# Names
# ---------------------------------------------------------------------------

def split_display_name(display: str | None) -> tuple[str | None, str | None]:
    """'Daphne van Domselaar' -> ('Daphne', 'van Domselaar'). One word -> (None, word)."""
    t = clean(display)
    if not t:
        return None, None
    parts = t.split(" ")
    if len(parts) == 1:
        return None, parts[0]
    return parts[0], " ".join(parts[1:])


def name_split_note(full_name: str | None, last_name: str | None) -> str | None:
    """Note when the site's full legal name does not end with the chosen last name."""
    full, last = clean(full_name), clean(last_name)
    if not full or not last:
        return None
    if full.lower().endswith(last.lower()):
        return None
    return "check name split"


# ---------------------------------------------------------------------------
# Missing fields / Needs review
# ---------------------------------------------------------------------------

def is_blank(value: object) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def missing_fields(row: dict[str, object]) -> list[str]:
    never = set(config.SITE_NEVER_PUBLISHES)
    return [f for f in config.MISSING_TRACKED_FIELDS if f not in never and is_blank(row.get(f))]


def needs_review(row: dict[str, object], review_reasons: list[str]) -> bool:
    return bool(review_reasons) or any(is_blank(row.get(f)) for f in config.KEY_FIELDS)
