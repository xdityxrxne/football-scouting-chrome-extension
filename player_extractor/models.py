"""Plain data containers shared by the parser, derive rules and the Excel store."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class Spell:
    """One continuous period at one club."""
    club: str
    club_id: str | None
    from_season: str
    to_season: str                 # season string or "Now"
    loan_from: str | None = None


@dataclass
class PlayerRecord:
    """One player. Field names mirror the Players sheet; blanks are None."""
    player_id: str
    url: str
    first_name: str | None = None
    last_name: str | None = None
    known_as: str | None = None
    full_name: str | None = None
    date_of_birth: date | None = None
    nationality: str | None = None
    place_of_birth: str | None = None
    homegrown: str | None = None
    primary_position: str | None = None
    secondary_positions: str | None = None
    preferred_foot: str | None = None
    height_cm: int | None = None
    weight_kg: int | None = None
    age_group: str | None = None
    current_club: str | None = None
    contract_expiry: date | None = None
    availability: str | None = None
    agent: str | None = None
    market_value_gbp: int | None = None
    spotter_id: str | None = None
    notes: list[str] = field(default_factory=list)          # tool-generated notes
    review_reasons: list[str] = field(default_factory=list) # uncertain mappings etc.
    has_current_season_club: bool = False

    def to_sheet_dict(self) -> dict[str, object]:
        """Values keyed by Players-sheet column name (derived columns filled by excel_store)."""
        return {
            "Spotter ID": self.spotter_id,
            "First name": self.first_name,
            "Last name": self.last_name,
            "Known as": self.known_as,
            "Date of birth": self.date_of_birth,
            "Nationality": self.nationality,
            "Place of birth": self.place_of_birth,
            "Homegrown": self.homegrown,
            "Primary position": self.primary_position,
            "Secondary positions": self.secondary_positions,
            "Preferred foot": self.preferred_foot,
            "Height (cm)": self.height_cm,
            "Weight (kg)": self.weight_kg,
            "Age group": self.age_group,
            "Current club": self.current_club,
            "Contract expiry": self.contract_expiry,
            "Availability": self.availability,
            "Agent": self.agent,
            "Market value (£)": self.market_value_gbp,
            "Playmakerstats URL": self.url,
            "Full name (site)": self.full_name,
        }

    @property
    def display_name(self) -> str:
        return " ".join(p for p in (self.first_name, self.last_name) if p) or self.known_as or self.full_name or ""
