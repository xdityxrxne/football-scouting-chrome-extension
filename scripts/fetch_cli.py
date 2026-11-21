"""
Command-line runner (for testing; the client uses the app).

    python scripts/fetch_cli.py --out players.xlsx URL [URL ...]
    python scripts/fetch_cli.py --cached            # re-parse ./cache/
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # run from the repo without installing

from player_extractor import config
from player_extractor.runner import run_cached, run_live


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("urls", nargs="*")
    ap.add_argument("--out", default=config.DEFAULT_WORKBOOK)
    ap.add_argument("--cached", action="store_true", help="re-parse ./cache/ instead of fetching")
    ap.add_argument("--max-pages", type=int, default=config.MAX_PAGES_PER_RUN)
    args = ap.parse_args()

    Path("logs").mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler("logs/app.log", encoding="utf-8"), logging.StreamHandler(sys.stdout)],
    )

    def status(msg: str) -> None:
        print(f"  > {msg}")

    if args.cached:
        summary = run_cached(args.out, status=status)
    else:
        summary = run_live(args.urls, args.out, status=status, max_pages=args.max_pages)

    print(f"\nMode: {summary.mode}  processed: {summary.processed}  added: {summary.added}  "
          f"updated: {summary.updated}  failed: {summary.failed}  needs review: {summary.flagged}")
    for r in summary.results:
        print(f"  {r.spotter_id}  {r.action:8}  {r.name}{'  NEEDS REVIEW' if r.needs_review else ''}")
    for url, why in summary.failures:
        print(f"  FAILED  {url}: {why}")
    if summary.stopped_early:
        print(f"  STOPPED: {summary.stopped_early}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
