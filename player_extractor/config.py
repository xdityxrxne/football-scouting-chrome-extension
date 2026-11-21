"""
All site-specific settings in one place.

If Playmakerstats changes its page layout, this is the only file that should
need editing. Everything here is plain Python data: strings, lists and dicts.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Site
# ---------------------------------------------------------------------------
SITE_BASE_URL = "https://www.playmakerstats.com"

# Player page URL looks like /player/<slug>/<numeric id>[/...]; team page /team/<slug>/<id>
PLAYER_URL_PATTERN = r"/player/[^/?#]+/(\d+)"
TEAM_URL_PATTERN = r"/team/[^/?#]+/(\d+)"

# ---------------------------------------------------------------------------
# Player page: CSS selectors
# ---------------------------------------------------------------------------
SEL_HEADER = "div.zz-entity-header"
SEL_DISPLAY_NAME = "h1 span.name"          # display name, may contain span.number
SEL_SHIRT_NUMBER = "span.number"           # inside the display name
SEL_HEADER_TEAM_LINK = "a[href*='/team/']"  # current-season club link in header (fallback)

SEL_PROFILE_CARD = "div.card-data.bio"
SEL_PROFILE_ROW = "div.card-data__row"
SEL_PROFILE_LABEL = ".card-data__label"
SEL_PROFILE_VALUE = ".card-data__value"
SEL_PROFILE_VALUE_TEXT = ".text"           # text inside flag+text widgets

SEL_MARKET_VALUE = "div.rectangle[title='Market value'] div.value"

SEL_CAREER_BODY = "div#coach_career"
SEL_CAREER_SECTION = "div.section"
SEL_CAREER_TABLE = "table.career"
CAREER_SECTION_CLUBS = "football"           # section whose table holds club spells (lower-case compare)
SEL_CAREER_TEAM_LINK = "a[href*='/team/']"
CAREER_LOAN_MARKER = "(L)"

# Profile labels (lower-case, compared with startswith / equality)
LABEL_FULL_NAME = ("name",)
LABEL_DOB = ("date of birth",)
LABEL_NATIONALITY = ("nationality",)            # also "Nationality / Dual Nationality"
LABEL_BIRTHPLACE = ("country of birth",)        # also "Country of Birth (Born)"
LABEL_POSITION = ("position",)
LABEL_FOOT = ("preferred foot",)
LABEL_HEIGHT_WEIGHT = ("height / weight", "height", "weight")
LABEL_CONTRACT = ("contract",)
LABEL_CURRENT_CLUB = ("current club",)
LABEL_AGENT = ("agent",)                        # never seen on the site; kept so it works if it appears
LABEL_HOMEGROWN = ("homegrown",)                # never seen on the site

EMPTY_VALUE_MARKERS = {"", "-", "–", "—", "n/a", "?"}

# ---------------------------------------------------------------------------
# Team / squad page
# ---------------------------------------------------------------------------
SEL_SQUAD_BODY = "div#team_squad"
SEL_SQUAD_PLAYER_LINK = "div.staff div.name a[href*='/player/']"

# ---------------------------------------------------------------------------
# Position mapping: site name -> Spotter code. Edit freely.
# Anything not listed is left blank and flagged with the raw value in Notes.
# ---------------------------------------------------------------------------
POSITION_CODES = ["GK", "CB", "RB", "LB", "RWB", "LWB", "CDM", "CM", "CAM", "RW", "LW", "ST", "CF"]

POSITION_MAP: dict[str, str] = {
    "goalkeeper": "GK",
    "centre back": "CB",
    "center back": "CB",
    "central defender": "CB",
    "right back": "RB",
    "left back": "LB",
    "right wing back": "RWB",
    "right wing-back": "RWB",
    "left wing back": "LWB",
    "left wing-back": "LWB",
    "defensive midfielder": "CDM",
    "centre midfielder": "CM",
    "central midfielder": "CM",
    "center midfielder": "CM",
    "attacking midfielder": "CAM",
    "right winger": "RW",
    "left winger": "LW",
    "striker": "ST",
    "centre forward": "CF",
    "center forward": "CF",
}

# Generic group names the site uses when it has no specific position.
# These are deliberately NOT mapped (too ambiguous) and always flagged.
GENERIC_POSITIONS = {"defender", "midfielder", "forward", "attacker"}

# ---------------------------------------------------------------------------
# Nationality labels: site country name -> label used in the sheet.
# Countries not listed are written exactly as the site shows them ("Portugal").
# ---------------------------------------------------------------------------
NATIONALITY_MAP: dict[str, str] = {
    "england": "English",
    "scotland": "Scottish",
    "wales": "Welsh",
    "northern ireland": "Northern Irish",
    "ireland": "Irish",
    "republic of ireland": "Irish",
}
NATIONALITY_JOINER = " / "

# ---------------------------------------------------------------------------
# Derived-field rules
# ---------------------------------------------------------------------------
AGE_GROUPS = [(15, "U15"), (18, "U18"), (21, "U21")]   # age < limit -> label; otherwise Senior
AGE_GROUP_DEFAULT = "Senior"

# Football season starts in this month (July): 2026-07-01 .. 2027-06-30 is "2026/27".
SEASON_START_MONTH = 7

# Market value. The site shows euros. £ conversion is OFF unless a rate is set here,
# e.g. MARKET_VALUE_EUR_TO_GBP_RATE = 0.85
MARKET_VALUE_EUR_TO_GBP_RATE: float | None = None

# ---------------------------------------------------------------------------
# Excel workbook
# ---------------------------------------------------------------------------
DEFAULT_WORKBOOK = "players.xlsx"
BACKUP_DIR = "backups"
SHEET_PLAYERS = "Players"
SHEET_HISTORY = "Club History"
SHEET_LEVELS = "Club Levels"
SHEET_LOG = "Run Log"

PLAYER_COLUMNS = [
    "Spotter ID", "First name", "Last name", "Known as", "Date of birth", "Nationality",
    "Place of birth", "Homegrown", "Primary position", "Secondary positions", "Preferred foot",
    "Height (cm)", "Weight (kg)", "Age group", "Current club", "Contract expiry", "Availability",
    "Agent", "Market value (£)", "Playmakerstats URL", "Missing fields", "Needs review", "Notes",
    "Last updated", "Full name (site)",
]
HISTORY_COLUMNS = ["Spotter ID", "Player name", "Club", "Level", "From", "To"]
LEVEL_COLUMNS = ["Club", "Level"]
LOG_COLUMNS = ["timestamp", "mode", "URLs processed", "added", "updated", "failed", "flagged", "notes"]

CLUB_LEVELS = ["Professional", "Semi-professional", "Amateur", "Academy"]

# Fields that count towards "Missing fields" when blank.
MISSING_TRACKED_FIELDS = [
    "First name", "Last name", "Date of birth", "Nationality", "Place of birth", "Homegrown",
    "Primary position", "Preferred foot", "Height (cm)", "Weight (kg)", "Age group",
    "Current club", "Contract expiry", "Availability", "Agent", "Market value (£)",
]
# Fields Playmakerstats never publishes (as of Nov 2026). They stay in the sheet for the client
# to fill by hand, but are NOT listed under "Missing fields" because they are always blank.
SITE_NEVER_PUBLISHES = ["Homegrown", "Agent"]

# Blank in any of these -> Needs review = Yes
KEY_FIELDS = ["First name", "Last name", "Date of birth", "Primary position", "Current club"]

# Prefix for notes the tool writes. Lines without it are the client's own and are never touched.
AUTO_NOTE_PREFIX = "(auto) "

SPOTTER_ID_PREFIX = "SP-"
SPOTTER_ID_WIDTH = 5

# ---------------------------------------------------------------------------
# Fetching (Milestone 3). Listed here so limits live in one place.
# ---------------------------------------------------------------------------
BROWSER_PROFILE_DIR = "browser_profile"
CACHE_DIR = "cache"
DELAY_SECONDS_MIN = 6.0
DELAY_SECONDS_MAX = 10.0
MAX_PAGES_PER_RUN = 300
PAGE_LOAD_TIMEOUT_MS = 60_000
HUMAN_CHECK_POLL_SECONDS = 3
HUMAN_CHECK_MAX_SECONDS = 180
HUMAN_CHECK_MAX_PER_RUN = 3
CHALLENGE_TITLE_MARKERS = ["just a moment", "attention required", "verify you are human"]
CHALLENGE_SELECTORS = ["#challenge-form", "#challenge-running", "#challenge-stage", "iframe[src*='challenges.cloudflare.com']"]
# A page only counts as loaded when the element we need is present (otherwise it is a
# challenge page, an error page or an interstitial, and it is never parsed or saved).
PAGE_READY_SELECTORS = {"player": SEL_PROFILE_CARD, "team": SEL_SQUAD_BODY}
AD_DOMAINS = [
    "doubleclick.net", "googlesyndication.com", "googleadservices.com", "adnxs.com",
    "adsrvr.org", "criteo.com", "criteo.net", "taboola.com", "outbrain.com", "pubmatic.com",
    "rubiconproject.com", "openx.net", "casalemedia.com", "amazon-adsystem.com",
    "smartadserver.com", "teads.tv", "33across.com", "yieldmo.com", "sharethrough.com",
    "media.net", "popads.net", "propellerads.com", "onclickads.net",
]
