@echo off
setlocal
chcp 65001 >nul 2>nul
set "PYTHONUTF8=1"
cd /d "%~dp0\..\.."
set "PY_CMD="
where py >nul 2>nul && set "PY_CMD=py -3"
if not defined PY_CMD where python >nul 2>nul && set "PY_CMD=python"
if not defined PY_CMD (
    echo [ERROR] Python was not found. Start run.bat once to install requirements.
    pause
    exit /b 1
)
%PY_CMD% -c "import google_auth_oauthlib.flow, requests" >nul 2>nul
if errorlevel 1 (
    echo Direct Drive control needs google-auth-oauthlib and requests.
    choice /C YN /N /M "Install these packages from PyPI now? [Y/N]: "
    if errorlevel 2 exit /b 2
    %PY_CMD% -m pip install --disable-pip-version-check google-auth-oauthlib requests
    if errorlevel 1 (
        echo [ERROR] Package installation failed. No OAuth or Drive command was run.
        pause
        exit /b 1
    )
)
%PY_CMD% "%~dp0authorize.py" %*
set "RESULT=%ERRORLEVEL%"
echo.
if not "%RESULT%"=="0" echo OAuth authorization did not complete. No Drive command was run.
pause
exit /b %RESULT%
