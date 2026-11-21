# Player Extractor – developer notes

Python 3.11+, Windows. No bot-protection bypass of any kind is used or permitted (see "Scope").

## Architecture

All modules live in the `player_extractor/` package; `app.py` (Streamlit) and `scripts/` sit at the repo root.

```
run.bat ──► capture_server (Flask, 127.0.0.1:8765)  ◄── extension/ (Chrome MV3 button)
        └─► app.py (Streamlit UI) ──► runner ──► fetcher (Playwright, visible Chrome)
                                        │           └─ cache/<player_id>.html
                                        ├─► parser ──► derive
                                        └─► excel_store ──► players.xlsx (+ backups/)
config: every selector, label, mapping and limit.   models: PlayerRecord / Spell dataclasses.
ids: Spotter IDs.   offline: reading saved pages.   logsetup: logs/app.log.
```

| Module | Responsibility |
|---|---|
| `config.py` | Selectors, profile labels, position/nationality maps, delays, limits, ad domains, sheet columns, `SITE_NEVER_PUBLISHES`. |
| `parser.py` | `parse_player(html, url, today=None) -> (PlayerRecord, [Spell])`, `parse_squad_links(html)`, `is_player_page`, `is_team_page`. Pure. |
| `derive.py` | Age group, availability, position mapping, units, seasons, contract month, name split, missing/review rules. Pure. |
| `excel_store.py` | `PlayerStore`: load / `upsert` / backup / save with styling. Replaces Club History per player; merges Notes; fills Level from Club Levels. |
| `runner.py` | `run_saved_pages`, `run_live`, `run_cached` -> `RunSummary`; writes Run Log. |
| `fetcher.py` | `Fetcher` context manager (persistent Chrome profile, ad blocking by domain, popup closing, overlay removal, human-check wait, polite delays, page cap, cache). `normalise_input_urls`. |
| `capture_server.py` | `create_app(workbook)`; `POST /capture {url, html}`. |
| `extension/` | Manifest V3 action button: grabs `outerHTML` + URL, posts to the server, shows a toast. |

## Data flow and guarantees

- Upsert key: Spotter ID if the row has one, otherwise the numeric player ID in the URL.
- New Spotter ID = highest existing + 1; never reused. Client-filled IDs are kept.
- Blank incoming values never overwrite existing values. "Missing fields" / "Needs review" are
  recomputed on the merged row.
- Notes: lines starting with `(auto) ` are regenerated; other lines belong to the client.
- A page is parsed only if it contains the profile card (`is_player_page`); challenge/error pages
  are rejected before anything touches the workbook.
- Every save first copies the existing workbook to `backups/`.

## Fixing selectors when the site changes

1. Save the new page from your browser into `samples/` (or use a file from `cache/`).
2. Open it and compare with [FIELD_MAP.md](FIELD_MAP.md); update the `SEL_*` / `LABEL_*` entries in `player_extractor/config.py`.
3. `pytest` – `tests/test_parser.py` asserts the real values from the sample pages, so a broken
   selector fails loudly.
4. Click **Re-process saved pages** in the app (or `python scripts/fetch_cli.py --cached`) to re-parse
   everything in `cache/` without touching the site.

Adding a position name: add it to `POSITION_MAP` (lower-case key -> code). Generic group words
stay in `GENERIC_POSITIONS` so they are flagged rather than guessed.
Adding a nationality label: `NATIONALITY_MAP`. Market value in £: set `MARKET_VALUE_EUR_TO_GBP_RATE`.

## Running

```
py -3.11 -m venv .venv && .venv\Scripts\pip install -r requirements-dev.txt   # `py -0` lists installed Pythons
.venv\Scripts\python -m playwright install chromium         # fallback browser only
.venv\Scripts\python -m pytest                               # 46 tests, ~10 s
.venv\Scripts\ruff check .                                    # lint
.venv\Scripts\python scripts/demo_offline.py                 # builds players.xlsx from samples/
.venv\Scripts\python -m player_extractor.capture_server      # browser-button endpoint
.venv\Scripts\python -m streamlit run app.py
.venv\Scripts\python scripts/fetch_cli.py --max-pages 3 URL ...   # live mode from the command line
```

`requirements.txt` holds the runtime dependencies the client installs; `requirements-dev.txt` adds pytest and ruff.

`run.bat` does all of the above for the client (venv on first run, pip, playwright, then starts the
capture server minimised and Streamlit). `make_shortcut.bat` creates the Desktop shortcut.

## Scope: the Cloudflare check

Playmakerstats sits behind Cloudflare. A browser started by Playwright (Chrome or Chromium,
persistent profile) is shown the "Verify you are human" Turnstile on every page, and in testing
a real person ticking the box did **not** clear it. The tool therefore waits for a human and gives
up politely; it does not and must not try to get around the check (no stealth plugins, no
fingerprint changes, no `--enable-automation` removal, no proxies). The supported live path is the
extension button in the client's own Chrome, which involves no automation at all.

## Tests

- `test_parser.py` – every sample page against the values in [FIELD_MAP.md](FIELD_MAP.md); squad links; spell
  merging incl. mixed season formats; rejection of non-profile pages.
- `test_derive.py` – age-group boundaries (birthday today), availability rules, position map,
  units, seasons, contract month, market value with/without rate, name split.
- `test_excel_store.py` – create, run twice (no duplicates, IDs stable), blanks don't overwrite,
  Notes/Club Levels preserved, pre-filled Spotter ID kept, backups.
- `test_capture_server.py` – end-to-end through the Flask test client.
- `test_fetcher_offline.py` – URL normalisation and cache round-trip (no browser).
