"""
Excel workbook storage (openpyxl).

PlayerStore loads the whole workbook into memory, applies upserts, and writes it back
with styled headers, frozen header row, autofilter, sensible column widths and real dates.
Client-owned content (Notes lines without the "(auto) " prefix, the Club Levels sheet)
is preserved on every save.
"""
from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from . import config, derive, ids
from .models import PlayerRecord, Spell
from .parser import player_id_from_url

log = logging.getLogger(__name__)

DATE_FORMAT = "YYYY-MM-DD"
DATETIME_FORMAT = "YYYY-MM-DD HH:MM"
DATE_COLUMNS = {"Date of birth", "Contract expiry"}
DATETIME_COLUMNS = {"Last updated", "timestamp"}

Row = dict[str, object]


@dataclass
class UpsertResult:
    spotter_id: str
    action: str                      # "added" | "updated"
    name: str
    needs_review: bool
    missing: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Reading helpers
# ---------------------------------------------------------------------------

def _as_date(value: object) -> object:
    if isinstance(value, datetime):
        return value.date()
    return value


def _read_sheet(ws: Worksheet, columns: list[str]) -> list[Row]:
    """Rows as dicts keyed by header text. Unknown columns are kept; missing ones are None."""
    rows: list[Row] = []
    header = [str(c.value).strip() if c.value is not None else "" for c in ws[1]] if ws.max_row >= 1 else []
    for raw in ws.iter_rows(min_row=2, values_only=True):
        if raw is None or all(v is None or str(v).strip() == "" for v in raw):
            continue
        row: Row = {col: None for col in columns}
        for key, value in zip(header, raw, strict=False):
            if key:
                row[key] = value
        rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# Notes merging
# ---------------------------------------------------------------------------

def merge_notes(existing: object, auto_notes: list[str]) -> str | None:
    """Keep the client's own lines, replace the tool's '(auto) ' lines."""
    prefix = config.AUTO_NOTE_PREFIX
    client_lines = []
    if existing:
        client_lines = [ln for ln in str(existing).splitlines() if ln.strip() and not ln.startswith(prefix)]
    seen: list[str] = []
    for n in auto_notes:
        line = prefix + n
        if line not in seen:
            seen.append(line)
    lines = client_lines + seen
    return "\n".join(lines) if lines else None


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------

class PlayerStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.players: list[Row] = []
        self.history: list[Row] = []
        self.levels: list[Row] = []
        self.log_rows: list[Row] = []

    # -- load / save ---------------------------------------------------------

    def load(self) -> PlayerStore:
        if not self.path.exists():
            log.info("workbook %s does not exist yet; starting empty", self.path)
            return self
        wb = load_workbook(self.path, data_only=True)
        if config.SHEET_PLAYERS in wb.sheetnames:
            self.players = _read_sheet(wb[config.SHEET_PLAYERS], config.PLAYER_COLUMNS)
            for row in self.players:
                for col in DATE_COLUMNS:
                    row[col] = _as_date(row.get(col))
        if config.SHEET_HISTORY in wb.sheetnames:
            self.history = _read_sheet(wb[config.SHEET_HISTORY], config.HISTORY_COLUMNS)
        if config.SHEET_LEVELS in wb.sheetnames:
            self.levels = _read_sheet(wb[config.SHEET_LEVELS], config.LEVEL_COLUMNS)
        if config.SHEET_LOG in wb.sheetnames:
            self.log_rows = _read_sheet(wb[config.SHEET_LOG], config.LOG_COLUMNS)
        wb.close()
        log.info("loaded %d players, %d history rows, %d club levels", len(self.players), len(self.history), len(self.levels))
        return self

    def backup(self) -> Path | None:
        if not self.path.exists():
            return None
        backup_dir = self.path.parent / config.BACKUP_DIR
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target = backup_dir / f"{self.path.stem}_{stamp}{self.path.suffix}"
        counter = 1
        while target.exists():
            target = backup_dir / f"{self.path.stem}_{stamp}_{counter}{self.path.suffix}"
            counter += 1
        shutil.copy2(self.path, target)
        log.info("backup written to %s", target)
        return target

    def save(self, make_backup: bool = True) -> Path:
        if make_backup:
            self.backup()
        wb = Workbook()
        wb.remove(wb.active)
        _write_sheet(wb.create_sheet(config.SHEET_PLAYERS), config.PLAYER_COLUMNS, self.players)
        _write_sheet(wb.create_sheet(config.SHEET_HISTORY), config.HISTORY_COLUMNS, self.history)
        _write_sheet(wb.create_sheet(config.SHEET_LEVELS), config.LEVEL_COLUMNS, self.levels)
        _write_sheet(wb.create_sheet(config.SHEET_LOG), config.LOG_COLUMNS, self.log_rows)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        wb.save(self.path)
        log.info("saved %s", self.path)
        return self.path

    # -- lookups -------------------------------------------------------------

    def find_player(self, spotter_id: str | None, player_id: str | None) -> Row | None:
        if spotter_id:
            for row in self.players:
                if str(row.get("Spotter ID") or "").strip().upper() == spotter_id.strip().upper():
                    return row
        if player_id:
            for row in self.players:
                if player_id_from_url(str(row.get("Playmakerstats URL") or "")) == player_id:
                    return row
        return None

    def level_for(self, club: str) -> str | None:
        for row in self.levels:
            if str(row.get("Club") or "").strip().lower() == club.strip().lower():
                return derive.clean(row.get("Level"))
        return None

    def has_club(self, club: str) -> bool:
        return any(str(r.get("Club") or "").strip().lower() == club.strip().lower() for r in self.levels)

    # -- upsert --------------------------------------------------------------

    def upsert(self, rec: PlayerRecord, spells: list[Spell], now: datetime | None = None) -> UpsertResult:
        now = now or datetime.now()
        existing = self.find_player(rec.spotter_id, rec.player_id)
        new_values = rec.to_sheet_dict()

        if existing is None:
            row: Row = {col: None for col in config.PLAYER_COLUMNS}
            row.update({k: v for k, v in new_values.items() if not derive.is_blank(v)})
            row["Spotter ID"] = rec.spotter_id if ids.is_spotter_id(rec.spotter_id) else ids.next_spotter_id(r.get("Spotter ID") for r in self.players)
            self.players.append(row)
            action = "added"
        else:
            row = existing
            for col, value in new_values.items():
                if col == "Spotter ID":
                    continue
                if not derive.is_blank(value):
                    row[col] = value
            if derive.is_blank(row.get("Spotter ID")):
                row["Spotter ID"] = ids.next_spotter_id(r.get("Spotter ID") for r in self.players)
            action = "updated"

        spotter_id = str(row["Spotter ID"])

        # Club History: replace this player's rows, filling Level from the lookup.
        # Clubs without a level are added to the Club Levels sheet with a blank Level
        # (that blank is the flag; nothing is written to Notes about it).
        self.history = [h for h in self.history if str(h.get("Spotter ID") or "") != spotter_id]
        player_name = rec.display_name or str(row.get("Known as") or "")
        for sp in spells:
            if not self.has_club(sp.club):
                self.levels.append({"Club": sp.club, "Level": None})
            self.history.append({
                "Spotter ID": spotter_id, "Player name": player_name, "Club": sp.club,
                "Level": self.level_for(sp.club), "From": sp.from_season, "To": sp.to_season,
            })

        # Derived columns on the merged row
        review_reasons = list(rec.review_reasons)
        auto_notes = list(rec.notes) + review_reasons
        row["Notes"] = merge_notes(row.get("Notes"), auto_notes)
        missing = derive.missing_fields(row)
        row["Missing fields"] = ", ".join(missing) or None
        flagged = derive.needs_review(row, review_reasons)
        row["Needs review"] = "Yes" if flagged else "No"
        row["Last updated"] = now

        return UpsertResult(spotter_id=spotter_id, action=action, name=player_name,
                            needs_review=flagged, missing=missing, notes=auto_notes)

    # -- run log -------------------------------------------------------------

    def add_log(self, mode: str, processed: int, added: int, updated: int, failed: int,
                flagged: int, notes: str = "", now: datetime | None = None) -> None:
        self.log_rows.append({
            "timestamp": now or datetime.now(), "mode": mode, "URLs processed": processed,
            "added": added, "updated": updated, "failed": failed, "flagged": flagged, "notes": notes or None,
        })


# ---------------------------------------------------------------------------
# Writing helpers
# ---------------------------------------------------------------------------

_HEADER_FONT = Font(bold=True, color="FFFFFF")
_HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
_REVIEW_FILL = PatternFill("solid", fgColor="FFF2CC")
_WRAP = Alignment(wrap_text=True, vertical="top")


def _write_sheet(ws: Worksheet, columns: list[str], rows: list[Row]) -> None:
    ws.append(columns)
    for cell in ws[1]:
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL
        cell.alignment = Alignment(vertical="center")
    for row in rows:
        ws.append([_cell_value(row.get(col)) for col in columns])
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(columns))}{max(len(rows) + 1, 1)}"

    for idx, col in enumerate(columns, start=1):
        letter = get_column_letter(idx)
        longest = len(col)
        for r in range(2, len(rows) + 2):
            cell = ws.cell(row=r, column=idx)
            if col in DATE_COLUMNS:
                cell.number_format = DATE_FORMAT
            elif col in DATETIME_COLUMNS:
                cell.number_format = DATETIME_FORMAT
            if col in ("Notes", "Missing fields"):
                cell.alignment = _WRAP
            v = cell.value
            if v is not None:
                text = v.strftime("%Y-%m-%d") if isinstance(v, date | datetime) else str(v)
                longest = max(longest, max((len(ln) for ln in text.splitlines()), default=0))
        ws.column_dimensions[letter].width = min(max(10, longest + 2), 60)

    if "Needs review" in columns:
        col_idx = columns.index("Needs review") + 1
        for r in range(2, len(rows) + 2):
            if ws.cell(row=r, column=col_idx).value == "Yes":
                for c in range(1, len(columns) + 1):
                    ws.cell(row=r, column=c).fill = _REVIEW_FILL


def _cell_value(value: object) -> object:
    if isinstance(value, str):
        return value if value.strip() else None
    return value
