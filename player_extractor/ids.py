"""Spotter ID handling: SP-00001, assigned once, never reused."""
from __future__ import annotations

import re
from collections.abc import Iterable

from . import config

_ID_RE = re.compile(r"^\s*" + re.escape(config.SPOTTER_ID_PREFIX) + r"(\d+)\s*$", re.IGNORECASE)


def format_spotter_id(number: int) -> str:
    return f"{config.SPOTTER_ID_PREFIX}{number:0{config.SPOTTER_ID_WIDTH}d}"


def parse_spotter_number(value: object) -> int | None:
    """Return the number inside 'SP-00012', or None if the value is not a Spotter ID."""
    if value is None:
        return None
    m = _ID_RE.match(str(value))
    return int(m.group(1)) if m else None


def next_spotter_id(existing: Iterable[object]) -> str:
    """Next free ID: one higher than the highest existing number (gaps are never refilled)."""
    highest = 0
    for value in existing:
        n = parse_spotter_number(value)
        if n is not None and n > highest:
            highest = n
    return format_spotter_id(highest + 1)


def is_spotter_id(value: object) -> bool:
    return parse_spotter_number(value) is not None
