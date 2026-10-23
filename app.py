# -*- coding: utf-8 -*-
"""
Windows Agent — نسخه ۰.۵
------------------------
یک رابط کاربری ساده با دو دکمه و دو تب:

  ۱) باز کردن lmarena در کروم و گرفتن اسکرین‌شات (ذخیره در گوگل درایو)
  ۲) گرفتن گزارش از برنامه‌های باز ویندوز
  + تب «آخرین تغییرات» و چراغ‌های وضعیت اینترنت / گوگل درایو

نسخه، هش کامیت و تاریخ جلالی ساخت در هدر پنجره نمایش داده می‌شود
تا همیشه مطمئن شوی کدام نسخه در حال اجراست.

نحوه اجرا: فایل run.bat را دوبار کلیک کنید.
"""

from __future__ import annotations

import ctypes
import os
import queue
import socket
import subprocess
import sys
import threading
import time
import traceback
import webbrowser
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tkinter as tk
from tkinter import scrolledtext, ttk

# ---------------------------------------------------------------- تنظیمات ---

APP_TITLE = "Windows Agent"
APP_VERSION = "0.9"

# ------------------------------------------------------------------
#  شناسنامه‌ی ساخت (اگر پوشه .git موجود باشد، مقدار واقعی از گیت خوانده می‌شود)
#  این مقادیر «نسخه پشتیبان» هستند تا حتی بدون گیت هم چیزی نمایش داده شود.
# ------------------------------------------------------------------
BUILD_COMMIT = "d47c91e"
BUILD_SUBJECT = "v0.4-dev: Arena Bridge"
BUILD_DATE_JALALI = "1405/08/01"
BUILD_TIME_TEHRAN = "23:26"

# منطقه زمانی تهران (بدون وابستگی به تنظیمات ویندوز)
TEHRAN = timezone(timedelta(hours=3, minutes=30), "Tehran")

# فاصله‌ی بررسی چراغ‌های وضعیت (ثانیه)
STATUS_CHECK_SECONDS = 5

# ------------------------------------------------------------------
#  تاریخچه تغییرات (تب «آخرین تغییرات»)
# ------------------------------------------------------------------
CHANGELOG: list[tuple[str, str, list[str]]] = [
    (
        "0.9",
        "۱۴۰۵/۰۸/۰۲",
        [
            "ساختار ساده شد: گوگل درایو فقط ScreenShots و logs",
            "پوشه codes محلی است و از گیت‌هاب جایگزین می‌شود",
            "با هر کامیت (تغییر version.txt) بسته کد از گیت‌هاب گرفته می‌شود",
            "نتیجه هر کد در logs گوگل درایو ذخیره می‌شود تا Arena بخواند",
            "هیچ کاری خودکار انجام نمی‌شود؛ سه کلید کنترل در بالای پنجره",
            "با باز شدن برنامه هیچ کدی دریافت یا اجرا نمی‌شود",
        ],
    ),
    (
        "0.8",
        "۱۴۰۵/۰۸/۰۲",
        [
            "پایش پوشه گوگل درایو از طریق لینک عمومی (بدون سینک محلی، بدون تأخیر)",
            "هر ۱۰ ثانیه فهرست پوشه از سرور گوگل خوانده می‌شود",
            "کدهای job_*.py که در آن پوشه گذاشته شوند خودکار دانلود و اجرا می‌شوند",
        ],
    ),
    (
        "0.7.1",
        "۱۴۰۵/۰۸/۰۲",
        [
            "تغییر آدرس هدف از lmarena به گوگل (تست مسیر بروزرسانی خودکار)",
            "نام فایل اسکرین‌شات: google_تاریخ_جلالی.png",
        ],
    ),
    (
        "0.7",
        "۱۴۰۵/۰۸/۰۱",
        [
            "دریافت فوری کد از گیت‌هاب (بدون انتظار برای سینک گوگل درایو)",
            "بروزرسانی خودکار برنامه در چند ثانیه پس از هر پوش",
            "دریافت کدهای جانبی از پوشه jobs در ریپو و اجرای خودکار",
            "گوگل درایو فقط برای اسکرین‌شات و گزارش‌ها و نتایج می‌ماند",
        ],
    ),
    (
        "0.6",
        "۱۴۰۵/۰۸/۰۱",
        [
            "اجراکننده کدهای جانبی داخل خود برنامه (تب «کدها»)",
            "هر فایل job_*.py در پوشه Codes به‌صورت خودکار شناسایی و اجرا می‌شود",
            "رفع خطای انکودینگ فارسی در خروجی کدهای اجراشده",
            "نتیجه هر اجرا در پوشه out ذخیره و در تب کدها نمایش داده می‌شود",
        ],
    ),
    (
        "0.5",
        "۱۴۰۵/۰۸/۰۱",
        [
            "نمایش نسخه، هش کامیت و تاریخ ساخت (جلالی + ساعت تهران) در هدر",
            "تب جدید «آخرین تغییرات» برای دیدن تاریخچه در خود برنامه",
            "چراغ وضعیت اینترنت و چراغ وضعیت اتصال گوگل درایو",
            "نام فایل‌ها با تاریخ جلالی و ساعت تهران",
            "حذف پنجره‌های تکراری در گزارش برنامه‌های باز",
            "فیلتر کردن خود برنامه از فهرست پنجره‌ها",
        ],
    ),
    (
        "0.3",
        "۱۴۰۵/۰۸/۰۱",
        [
            "اسکرین‌شات‌ها در My Drive/Windows-Agent-DB/ScreenShots",
            "گزارش‌ها در My Drive/Windows-Agent-DB/logs",
            "اگر گوگل درایو نبود، ذخیره موقت روی دسکتاپ با هشدار",
        ],
    ),
    (
        "0.2",
        "۱۴۰۵/۰۸/۰۱",
        [
            "کاهش زمان انتظار از ۱۰ به ۵ ثانیه",
            "ذخیره در گوگل درایو به‌جای دسکتاپ",
        ],
    ),
    (
        "0.1",
        "۱۴۰۵/۰۸/۰۱",
        [
            "نسخه اول: باز کردن lmarena در کروم و گرفتن اسکرین‌شات",
            "گزارش برنامه‌های باز ویندوز",
        ],
    ),
]

LMARENA_URL = "https://www.google.com"

# بعد از باز شدن کروم چند ثانیه صبر کنیم تا صفحه کامل لود شود
PAGE_LOAD_SECONDS = 5

# پیشوند نام فایل اسکرین‌شات
SCREENSHOT_PREFIX = "google"

# ------------------------------------------------------------------
#  مسیرهای ذخیره
#  گوگل درایو فقط دو چیز دارد: ScreenShots و logs
# ------------------------------------------------------------------
DRIVE_BASE_DIR = r"C:\Users\alibatel\My Drive\Windows-Agent-DB"

# اسکرین‌شات‌ها  →  ...\Windows-Agent-DB\ScreenShots
SCREENSHOT_DIR = DRIVE_BASE_DIR + r"\ScreenShots"

# گزارش‌ها و نتیجه کدها  →  ...\Windows-Agent-DB\logs
REPORT_DIR = DRIVE_BASE_DIR + r"\logs"

# خود برنامه و پوشه codes محلی هستند (کنار app.py)
LOCAL_BASE_DIR = Path(__file__).resolve().parent
STAMP_FILE = LOCAL_BASE_DIR / "build_stamp.json"
CODES_DIR = str(LOCAL_BASE_DIR / "codes")
CODES_STATE_FILE = str(LOCAL_BASE_DIR / "codes_state.json")
SETTINGS_FILE = LOCAL_BASE_DIR / "settings.json"

DEFAULT_SETTINGS = {"auto_fetch": False, "auto_run": False, "auto_update_app": False}

# ------------------------------------------------------------------
#  دریافت کد از گیت‌هاب
#  هر بار version.txt در ریپو عوض شود:
#    ۱) zip ریپو گرفته می‌شود
#    ۲) محتویات پوشه codes جایگزین می‌شود
#    ۳) app.py در صورت تغییر بروز و برنامه ری‌استارت می‌شود
# ------------------------------------------------------------------
GITHUB_OWNER = "soheylfriend-MAJIDgit"
GITHUB_REPO = "Windows-Agent"
GITHUB_BRANCH = "arena/025c788f-windows-agent"
GITHUB_CODES_PATH = "codes"
GITHUB_VERSION_FILE = "version.txt"

