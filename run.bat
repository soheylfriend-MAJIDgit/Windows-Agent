@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
title Windows Agent

rem ===============================================================
rem  Windows Agent launcher (v1.7-16 - network acceptance gating + local OCR installer)
rem  Double-click this file to start the app.
rem  Required packages are installed automatically on first run.
rem ===============================================================

rem --- 1) find Python -------------------------------------------------
set "PY_CMD="
where py >nul 2>nul && set "PY_CMD=py -3"
if not defined PY_CMD (
    where python >nul 2>nul && set "PY_CMD=python"
)
if not defined PY_CMD (
    echo.
    echo [ERROR] Python was not found on this computer.
    echo Install Python 3.9+ from https://www.python.org/downloads/windows/
    echo and make sure "Add python.exe to PATH" is checked.
    echo.
    pause
    exit /b 1
)

rem --- 2) required packages -------------------------------------------
set "MISSING="
%PY_CMD% -c "import webview" >nul 2>nul || set "MISSING=!MISSING! pywebview"
%PY_CMD% -c "import PIL" >nul 2>nul || set "MISSING=!MISSING! Pillow"

if defined MISSING (
    echo.
    echo ============================================================
    echo   Installing required packages:!MISSING!
    echo   This happens only once and takes a minute.
    echo ============================================================
    echo.
    %PY_CMD% -m pip install --upgrade pip >nul 2>nul
    %PY_CMD% -m pip install --disable-pip-version-check!MISSING!
    if errorlevel 1 (
        echo.
        echo [WARN] First attempt failed. Trying with a mirror ...
        %PY_CMD% -m pip install --disable-pip-version-check --index-url https://pypi.org/simple!MISSING!
    )
    rem --- verify again
    set "STILL="
    %PY_CMD% -c "import webview" >nul 2>nul || set "STILL=!STILL! pywebview"
    %PY_CMD% -c "import PIL" >nul 2>nul || set "STILL=!STILL! Pillow"
    if defined STILL (
        echo.
        echo [ERROR] Could not install:!STILL!
        echo Run this command manually, then start again:
        echo     %PY_CMD% -m pip install pywebview Pillow
        echo.
        echo If you use a proxy ^(v2rayN^), make sure it is running.
        echo.
        pause
        exit /b 1
    )
    echo.
    echo   All packages are installed.
    echo.
)

rem --- 3) Keep the visible build identity current --------------------
%PY_CMD% "%~dp0tools\update_build_stamp.py"

rem --- 4) Optional isolated PaddleOCR install (explicit user consent) --
set "VISION_READY="
set "VISION_ROOT=%LOCALAPPDATA%\Windows-Agent\vision"
if exist "%VISION_ROOT%\.venv\Scripts\python.exe" if exist "%VISION_ROOT%\paddle_ocr_helper.py" if exist "%VISION_ROOT%\vision_ready.json" set "VISION_READY=1"
if not defined VISION_READY (
    echo.
    echo Local PaddleOCR is not installed or has not passed its offline self-test.
    echo This feature is optional; Windows Agent will still start without OCR.
    echo Arena prompt execution stays disabled until OCR and network checks are verified.
    choice /C YN /N /M "Run the isolated PaddleOCR installer? Initial model download needs internet [Y/N]: "
    if not errorlevel 2 (
        call "%~dp0install_vision.bat"
    )
)

rem --- 5) WebView2 Runtime (the browser engine of the window) ----------
set "WEBVIEW2="
reg query "HKLM\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}" /v pv >nul 2>nul && set "WEBVIEW2=1"
if not defined WEBVIEW2 reg query "HKLM\SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}" /v pv >nul 2>nul && set "WEBVIEW2=1"
if not defined WEBVIEW2 reg query "HKCU\SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}" /v pv >nul 2>nul && set "WEBVIEW2=1"

if not defined WEBVIEW2 (
    echo.
    echo ------------------------------------------------------------
    echo   The "WebView2 Runtime" is missing.
    echo   The window of the app needs it. Install it once from:
    echo   https://developer.microsoft.com/microsoft-edge/webview2/
    echo   Windows 11 and most updated Windows 10 already have it.
    echo ------------------------------------------------------------
    echo.
)

rem --- 4) run the GUI without a console window -------------------------
set "PYW_EXE="
for /f "delims=" %%i in ('%PY_CMD% -c "import sys,os;print(os.path.join(os.path.dirname(sys.executable),'pythonw.exe'))"') do set "PYW_EXE=%%i"

if defined PYW_EXE if exist "%PYW_EXE%" (
    start "" "%PYW_EXE%" "%~dp0app.py"
    exit /b 0
)

rem fallback: run with a console window (so errors are visible)
%PY_CMD% "%~dp0app.py"
if errorlevel 1 (
    echo.
    echo [ERROR] The app closed with an error.
    echo Details are saved in: Google Drive\Windows-Agent-DB\logs\errors
    echo.
    pause
)
exit /b 0
