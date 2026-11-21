"""
Player Extractor - simple screen for the scouting team (Streamlit).

    streamlit run app.py
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

import streamlit as st

from player_extractor import config
from player_extractor.logsetup import setup_logging

setup_logging()
log = logging.getLogger("app")

st.set_page_config(page_title="Player Extractor", page_icon="⚽", layout="wide")
st.title("Player Extractor")
st.caption("Saves Playmakerstats player details into your Excel file.")

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Excel file")
    workbook = st.text_input("File name (created if it does not exist)", value=config.DEFAULT_WORKBOOK)
    wb_path = Path(workbook)
    if wb_path.exists():
        st.success(f"Found: {wb_path.resolve()}")
    else:
        st.info("This file will be created on the first run.")
    if st.button("Open Excel file", disabled=not wb_path.exists()):
        try:
            os.startfile(wb_path.resolve())  # type: ignore[attr-defined]
        except Exception as e:  # noqa: BLE001
            log.exception("open excel failed")
            st.error(f"Could not open the file: {e}")
    st.divider()
    st.markdown(
        "**Tip:** the easiest way to add a player is the **Save player to Spotter** button in Chrome "
        "(see the README). Browse to the player, click the button, done."
    )

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def show_summary(summary) -> None:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Added", summary.added)
    c2.metric("Updated", summary.updated)
    c3.metric("Could not load", summary.failed)
    c4.metric("Needs review", summary.flagged)
    if summary.stopped_early:
        st.warning(summary.stopped_early)
    if summary.results:
        st.subheader("Players processed")
        st.dataframe(
            [{"Spotter ID": r.spotter_id, "Player": r.name, "What happened": r.action,
              "Needs review": "Yes" if r.needs_review else "No",
              "Missing": ", ".join(r.missing), "Notes": "\n".join(r.notes)} for r in summary.results],
            use_container_width=True, hide_index=True,
        )
    flagged = [r for r in summary.results if r.needs_review]
    if flagged:
        st.subheader("Please check these players")
        for r in flagged:
            st.markdown(f"- **{r.name}** ({r.spotter_id}): " + "; ".join(r.notes or ["key information missing"])
                        + (f". Missing: {', '.join(r.missing)}" if r.missing else ""))
    if summary.failures:
        st.subheader("Could not be processed")
        for what, why in summary.failures:
            st.markdown(f"- {what}: {why}")
    if summary.workbook.exists():
        st.download_button("Download the Excel file", data=summary.workbook.read_bytes(),
                           file_name=summary.workbook.name,
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def run_with_progress(fn, *args, **kwargs):
    bar = st.progress(0, text="Starting")
    status_box = st.empty()
    messages: list[str] = []

    def status(msg: str) -> None:
        messages.append(msg)
        status_box.info(msg)

    def progress(done: int, total: int) -> None:
        bar.progress(min(done / total, 1.0) if total else 1.0, text=f"{done} of {total}")

    try:
        summary = fn(*args, status=status, progress=progress, **kwargs)
    except PermissionError:
        log.exception("workbook locked")
        st.error("The Excel file is open in Excel. Please close it and run again.")
        return
    except Exception as e:  # noqa: BLE001
        log.exception("run failed")
        st.error(f"Something went wrong: {e}. Details are in logs/app.log.")
        return
    bar.progress(1.0, text="Finished")
    status_box.success("Finished")
    show_summary(summary)


# ---------------------------------------------------------------------------
# Main actions
# ---------------------------------------------------------------------------
tab_links, tab_tools = st.tabs(["Fetch from links", "Other tools"])

with tab_links:
    st.markdown(
        "Paste Playmakerstats **player** or **team** links below, one per line, then click **Run**. "
        "A Chrome window will open and load each page with a short pause in between."
    )
    st.warning(
        "Playmakerstats usually shows a **'Verify you are human'** check to this automated window, "
        "and in our tests it could not be passed even by a person. If that happens, use the "
        "**Save player to Spotter** button in your normal Chrome instead (see the README)."
    )
    links = st.text_area("Links (one per line)", height=160,
                         placeholder="https://www.playmakerstats.com/player/alessia-russo/482425\n"
                                     "https://www.playmakerstats.com/team/arsenal/16654")
    max_pages = st.number_input("Maximum pages this run", min_value=1, max_value=config.MAX_PAGES_PER_RUN,
                                value=min(50, config.MAX_PAGES_PER_RUN))
    if st.button("Run", type="primary", use_container_width=True):
        urls = [ln for ln in links.splitlines() if ln.strip()]
        if not urls:
            st.error("Please paste at least one link.")
        else:
            from player_extractor.runner import run_live
            run_with_progress(run_live, urls, wb_path, max_pages=int(max_pages))

with tab_tools:
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Try offline demo** - fills the Excel file from the sample pages in the `samples` folder.")
        if st.button("Try offline demo", use_container_width=True):
            from player_extractor.runner import run_saved_pages
            run_with_progress(run_saved_pages, "samples", wb_path, mode="offline demo")
    with col2:
        st.markdown("**Re-process saved pages** - reads every page already saved in the `cache` folder again "
                    "(no internet needed). Useful after a fix.")
        if st.button("Re-process saved pages", use_container_width=True):
            from player_extractor.runner import run_cached
            run_with_progress(run_cached, wb_path)

    st.divider()
    st.markdown("**Browser button status**")
    try:
        import urllib.request
        with urllib.request.urlopen("http://127.0.0.1:8765/health", timeout=2) as r:
            st.success("The 'Save player to Spotter' button is ready (capture server running).")
    except Exception:  # noqa: BLE001
        st.info("The capture server is not running. It starts automatically with run.bat; "
                "or start it with: python -m player_extractor.capture_server")
        if st.button("Start capture server"):
            try:
                subprocess.Popen([sys.executable, "-m", "player_extractor.capture_server", "--workbook", str(wb_path)],
                                 creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0))
                st.success("Started. Give it a few seconds, then refresh this page.")
            except Exception as e:  # noqa: BLE001
                log.exception("start capture server failed")
                st.error(f"Could not start it: {e}")
