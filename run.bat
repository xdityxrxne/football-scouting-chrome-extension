@echo off
setlocal
cd /d "%~dp0"
title Player Extractor
if not exist logs mkdir logs

echo ==========================================
echo   Player Extractor
echo ==========================================
echo.

rem ---- 1. find Python 3.11 / 3.12 / 3.13 (preferred in that order) -------
rem The pinned packages have no installers for 3.14 yet, so newer versions are not used.
rem "py -0" lists every Python the launcher knows, including ones installed by other tools.
set "PY="
for %%V in (3.11 3.12 3.13) do (
    if not defined PY (
        for /f "tokens=1" %%T in ('py -0 2^>nul ^| findstr /C:"%%V"') do (
            if not defined PY (
                py %%T -c "import sys" >nul 2>&1 && set "PY=py %%T"
            )
        )
    )
)
if not defined PY (
    python -c "import sys; raise SystemExit(0 if (3,11) <= sys.version_info[:2] <= (3,13) else 1)" >nul 2>&1 && set "PY=python"
)
if not defined PY (
    echo Python 3.11 was not found.
    echo Please install Python 3.11 from https://www.python.org/downloads/windows/
    echo and tick "Add python.exe to PATH" during the install. Then run this again.
    pause
    exit /b 1
)

rem ---- 2. first-time setup ----------------------------------------------
if not exist ".venv\Scripts\python.exe" (
    echo First-time setup: preparing the program. This takes a few minutes...
    %PY% -m venv .venv >> logs\setup.log 2>&1
    if errorlevel 1 goto setup_failed
)
if not exist ".venv\.installed" (
    echo Installing components ^(one-off^)...
    ".venv\Scripts\python.exe" -m pip install --upgrade pip >> logs\setup.log 2>&1
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt >> logs\setup.log 2>&1
    if errorlevel 1 goto setup_failed
    echo Installing the browser component ^(one-off, may take a few minutes^)...
    ".venv\Scripts\python.exe" -m playwright install chromium >> logs\setup.log 2>&1
    echo ok > ".venv\.installed"
    echo Setup finished.
    echo.
)

rem ---- 3. start the browser-button server and the app --------------------
netstat -ano | findstr /C:"127.0.0.1:8765" | findstr LISTENING >nul
if errorlevel 1 (
    echo Starting the 'Save player to Spotter' button service...
    start "Spotter button service" /min ".venv\Scripts\python.exe" -m player_extractor.capture_server
) else (
    echo The 'Save player to Spotter' button service is already running.
)
echo Opening the Player Extractor in your web browser...
echo (Keep this window open while you use the program. Close it to stop.)
echo.
rem The app writes to its own log: logs\app.log is held open by the button service.
".venv\Scripts\python.exe" -m streamlit run app.py --server.headless false --server.port 8501 --browser.gatherUsageStats false >> logs\streamlit.log 2>&1
goto end

:setup_failed
echo.
echo Setup did not finish. Please send the file logs\setup.log to your support contact.
pause
exit /b 1

:end
endlocal
