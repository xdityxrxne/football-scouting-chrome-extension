"""Reading saved pages from disk (samples/ and cache/). No network."""
from __future__ import annotations

import logging
import re
from pathlib import Path

log = logging.getLogger(__name__)

_SAVED_FROM = re.compile(r"<!--\s*saved from\s+(\S+)", re.IGNORECASE)


def read_saved_page(path: Path) -> tuple[str | None, str]:
    """Return (url, html). URL comes from the '<!-- saved from URL -->' comment, else None."""
    html = path.read_text(encoding="utf-8", errors="replace")
    m = _SAVED_FROM.search(html[:2000])
    url = m.group(1) if m else None
    if url is None:
        log.warning("%s has no 'saved from' comment; URL unknown", path.name)
    return url, html


def list_saved_pages(folder: Path) -> list[Path]:
    return sorted(p for p in folder.glob("*.html") if p.is_file())
