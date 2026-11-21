"""
Live fetching with a visible browser the user can see and interact with.

Rules (deliberately simple, no tricks):
- Uses the user's installed Google Chrome (channel="chrome") with a persistent profile in
  ./browser_profile, so cookie choices and passed checks persist. Falls back to Playwright's
  Chromium only if Chrome is not installed.
- One page at a time, random 6-10 s pause between page loads, hard cap on pages per run.
- If the site shows a human-verification check, we simply wait for the person to complete it.
- Ad/tracker requests are blocked by domain list; popup tabs are closed; full-screen overlays are removed.
- Every fetched page is saved to ./cache/<id>.html so it can be re-parsed later without re-fetching.
"""
from __future__ import annotations

import logging
import random
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import BrowserContext, Page, Playwright, sync_playwright
from playwright.sync_api import Error as PlaywrightError

from . import config
from .parser import canonical_player_url, parse_squad_links, player_id_from_url, team_id_from_url

log = logging.getLogger(__name__)

StatusCallback = Callable[[str], None]

MSG_HUMAN_CHECK = "Please complete the check in the browser window"
MSG_TOO_MANY_CHECKS = "Site is asking for verification too often, please try again later."


class FetchError(Exception):
    """A single page could not be fetched (after the retry)."""


class TooManyChallenges(Exception):
    """The site asked for human verification more often than allowed in one run."""


class PageLimitReached(Exception):
    """The per-run page cap was hit."""


# ---------------------------------------------------------------------------
# URL classification
# ---------------------------------------------------------------------------

def classify_url(url: str) -> str:
    """'player' | 'team' | 'unknown'."""
    if player_id_from_url(url):
        return "player"
    if team_id_from_url(url):
        return "team"
    return "unknown"


def canonical_team_url(url: str) -> str:
    import re
    m = re.search(r"(/team/[^/?#]+/\d+)", url or "")
    return config.SITE_BASE_URL + m.group(1) if m else url


