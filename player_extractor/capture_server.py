"""
Local capture server for the "Save player to Spotter" browser button.

Listens on http://127.0.0.1:8765 only (never reachable from other machines).
POST /capture  {"url": "...", "html": "..."}  -> parses the page and upserts it into the workbook.
GET  /health                                  -> {"ok": true}

Run:  python -m player_extractor.capture_server [--workbook players.xlsx] [--port 8765]
"""
from __future__ import annotations

import argparse
import logging
import threading
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, request

from . import config
from .excel_store import PlayerStore
from .fetcher import save_to_cache
from .logsetup import setup_logging
from .parser import canonical_player_url, is_player_page, parse_player, player_id_from_url

log = logging.getLogger("capture_server")

HOST = "127.0.0.1"
DEFAULT_PORT = 8765


def create_app(workbook: str | Path = config.DEFAULT_WORKBOOK, cache_dir: str | Path = config.CACHE_DIR) -> Flask:
    app = Flask(__name__)
    app.config["WORKBOOK"] = Path(workbook)
    app.config["CACHE_DIR"] = Path(cache_dir)
    lock = threading.Lock()

    @app.after_request
    def allow_extension(resp):
        # The extension calls us from the Playmakerstats tab; allow that cross-origin call.
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
        resp.headers["Access-Control-Allow-Methods"] = "POST, GET, OPTIONS"
        return resp

    @app.get("/health")
    def health():
        return jsonify(ok=True, workbook=str(app.config["WORKBOOK"]))

    @app.route("/capture", methods=["POST", "OPTIONS"])
    def capture():
        if request.method == "OPTIONS":
            return ("", 204)
        data = request.get_json(silent=True) or {}
        url = str(data.get("url") or "")
        html = str(data.get("html") or "")
        if not player_id_from_url(url):
            return jsonify(ok=False, error="This is not a Playmakerstats player page."), 400
        if not is_player_page(html):
            return jsonify(ok=False, error="The page does not look like a player profile (is the human check still showing?)."), 400
        url = canonical_player_url(url)
        with lock:
            try:
                save_to_cache(url, html, app.config["CACHE_DIR"])
                store = PlayerStore(app.config["WORKBOOK"]).load()
                rec, spells = parse_player(html, url)
                res = store.upsert(rec, spells)
                store.add_log("browser button", 1, int(res.action == "added"), int(res.action == "updated"),
                              0, int(res.needs_review), url, now=datetime.now())
                store.save()
            except PermissionError:
                log.exception("workbook locked")
                return jsonify(ok=False, error="The Excel file is open in Excel. Please close it and click again."), 409
            except Exception as e:  # noqa: BLE001
                log.exception("capture failed for %s", url)
                return jsonify(ok=False, error=f"Could not save this player: {e}"), 500
        log.info("captured %s -> %s %s", url, res.action, res.spotter_id)
        return jsonify(ok=True, name=res.name, spotter_id=res.spotter_id, action=res.action,
                       needs_review=res.needs_review, missing=res.missing, notes=res.notes)

    return app


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workbook", default=config.DEFAULT_WORKBOOK)
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = ap.parse_args()
    setup_logging(also_console=True)
    app = create_app(args.workbook)
    log.info("capture server on http://%s:%d (workbook %s)", HOST, args.port, args.workbook)
    app.run(host=HOST, port=args.port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
