@echo off
setlocal
cd /d "%~dp0"
title Arena Bridge

rem ---------------------------------------------------------------
rem  Arena Bridge launcher
rem  Watches the "codes" folder in Google Drive and runs job_*.py
rem ---------------------------------------------------------------

set "PY_CMD="
where py >nul 2>nul && set "PY_CMD=py -3"
if not defined PY_CMD (
    where python >nul 2>nul && set "PY_CMD=python"
)
if not defined PY_CMD (
    echo [ERROR] Python was not found. Install Python 3.9+ first.
    pause
    exit /b 1
)

rem --- run silently in the background with pythonw ---
set "PYW_EXE="
for /f "delims=" %%i in ('%PY_CMD% -c "import sys,os;print(os.path.join(os.path.dirname(sys.executable),'pythonw.exe'))"') do set "PYW_EXE=%%i"

if defined PYW_EXE if exist "%PYW_EXE%" (
    start "" "%PYW_EXE%" "%~dp0bridge_watcher.pyw"
    echo Arena Bridge started in the background.
    echo Watch status here:  %~dp0status.txt
    timeout /t 3 >nul
    exit /b 0
)

rem fallback: visible console
%PY_CMD% "%~dp0bridge_watcher.pyw"
pause
exit /b 0
