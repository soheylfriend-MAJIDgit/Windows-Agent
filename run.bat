@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
title Windows Agent

rem ===============================================================
rem  Windows Agent launcher
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

rem --- 2) required packages ------------------------------------------
set "MISSING="
%PY_CMD% -c "import pygame" >nul 2>nul || set "MISSING=!MISSING! pygame"
%PY_CMD% -c "import arabic_reshaper" >nul 2>nul || set "MISSING=!MISSING! arabic-reshaper"
%PY_CMD% -c "import bidi" >nul 2>nul || set "MISSING=!MISSING! python-bidi"
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
    %PY_CMD% -c "import pygame" >nul 2>nul || set "STILL=!STILL! pygame"
    %PY_CMD% -c "import arabic_reshaper" >nul 2>nul || set "STILL=!STILL! arabic-reshaper"
    %PY_CMD% -c "import bidi" >nul 2>nul || set "STILL=!STILL! python-bidi"
    %PY_CMD% -c "import PIL" >nul 2>nul || set "STILL=!STILL! Pillow"
    if defined STILL (
        echo.
        echo [ERROR] Could not install:!STILL!
        echo Run this command manually, then start again:
        echo     %PY_CMD% -m pip install pygame arabic-reshaper python-bidi Pillow
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

rem --- 3) run the GUI without a console window -----------------------
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
