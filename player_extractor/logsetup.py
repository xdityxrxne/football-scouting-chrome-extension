"""One place to configure logging: details go to ./logs/app.log, never to the user's screen."""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "app.log"


def setup_logging(also_console: bool = False, level: int = logging.INFO) -> Path:
    LOG_DIR.mkdir(exist_ok=True)
    root = logging.getLogger()
    if any(getattr(h, "_spotter", False) for h in root.handlers):
        return LOG_FILE
    root.setLevel(level)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    fh = RotatingFileHandler(LOG_FILE, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    fh.setFormatter(fmt)
    fh._spotter = True  # type: ignore[attr-defined]
    root.addHandler(fh)
    if also_console:
        ch = logging.StreamHandler()
        ch.setFormatter(fmt)
        ch._spotter = True  # type: ignore[attr-defined]
        root.addHandler(ch)
    return LOG_FILE
