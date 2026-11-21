"""
Offline demo: parse every saved page in ./samples/ and build players.xlsx.

    python scripts/demo_offline.py [--out players.xlsx] [--samples samples]
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # run from the repo without installing

from player_extractor import config
from player_extractor.runner import run_saved_pages


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=config.DEFAULT_WORKBOOK)
    ap.add_argument("--samples", default="samples")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    summary = run_saved_pages(args.samples, args.out)
    print(f"\nDone: {len(summary.results)} players written to {args.out}")
    for r in summary.results:
        print(f"  {r.spotter_id}  {r.action:8}  {r.name}{'  NEEDS REVIEW' if r.needs_review else ''}")
        if r.missing:
            print(f"             missing: {', '.join(r.missing)}")
    for name, why in summary.failures:
        print(f"  FAILED  {name}: {why}")


if __name__ == "__main__":
    main()