def _is_site_url(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return host.endswith(urlparse(config.SITE_BASE_URL).netloc.lower().removeprefix("www."))


def normalise_input_urls(lines: list[str]) -> tuple[list[str], list[str]]:
    """Clean pasted lines into canonical URLs. Returns (urls, rejected_lines)."""
    urls: list[str] = []
    rejected: list[str] = []
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if not line.startswith("http"):
            line = config.SITE_BASE_URL + ("" if line.startswith("/") else "/") + line
        if not _is_site_url(line):
            rejected.append(raw.strip())
            continue
        kind = classify_url(line)
        if kind == "player":
            url = canonical_player_url(line)
        elif kind == "team":
            url = canonical_team_url(line)
        else:
            rejected.append(raw.strip())
            continue
        if url not in urls:
            urls.append(url)
    return urls, rejected


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

def cache_path_for(url: str, cache_dir: Path) -> Path:
    pid = player_id_from_url(url)
    if pid:
        return cache_dir / f"{pid}.html"
    tid = team_id_from_url(url)
    return cache_dir / f"team_{tid}.html"


def save_to_cache(url: str, html: str, cache_dir: Path) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    text = f"<!DOCTYPE html>\n<!-- saved from {url} on {stamp} -->\n{html}"
    path = cache_path_for(url, cache_dir)
    path.write_text(text, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Fetcher
# ---------------------------------------------------------------------------

class Fetcher:
    """Context manager owning one browser window for the whole run."""

    def __init__(self, status: StatusCallback | None = None,
                 profile_dir: str | Path = config.BROWSER_PROFILE_DIR,
                 cache_dir: str | Path = config.CACHE_DIR,
                 max_pages: int = config.MAX_PAGES_PER_RUN):
        self.status = status or (lambda msg: log.info("status: %s", msg))
        # Chrome refuses a relative user-data-dir, so both paths are made absolute.
        self.profile_dir = Path(profile_dir).resolve()
        self.cache_dir = Path(cache_dir).resolve()
        self.max_pages = max_pages
        self.pages_loaded = 0
        self.challenges_seen = 0
        self.browser_name = ""
        self._pw: Playwright | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._last_load: float | None = None

    # -- lifecycle -----------------------------------------------------------

    def __enter__(self) -> Fetcher:
        self._pw = sync_playwright().start()
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self._context = self._launch()
        self._context.set_default_timeout(config.PAGE_LOAD_TIMEOUT_MS)
        self._context.route("**/*", self._block_ads)
        self._context.on("page", self._on_new_page)
        self._page = self._context.pages[0] if self._context.pages else self._context.new_page()
        return self

    def __exit__(self, *exc) -> None:
        try:
            if self._context:
                self._context.close()
        except PlaywrightError:
            pass
        if self._pw:
            self._pw.stop()

    def _launch(self) -> BrowserContext:
        assert self._pw is not None
        common = dict(user_data_dir=str(self.profile_dir), headless=False, viewport=None)
        try:
            ctx = self._pw.chromium.launch_persistent_context(channel="chrome", **common)
            self.browser_name = "Google Chrome"
            log.info("launched Google Chrome with profile %s", self.profile_dir)
            return ctx
        except PlaywrightError as e:
            log.warning("Google Chrome not available (%s); falling back to Chromium", str(e).splitlines()[0])
        ctx = self._pw.chromium.launch_persistent_context(**common)
        self.browser_name = "Chromium"
        log.info("launched Chromium with profile %s", self.profile_dir)
        return ctx

    # -- ads / popups --------------------------------------------------------

    @staticmethod
    def _block_ads(route) -> None:
        host = urlparse(route.request.url).netloc.lower()
        if any(host == d or host.endswith("." + d) for d in config.AD_DOMAINS):
            route.abort()
        else:
            route.continue_()

    def _on_new_page(self, page: Page) -> None:
        if page is self._page:
            return
        log.info("closing popup tab: %s", page.url or "(blank)")
        try:
            page.close()
        except PlaywrightError:
            pass

    def _dismiss_overlays(self) -> None:
        """Press Escape and remove full-screen fixed overlays. Never clicks anything."""
        assert self._page is not None
        try:
            self._page.keyboard.press("Escape")
            self._page.evaluate(
                """() => {
                    const vw = window.innerWidth, vh = window.innerHeight;
                    for (const el of Array.from(document.querySelectorAll('body *'))) {
                        const st = getComputedStyle(el);
                        if (st.position !== 'fixed') continue;
                        const r = el.getBoundingClientRect();
                        const covers = r.width >= vw * 0.9 && r.height >= vh * 0.9;
                        const isCookie = /cookie|consent|gdpr|privacy/i.test(el.id + ' ' + el.className);
                        if (covers && !isCookie) el.remove();
                    }
                }"""
            )
        except PlaywrightError as e:
            log.debug("overlay cleanup skipped: %s", e)

    # -- human check ---------------------------------------------------------

    def _is_challenge(self) -> bool:
        assert self._page is not None
        try:
            title = (self._page.title() or "").lower()
        except PlaywrightError:
            return False
        if any(m in title for m in config.CHALLENGE_TITLE_MARKERS):
            return True
        for sel in config.CHALLENGE_SELECTORS:
            try:
                if self._page.query_selector(sel) is not None:
                    return True
            except PlaywrightError:
                continue
        return False

    def _page_is_ready(self, kind: str) -> bool:
        """The element we need (profile card / squad list) is on the page."""
        assert self._page is not None
        sel = config.PAGE_READY_SELECTORS.get(kind)
        if sel is None:
            return not self._is_challenge()
        try:
            return self._page.query_selector(sel) is not None
        except PlaywrightError:
            return False

    def _wait_for_real_page(self, url: str, kind: str) -> None:
        """
        Poll until the real page is there. If a human check is showing, tell the user and wait
        for them. Raises FetchError after the time limit, TooManyChallenges if checks keep coming.
        """
        if self._page_is_ready(kind):
            return
        challenged = False
        deadline = time.monotonic() + config.HUMAN_CHECK_MAX_SECONDS
        while time.monotonic() < deadline:
            if not challenged and self._is_challenge():
                challenged = True
                self.challenges_seen += 1
                if self.challenges_seen > config.HUMAN_CHECK_MAX_PER_RUN:
                    raise TooManyChallenges(MSG_TOO_MANY_CHECKS)
                self.status(MSG_HUMAN_CHECK)
                log.info("human check shown for %s (occurrence %d)", url, self.challenges_seen)
            time.sleep(config.HUMAN_CHECK_POLL_SECONDS)
            if self._page_is_ready(kind):
                if challenged:
                    self.status("Thanks, continuing")
                return
        if challenged:
            raise FetchError(f"verification not completed within {config.HUMAN_CHECK_MAX_SECONDS} s")
        raise FetchError("page loaded but it is not a Playmakerstats profile/squad page")

    # -- fetching ------------------------------------------------------------

    def _polite_pause(self) -> None:
        if self._last_load is None:
            return
        wait = random.uniform(config.DELAY_SECONDS_MIN, config.DELAY_SECONDS_MAX)
        self.status(f"Waiting {wait:.0f} s before the next page (being polite to the site)")
        time.sleep(wait)

    def _load_once(self, url: str) -> str:
        assert self._context is not None
        if self._page is None or self._page.is_closed():
            log.info("browser tab was closed; opening a new one")
            self._page = self._context.new_page()
        self._polite_pause()
        if self.pages_loaded >= self.max_pages:
            raise PageLimitReached(f"page limit of {self.max_pages} reached")
        self.status(f"Opening {url}")
        self._page.goto(url, wait_until="domcontentloaded")
        self.pages_loaded += 1
        self._last_load = time.monotonic()
        self._wait_for_real_page(url, classify_url(url))
        try:
            self._page.wait_for_load_state("load", timeout=15_000)
        except PlaywrightError:
            pass
        self._dismiss_overlays()
        html = self._page.content()
        if len(html) < 2000:
            raise FetchError("page came back almost empty")
        return html

    def fetch(self, url: str) -> str:
        """Fetch one page (with one retry), save it to the cache and return the HTML."""
        try:
            html = self._load_once(url)
        except (TooManyChallenges, PageLimitReached):
            raise
        except (PlaywrightError, FetchError) as first:
            log.warning("first attempt failed for %s: %s", url, first)
            self.status("That page did not load, trying once more")
            try:
                html = self._load_once(url)
            except (TooManyChallenges, PageLimitReached):
                raise
            except (PlaywrightError, FetchError) as second:
                raise FetchError(str(second).splitlines()[0]) from second
        save_to_cache(url, html, self.cache_dir)
        return html

    def expand_team_urls(self, urls: list[str]) -> tuple[list[str], list[tuple[str, str]]]:
        """Replace team URLs by their squad's player URLs (fetching each team page once)."""
        players: list[str] = []
        failures: list[tuple[str, str]] = []
        for url in urls:
            if classify_url(url) != "team":
                if url not in players:
                    players.append(url)
                continue
            try:
                html = self.fetch(url)
            except (TooManyChallenges, PageLimitReached):
                raise
            except FetchError as e:
                failures.append((url, str(e)))
                continue
            links = parse_squad_links(html)
            self.status(f"Found {len(links)} players in the squad list")
            if not links:
                failures.append((url, "no squad list found on the team page"))
            for link in links:
                if link not in players:
                    players.append(link)
        return players, failures
