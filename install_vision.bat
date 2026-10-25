@echo off
setlocal
cd /d "%~dp0"
title Windows Agent - نصب PaddleOCR محلی

echo.
echo ============================================================
echo   نصب اختیاری PaddleOCR محلی برای Windows Agent
echo ============================================================
echo.
echo این نصب در مسیر جداگانه زیر انجام می‌شود:
echo   %%LOCALAPPDATA%%\Windows-Agent\vision
echo.
echo PaddlePaddle، PaddleOCR و مدل‌های اولیه دانلود می‌شوند.
echo فایل تصویر و متن OCR شما به سرویس ابری ارسال نمی‌شود.
echo دانلود مدل ممکن است چند دقیقه و چندصد مگابایت زمان ببرد.
echo برنامه‌ی اصلی و app.py تغییر نمی‌کنند.
echo.
choice /C YN /N /M "برای ادامه و دانلود وابستگی‌ها Y، برای انصراف N را بزنید: "
if errorlevel 2 exit /b 0

set "PY_CMD="
where py >nul 2>nul && py -3.11 -c "import sys; print(sys.version)" >nul 2>nul && set "PY_CMD=py -3.11"
if not defined PY_CMD where python >nul 2>nul && set "PY_CMD=python"
if not defined PY_CMD (
    echo [خطا] Python 3.11 پیدا نشد. نسخه‌های pin شده‌ی PaddleOCR به Python 3.11 نیاز دارند.
    pause
    exit /b 1
)
if not defined PY_CMD (
    echo [خطا] Python پیدا نشد. ابتدا Python برنامه را نصب کنید.
    pause
    exit /b 1
)

%PY_CMD% "%~dp0tools\vision\install_vision.py" --install-packages
if errorlevel 1 (
    echo.
    echo [خطا] نصب PaddleOCR کامل نشد. جزئیات بالا را بررسی کنید.
    echo می‌توانید دوباره همین فایل را اجرا کنید؛ app.py تغییری نکرده است.
    pause
    exit /b 1
)

echo.
echo آزمون آفلاین helper و مدل‌های محلی...
set "VISION_ROOT=%LOCALAPPDATA%\Windows-Agent\vision"
"%VISION_ROOT%\.venv\Scripts\python.exe" "%VISION_ROOT%\paddle_ocr_helper.py" --selftest --offline --json
if errorlevel 1 (
    echo.
    echo [خطا] آزمون آفلاین ناموفق بود. قابلیت Arena فعال نخواهد شد.
    pause
    exit /b 1
)
"%VISION_ROOT%\.venv\Scripts\python.exe" -c "from pathlib import Path; import json,datetime; p=Path(r'%VISION_ROOT%')/'vision_ready.json'; p.write_text(json.dumps({'ok':True,'testedAt':datetime.datetime.now().isoformat(timespec='seconds')}),encoding='utf-8')"
if errorlevel 1 (
    echo [خطا] ثبت وضعیت نصب آماده نشد.
    pause
    exit /b 1
)
echo.
echo نصب و آزمون اولیه موفق بود. اکنون Windows Agent را دوباره اجرا کنید.
echo توجه: قابلیت‌ها فقط پس از آزمون واقعی سازگاری و Heartbeat تایید می‌شوند.
pause
exit /b 0
