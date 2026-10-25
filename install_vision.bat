@echo off
setlocal
chcp 65001 >nul 2>nul
set "PYTHONUTF8=1"
cd /d "%~dp0"
title Windows Agent - Local PaddleOCR Setup

echo.
echo ============================================================
echo   Optional isolated PaddleOCR setup for Windows Agent
echo ============================================================
echo.
echo Install location:
echo   %%LOCALAPPDATA%%\Windows-Agent\vision
echo.
echo PaddlePaddle, PaddleOCR and initial CPU models will be downloaded.
echo Your screenshots and OCR text are not uploaded to a cloud service.
echo The model download may take several minutes and may be large.
echo The main application and app.py will not be modified.
echo.
choice /C YN /N /M "Continue and download the dependencies? Press Y or N: "
if errorlevel 2 exit /b 0

set "PY_CMD="
where py >nul 2>nul && py -3.11 -c "import sys; print(sys.version)" >nul 2>nul && set "PY_CMD=py -3.11"
if not defined PY_CMD where python >nul 2>nul && set "PY_CMD=python"
if not defined PY_CMD (
    echo [ERROR] Python was not found. Python 3.11 is recommended for the pinned PaddleOCR packages.
    pause
    exit /b 1
)

rem Paddle's native libpaddle.pyd requires the Microsoft VC++ x64 runtime.
%PY_CMD% -c "import ctypes; ctypes.WinDLL('vcruntime140.dll'); ctypes.WinDLL('vcruntime140_1.dll'); ctypes.WinDLL('msvcp140.dll')" >nul 2>nul
if errorlevel 1 (
    echo.
    echo Paddle's native core needs Microsoft's Visual C++ x64 runtime.
    echo The installer will download it from the official Microsoft URL and request admin approval.
    choice /C YN /N /M "Install the Microsoft runtime prerequisite? [Y/N]: "
    if errorlevel 2 (
        echo [ERROR] PaddleOCR cannot load without the VC++ runtime.
        pause
        exit /b 1
    )
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\vision\install_vc_runtime.ps1"
    set "VC_INSTALL_RESULT=%ERRORLEVEL%"
    if "%VC_INSTALL_RESULT%"=="3010" (
        echo Windows needs to restart before PaddleOCR can load. Restart, then run this BAT again.
        pause
        exit /b 1
    )
    if not "%VC_INSTALL_RESULT%"=="0" (
        echo [ERROR] The Microsoft runtime could not be installed.
        pause
        exit /b 1
    )
    %PY_CMD% -c "import ctypes; ctypes.WinDLL('vcruntime140.dll'); ctypes.WinDLL('vcruntime140_1.dll'); ctypes.WinDLL('msvcp140.dll')" >nul 2>nul
    if errorlevel 1 (
        echo [ERROR] The VC++ runtime is still unavailable. Restart Windows and retry.
        pause
        exit /b 1
    )
)

%PY_CMD% "%~dp0tools\vision\install_vision.py" --install-packages
if errorlevel 1 (
    echo.
    echo [ERROR] PaddleOCR setup did not complete. Review the error above and try again.
    pause
    exit /b 1
)

set "VISION_ROOT=%LOCALAPPDATA%\Windows-Agent\vision"
echo.
echo Running the offline self-test...
"%VISION_ROOT%\.venv\Scripts\python.exe" "%VISION_ROOT%\paddle_ocr_helper.py" --selftest --offline --json >nul
if errorlevel 1 (
    echo.
    echo [ERROR] Offline self-test failed. Arena OCR will remain unavailable.
    pause
    exit /b 1
)
"%VISION_ROOT%\.venv\Scripts\python.exe" -c "from pathlib import Path; import json,datetime; p=Path(r'%VISION_ROOT%')/'vision_ready.json'; p.write_text(json.dumps({'ok':True,'testedAt':datetime.datetime.now().isoformat(timespec='seconds')}),encoding='utf-8')"
if errorlevel 1 (
    echo [ERROR] Could not save the local readiness marker.
    pause
    exit /b 1
)
echo.
echo Setup and offline self-test succeeded. Restart Windows Agent.
echo Capabilities remain disabled until the required real-Windows acceptance tests pass.
pause
exit /b 0
