@echo off
setlocal
cd /d "%~dp0"
title Windows Agent

rem ---------------------------------------------------------------
rem  Windows Agent launcher
rem  Double-click this file to start the app.
rem ---------------------------------------------------------------

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

rem --- 2) install the only requirement if needed (Pillow) -------------
%PY_CMD% -c "import PIL" >nul 2>nul
if errorlevel 1 (
    echo Installing required package: Pillow ...
    %PY_CMD% -m pip install --quiet --disable-pip-version-check Pillow
    %PY_CMD% -c "import PIL" >nul 2>nul
    if errorlevel 1 (
        echo.
        echo [ERROR] Could not install Pillow automatically.
        echo Run this command manually:  %PY_CMD% -m pip install Pillow
        echo.
        pause
        exit /b 1
    )
)

rem --- 3) run the GUI without a console window ------------------------
rem  pythonw.exe sits next to python.exe; locating it this way avoids
rem  the Microsoft Store "python" alias stub.
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
    echo [ERROR] The app closed with an error. See error.log next to app.py
    echo.
    pause
)
exit /b 0