# هر چند ثانیه نسخه گیت‌هاب بررسی شود
SYNC_POLL_SECONDS = 10

# آیا بعد از بروزرسانی، برنامه خودش را دوباره راه‌اندازی کند؟
AUTO_RESTART_ON_UPDATE = True

# حداکثر زمان اجرای هر کد جانبی (ثانیه)
CODES_MAX_RUNTIME = 600

# اگر گوگل درایو در دسترس نباشد، این‌ها کجا ذخیره شوند؟
# None یعنی روی دسکتاپ (با زیرپوشه‌های ScreenShots و logs)
FALLBACK_BASE_DIR = None

IS_WINDOWS = os.name == "nt"

# مسیر فایل خطاها (کنار خود برنامه) تا اگر برنامه بالا نیامد دلیلش معلوم شود
ERROR_LOG = Path(__file__).resolve().parent / "error.log"


# ------------------------------------------------------ تاریخ جلالی / تهران ---

FA_MONTHS = [
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]

FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def to_fa(value: str) -> str:
    """تبدیل رقم‌های لاتین به فارسی برای نمایش."""
    return str(value).translate(FA_DIGITS)


def gregorian_to_jalali(gy: int, gm: int, gd: int) -> tuple[int, int, int]:
    """تبدیل تاریخ میلادی به جلالی (بدون هیچ کتابخانه بیرونی)."""
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2, gm2, gd2 = gy - 1600, gm - 1, gd - 1
    g_day_no = (
        365 * gy2 + (gy2 + 3) // 4 - (gy2 + 99) // 100 + (gy2 + 399) // 400
    )
    g_day_no += g_d_m[gm2] + gd2
    if gm > 2 and ((gy % 4 == 0 and gy % 100 != 0) or gy % 400 == 0):
        g_day_no += 1
    j_day_no = g_day_no - 79
    j_np = j_day_no // 12053
    j_day_no %= 12053
    jy = 979 + 33 * j_np + 4 * (j_day_no // 1461)
    j_day_no %= 1461
    if j_day_no >= 366:
        jy += (j_day_no - 1) // 365
        j_day_no = (j_day_no - 1) % 365
    if j_day_no < 186:
        jm, jd = 1 + j_day_no // 31, 1 + j_day_no % 31
    else:
        jm, jd = 7 + (j_day_no - 186) // 30, 1 + (j_day_no - 186) % 30
    return jy, jm, jd


def tehran_now() -> datetime:
    """زمان فعلی تهران؛ مستقل از منطقه زمانی تنظیم‌شده در ویندوز."""
    return datetime.now(TEHRAN)


def jalali_parts(dt: datetime) -> tuple[int, int, int]:
    return gregorian_to_jalali(dt.year, dt.month, dt.day)


def jalali_date(dt: datetime) -> str:
    """۱۴۰۵/۰۸/۰۱"""
    jy, jm, jd = jalali_parts(dt)
    return f"{jy:04d}/{jm:02d}/{jd:02d}"


def jalali_long(dt: datetime) -> str:
    """۱ آبان ۱۴۰۵"""
    jy, jm, jd = jalali_parts(dt)
    return f"{jd} {FA_MONTHS[jm - 1]} {jy}"


def jalali_stamp(dt: datetime) -> str:
    """۱۴۰۵-۰۸-۰۱_۲۳-۵۰-۱۲ برای نام فایل."""
    jy, jm, jd = jalali_parts(dt)
    return f"{jy:04d}-{jm:02d}-{jd:02d}_{dt:%H-%M-%S}"


def short_hash(data: bytes) -> str:
    """شناسه کوتاه محتوا (برای تشخیص نسخه، بدون نیاز به گیت)."""
    import hashlib

    return hashlib.sha256(data).hexdigest()[:8]


def build_info() -> dict:
    """اطلاعات ساخت: اگر مخزن گیت موجود باشد از آن، وگرنه از مقادیر ثابت."""
    info = {
        "commit": BUILD_COMMIT,
        "filehash": "",
        "source_label": "مقدار ثابت",
        "subject": BUILD_SUBJECT,
        "date": BUILD_DATE_JALALI,
        "time": BUILD_TIME_TEHRAN,
        "dirty": False,
        "source": "embedded",
    }
    base = Path(__file__).resolve().parent
    try:
        info["filehash"] = short_hash(Path(__file__).read_bytes())
    except OSError:
        pass

    # اگر برنامه از طریق بروزرسانی خودکار به‌روز شده باشد، هش واقعی این‌جاست
    try:
        import json

        stamp = json.loads(STAMP_FILE.read_text(encoding="utf-8"))
        if stamp.get("version"):
            info.update(
                commit=str(stamp["version"]),
                date=stamp.get("date", info["date"]),
                time=stamp.get("time", info["time"]),
                source="stamp",
                source_label="بروزرسانی خودکار",
            )
            return info
    except (OSError, ValueError):
        pass

    if not (base / ".git").exists():
        # بدون گیت: زمان ویرایش خود فایل را نشان می‌دهیم
        try:
            mtime = datetime.fromtimestamp(Path(__file__).stat().st_mtime, TEHRAN)
            info.update(date=jalali_date(mtime), time=f"{mtime:%H:%M}")
        except OSError:
            pass
        return info
    try:
        out = subprocess.run(
            ["git", "-C", str(base), "log", "-1", "--format=%h%x1f%ct%x1f%s"],
            capture_output=True,
            text=True,
            timeout=3,
            creationflags=(subprocess.CREATE_NO_WINDOW if IS_WINDOWS else 0),
        )
        if out.returncode == 0 and out.stdout.strip():
            commit, epoch, subject = out.stdout.strip().split("\x1f", 2)
            moment = datetime.fromtimestamp(int(epoch), TEHRAN)
            info.update(
                commit=commit.strip(),
                subject=subject.strip()[:70],
                date=jalali_date(moment),
                time=f"{moment:%H:%M}",
                source="git",
                source_label="مخزن گیت",
            )
        status = subprocess.run(
            ["git", "-C", str(base), "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=3,
            creationflags=(subprocess.CREATE_NO_WINDOW if IS_WINDOWS else 0),
        )
        info["dirty"] = bool(status.stdout.strip())
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return info


# ------------------------------------------------------------ ابزار ویندوز ---

def enable_dpi_awareness() -> None:
    """جلوگیری از تار شدن / بریده شدن اسکرین‌شات در نمایشگرهای با مقیاس‌بندی."""
    if not IS_WINDOWS:
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PER_MONITOR_AWARE
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def get_desktop_dir() -> Path:
    """مسیر واقعی دسکتاپ کاربر (شامل حالت OneDrive)."""
    if IS_WINDOWS:
        try:
            import uuid

            class _GUID(ctypes.Structure):
                _fields_ = [
                    ("Data1", ctypes.c_ulong),
                    ("Data2", ctypes.c_ushort),
                    ("Data3", ctypes.c_ushort),
                    ("Data4", ctypes.c_ubyte * 8),
                ]

            # FOLDERID_Desktop
            guid = _GUID.from_buffer_copy(
                uuid.UUID("B4BFCC3A-DB2C-424C-B029-7FE99A87C641").bytes_le
            )
            path_ptr = ctypes.c_wchar_p()
            result = ctypes.windll.shell32.SHGetKnownFolderPath(
                ctypes.byref(guid), 0, None, ctypes.byref(path_ptr)
            )
            if result == 0 and path_ptr.value:
                desktop = Path(path_ptr.value)
                ctypes.windll.ole32.CoTaskMemFree(path_ptr)
                if desktop.is_dir():
                    return desktop
        except Exception:
            pass

    candidates = []
    onedrive = os.environ.get("OneDrive")
    if onedrive:
        candidates.append(Path(onedrive) / "Desktop")
    candidates.append(Path.home() / "Desktop")
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return Path.home()


def resolve_dir(target_setting: str | None, fallback_subfolder: str | None = None) -> tuple[Path, bool]:
    """پوشه مقصد را برمی‌گرداند.

    خروجی: (مسیر، آیا مسیر گوگل درایو استفاده شد؟)

    قانون مهم: خود پوشه‌ی `My Drive` هرگز ساخته نمی‌شود؛ فقط زیرپوشه‌های داخل
    پوشه پروژه ساخته می‌شوند. چون اگر Google Drive اجرا نباشد، ساختن دستی
    آن پوشه یک پوشه‌ی محلی بی‌فایده می‌سازد که هیچ‌وقت sync نمی‌شود.
    """
    target: Path | None = Path(target_setting) if target_setting else None
    if target is not None and not target.is_absolute():
        target = None  # فقط مسیرهای مطلق ویندوزی معتبرند

    if target is not None:
        if target.is_dir():
            return target, True
        # پوشه نیست؛ فقط اگر پوشه‌ی والدش (که گوگل درایو ساخته) موجود باشد می‌سازیم
        if target.parent.is_dir():
            try:
                target.mkdir(exist_ok=True)
                return target, True
            except OSError:
                pass

    base = Path(FALLBACK_BASE_DIR) if FALLBACK_BASE_DIR else get_desktop_dir()
    if fallback_subfolder:
        base = base / fallback_subfolder
    return base, False


def drive_available() -> bool:
    """آیا پوشه‌ی پروژه در گوگل درایو در دسترس است؟"""
    base = Path(DRIVE_BASE_DIR)
    return base.is_absolute() and base.is_dir()


def resolve_screenshot_dir() -> tuple[Path, bool]:
    return resolve_dir(SCREENSHOT_DIR, "ScreenShots")


def resolve_report_dir() -> tuple[Path, bool]:
    return resolve_dir(REPORT_DIR, "logs")


def human_size(num_bytes: int) -> str:
    if num_bytes >= 1024 * 1024:
        return f"{num_bytes / (1024 * 1024):,.1f} مگابایت"
    return f"{num_bytes / 1024:,.0f} کیلوبایت"


def find_chrome() -> str | None:
    """مسیر chrome.exe را پیدا می‌کند."""
    if not IS_WINDOWS:
        return None

    candidates = [
        Path(os.environ.get("PROGRAMFILES", r"C:\Program Files"))
        / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"))
        / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)

    # جستجو در رجیستری (App Paths)
    try:
        import winreg

        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            try:
                key = winreg.OpenKey(
                    hive,
                    r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe",
                )
                value, _ = winreg.QueryValueEx(key, "")
                winreg.CloseKey(key)
                if value and Path(value).is_file():
                    return value
            except OSError:
                continue
    except Exception:
        pass

    return None


def open_in_chrome(url: str) -> str:
    """سایت را در یک پنجره جدید کروم باز می‌کند و توضیح می‌دهد با چه چیزی باز شد."""
    chrome = find_chrome()
    if chrome:
        subprocess.Popen(
            [chrome, "--new-window", "--start-maximized", url],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return "Google Chrome"

    if IS_WINDOWS:
        os.startfile(url)  # noqa: S606 - مرورگر پیش‌فرض ویندوز
        return "مرورگر پیش‌فرض ویندوز"

    webbrowser.open(url)
    return "مرورگر پیش‌فرض"


def take_screenshot(dest_dir: Path) -> Path:
    """اسکرین‌شات از کل صفحه (همه مانیتورها) می‌گیرد و ذخیره می‌کند."""
    from PIL import ImageGrab

    dest_dir.mkdir(parents=True, exist_ok=True)
    stamp = jalali_stamp(tehran_now())
    target = dest_dir / f"{SCREENSHOT_PREFIX}_{stamp}.png"

    try:
        image = ImageGrab.grab(all_screens=True)  # همه مانیتورها
    except Exception:
        image = ImageGrab.grab()  # پشتیبان: فقط مانیتور اصلی

    image.save(target, "PNG")
    return target


# ----------------------------------------------------- گزارش برنامه‌های باز ---

def _prepare_windows_api() -> None:
    """امضای توابع ویندوزی را برای سیستم‌های ۶۴ بیتی درست تنظیم می‌کند."""
    kernel32 = ctypes.windll.kernel32
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_bool, ctypes.c_ulong]
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.QueryFullProcessImageNameW.argtypes = [
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.c_wchar_p,
        ctypes.POINTER(ctypes.c_ulong),
    ]
    kernel32.QueryFullProcessImageNameW.restype = ctypes.c_bool


def _process_name(pid: int) -> str:
    kernel32 = ctypes.windll.kernel32
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return "?"
    try:
        size = ctypes.c_ulong(1024)
        buffer = ctypes.create_unicode_buffer(size.value)
        if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return Path(buffer.value).name
    finally:
        kernel32.CloseHandle(handle)
    return "?"


def collect_open_windows() -> list[dict]:
    """فهرست پنجره‌های قابل مشاهده‌ی ویندوز را برمی‌گرداند."""
    if not IS_WINDOWS:
        raise RuntimeError("این قابلیت فقط روی ویندوز کار می‌کند.")

    _prepare_windows_api()
    user32 = ctypes.windll.user32
    windows: list[dict] = []
    seen: set[tuple[int, str]] = set()
    enum_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def _callback(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return True
        ex_style = user32.GetWindowLongW(hwnd, -20)  # GWL_EXSTYLE
        if ex_style & 0x00000080:  # WS_EX_TOOLWINDOW
            return True

        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        title = buffer.value.strip()
        if not title:
            return True

        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        process = _process_name(pid.value)

        # خود برنامه را در گزارش نیاور
        if process.lower() in {"python.exe", "pythonw.exe", "py.exe"} and (
            "Windows Agent" in title
        ):
            return True

        # پنجره‌های کاملاً تکراری (همان PID و همان عنوان) را یک بار بشمار
        key = (pid.value, title)
        if key in seen:
            return True
        seen.add(key)

        windows.append({"title": title, "pid": pid.value, "process": process})
        return True

    user32.EnumWindows(enum_proc(_callback), 0)
    windows.sort(key=lambda item: (item["process"].lower(), item["title"].lower()))
    return windows


def format_windows_report(windows: list[dict]) -> str:
    now = tehran_now()
    now_text = (
        f"{jalali_long(now)} — {now:%H:%M:%S} "
        f"(جلالی {jalali_date(now)} | ساعت تهران)"
    )

    counts: dict[str, int] = {}
    for window in windows:
        counts[window["process"]] = counts.get(window["process"], 0) + 1

    lines = [
        "گزارش برنامه‌های باز ویندوز",
        "=" * 60,
        f"تاریخ: {now_text}",
        f"تعداد پنجره‌های قابل مشاهده: {len(windows)}",
        "",
        "خلاصه بر اساس برنامه:",
        "-" * 60,
    ]
    if counts:
        for process, count in sorted(counts.items()):
            lines.append(f"{process}: {count} پنجره")
    else:
        lines.append("(هیچ پنجره‌ای پیدا نشد)")

    lines += ["", "جزئیات پنجره‌ها:", "-" * 60]
    if windows:
        for index, window in enumerate(windows, start=1):
            lines.append(f"{index}. {window['process']}  (PID {window['pid']})")
            lines.append(f"   عنوان: {window['title']}")
    else:
        lines.append("(هیچ پنجره‌ای پیدا نشد)")

    lines.append("")
    return "\n".join(lines)


def save_report(report_text: str, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    stamp = jalali_stamp(tehran_now())
    target = dest_dir / f"open_apps_report_{stamp}.txt"
    target.write_text(report_text, encoding="utf-8-sig")
    return target


# ------------------------------------------------ دریافت کد از گیت‌هاب ---
#  همه چیز از یک مسیر: zip کل ریپو از codeload.github.com
#  (بدون کلید API، بدون محدودیت نرخ)

GITHUB_ZIP = "https://codeload.github.com/{owner}/{repo}/zip/refs/heads/{branch}"


def _system_proxy() -> str | None:
    """پروکسی سیستم ویندوز را می‌خواند (مثلاً v2rayN که پروکسی سیستم را ست می‌کند)."""
    if not IS_WINDOWS:
        return os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
        )
        enabled, _ = winreg.QueryValueEx(key, "ProxyEnable")
        server, _ = winreg.QueryValueEx(key, "ProxyServer")
        winreg.CloseKey(key)
        if not enabled or not server:
            return os.environ.get("HTTPS_PROXY")
        if "=" in server:  # مثل http=127.0.0.1:10809;https=127.0.0.1:10809
            for part in server.split(";"):
                if part.lower().startswith("https="):
                    server = part.split("=", 1)[1]
                    break
        return f"http://{server}"
    except (OSError, ImportError, ValueError):
        return os.environ.get("HTTPS_PROXY")


def _http_get_bytes(url: str, timeout: float = 30.0) -> bytes | None:
    """دریافت محتوا؛ اگر پروکسی سیستم فعال باشد از آن استفاده می‌کند."""
    import urllib.error
    import urllib.request

    handlers = []
    proxy = _system_proxy()
    if proxy:
        handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    opener = urllib.request.build_opener(*handlers)

    request = urllib.request.Request(
        url, headers={"User-Agent": "Windows-Agent", "Cache-Control": "no-cache"}
    )
    try:
        with opener.open(request, timeout=timeout) as response:
            if response.status != 200:
                return None
            return response.read()
    except (urllib.error.HTTPError, urllib.error.URLError, OSError):
        return None


def repo_zip() -> bytes | None:
    """zip کل ریپو."""
    url = GITHUB_ZIP.format(
        owner=GITHUB_OWNER, repo=GITHUB_REPO, branch=GITHUB_BRANCH
    )
    return _http_get_bytes(url, timeout=40)


def extract_folder(zip_bytes: bytes, folder: str) -> dict[str, bytes]:
    """محتویات یک پوشه از zip را بیرون می‌کشد: {نام فایل: محتوا}"""
    import io
    import zipfile

    result: dict[str, bytes] = {}
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            for name in zf.namelist():
                if name.endswith("/"):
                    continue
                parts = name.split("/", 1)
                if len(parts) != 2:
                    continue
                inner = parts[1]
                prefix = folder.rstrip("/") + "/"
                if inner.startswith(prefix) and "/" not in inner[len(prefix):]:
                    result[inner[len(prefix):]] = zf.read(name)
    except (zipfile.BadZipFile, OSError):
        return {}
    return result


def extract_file(zip_bytes: bytes, path: str) -> bytes | None:
    import io
    import zipfile

    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            for name in zf.namelist():
                parts = name.split("/", 1)
                if len(parts) == 2 and parts[1] == path:
                    return zf.read(name)
    except (zipfile.BadZipFile, OSError):
        return None
    return None


# ------------------------------------------------- اجراکننده کدهای جانبی ---

def load_settings() -> dict:
    """تنظیمات کاربر. پیش‌فرض: همه چیز خاموش."""
    data = dict(DEFAULT_SETTINGS)
    try:
        import json

        raw = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            for key in DEFAULT_SETTINGS:
                data[key] = bool(raw.get(key, False))
    except (OSError, ValueError):
        pass
    return data


def save_settings(data: dict) -> None:
    try:
        import json

        SETTINGS_FILE.write_text(
            json.dumps({k: bool(v) for k, v in data.items()}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass


def load_codes_state() -> dict:
    try:
        import json

        return json.loads(Path(CODES_STATE_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_codes_state(state: dict) -> None:
    try:
        import json

        Path(CODES_STATE_FILE).write_text(
            json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError:
        pass


def run_code_job(path: Path) -> tuple[bool, str, str]:
    """یک فایل job_*.py را اجرا و نتیجه را در logs گوگل درایو ذخیره می‌کند.

    خروجی: (موفق بود؟، نام فایل، متن نتیجه)
    """
    started = time.time()
    dest_dir, _ = resolve_report_dir()
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        dest_dir = Path(CODES_DIR)

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    exit_code: int | str = "?"
    stdout_text = stderr_text = ""
    try:
        completed = subprocess.run(
            [sys.executable, str(path)],
            cwd=str(path.parent),
            capture_output=True,
            timeout=CODES_MAX_RUNTIME,
            env=env,
            creationflags=(subprocess.CREATE_NO_WINDOW if IS_WINDOWS else 0),
        )
        exit_code = completed.returncode
        stdout_text = completed.stdout.decode("utf-8", errors="replace")
        stderr_text = completed.stderr.decode("utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        exit_code = "TIMEOUT"
        stderr_text = f"اجرا بیش از {CODES_MAX_RUNTIME} ثانیه طول کشید."
    except Exception:
        stderr_text = traceback.format_exc()

    duration = time.time() - started
    now = tehran_now()
    ok = exit_code == 0

    text = "\n".join(
        [
            "نتیجه اجرای کد Arena",
            "=" * 58,
            f"فایل: {path.name}",
            f"شروع: {jalali_long(now)} — {now:%H:%M:%S} تهران",
            f"مدت: {duration:.1f} ثانیه",
            f"کد خروج: {exit_code}",
            "",
            "----- خروجی -----",
            stdout_text.rstrip() or "(خالی)",
            "",
            "----- خطاها -----",
            stderr_text.rstrip() or "(خالی)",
            "",
        ]
    )

    try:
        (dest_dir / f"{path.stem}_result.txt").write_text(text, encoding="utf-8")
    except OSError:
        pass

    state = load_codes_state()
    state[path.name] = {
        "hash": short_hash(path.read_bytes()) if path.exists() else "",
        "ran_at": f"{jalali_date(now)} {now:%H:%M:%S}",
        "exit_code": exit_code,
        "ok": ok,
        "duration_s": round(duration, 1),
    }
    save_codes_state(state)

    return ok, path.name, text


# -------------------------------------------------- بررسی وضعیت اتصال‌ها ---

def check_internet(timeout: float = 1.5) -> bool:
    """آیا به اینترنت دسترسی هست؟ (اتصال مستقیم تست می‌شود، بدون درخواست وب)"""
    try:
        sock = socket.create_connection(("8.8.8.8", 53), timeout=timeout)
        sock.close()
        return True
    except OSError:
        pass
    try:
        socket.gethostbyname("www.google.com")
        return True
    except OSError:
        return False


def check_google_drive() -> tuple[bool, str]:
    """آیا گوگل درایو (Drive for Desktop) وصل است؟"""
    options = [Path(DRIVE_BASE_DIR)]
    home_drive = Path.home() / "My Drive"
    options.append(home_drive)

    for path in options:
        try:
            if path.is_dir():
                return True, f"مسیر در دسترس است"
        except OSError:
            continue

    if IS_WINDOWS:
        try:
            out = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq GoogleDriveFS.exe", "/NH"],
                capture_output=True,
                text=True,
                timeout=4,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            if "GoogleDriveFS" in out.stdout:
                return False, "برنامه Drive باز است ولی مسیر My Drive پیدا نشد"
        except (OSError, subprocess.SubprocessError):
            pass

    return False, "در دسترس نیست"


# ------------------------------------------------------------ رابط کاربری ---

class AgentApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.log_queue: queue.Queue[str] = queue.Queue()
        self.ui_queue: queue.Queue = queue.Queue()
        self.busy = False

        root.title(f"{APP_TITLE} — نسخه {APP_VERSION} ({build_info()['commit']})")
        root.geometry("760x560")
        root.minsize(640, 460)
        root.configure(bg="#f4f6fb")

        base_font = ("Segoe UI", 10)
        self.font_normal = base_font
        self.font_button = ("Segoe UI", 11, "bold")

        self.settings = load_settings()
        self._sync_running = False
        self._sync_stop = threading.Event()

        self._build_ui()
        self.root.after(120, self._drain_log_queue)
        self._start_status_monitor()

        if self.settings["auto_fetch"]:
            self.start_sync()

        self.log(f"به Windows Agent خوش آمدید — نسخه {APP_VERSION}")
        self.log(
            f"نسخه در حال اجرا: کامیت {self.build['commit']} "
            f"| تاریخ ساخت {self.build['date']} ساعت {self.build['time']} تهران"
        )
        self.log(f"فایل در حال اجرا: {Path(__file__).resolve()}")
        self.log(f"دکمه اول: باز کردن {LMARENA_URL} در کروم و گرفتن اسکرین‌شات.")
        self.log("دکمه دوم: گزارش برنامه‌های باز ویندوز.")
        self.log("تب «آخرین تغییرات» تاریخچه نسخه‌ها را نشان می‌دهد.")
        self.log("")
        self.log("🔒 هیچ کاری خودکار انجام نشد. کنترل کامل دست شماست.")
        self.log(
            "   دریافت خودکار کد: "
            + ("روشن" if self.settings["auto_fetch"] else "خاموش")
            + " | اجرای خودکار: "
            + ("روشن" if self.settings["auto_run"] else "خاموش")
            + " | آپدیت برنامه: "
            + ("روشن" if self.settings["auto_update_app"] else "خاموش")
        )
        self.log("   برای گرفتن کدها دکمه «بررسی و دریافت کد» را بزنید.")
        self.log(f"منبع کد: {GITHUB_OWNER}/{GITHUB_REPO} @ {GITHUB_BRANCH}")
        self.log(f"پوشه کدها (محلی): {CODES_DIR}")
        self.log("")

        shots_dir, shots_ok = resolve_screenshot_dir()
        reports_dir, reports_ok = resolve_report_dir()

        if shots_ok and reports_ok:
            self.log(f"✔ اسکرین‌شات‌ها: {shots_dir}")
            self.log(f"✔ گزارش‌ها:   {reports_dir}")
        else:
            if shots_ok:
                self.log(f"✔ اسکرین‌شات‌ها: {shots_dir}")
            else:
                self.log(f"⚠️ مسیر اسکرین‌شات پیدا نشد: {SCREENSHOT_DIR}")
            if reports_ok:
                self.log(f"✔ گزارش‌ها:   {reports_dir}")
            else:
                self.log(f"⚠️ مسیر گزارش‌ها پیدا نشد: {REPORT_DIR}")
            self.log("   Google Drive برای ویندوز را اجرا کنید تا پوشه My Drive متصل شود.")
            self.log(f"   تا آن موقع فایل‌ها موقتاً روی دسکتاپ ذخیره می‌شوند: {get_desktop_dir()}")
        self.log("")
        if not IS_WINDOWS:
            self.log("⚠️ توجه: این برنامه برای ویندوز نوشته شده است.")
            self.log("   گرفتن اسکرین‌شات و گزارش پنجره‌ها فقط روی ویندوز کار می‌کند.")
            self.log("")

    # --- ساخت رابط -----------------------------------------------------------

    def _build_ui(self) -> None:
        self.build = build_info()
        bg = "#f4f6fb"

        # ---------------------------- هدر ----------------------------
        header = tk.Frame(self.root, bg="#1f2a44", pady=12)
        header.pack(fill="x")

        tk.Label(
            header,
            text="🤖  Windows Agent",
            font=("Segoe UI", 17, "bold"),
            fg="white",
            bg="#1f2a44",
        ).pack()

        ident = (
            self.build.get("filehash")
            or self.build.get("commit")
            or "?"
        )
        stamp = f"نسخه {to_fa(APP_VERSION)}  ·  شناسه {ident}"
        tk.Label(
            header,
            text=stamp,
            font=("Segoe UI", 11, "bold"),
            fg="#9ec3ff",
            bg="#1f2a44",
        ).pack(pady=(6, 0))

        try:
            jy, jm, jd = (int(part) for part in self.build["date"].split("/"))
            long_date = f"{to_fa(jd)} {FA_MONTHS[jm - 1]} {to_fa(jy)}"
        except (ValueError, IndexError):
            long_date = self.build["date"]
        date_line = (
            f"ساخته‌شده: {long_date} — ساعت {to_fa(self.build['time'])} تهران"
        )
        tk.Label(
            header,
            text=date_line,
            font=("Segoe UI", 9),
            fg="#c7d0e4",
            bg="#1f2a44",
        ).pack(pady=(2, 0))

        # ------------------------ نوار چراغ‌ها ------------------------
        lamps_bar = tk.Frame(self.root, bg="#e8edf7", pady=6)
        lamps_bar.pack(fill="x")

        self.lamp_internet = self._make_lamp(lamps_bar, "اینترنت")
        self.lamp_drive = self._make_lamp(lamps_bar, "گوگل درایو")
        self.lamp_github = self._make_lamp(lamps_bar, "گیت‌هاب")

        tk.Label(
            lamps_bar,
            text="وضعیت زنده",
            font=("Segoe UI", 8),
            fg="#6b7691",
            bg="#e8edf7",
        ).pack(side="right", padx=14)

        # ------------------- پنل کنترل خودکارسازی -------------------
        auto_bar = tk.LabelFrame(
            self.root,
            text="  کنترل خودکارسازی (پیش‌فرض: خاموش)  ",
            font=("Tahoma", 9, "bold"),
            bg="#ffffff",
            fg="#3b4763",
            bd=1,
            relief="solid",
            pady=6,
        )
        auto_bar.pack(fill="x", padx=12, pady=(8, 0))

        self.var_auto_fetch = tk.BooleanVar(value=self.settings["auto_fetch"])
        self.var_auto_run = tk.BooleanVar(value=self.settings["auto_run"])
        self.var_auto_update = tk.BooleanVar(value=self.settings["auto_update_app"])

        tk.Checkbutton(
            auto_bar,
            text="به‌روزرسانی خودکار خود برنامه",
            variable=self.var_auto_update,
            font=("Tahoma", 9),
            bg="#ffffff",
            fg="#1f2a44",
            activebackground="#ffffff",
            anchor="e",
            cursor="hand2",
            command=self.action_toggle_auto,
        ).pack(side="right", padx=4)

        tk.Checkbutton(
            auto_bar,
            text="دریافت خودکار کد از گیت‌هاب (هر ۱۰ ثانیه)",
            variable=self.var_auto_fetch,
            font=("Tahoma", 9),
            bg="#ffffff",
            fg="#1f2a44",
            activebackground="#ffffff",
            anchor="e",
            cursor="hand2",
            command=self.action_toggle_auto,
        ).pack(side="right", padx=(14, 4))

        tk.Checkbutton(
            auto_bar,
            text="اجرای خودکار کدهای جدید",
            variable=self.var_auto_run,
            font=("Tahoma", 9),
            bg="#ffffff",
            fg="#1f2a44",
            activebackground="#ffffff",
            anchor="e",
            cursor="hand2",
            command=self.action_toggle_auto,
        ).pack(side="right", padx=4)

        self.auto_indicator = tk.Label(
            auto_bar,
            text="",
            font=("Tahoma", 8),
            bg="#ffffff",
            fg="#8a93a6",
        )
        self.auto_indicator.pack(side="left", padx=10)

        # ------------------------- تب‌ها -------------------------
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TNotebook", background=bg, borderwidth=0)
        style.configure(
            "TNotebook.Tab", font=("Segoe UI", 10, "bold"), padding=(18, 8)
        )

        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=12, pady=(8, 4))
        self.notebook = notebook

        # ---------- تب ۱: عملیات ----------
        tab_main = tk.Frame(notebook, bg=bg)
        notebook.add(tab_main, text="  عملیات  ")

        buttons_frame = tk.Frame(tab_main, bg=bg, pady=12)
        buttons_frame.pack(fill="x", padx=6)

        self.btn_capture = tk.Button(
            buttons_frame,
            text="📸  باز کردن سایت و گرفتن اسکرین‌شات",
            font=self.font_button,
            bg="#2f6fed",
            fg="white",
            activebackground="#255bc4",
            activeforeground="white",
            relief="flat",
            cursor="hand2",
            pady=14,
            command=self.action_capture,
        )
        self.btn_capture.pack(side="right", expand=True, fill="x", padx=(0, 8))

        self.btn_report = tk.Button(
            buttons_frame,
            text="📋  گزارش برنامه‌های باز",
            font=self.font_button,
            bg="#2e9e6b",
            fg="white",
            activebackground="#268158",
            activeforeground="white",
            relief="flat",
            cursor="hand2",
            pady=14,
            command=self.action_report,
        )
        self.btn_report.pack(side="right", expand=True, fill="x", padx=(8, 0))

        log_frame = tk.LabelFrame(
            tab_main,
            text="  وضعیت  ",
            font=("Segoe UI", 9, "bold"),
            bg=bg,
            fg="#3b4763",
            bd=1,
            relief="solid",
        )
        log_frame.pack(fill="both", expand=True, padx=6, pady=(0, 6))

        self.log_box = scrolledtext.ScrolledText(
            log_frame,
            wrap="word",
            font=("Consolas", 10),
            bg="#ffffff",
            fg="#1f2a44",
            relief="flat",
            padx=10,
            pady=8,
        )
        self.log_box.pack(fill="both", expand=True, padx=6, pady=6)
        self.log_box.configure(state="disabled")
        self.log_box.tag_configure("fa", font=("Tahoma", 10))

        # ---------- تب ۲: آخرین تغییرات ----------
        tab_changes = tk.Frame(notebook, bg=bg)
        notebook.add(tab_changes, text="  آخرین تغییرات  ")

        self.changes_box = scrolledtext.ScrolledText(
            tab_changes,
            wrap="word",
            font=("Tahoma", 10),
            bg="#ffffff",
            fg="#1f2a44",
            relief="flat",
            padx=14,
            pady=12,
        )
        self.changes_box.pack(fill="both", expand=True, padx=6, pady=6)
        self.changes_box.insert("end", self._changelog_text())
        self.changes_box.configure(state="disabled")

        # ---------- تب ۳: کدها ----------
        tab_codes = tk.Frame(notebook, bg=bg)
        notebook.add(tab_codes, text="  کدها  ")

        codes_top = tk.Frame(tab_codes, bg=bg)
        codes_top.pack(fill="x", padx=6, pady=(6, 0))

        tk.Label(
            codes_top,
            text=f"پوشه کدها: {CODES_DIR}",
            font=("Tahoma", 9),
            bg=bg,
            fg="#3b4763",
            anchor="e",
        ).pack(side="right")

        self.codes_status = tk.Label(
            codes_top,
            text="در انتظار دستور شما",
            font=("Tahoma", 9, "bold"),
            bg=bg,
            fg="#8a93a6",
            anchor="w",
        )
        self.codes_status.pack(side="left", padx=(0, 10))

        self.btn_run_codes = tk.Button(
            codes_top,
            text="▶️  اجرای کدهای جدید",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            bg="#2e9e6b",
            fg="white",
            activebackground="#268158",
            activeforeground="white",
            cursor="hand2",
            padx=12,
            pady=4,
            command=self.action_run_codes,
        )
        self.btn_run_codes.pack(side="left", padx=6)

        self.btn_fetch = tk.Button(
            codes_top,
            text="📥  بررسی و دریافت کد",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            bg="#2f6fed",
            fg="white",
            activebackground="#255bc4",
            activeforeground="white",
            cursor="hand2",
            padx=12,
            pady=4,
            command=self.action_fetch_codes,
        )
        self.btn_fetch.pack(side="left", padx=6)

        self.codes_box = scrolledtext.ScrolledText(
            tab_codes,
            wrap="word",
            font=("Consolas", 10),
            bg="#ffffff",
            fg="#1f2a44",
            relief="flat",
            padx=10,
            pady=8,
        )
        self.codes_box.pack(fill="both", expand=True, padx=6, pady=6)
        self.codes_box.configure(state="disabled")
        self.codes_box.insert("end", self._codes_summary())
        self.codes_box.configure(state="disabled")

        # ------------------------- پاصفحه -------------------------
        footer = tk.Label(
            self.root,
            text=f"فایل در حال اجرا: {Path(__file__).resolve()}",
            font=("Segoe UI", 8),
            fg="#6b7691",
            bg=bg,
        )
        footer.pack(pady=(0, 6))

        self._refresh_auto_indicator()

    # --- چراغ‌های وضعیت ------------------------------------------------------

    def _make_lamp(self, parent, title: str) -> dict:
        bg = "#e8edf7"
        box = tk.Frame(parent, bg=bg)
        box.pack(side="right", padx=10)

        canvas = tk.Canvas(
            box, width=14, height=14, bg=bg, highlightthickness=0, bd=0
        )
        dot = canvas.create_oval(1, 1, 13, 13, fill="#9aa4b8", outline="")
        canvas.pack(side="right", padx=(4, 0))

        caption = tk.Label(
            box,
            text="در حال بررسی…",
            font=("Segoe UI", 8),
            bg=bg,
            fg="#6b7691",
        )
        caption.pack(side="right", padx=(6, 0))

        label = tk.Label(
            box,
            text=title,
            font=("Segoe UI", 9, "bold"),
            bg=bg,
            fg="#3b4763",
        )
        label.pack(side="right")

        return {"canvas": canvas, "dot": dot, "caption": caption}

    def _set_lamp(self, lamp: dict, state: str, text: str = "") -> None:
        colors = {"ok": "#22a06b", "bad": "#d64545", "wait": "#9aa4b8"}
        lamp["canvas"].itemconfigure(lamp["dot"], fill=colors.get(state, "#9aa4b8"))
        if text:
            lamp["caption"].configure(text=text)

    def _changelog_text(self) -> str:
        lines = [
            f"{APP_TITLE} — تاریخچه تغییرات",
            "=" * 58,
            f"نسخه در حال اجرا: {APP_VERSION}",
            f"شناسه فایل: {self.build.get('filehash') or '?'}",
            f"کامیت: {self.build['commit']} — {self.build['subject']}",
            f"تاریخ ساخت: {self.build['date']} — ساعت {self.build['time']} تهران",
            f"منبع اطلاعات ساخت: "
            f"{'مخزن گیت' if self.build['source'] == 'git' else 'مقدار ثابت داخل فایل'}",
            f"فایل: {Path(__file__).resolve()}",
            "",
        ]
        for version, date, items in CHANGELOG:
            lines.append(f"◾ نسخه {version} — {date}")
            for item in items:
                lines.append(f"   • {item}")
            lines.append("")
        return "\n".join(lines)

    # --- همگام‌سازی با گیت‌هاب --------------------------------------------------

    def _run_on_ui(self, fn) -> None:
        """اجرای یک تغییر رابط کاربری از دل نخست (thread) به‌صورت امن."""
        self.ui_queue.put(fn)

    def start_sync(self) -> None:
        """پایش خودکار؛ فقط وقتی کاربر روشنش کرده باشد."""
        if self._sync_running:
            return
        self._sync_running = True
        self._sync_stop.clear()

        def loop() -> None:
            while not self._sync_stop.is_set():
                try:
                    self.sync_once()
                except Exception:
                    pass
                self._sync_stop.wait(SYNC_POLL_SECONDS)

        threading.Thread(target=loop, daemon=True).start()

    def stop_sync(self) -> None:
        self._sync_running = False
        self._sync_stop.set()

    # --- دکمه‌های دستی --------------------------------------------------------

    def action_fetch_codes(self) -> None:
        """دکمه «بررسی و دریافت کد» — فقط دریافت، بدون اجرا."""
        if self.busy:
            return
        self.log("📥 بررسی نسخه جدید در گیت‌هاب…")
        threading.Thread(target=self.sync_once, kwargs={"manual": True}, daemon=True).start()

    def action_run_codes(self) -> None:
        """دکمه «اجرای کدهای جدید» — با فشار خودت اجرا می‌شود."""
        if self.busy:
            return
        self.run_pending_codes(manual=True)

    def action_toggle_auto(self) -> None:
        """کلیک روی کلیدهای خودکارسازی."""
        auto_fetch = self.var_auto_fetch.get()
        auto_run = self.var_auto_run.get()
        auto_update = self.var_auto_update.get()

        # اجرا/آپدیت خودکار بی‌معنی است اگر دریافت خودکار خاموش باشد
        if (auto_run or auto_update) and not auto_fetch:
            self.var_auto_fetch.set(True)
            auto_fetch = True

        self.settings["auto_fetch"] = auto_fetch
        self.settings["auto_run"] = auto_run
        self.settings["auto_update_app"] = auto_update
        save_settings(self.settings)

        if auto_fetch:
            self.start_sync()
        else:
            self.stop_sync()

        self.log(
            "⚙️ تنظیمات ذخیره شد — دریافت خودکار: "
            + ("روشن" if auto_fetch else "خاموش")
            + " | اجرای خودکار: "
            + ("روشن" if auto_run else "خاموش")
            + " | آپدیت برنامه: "
            + ("روشن" if auto_update else "خاموش")
        )
        self._refresh_auto_indicator()

    def _refresh_auto_indicator(self) -> None:
        text = (
            f"دریافت خودکار: {'روشن' if self.settings['auto_fetch'] else 'خاموش'}"
            f"  ·  اجرا: {'روشن' if self.settings['auto_run'] else 'خاموش'}"
            f"  ·  آپدیت برنامه: {'روشن' if self.settings['auto_update_app'] else 'خاموش'}"
        )
        self.auto_indicator.configure(
            text=text,
            fg="#2e9e6b" if self.settings["auto_fetch"] else "#8a93a6",
        )

    def sync_once(self, manual: bool = False) -> bool:
        """بسته کد را از گیت‌هاب می‌گیرد. اجرا فقط با اجازه کاربر."""
        data = repo_zip()
        if not data:
            self._run_on_ui(lambda: self._set_lamp(self.lamp_github, "bad", "قطع"))
            if manual:
                self.log("❌ دریافت از گیت‌هاب ممکن نشد (اینترنت یا پروکسی را چک کنید).")
            return False

        version_bytes = extract_file(data, GITHUB_VERSION_FILE)
        version = (
            version_bytes.decode("utf-8", errors="replace").strip()
            if version_bytes
            else "?"
        )
        self._last_version = version
        self._run_on_ui(
            lambda: self._set_lamp(self.lamp_github, "ok", version[:7])
        )

        remote_app = extract_file(data, "app.py")
        app_differs = False
        try:
            app_differs = bool(remote_app) and remote_app != Path(__file__).resolve().read_bytes()
        except OSError:
            app_differs = False

        if app_differs and self.settings["auto_update_app"]:
            if self._update_app_if_needed(data, version):
                return True  # برنامه خودش را ری‌استارت می‌کند
        elif app_differs and manual:
            self.log("ℹ️ نسخه تازه‌تری از خود برنامه هم وجود دارد.")
            self.log("   نصب نمی‌شود مگر گزینه «به‌روزرسانی خودکار برنامه» را روشن کنی.")

        changed = self._replace_codes(data)
        if manual:
            if changed:
                self.log("✅ کدهای جدید در پوشه codes قرار گرفت (هنوز اجرا نشده‌اند).")
                self.log("   برای اجرا دکمه «اجرای کدهای جدید» را بزنید.")
            else:
                self.log("✅ کدها به‌روز است؛ چیز تازه‌ای نبود.")
        elif changed and self.settings["auto_run"]:
            self.log("🔁 اجرای خودکار روشن است — کدهای جدید اجرا می‌شوند.")
            self.run_pending_codes(manual=False)

        self._run_on_ui(self.refresh_codes_box)
        return True

    def _update_app_if_needed(self, data: bytes, version: str) -> bool:
        remote = extract_file(data, "app.py")
        if not remote:
            return False
        here = Path(__file__).resolve()
        try:
            if remote == here.read_bytes():
                return False
        except OSError:
            return False

        import py_compile
        import tempfile

        try:
            with tempfile.NamedTemporaryFile(
                "w", suffix=".py", delete=False, encoding="utf-8"
            ) as fh:
                fh.write(remote.decode("utf-8", errors="replace"))
                temp_path = fh.name
            py_compile.compile(temp_path, doraise=True)
            Path(temp_path).unlink(missing_ok=True)
        except Exception as exc:
            self.log(f"⚠️ نسخه جدید سالم نیست، اعمال نشد: {exc}")
            return False

        backup = here.with_name(f"app.backup-{datetime.now():%Y%m%d-%H%M%S}.py")
        try:
            backup.write_bytes(here.read_bytes())
            here.write_bytes(remote)
        except OSError as exc:
            self.log(f"⚠️ نوشتن نسخه جدید ممکن نشد: {exc}")
            return False

        try:
            import json

            STAMP_FILE.write_text(
                json.dumps(
                    {
                        "version": version,
                        "date": jalali_date(tehran_now()),
                        "time": f"{tehran_now():%H:%M}",
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        except OSError:
            pass

        self.log(f"🔄 برنامه بروز شد (نسخه {version}) — پشتیبان: {backup.name}")
        if AUTO_RESTART_ON_UPDATE:
            self.log("   راه‌اندازی مجدد در ۲ ثانیه…")
            time.sleep(2)
            try:
                subprocess.Popen([sys.executable, str(here)])
            except OSError:
                pass
            os._exit(0)
        return True

    def _replace_codes(self, data: bytes) -> bool:
        """محتویات پوشه codes ریپو جایگزین پوشه codes محلی می‌شود."""
        files = extract_folder(data, GITHUB_CODES_PATH)
        codes_dir = Path(CODES_DIR)
        try:
            codes_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self.log(f"⚠️ ساخت پوشه codes ممکن نشد: {exc}")
            return False

        removed = 0
        for existing in codes_dir.glob("*.py"):
            if existing.name not in files:
                try:
                    existing.unlink()
                    removed += 1
                except OSError:
                    pass

        written = 0
        unchanged = 0
        for name, content in files.items():
            target = codes_dir / name
            try:
                if target.exists() and target.read_bytes() == content:
                    unchanged += 1
                    continue
                target.write_bytes(content)
                written += 1
            except OSError as exc:
                self.log(f"⚠️ نوشتن {name} ممکن نشد: {exc}")

        if written or removed:
            self.log(
                f"📁 پوشه codes به‌روز شد: {written} فایل جدید/تغییریافته"
                + (f"، {removed} حذف‌شده" if removed else "")
            )
        return written > 0 or removed > 0

    def run_pending_codes(self, manual: bool = True) -> None:
        """کدهایی که تازه آمده‌اند یا تغییر کرده‌اند را اجرا می‌کند."""
        codes_dir = Path(CODES_DIR)
        state = load_codes_state()
        pending = []

        for path in sorted(codes_dir.glob("job_*.py")):
            try:
                current = short_hash(path.read_bytes())
            except OSError:
                continue
            if state.get(path.name, {}).get("hash") == current:
                continue
            pending.append(path)

        if not pending:
            if manual:
                self.log("✅ کد جدیدی برای اجرا نیست. همه کدها قبلاً اجرا شده‌اند.")
            self._run_on_ui(self.refresh_codes_box)
            return

        self._run_on_ui(
            lambda: self.codes_status.configure(text="در حال اجرا…", fg="#2f6fed")
        )
        for path in pending:
            self.log(f"▶️ اجرای {path.name}")
            ok, name, text = run_code_job(path)
            for line in text.splitlines()[-10:]:
                self.log(f"   {line}")
            self.log(f"{'✅' if ok else '❌'} پایان {name}")
            self._run_on_ui(
                lambda n=name, o=ok: self.codes_status.configure(
                    text=f"آخرین اجرا: {n} — {'موفق' if o else 'خطا'}",
                    fg="#2e9e6b" if o else "#d64545",
                )
            )
        self._run_on_ui(self.refresh_codes_box)

    # --- موتور اجرای کدهای جانبی ---------------------------------------------

    def _codes_summary(self) -> str:
        state = load_codes_state()
        lines = [
            "کدهای جانبی",
            "=" * 58,
            f"منبع کد: GitHub — {GITHUB_OWNER}/{GITHUB_REPO} ({GITHUB_BRANCH})",
            f"آخرین نسخه دریافتی: {getattr(self, '_last_version', None) or '—'}",
            f"دریافت خودکار: {'روشن' if self.settings['auto_fetch'] else 'خاموش'}"
            f"  ·  اجرای خودکار: {'روشن' if self.settings['auto_run'] else 'خاموش'}"
            f"  ·  آپدیت برنامه: {'روشن' if self.settings['auto_update_app'] else 'خاموش'}",
            "",
            "روش کار:",
            "  ۱) دکمه «بررسی و دریافت کد» → کدها از گیت‌هاب در پوشه codes می‌آیند.",
            "  ۲) دکمه «اجرای کدهای جدید» → همان کدها اجرا و نتیجه در logs نوشته می‌شود.",
            "  هیچ‌کدام از این دو کار تا وقتی خودت نزنی انجام نمی‌شود.",
            "",
            f"پوشه کدها: {CODES_DIR}",
            f"پوشه نتیجه: {REPORT_DIR}",
            "",
        ]
        if not state:
            lines.append("هنوز هیچ کدی اجرا نشده است.")
            lines.append("")
            lines.append(
                "هر فایلی با نام job_*.py که در پوشه کدها قرار بگیرد، "
                "خودکار اجرا می‌شود."
            )
        else:
            lines.append(f"تعداد کدهای اجراشده: {len(state)}")
            lines.append("")
            for name, info in sorted(state.items()):
                mark = "✔" if info.get("ok") else "✘"
                lines.append(
                    f"{mark} {name} — کد خروج {info.get('exit_code')} "
                    f"— {info.get('ran_at')} — {info.get('duration_s')} ثانیه"
                )
        lines.append("")
        return "\n".join(lines)

    def refresh_codes_box(self) -> None:
        self.codes_box.configure(state="normal")
        self.codes_box.delete("1.0", "end")
        self.codes_box.insert("end", self._codes_summary())
        self.codes_box.configure(state="disabled")

    # --- پایش وضعیت اتصال ----------------------------------------------------

    def _start_status_monitor(self) -> None:
        self.status_queue: queue.Queue[tuple[bool, bool, str]] = queue.Queue()

        def worker() -> None:
            while True:
                try:
                    internet = check_internet()
                    drive_ok, drive_msg = check_google_drive()
                    self.status_queue.put((internet, drive_ok, drive_msg))
                except Exception:
                    self.status_queue.put((False, False, "خطا در بررسی"))
                time.sleep(STATUS_CHECK_SECONDS)

        threading.Thread(target=worker, daemon=True).start()
        self._poll_status()

    def _poll_status(self) -> None:
        try:
            while True:
                internet, drive_ok, drive_msg = self.status_queue.get_nowait()
                self._set_lamp(
                    self.lamp_internet,
                    "ok" if internet else "bad",
                    "وصل" if internet else "قطع",
                )
                self._set_lamp(
                    self.lamp_drive,
                    "ok" if drive_ok else "bad",
                    "وصل" if drive_ok else "قطع",
                )
                if not drive_ok:
                    self.lamp_drive["caption"].configure(text=drive_msg[:40])
        except queue.Empty:
            pass
        self.root.after(300, self._poll_status)

    # --- لاگ ----------------------------------------------------------------

    def log(self, message: str) -> None:
        """نوشتن در کادر وضعیت (از هر تردی قابل استفاده است)."""
        self.log_queue.put(message)

    def _drain_log_queue(self) -> None:
        try:
            while True:
                message = self.log_queue.get_nowait()
                self.log_box.configure(state="normal")
                self.log_box.insert("end", message + "\n")
                self.log_box.see("end")
                self.log_box.configure(state="disabled")
        except queue.Empty:
            pass

        try:
            while True:
                fn = self.ui_queue.get_nowait()
                try:
                    fn()
                except Exception:
                    pass
        except queue.Empty:
            pass

        self.root.after(120, self._drain_log_queue)

    # --- اجرای کارها در ترد جدا ---------------------------------------------

    def _set_busy(self, busy: bool) -> None:
        self.busy = busy
        state = "disabled" if busy else "normal"
        self.btn_capture.configure(state=state)
        self.btn_report.configure(state=state)
        self.root.configure(cursor="watch" if busy else "")

    def _run_task(self, label: str, job) -> None:
        if self.busy:
            return
        self._set_busy(True)
        self.log(f"── {label} ──")

        def runner() -> None:
            try:
                job()
            except Exception as exc:  # noqa: BLE001 - خطا باید در UI دیده شود
                self.log(f"❌ خطا: {exc}")
                self.log(traceback.format_exc())
            finally:
                self.root.after(0, lambda: self._set_busy(False))

        threading.Thread(target=runner, daemon=True).start()

    # --- دکمه ۱: اسکرین‌شات --------------------------------------------------

    def action_capture(self) -> None:
        self._run_task("باز کردن سایت و گرفتن اسکرین‌شات", self._job_capture)

    def _job_capture(self) -> None:
        dest, on_drive = resolve_screenshot_dir()
        if on_drive:
            self.log(f"پوشه مقصد (گوگل درایو): {dest}")
        else:
            self.log(f"⚠️ پوشه گوگل درایو در دسترس نیست: {SCREENSHOT_DIR}")
            self.log("   آیا Google Drive برای ویندوز در حال اجراست؟ (آیکون آن در سینی)")
            self.log(f"   این بار موقتاً اینجا ذخیره می‌شود: {dest}")

        self.log(f"باز کردن {LMARENA_URL} در کروم …")
        browser = open_in_chrome(LMARENA_URL)
        self.log(f"مرورگر اجرا شد: {browser}")

        self.log(f"صبر می‌کنیم تا صفحه باز شود ({PAGE_LOAD_SECONDS} ثانیه) …")
        for remaining in range(PAGE_LOAD_SECONDS, 0, -1):
            self.log(f"   … {remaining}")
            time.sleep(1)

        self.log("در حال گرفتن اسکرین‌شات از کل صفحه …")
        path = take_screenshot(dest)
        size_bytes = path.stat().st_size if path.exists() else 0
        self.log(f"✅ اسکرین‌شات ذخیره شد: {path}")
        self.log(f"   حجم فایل: {human_size(size_bytes)}")
        if on_drive:
            self.log("   گوگل درایو به‌صورت خودکار آن را آپلود می‌کند؛ چند لحظه صبر کنید.")
        self.log("")

    # --- دکمه ۲: گزارش برنامه‌های باز ----------------------------------------

    def action_report(self) -> None:
        self._run_task("گرفتن گزارش برنامه‌های باز", self._job_report)

    def _job_report(self) -> None:
        dest, on_drive = resolve_report_dir()
        if on_drive:
            self.log(f"پوشه گزارش‌ها (گوگل درایو): {dest}")
        else:
            self.log(f"⚠️ پوشه گزارش‌های گوگل درایو در دسترس نیست: {REPORT_DIR}")
            self.log(f"   این بار موقتاً اینجا ذخیره می‌شود: {dest}")

        self.log("در حال خواندن پنجره‌های باز ویندوز …")
        windows = collect_open_windows()
        report = format_windows_report(windows)

        self.log(f"تعداد پنجره‌های پیدا شده: {len(windows)}")
        for window in windows:
            self.log(f"   • {window['process']} — {window['title']}")

        path = save_report(report, dest)
        self.log(f"✅ گزارش ذخیره شد: {path}")
        self.log("")


# ------------------------------------------------------------------ شروع ---

def main() -> None:
    enable_dpi_awareness()
    root = tk.Tk()
    try:
        root.iconbitmap(default="")
    except Exception:
        pass
    AgentApp(root)
    root.mainloop()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # اگر رابط کاربری بالا نیامد، حداقل دلیلش را ذخیره کن
        try:
            with ERROR_LOG.open("a", encoding="utf-8") as fh:
                fh.write(f"\n==== {datetime.now():%Y-%m-%d %H:%M:%S} ====\n")
                fh.write(traceback.format_exc())
        except Exception:
            pass
        ctypes.windll.user32.MessageBoxW(
            0,
            "برنامه با خطا بسته شد.\nجزئیات در فایل error.log کنار برنامه ذخیره شد.",
            "Windows Agent",
            0x10,
        )
        sys.exit(1)
