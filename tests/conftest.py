from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from player_extractor.offline import read_saved_page  # noqa: E402

SAMPLES = ROOT / "samples"
TODAY = date(2026, 11, 14)   # the day the samples were saved; keeps age/season tests stable


@pytest.fixture(scope="session")
def today() -> date:
    return TODAY


def load_sample(name: str) -> tuple[str, str]:
    url, html = read_saved_page(SAMPLES / name)
    assert url, f"{name} has no saved-from URL"
    return url, html


@pytest.fixture(scope="session")
def samples() -> dict[str, tuple[str, str]]:
    return {p.name: load_sample(p.name) for p in SAMPLES.glob("player_*.html")}
