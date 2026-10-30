@echo off
setlocal
chcp 65001 >nul 2>nul
set "PYTHONUTF8=1"
cd /d "%~dp0\..\.."
set "PY_CMD="
where py >nul 2>nul && set "PY_CMD=py -3"
if not defined PY_CMD where python >nul 2>nul && set "PY_CMD=python"
if not defined PY_CMD (
    echo [ERROR] Python was not found.
    pause
    exit /b 1
)
%PY_CMD% "%~dp0record_acceptance.py" %*
set "RESULT=%ERRORLEVEL%"
echo.
if not "%RESULT%"=="0" echo Acceptance not passed; no readiness marker was granted.
pause
exit /b %RESULT%
