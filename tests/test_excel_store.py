from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from conftest import load_sample
from openpyxl import load_workbook

from player_extractor import config, ids
from player_extractor.excel_store import PlayerStore, merge_notes
from player_extractor.models import PlayerRecord, Spell
from player_extractor.parser import parse_player

TODAY = date(2026, 11, 14)
NOW = datetime(2026, 11, 14, 12, 0)
PLAYER_FILES = [
    "player_wsl_star_alessia_russo.html",
    "player_dual_nationality_lucy_bronze.html",
    "player_long_career_kim_little.html",
    "player_championship_emily_syme.html",
    "player_sparse_youth_neeve_mcdonald.html",
]


def run_all(path: Path) -> list:
    store = PlayerStore(path).load()
    results = []
    for name in PLAYER_FILES:
        url, html = load_sample(name)
        rec, spells = parse_player(html, url, today=TODAY)
        results.append(store.upsert(rec, spells, now=NOW))
    store.add_log("test", len(PLAYER_FILES), 0, 0, 0, 0, now=NOW)
    store.save()
    return results


def read_rows(path: Path, sheet: str) -> list[dict]:
    wb = load_workbook(path, data_only=True)
    ws = wb[sheet]
    header = [c.value for c in ws[1]]
    rows = [dict(zip(header, r, strict=False)) for r in ws.iter_rows(min_row=2, values_only=True) if any(v is not None for v in r)]
    wb.close()
    return rows


# ---------------------------------------------------------------------------

def test_spotter_ids():
    assert ids.format_spotter_id(1) == "SP-00001"
    assert ids.next_spotter_id([]) == "SP-00001"
    assert ids.next_spotter_id(["SP-00001", "SP-00007", None, "junk"]) == "SP-00008"
    assert ids.next_spotter_id(["sp-00003"]) == "SP-00004"
    assert ids.is_spotter_id("SP-00012") and not ids.is_spotter_id("12")


def test_first_run_creates_workbook_with_all_sheets(tmp_path):
    path = tmp_path / "players.xlsx"
    results = run_all(path)
    assert [r.action for r in results] == ["added"] * 5
    assert [r.spotter_id for r in results] == [f"SP-0000{i}" for i in range(1, 6)]

    wb = load_workbook(path)
    assert wb.sheetnames == [config.SHEET_PLAYERS, config.SHEET_HISTORY, config.SHEET_LEVELS, config.SHEET_LOG]
    ws = wb[config.SHEET_PLAYERS]
    assert [c.value for c in ws[1]] == config.PLAYER_COLUMNS
    assert ws.freeze_panes == "A2"
    assert ws.auto_filter.ref.startswith("A1:")
    assert ws[1][0].font.bold
    # dates are real dates with the right display format
    dob_col = config.PLAYER_COLUMNS.index("Date of birth") + 1
    cell = ws.cell(row=2, column=dob_col)
    assert isinstance(cell.value, datetime) and cell.number_format == "YYYY-MM-DD"
    wb.close()

    players = read_rows(path, config.SHEET_PLAYERS)
    assert len(players) == 5
    russo = next(p for p in players if p["Last name"] == "Russo")
    assert russo["Primary position"] == "ST"
    assert russo["Full name (site)"] == "Alessia Mia Teresa Russo"
    assert russo["Date of birth"].date() == date(1999, 2, 8)
    assert "Homegrown" not in russo["Missing fields"] and "Agent" not in russo["Missing fields"]  # never published
    assert "Contract expiry" in russo["Missing fields"]
    assert russo["Known as"] == "Alessia Russo"
    bronze = next(p for p in players if p["Last name"] == "Bronze")
    assert bronze["Needs review"] == "No"           # complete key data; missing club levels are not noted
    assert "club level" not in (bronze["Notes"] or "")
    little = next(p for p in players if p["Last name"] == "Little")
    assert little["Needs review"] == "Yes"          # stale contract date
    mcd = next(p for p in players if p["Last name"] == "McDonald")
    assert mcd["Needs review"] == "Yes"
    assert "Date of birth" in mcd["Missing fields"]
    assert "(auto) primary position too generic: Defender" in mcd["Notes"]

    history = read_rows(path, config.SHEET_HISTORY)
    assert len(history) == 4 + 10 + 8 + 5 + 1    # Russo, Bronze, Little, Syme, McDonald
    assert all(h["Spotter ID"].startswith("SP-") for h in history)
    levels = read_rows(path, config.SHEET_LEVELS)
    clubs = {lvl["Club"] for lvl in levels}
    assert {"Arsenal", "Chelsea", "Bristol City", "Sheffield United", "North Carolina Tar Heels"} <= clubs
    assert all(lvl["Level"] is None for lvl in levels)
    assert len(read_rows(path, config.SHEET_LOG)) == 1


