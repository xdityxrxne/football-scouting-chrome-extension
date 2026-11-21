# FIELD_MAP — where each field lives on a saved Playmakerstats player page

Milestone 1 result. Based only on the 7 files in `./samples/` (5 player pages, 2 women's squad pages), saved 2026-11-14.
Nothing below was fetched from the live site.

Samples (and the player ID taken from each URL):

| File | URL | Player ID |
|---|---|---|
| player_wsl_star_alessia_russo.html | /player/alessia-russo/482425 | 482425 |
| player_dual_nationality_lucy_bronze.html | /player/lucy-bronze/153162 | 153162 |
| player_long_career_kim_little.html | /player/kim-little/132319 | 132319 |
| player_championship_emily_syme.html | /player/emily-syme/563784 | 563784 |
| player_sparse_youth_neeve_mcdonald.html | /player/neeve-mcdonald/3697506 | 3697506 |
| team_arsenal_women.html | /team/arsenal/16654 | team 16654 |
| team_bristol_city_women.html | /team/bristol-city/109452 | team 109452 |

Every file begins with `<!-- saved from <URL> on <timestamp> -->`; the offline loader will read the URL from that comment. Files are UTF-8 (`<meta charset="UTF-8">`).

## Page anatomy (player page)

- **Header** `div.zz-entity-header`: `h1 > span.name` holds the display name, with an optional `span.number` (shirt number, e.g. "23.") inside it. Below it `div.zz-enthdr-info` shows nationality flag, age, a *generic* position ("Forward"/"Midfielder"/"Defender"), "Women", "Football". Also contains the **Market value** pill (only when the site has one) and the current-season club link.
- **PROFILE card** `div.card-data.bio`: a list of `div.card-data__row`, each with `span.card-data__label` + one `.card-data__value` or a `.card-data__values` group of several. Rows that are collapsed behind "more" carry class `hiddentr d-none` but are present in the HTML, so they parse fine. **Only rows that have data are rendered** (no label = field absent), except Date of Birth which shows "-" when unknown.
- **Career card** (`h2.card-data__title` = "Career"): `div#coach_career` → `div.section` ("Football") → `table.career` with columns `[blank, SEASON, TEAM, G, GS, AST]`. A second `div.section` "EDITIONS" + `table.career` lists international tournaments (not club spells — must be skipped).
- **Transfers card** (present on 4/5 pages, absent for McDonald): `div.transfer-line` blocks with two `span.team` and `span.date` (dd/mm/yyyy). Not needed for the sheets; noted for completeness.

## Players sheet

| Field | Where on the page (selector / label) | Found in samples | Notes |
|---|---|---|---|
| Spotter ID | — (ours, assigned by the tool) | n/a | |
| First name / Last name | `h1 span.name` text minus `span.number` ("Alessia Russo"); split on last space as a *default*. Full legal name is in PROFILE row **Name** ("Alessia Mia Teresa Russo") | 5/5 | Split is a heuristic → set **Needs review** only if name has ≠2 tokens? No: brief says never guess, so: First = all tokens but last, Last = last token, and add a Note "name split automatically" when the name has >2 tokens. |
| Known as | `h1 span.name` (minus number) when it differs from PROFILE **Name** | 5/5 | e.g. "Lucy Bronze" vs "Lucia Roberta Tough Bronze"; "Kim Little" vs "Kim Alison Little". Blank when identical. |
| Date of birth | PROFILE row **Date of Birth**, value "1999-02-08 (27 -yrs-old)" → first 10 chars | 4/5 (McDonald shows "-") | Already ISO. |
| Nationality | PROFILE row **Nationality** or **Nationality / Dual Nationality**; each `.card-data__value .text` is one country | 5/5 | Bronze: "England", "Portugal" → "English / Portugal" per the brief's style via `config.NATIONALITY_MAP`. Also in header flag (ignored). |
| Place of birth | PROFILE row **Country of Birth** or **Country of Birth (Born)**; `.text` is "England" or "England (Taunton)" | Country 5/5; town 1/5 (Syme) | Town only when in brackets. Country alone → Place of birth = country (fill), no town. |
| Homegrown | **not on page** | 0/5 | No label anywhere. Blank + flagged. |
| Primary position | PROFILE row **Position**: `.card-data__values > .card-data__value` — the **first** one | 5/5 | Values seen: Striker; Right Back; Attacking Midfielder; Defender (McDonald, generic → unmappable → blank + flag + raw in Notes). Also `img[alt]` icons carry the same names. Header shows only the generic group word — not used. |
| Secondary positions | same row, 2nd+ `.card-data__value` | 3/5 | Bronze "Centre Back"; Little "Centre Midfielder"; Syme "Forward" (generic → unmapped → flag). |
| Preferred foot | PROFILE row **Preferred foot** | 3/5 (Russo, Bronze, Little) | "Right". Row absent for Syme, McDonald. |
| Height (cm) | PROFILE row **Height / Weight**: "175 cm / 68 kg" → first number | 3/5 | Row absent for Syme, McDonald. |
| Weight (kg) | same row, second number | 3/5 | Must tolerate "175 cm / -" style if only one is known (not seen in samples; code defensively). |
| Age group | derived from DOB | 4/5 derivable | |
| Current club | PROFILE row **Current club** (`hiddentr`), `.text` | 5/5 | Cross-check: header `a[href^="/team/"]` inside `.zz-entity-header` and first career row. Use PROFILE row; fall back to header link. |
| Contract expiry | PROFILE row **Contract**, value "2027/06" (YYYY/MM) | 2/5 (Bronze 2027/06, Little 2026/06) | Only year+month published. Proposal: write as last day of that month (2027-06-30) and add Note "contract month only". Day is **not** on the page. |
| Availability | derived from Contract expiry | 2/5 derivable | 3/5 → blank + flag. |
| Agent | **not on page** | 0/5 | No "agent" text anywhere in any sample. |
| Market value (£) | header pill `div.rectangle[title="Market value"] div.value span` — "100 k €" | 1/5 (Little) | Site publishes **euros** only. Per brief: leave £ blank, put raw "100 k €" in Notes. |
| Playmakerstats URL | from the saved-from comment / the URL passed in; canonical `a[href]` in `h1`'s parent `.profile_picture a` also equals `/player/<slug>/<id>` | 5/5 | Player ID = last path segment (digits). |
| Missing fields / Needs review / Notes / Last updated | derived | n/a | |

Also available but not requested: Status ("Active"), Caps / Youth Caps, social Links, shirt number, Transfers list with dates and fees ("-" everywhere in samples).

## Club History sheet (per spell)

Source: `div#coach_career table.career` under the `div.section` whose text is "Football" (skip the "EDITIONS" section).

| Column | Where | Notes |
|---|---|---|
| Club | `td:nth-child(3) .text a` text; `a[href]` = `/team/<slug>/<team-id>?epoca_id=<season-id>` | Team ID is stable across seasons — use it to group rows into spells. |
| Season | `td:nth-child(2)` text | Formats seen: `2026/27`, and calendar-year leagues `2018`, `2017`, `2022`, `2016`, `2009` (NWSL/US college). **Blank season cell = continuation row: same season as the row above** (two clubs in one season). |
| Loan marker | literal `(L)` text node in the team cell + `<span>[Parent Club]</span>`; the `a[title]` reads "Loan - Aston Villa" | Syme 2021/22 Sheffield United (L) [Aston Villa]; Little 2022 Seattle Reign (L) [Arsenal]; 2016 Melbourne City (L) [Seattle Reign]. Proposal: Club = loan club, add Note "loan from X"; keep the parent-club row as its own spell. |
| Squad label | `<span>[Women]</span>`, `[Women Universitário]` | Ignored for the sheet. |
| From / To | Rows are one-per-season, newest first; the tool merges consecutive rows with the same team ID into one spell: From = oldest season, To = newest season, or "Now" when the newest season is the current season (2026/27, i.e. the first row's season). | Calendar-year seasons ("2018") are written as-is, not forced into YYYY/YY, since 2018 ≠ 2018/19. |
| Level | lookup from Club Levels sheet; not on the page | — |

Row count sanity: Russo 11 rows, Bronze 23, Little 24, Syme 12, McDonald 1.

## Squad / team pages

- Squad list: `div#team_squad` → repeating pairs of `div.section` (Goalkeeper / Defender / Midfielder / Forward) and `div.staff_line` → `div.staff` → `div.name .text a[href^="/player/"]` (href like `/player/emily-mutch/729112?epoca_id=156`), plus `div.number` (shirt or "-") and `span` age ("25 -yrs-old" or "-").
- Counts: Arsenal 28 players, Bristol City 31 players in `#team_squad`.
- Other `/player/` links on the page (Most Games/Most Goals tables, MOST USED XI, Transfers card, Related Teams) are **outside** `#team_squad` and will be ignored, so recently-departed players listed under Transfers are not collected.
- Team ID = last path segment of `/team/<slug>/<id>`. Squad links carry `?epoca_id=156` (season id for 2026/27); the tool strips the query before fetching the player page.
- Page title "Arsenal (Women) - England - …" identifies the women's team.

## Fields Playmakerstats does not appear to publish (from these samples)

1. **Homegrown** — nowhere on the page. Will always be blank + flagged unless the client fills it by hand.
2. **Agent** — nowhere on the page.
3. **Contract expiry day** — only year/month ("2027/06"), and only on 2 of 5 pages.
4. **Market value in £** — euros only, and only for 1 of 5 players. Raw value goes to Notes.
5. **Place of birth (town)** — only when the site shows it in brackets; 1 of 5.
6. **Preferred foot, Height, Weight** — absent for lower-profile players (Syme, McDonald).
7. **Date of birth** — absent for youth players (McDonald shows "-"), which also blocks Age group.
8. **Club level** (Professional/Semi-pro/…) — not on the site; comes from the client-edited Club Levels sheet.
9. **Specific position for youth/sparse players** — McDonald only has "Defender", which cannot be mapped to one of the 13 codes; flagged with the raw value.

## Decisions I'd like confirmed (or I'll go with the proposal)

- Contract "2027/06" → stored as 2027-06-30 with Note "contract month only". Alternative: leave blank.
- Name split: First = everything but the last word, Last = last word, from the short display name (not the full legal name). Multi-part surnames ("van Domselaar", "De Almeida", "Wubben-Moy") will be split wrong by this rule; such names get a Note so the client can fix them. The full legal name is **not** stored anywhere unless you want a column for it.
- Loan spells: Club = the loan club, Note "loan from <parent>"; parent club's own row in the same season remains a separate spell.
- Calendar-year seasons ("2018") kept as "2018", not rewritten to "2018/19".
