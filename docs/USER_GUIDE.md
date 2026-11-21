# Player Extractor – how to use it

This program copies player details from the Playmakerstats website into an Excel file
(`players.xlsx`). You never have to type a command. Everything is a double-click or a button.

---

## 1. First-time setup (once, about 10 minutes)

1. Make sure **Python 3.11 or newer** is installed. If you are not sure, open the Start menu and
   type "Python". If nothing shows up, install it from https://www.python.org/downloads/windows/
   and tick **"Add python.exe to PATH"** on the first screen of the installer.
2. Open the **Player Extractor** folder.
3. Double-click **`make_shortcut.bat`**. This puts a **Player Extractor** icon on your Desktop.
4. Double-click the new **Player Extractor** icon on the Desktop.
   The first time it prepares itself (a black window shows progress). Wait until a web page called
   **Player Extractor** opens in your browser. Later starts take a few seconds.
5. Install the browser button (next section).

Keep the black window open while you use the program. Closing it stops the program.

## 2. Install the "Save player to Spotter" button in Chrome (once)

This button is the easiest way to add players, and it works even when the website asks
"Verify you are human", because you are browsing normally.

1. Open Google Chrome.
2. In the address bar type `chrome://extensions` and press Enter.
3. Turn on **Developer mode** (switch in the top-right corner).
4. Click **Load unpacked**.
5. Choose the folder **`extension`** inside the Player Extractor folder, then **Select folder**.
6. Click the puzzle-piece icon to the right of the address bar and **pin** "Save player to Spotter"
   so it is always visible.

*(Screenshot placeholder: chrome://extensions with Developer mode on and the Load unpacked button.)*
*(Screenshot placeholder: the pinned button next to the address bar.)*

## 3. Adding a player (the normal way)

1. Make sure the Player Extractor is running (Desktop icon; the black window is open).
2. In Chrome, go to the player's page on www.playmakerstats.com
   (for example `https://www.playmakerstats.com/player/alessia-russo/482425`).
   If the site shows "Verify you are human", tick it as usual.
3. Click the **Save player to Spotter** button.
4. A green message appears: **"Saved: Alessia Russo (3 fields missing)"**. Done.
   A red message tells you what went wrong (for example, the program is not running).

Each click saves the player, their club history, and adds any new clubs to the Club Levels sheet.

## 4. Updating a player

Simply save the player again (section 3). The existing row is updated, nothing is duplicated,
and the **Spotter ID never changes**. Anything you typed yourself in the **Notes** column is kept.
Values already in the sheet are never blanked out by the website.

## 5. The Player Extractor page (in your web browser)

- **Excel file** (left side): the file name to use; `players.xlsx` is the default.
  **Open Excel file** opens it in Excel.
- **Fetch from links**: paste player or team links and click **Run**. A Chrome window opens and
  loads the pages one by one. **Note:** the website usually shows a "Verify you are human" check to
  this window and, in our tests, it did not accept the tick. If that happens, use the browser button
  (section 3) instead. Nothing wrong is ever written to the Excel file when a page fails.
- **Other tools → Try offline demo**: fills the file from the example pages in the `samples` folder,
  so you can see what the result looks like.
- **Other tools → Re-process saved pages**: every page you have ever saved is kept in the `cache`
  folder. This button reads them all again without the internet (useful after a fix).
- **Download the Excel file**: a copy of the file.

**Close the Excel file before saving players.** If it is open in Excel, the program cannot write to
it and will tell you.

## 6. What the Excel sheets contain

- **Players** – one row per player. Columns include Spotter ID, names, date of birth, nationality,
  position codes, height/weight, age group, current club, contract expiry, availability, the
  Playmakerstats link, **Missing fields**, **Needs review**, **Notes** and the full name as shown on
  the site.
- **Club History** – one row per spell at a club (From / To season, "Now" = current).
- **Club Levels** – a list of every club seen, with a **Level** column for you to fill in
  (Professional / Semi-professional / Amateur / Academy). Fill it in once; it is used for every
  player's club history from then on. New clubs are added with a blank Level.
- **Run Log** – what was done and when.

### What "Needs review" means

**Yes** means a person should look at the row, because one of these happened:
- a key field is missing (first name, last name, date of birth, position, current club);
- the website's position was too vague to use (for example just "Defender") – the original word
  is in Notes;
- the contract date on the site has passed but the player is still listed this season
  ("contract date may be out of date");
- the name could not be split with confidence ("check name split").

Rows with **Needs review = Yes** are shaded yellow. Lines in Notes that start with `(auto)` were
written by the program and will be refreshed next time; your own lines are left alone.

### Fields the website does not publish

Playmakerstats does **not** show **Homegrown** or **Agent** for any player, so those columns are
always empty unless you fill them in yourself. They are not listed under "Missing fields".
Also: contract dates are shown as month only (we use the last day of that month), market values
are in euros (kept in Notes, the £ column stays empty), and youth players often have no date of
birth, height, weight or exact position.

## 7. If the website asks for verification

- **Using the browser button:** tick the box as you normally would, wait for the player page to
  show, then click the button.
- **Using "Fetch from links":** the program pauses and shows "Please complete the check in the
  browser window". If it does not accept the tick, close the Chrome window and use the browser
  button instead. If the check appears more than 3 times in one run the program stops and says
  "Site is asking for verification too often, please try again later."

## 8. Backups

Every time the Excel file is saved, the previous version is copied into the **`backups`** folder
with the date and time in the name, for example `players_20261114_153000.xlsx`. To go back,
copy one of them over `players.xlsx`.

## 9. If something goes wrong

- The black window closed by itself / nothing opens: double-click the Desktop icon again.
- "The Excel file is open": close Excel and try again.
- Anything else: send the files **`logs\app.log`** and **`logs\streamlit.log`** (and
  `logs\setup.log` for setup problems) to your support contact.