def test_second_run_no_duplicates_ids_stable(tmp_path):
    path = tmp_path / "players.xlsx"
    first = run_all(path)
    second = run_all(path)
    assert [r.action for r in second] == ["updated"] * 5
    assert [r.spotter_id for r in first] == [r.spotter_id for r in second]
    players = read_rows(path, config.SHEET_PLAYERS)
    assert len(players) == 5
    assert len({p["Spotter ID"] for p in players}) == 5
    history = read_rows(path, config.SHEET_HISTORY)
    assert len(history) == 28                   # replaced, not appended
    assert len(read_rows(path, config.SHEET_LEVELS)) == len({lvl["Club"] for lvl in read_rows(path, config.SHEET_LEVELS)})
    assert len(read_rows(path, config.SHEET_LOG)) == 2
    backups = list((tmp_path / config.BACKUP_DIR).glob("players_*.xlsx"))
    assert len(backups) == 1                    # one backup, taken before the second save


def test_client_edits_preserved_and_blanks_do_not_overwrite(tmp_path):
    path = tmp_path / "players.xlsx"
    run_all(path)

    # client edits: a note, a club level, a manual Homegrown value
    store = PlayerStore(path).load()
    little = next(p for p in store.players if p["Last name"] == "Little")
    little["Notes"] = "Scout saw her 3 Nov, very good\n" + (little["Notes"] or "")
    little["Homegrown"] = "No"
    arsenal = next(lvl for lvl in store.levels if lvl["Club"] == "Arsenal")
    arsenal["Level"] = "Professional"
    store.save(make_backup=False)

    run_all(path)
    players = read_rows(path, config.SHEET_PLAYERS)
    little = next(p for p in players if p["Last name"] == "Little")
    assert little["Notes"].splitlines()[0] == "Scout saw her 3 Nov, very good"
    assert little["Notes"].count("(auto) market value (site): 100 k €") == 1   # auto notes not duplicated
    assert little["Homegrown"] == "No"                                         # blank from site did not wipe it
    history = read_rows(path, config.SHEET_HISTORY)
    assert all(h["Level"] == "Professional" for h in history if h["Club"] == "Arsenal")
    assert any(h["Level"] is None for h in history if h["Club"] != "Arsenal")
    levels = read_rows(path, config.SHEET_LEVELS)
    assert next(lvl for lvl in levels if lvl["Club"] == "Arsenal")["Level"] == "Professional"


def test_client_prefilled_spotter_id_is_kept(tmp_path):
    path = tmp_path / "players.xlsx"
    store = PlayerStore(path)
    store.players.append({**{c: None for c in config.PLAYER_COLUMNS},
                          "Spotter ID": "SP-00042",
                          "Playmakerstats URL": "https://www.playmakerstats.com/player/lucy-bronze/153162"})
    store.save(make_backup=False)
    results = run_all(path)
    bronze = next(r for r in results if r.name == "Lucy Bronze")
    assert bronze.spotter_id == "SP-00042" and bronze.action == "updated"
    others = [r.spotter_id for r in results if r.name != "Lucy Bronze"]
    assert others == ["SP-00043", "SP-00044", "SP-00045", "SP-00046"]   # never reuse lower numbers


def test_update_changes_fields_and_refreshes_last_updated(tmp_path):
    path = tmp_path / "players.xlsx"
    store = PlayerStore(path)
    rec = PlayerRecord(player_id="999", url="https://www.playmakerstats.com/player/test/999",
                       first_name="Test", last_name="Player", current_club="Old FC", height_cm=170)
    store.upsert(rec, [Spell("Old FC", "1", "2024/25", "Now")], now=datetime(2026, 1, 1))
    rec2 = PlayerRecord(player_id="999", url="https://www.playmakerstats.com/player/test/999",
                        first_name="Test", last_name="Player", current_club="New FC")
    res = store.upsert(rec2, [Spell("Old FC", "1", "2024/25", "2025/26"), Spell("New FC", "2", "2026/27", "Now")], now=datetime(2026, 6, 1))
    assert res.action == "updated"
    row = store.players[0]
    assert row["Current club"] == "New FC"
    assert row["Height (cm)"] == 170               # blank in new record -> kept
    assert row["Last updated"] == datetime(2026, 6, 1)
    assert [(h["Club"], h["To"]) for h in store.history] == [("Old FC", "2025/26"), ("New FC", "Now")]


def test_merge_notes():
    assert merge_notes(None, []) is None
    assert merge_notes("client line", ["x"]) == "client line\n(auto) x"
    assert merge_notes("client line\n(auto) old", ["new"]) == "client line\n(auto) new"
    assert merge_notes(None, ["a", "a"]) == "(auto) a"
