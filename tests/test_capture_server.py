from __future__ import annotations

from pathlib import Path

from conftest import load_sample

from player_extractor.capture_server import create_app
from player_extractor.excel_store import PlayerStore


def test_capture_saves_player_and_rejects_bad_pages(tmp_path: Path):
    wb = tmp_path / "players.xlsx"
    app = create_app(wb, cache_dir=tmp_path / "cache")
    client = app.test_client()

    assert client.get("/health").get_json()["ok"] is True

    url, html = load_sample("player_dual_nationality_lucy_bronze.html")
    r = client.post("/capture", json={"url": url, "html": html})
    data = r.get_json()
    assert r.status_code == 200 and data["ok"] is True
    assert data["name"] == "Lucy Bronze" and data["spotter_id"] == "SP-00001" and data["action"] == "added"
    assert data["needs_review"] is False
    assert (tmp_path / "cache" / "153162.html").exists()

    # same player again -> updated, same ID
    r = client.post("/capture", json={"url": url, "html": html})
    assert r.get_json()["action"] == "updated" and r.get_json()["spotter_id"] == "SP-00001"
    store = PlayerStore(wb).load()
    assert len(store.players) == 1 and len(store.log_rows) == 2
    assert store.log_rows[0]["mode"] == "browser button"

    # not a player URL
    r = client.post("/capture", json={"url": "https://www.playmakerstats.com/team/arsenal/16654", "html": html})
    assert r.status_code == 400
    # a challenge page is refused, nothing written
    r = client.post("/capture", json={"url": url, "html": "<html><title>Just a moment...</title></html>"})
    assert r.status_code == 400 and "human check" in r.get_json()["error"]
    assert len(PlayerStore(wb).load().players) == 1

    # CORS preflight from the extension
    r = client.options("/capture")
    assert r.status_code == 204 and r.headers["Access-Control-Allow-Origin"] == "*"
