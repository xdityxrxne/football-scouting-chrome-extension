"""Fetcher helpers that need no browser."""
from __future__ import annotations

from pathlib import Path

from player_extractor.fetcher import cache_path_for, classify_url, normalise_input_urls, save_to_cache
from player_extractor.offline import read_saved_page


def test_classify_and_normalise():
    urls, rejected = normalise_input_urls([
        "https://www.playmakerstats.com/player/alessia-russo/482425/results?x=1",
        "  /player/emily-mutch/729112?epoca_id=156  ",
        "https://www.playmakerstats.com/team/bristol-city/109452?epoca_id=156",
        "",
        "https://example.com/player/x/1",
        "not a link",
        "https://www.playmakerstats.com/player/alessia-russo/482425",   # duplicate
    ])
    assert urls == [
        "https://www.playmakerstats.com/player/alessia-russo/482425",
        "https://www.playmakerstats.com/player/emily-mutch/729112",
        "https://www.playmakerstats.com/team/bristol-city/109452",
    ]
    assert rejected == ["https://example.com/player/x/1", "not a link"]
    assert classify_url(urls[0]) == "player" and classify_url(urls[2]) == "team"


def test_cache_roundtrip(tmp_path: Path):
    url = "https://www.playmakerstats.com/player/kim-little/132319"
    path = save_to_cache(url, "<html><body>hi</body></html>", tmp_path)
    assert path == tmp_path / "132319.html"
    assert cache_path_for("https://www.playmakerstats.com/team/arsenal/16654", tmp_path) == tmp_path / "team_16654.html"
    read_url, html = read_saved_page(path)
    assert read_url == url and "hi" in html
