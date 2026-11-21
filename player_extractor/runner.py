"""
Orchestration shared by the command line, the Streamlit app and the capture server:
fetch (or read) pages -> parse -> upsert -> save workbook + run log.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from . import config
from .excel_store import PlayerStore, UpsertResult
from .offline import list_saved_pages, read_saved_page
from .parser import is_player_page, parse_player, player_id_from_url

log = logging.getLogger(__name__)

StatusCallback = Callable[[str], None]
ProgressCallback = Callable[[int, int], None]   # (done, total)


@dataclass
class RunSummary:
    mode: str
    workbook: Path
    results: list[UpsertResult] = field(default_factory=list)
    failures: list[tuple[str, str]] = field(default_factory=list)   # (url or file, reason)
    processed: int = 0
    stopped_early: str | None = None

    @property
    def added(self) -> int:
        return sum(r.action == "added" for r in self.results)

    @property
    def updated(self) -> int:
        return sum(r.action == "updated" for r in self.results)

    @property
    def flagged(self) -> int:
        return sum(r.needs_review for r in self.results)

    @property
    def failed(self) -> int:
        return len(self.failures)


def _noop(*_a) -> None:
    pass


class NotAPlayerPage(Exception):
    pass


def process_html(store: PlayerStore, url: str, html: str, summary: RunSummary) -> UpsertResult:
    if not is_player_page(html):
        raise NotAPlayerPage("not a player profile page (no profile card found)")
    rec, spells = parse_player(html, url)
    res = store.upsert(rec, spells)
    summary.results.append(res)
    log.info("%s %s (%s) review=%s", res.action, res.name, res.spotter_id, res.needs_review)
    return res


def _finish(store: PlayerStore, summary: RunSummary) -> RunSummary:
    notes = []
    if summary.stopped_early:
        notes.append(summary.stopped_early)
    if summary.failures:
        notes.append("failed: " + "; ".join(f"{u} ({why})" for u, why in summary.failures))
    store.add_log(summary.mode, summary.processed, summary.added, summary.updated,
                  summary.failed, summary.flagged, " | ".join(notes), now=datetime.now())
    store.save()
    return summary


# ---------------------------------------------------------------------------
# Saved pages (samples/ or cache/)
# ---------------------------------------------------------------------------

def run_saved_pages(folder: str | Path, workbook: str | Path, mode: str = "offline demo",
                    status: StatusCallback = _noop, progress: ProgressCallback = _noop) -> RunSummary:
    folder, workbook = Path(folder), Path(workbook)
    summary = RunSummary(mode=mode, workbook=workbook)
    store = PlayerStore(workbook).load()
    pages = [p for p in list_saved_pages(folder)]
    player_pages = []
    for path in pages:
        url, html = read_saved_page(path)
        if url and player_id_from_url(url):
            player_pages.append((path, url, html))
        else:
            log.info("skipping %s (not a player page)", path.name)
    total = len(player_pages)
    for i, (path, url, html) in enumerate(player_pages, start=1):
        status(f"Reading {path.name}")
        summary.processed += 1
        try:
            process_html(store, url, html, summary)
        except NotAPlayerPage as e:
            log.warning("%s: %s", path.name, e)
            summary.failures.append((path.name, str(e)))
        except Exception as e:  # noqa: BLE001
            log.exception("failed on %s", path.name)
            summary.failures.append((path.name, str(e)))
        progress(i, total)
    return _finish(store, summary)


# ---------------------------------------------------------------------------
# Live
# ---------------------------------------------------------------------------

def run_live(urls: list[str], workbook: str | Path, status: StatusCallback = _noop,
             progress: ProgressCallback = _noop, max_pages: int = config.MAX_PAGES_PER_RUN) -> RunSummary:
    """Fetch player/team URLs in a visible browser and upsert into the workbook."""
    from .fetcher import Fetcher, FetchError, PageLimitReached, TooManyChallenges, normalise_input_urls

    workbook = Path(workbook)
    summary = RunSummary(mode="live", workbook=workbook)
    clean_urls, rejected = normalise_input_urls(urls)
    for bad in rejected:
        summary.failures.append((bad, "not a Playmakerstats player or team link"))
    if not clean_urls:
        status("No usable links found")
        return summary

    store = PlayerStore(workbook).load()
    status("Opening the browser window")
    try:
        with Fetcher(status=status, max_pages=max_pages) as fetcher:
            status(f"Using {fetcher.browser_name}")
            player_urls, team_failures = fetcher.expand_team_urls(clean_urls)
            summary.failures.extend(team_failures)
            total = len(player_urls)
            status(f"{total} player page(s) to fetch")
            for i, url in enumerate(player_urls, start=1):
                summary.processed += 1
                try:
                    html = fetcher.fetch(url)
                    res = process_html(store, url, html, summary)
                    status(f"{res.action.capitalize()}: {res.name}" + (" (needs review)" if res.needs_review else ""))
                except (TooManyChallenges, PageLimitReached):
                    summary.processed -= 1
                    raise
                except (FetchError, NotAPlayerPage) as e:
                    log.warning("failed %s: %s", url, e)
                    summary.failures.append((url, str(e)))
                    status(f"Could not load {url}")
                except Exception as e:  # noqa: BLE001 - parser/store problem on one page
                    log.exception("failed processing %s", url)
                    summary.failures.append((url, f"could not be processed: {e}"))
                progress(i, total)
    except TooManyChallenges as e:
        summary.stopped_early = str(e)
        status(str(e))
    except PageLimitReached as e:
        summary.stopped_early = str(e)
        status(f"Stopped: {e}")
    except Exception as e:  # noqa: BLE001 - browser failed to start etc.
        log.exception("live run aborted")
        summary.stopped_early = f"browser problem: {str(e).splitlines()[0]}"
        status("The browser could not be started or crashed. Details are in logs/app.log.")

    status("Saving the Excel file")
    return _finish(store, summary)


def run_cached(workbook: str | Path, status: StatusCallback = _noop, progress: ProgressCallback = _noop) -> RunSummary:
    """Re-parse every page in ./cache/ (useful after a selector fix) without touching the site."""
    return run_saved_pages(config.CACHE_DIR, workbook, mode="re-process cache", status=status, progress=progress)
