# -*- coding: utf-8 -*-
"""
Windows Agent — نسخه ۱.۳
------------------------
رابط کاربری با pygame (گرافیک برداری، سایه، انیمیشن و صدا)

  ۱) باز کردن سایت در کروم و گرفتن اسکرین‌شات (ذخیره در گوگل درایو)
  ۲) گرفتن گزارش از برنامه‌های باز ویندوز
  ۳) بررسی مخزن ایجنت همکار ← ذخیره در CODES روی دسکتاپ ← اجرا
  ۴) کتابخانه کدها با دکمه پخش برای اجرای مجدد
  + کلید حالت دستی/خودکار با تایمر دایره‌ای و افکت صوتی

نحوه اجرا: فایل run.bat را دوبار کلیک کنید (کتابخانه‌های لازم را خودش نصب می‌کند).
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

# ---------------------------------------------------------------- تنظیمات ---

APP_TITLE = "Windows Agent"
APP_VERSION = "1.3"

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
        "1.3",
        "۱۴۰۵/۰۸/۰۲",
        [
            "رابط کاربری از Tkinter به pygame منتقل شد",
            "گرافیک برداری: کارت‌های گرد، سایه، انیمیشن و حالت هاور",
            "افکت صوتی برای کلیک، باز شدن، اجرا، موفقیت، خطا و شاتر",
            "تایمر دایره‌ای برای شمارش معکوس حالت خودکار",
            "تب «کتابخانه کدها» با دکمه پخش برای اجرای مجدد هر کد",
            "run.bat کتابخانه‌های لازم را خودش نصب می‌کند",
        ],
    ),
    (
        "1.2",
        "۱۴۰۵/۰۸/۰۲",
        [
            "رابط کاربری کامل بازطراحی شد",
            "تم تاریک و روشن با کلید تغییر تم در هدر",
            "فونت وزیرمتن همراه برنامه",
            "کلید کشویی گرد برای حالت دستی/خودکار",
            "تب‌های کپسولی، کارت‌ها و نوار وضعیت تازه",
            "ساعت و تاریخ جلالی زنده در هدر",
            "مخزن ایجنت مادر در برنامه قابل تنظیم شد",
        ],
    ),
    (
        "1.1",
        "۱۴۰۵/۰۸/۰۲",
        [
            "هیچ فایلی در پوشه خود برنامه ذخیره نمی‌شود",
            "تنظیمات و وضعیت در پوشه کاربر (LOCALAPPDATA) ذخیره می‌شوند",
            "پشتیبان نسخه قبلی هم در همان پوشه است، نه کنار app.py",
            "همه خطاها در Google Drive\logs\errors ذخیره می‌شوند",
            "خطای دریافت مخزن، خطای اجرا و خطای شروع همه ثبت می‌شوند",
        ],
    ),
    (
        "1.0",
        "۱۴۰۵/۰۸/۰۲",
        [
            "پوشه codes از مخزن خودمان حذف شد",
            "مخزن ایجنت همکار جداگانه بررسی می‌شود",
            "کدها در پوشه CODES روی دسکتاپ ذخیره می‌شوند",
            "یک کلید: حالت دستی (هر مرحله اجازه) یا حالت خودکار",
            "مخزن و شاخه ایجنت همکار داخل خود برنامه قابل تنظیم است",
        ],
    ),
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

# پوشه‌ی خود برنامه — هیچ فایلی اینجا نوشته نمی‌شود
LOCAL_BASE_DIR = Path(__file__).resolve().parent

# همه‌ی فایل‌های وضعیت در پوشه‌ی کاربر ذخیره می‌شوند، نه کنار برنامه
IS_WINDOWS = os.name == "nt"
if IS_WINDOWS:
    STATE_DIR = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "Windows-Agent"
else:
    STATE_DIR = Path.home() / ".windows-agent"

BACKUP_DIR = STATE_DIR / "backups"
STAMP_FILE = STATE_DIR / "build_stamp.json"
CODES_STATE_FILE = str(STATE_DIR / "codes_state.json")
SETTINGS_FILE = STATE_DIR / "settings.json"

# پوشه کدهای ایجنت همکار روی دسکتاپ ساخته می‌شود
CODES_FOLDER_NAME = "CODES"

# تنظیمات پیش‌فرض — همه چیز دستی است تا خودت روشنش کنی
DEFAULT_SETTINGS = {
    "auto": False,          # یک کلید: خودکار یا دستی
    "theme": "dark",        # dark یا light
    # مخزن ایجنت مادر (خود برنامه)
    "mother_owner": "soheylfriend-MAJIDgit",
    "mother_repo": "Windows-Agent",
    "mother_branch": "arena/025c788f-windows-agent",
    # مخزن ایجنت همکار (کدها)
    "collab_owner": "soheylfriend-MAJIDgit",
    "collab_repo": "Windows-Agent-hamkar",
    "collab_branch": "arena/beecb74c-windows-agent-hamkar",
}

THEMES: dict[str, dict[str, str]] = {
    "dark": {
        "bg": "#161511", "surface": "#1e1d17", "surface2": "#26241d",
        "border": "#34322a", "border_strong": "#46443a",
        "text": "#eceade", "text_dim": "#a39e8d",
        "accent": "#3ab5a5", "accent_strong": "#5ecdbc", "accent_soft": "#1d2e2b",
        "danger": "#e07b74", "danger_soft": "#33211f",
        "ok": "#4cc696", "ok_soft": "#1c2e26",
        "warn": "#f08a5d", "warn_soft": "#34211a",
        "due": "#6fa8e8", "due_soft": "#1c2733",
    },
    "light": {
        "bg": "#f6f5f1", "surface": "#ffffff", "surface2": "#efede7",
        "border": "#e2dfd6", "border_strong": "#cfccc2",
        "text": "#23211c", "text_dim": "#6e6a5e",
        "accent": "#0d7a6f", "accent_strong": "#0a5f57", "accent_soft": "#e1f0ec",
        "danger": "#b3403a", "danger_soft": "#f9e8e7",
        "ok": "#1b7f5e", "ok_soft": "#e2f2e8",
        "warn": "#c2410c", "warn_soft": "#fdece3",
        "due": "#2c6cb8", "due_soft": "#e4eefb",
    },
}

# ------------------------------------------------------------------
#  دو مخزن داریم:
#   ۱) مخزن خودمان (اینجا)  →  فقط نسخه خود برنامه
#   ۲) مخزن ایجنت همکار      →  کدهای پایتونی که باید اجرا شوند
# ------------------------------------------------------------------
GITHUB_OWNER = "soheylfriend-MAJIDgit"
GITHUB_REPO = "Windows-Agent"
GITHUB_BRANCH = "arena/025c788f-windows-agent"
GITHUB_VERSION_FILE = "version.txt"

# هر چند ثانیه مخزن همکار بررسی شود (حالت خودکار)
SYNC_POLL_SECONDS = 10

# آیا بعد از بروزرسانی، برنامه خودش را دوباره راه‌اندازی کند؟
AUTO_RESTART_ON_UPDATE = True

# حداکثر زمان اجرای هر کد جانبی (ثانیه)
CODES_MAX_RUNTIME = 600

# اگر گوگل درایو در دسترس نباشد، این‌ها کجا ذخیره شوند؟
# None یعنی روی دسکتاپ (با زیرپوشه‌های ScreenShots و logs)
FALLBACK_BASE_DIR = None

# زیرپوشه‌ی خطاها داخل logs گوگل درایو
ERROR_SUBFOLDER = "errors"


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


def error_dir() -> Path:
    """پوشه خطاها: گوگل درایو\logs\errors (اگر در دسترس نبود، پوشه وضعیت)."""
    try:
        dest, _ = resolve_report_dir()
        target = Path(dest) / ERROR_SUBFOLDER
        target.mkdir(parents=True, exist_ok=True)
        return target
    except OSError:
        pass
    except Exception:
        pass
    target = STATE_DIR / ERROR_SUBFOLDER
    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return target


def write_error(context: str, detail: str = "") -> Path | None:
    """هر خطا یا مشکلی را در فایل خطای همان روز ذخیره می‌کند."""
    now = tehran_now()
    name = f"errors_{jalali_date(now).replace('/', '-')}.txt"
    path = error_dir() / name
    block = [
        "=" * 62,
        f"زمان: {jalali_long(now)} — {now:%H:%M:%S} تهران",
        f"موضوع: {context}",
        f"نسخه برنامه: {APP_VERSION}",
        (detail.rstrip() or "(بدون جزئیات)"),
        "",
    ]
    try:
        with path.open("a", encoding="utf-8") as fh:
            fh.write("\n".join(block) + "\n")
        return path
    except OSError:
        return None


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


def repo_zip(
    owner: str = GITHUB_OWNER, repo: str = GITHUB_REPO, branch: str = GITHUB_BRANCH
) -> bytes | None:
    """zip کل ریپو (بدون کلید API، بدون محدودیت درخواست)."""
    if not (owner and repo and branch):
        return None
    url = GITHUB_ZIP.format(owner=owner, repo=repo, branch=branch)
    return _http_get_bytes(url, timeout=40)


def ensure_codes_dir() -> Path:
    """پوشه CODES روی دسکتاپ؛ اگر نبود ساخته می‌شود."""
    target = get_desktop_dir() / CODES_FOLDER_NAME
    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return target


def extract_py_files(zip_bytes: bytes) -> dict[str, bytes]:
    """فایل‌های پایتون سطح بالای مخزن: {نام فایل: محتوا}"""
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
                if "/" in inner or not inner.lower().endswith(".py"):
                    continue
                if inner.startswith("."):
                    continue
                result[inner] = zf.read(name)
    except (zipfile.BadZipFile, OSError):
        return {}
    return result


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
    """تنظیمات کاربر؛ مقادیر ذخیره‌شده روی پیش‌فرض‌ها سوار می‌شوند."""
    data = dict(DEFAULT_SETTINGS)
    try:
        import json

        raw = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            for key, default in DEFAULT_SETTINGS.items():
                value = raw.get(key, default)
                data[key] = value if isinstance(value, type(default)) else default
    except (OSError, ValueError, TypeError):
        pass
    return data


def save_settings(data: dict) -> None:
    try:
        import json

        STATE_DIR.mkdir(parents=True, exist_ok=True)

        SETTINGS_FILE.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
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

        Path(CODES_STATE_FILE).parent.mkdir(parents=True, exist_ok=True)
        Path(CODES_STATE_FILE).write_text(
            json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError:
        pass


def run_code_job(path: Path) -> tuple[bool, str, str]:
    """یک فایل پایتون را اجرا و نتیجه را در logs گوگل درایو ذخیره می‌کند.

    خروجی: (موفق بود؟، نام فایل، متن نتیجه)
    """
    started = time.time()
    dest_dir, _ = resolve_report_dir()
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        dest_dir = ensure_codes_dir()

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


# ============================================================ گرافیک pygame ===

import colorsys
import math

try:
    import pygame
except ImportError:  # run.bat نصبش می‌کند
    pygame = None

# ------------------------------------------------------------ رنگ و سایه ---


def hex_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i: i + 2], 16) for i in (0, 2, 4))


def mix(a, b, t: float):
    """ترکیب دو رنگ."""
    ca, cb = hex_rgb(a) if isinstance(a, str) else a, hex_rgb(b) if isinstance(b, str) else b
    return tuple(int(ca[i] + (cb[i] - ca[i]) * t) for i in range(3))


def lighten(color, amount: float):
    c = hex_rgb(color) if isinstance(color, str) else color
    return tuple(min(255, int(v + (255 - v) * amount)) for v in c)


def darken(color, amount: float):
    c = hex_rgb(color) if isinstance(color, str) else color
    return tuple(max(0, int(v * (1 - amount))) for v in c)


def with_alpha(color, alpha: int):
    c = hex_rgb(color) if isinstance(color, str) else color
    return (c[0], c[1], c[2], max(0, min(255, alpha)))


# ------------------------------------------------------------ متن فارسی ---

try:
    import re

    import arabic_reshaper
    from bidi.algorithm import get_display

    _RESHAPER = arabic_reshaper.ArabicReshaper(
        configuration={"delete_harakat": False, "support_ligatures": True}
    )

    # اعداد و کلمات لاتین باید چپ‌به‌راست بمانند (ساعت، نسخه، لینک)
    _LTR_RUN = re.compile(
        r"([A-Za-z0-9\u06F0-\u06F9\u0660-\u0669][A-Za-z0-9\u06F0-\u06F9\u0660-\u0669:/._\-+%#@?=&]*)"
    )

    def shape_text(text: str) -> str:
        """چسباندن حروف فارسی، ترتیب راست‌به‌چپ، و نگه‌داشتن اعداد/لاتین."""
        try:
            guarded = _LTR_RUN.sub("\u202a" + r"\1" + "\u202c", text)
            return get_display(_RESHAPER.reshape(guarded))
        except Exception:
            return text

except Exception:  # اگر کتابخانه نبود، متن خام نمایش داده می‌شود

    def shape_text(text: str) -> str:
        return text


class Fonts:
    """مدیریت فونت‌های وزیرمتن با کش."""

    def __init__(self) -> None:
        self.dir = LOCAL_BASE_DIR / "assets" / "fonts"
        self.cache: dict[tuple[int, bool], "pygame.font.Font"] = {}
        self.shape_cache: dict[str, str] = {}

    def _path(self, bold: bool):
        name = "Vazirmatn-Bold.ttf" if bold else "Vazirmatn-Regular.ttf"
        candidate = self.dir / name
        return candidate if candidate.is_file() else None

    def get(self, size: int, bold: bool = False):
        key = (size, bold)
        if key not in self.cache:
            path = self._path(bold)
            if path:
                self.cache[key] = pygame.font.Font(str(path), size)
            else:
                self.cache[key] = pygame.font.SysFont("tahoma,arial", size, bold=bold)
        return self.cache[key]

    def shaped(self, text: str) -> str:
        if text not in self.shape_cache:
            if len(self.shape_cache) > 800:
                self.shape_cache.clear()
            self.shape_cache[text] = shape_text(text)
        return self.shape_cache[text]

    def render(self, text: str, size: int, color, bold: bool = False):
        return self.get(size, bold).render(self.shaped(text), True, color)

    def width(self, text: str, size: int, bold: bool = False) -> int:
        return self.get(size, bold).size(self.shaped(text))[0]

    def wrap(self, text: str, size: int, max_width: int, bold: bool = False) -> list[str]:
        """شکستن متن به سطرهای جا‌شده در عرض مشخص."""
        words = text.split(" ")
        lines: list[str] = []
        current = ""
        for word in words:
            trial = f"{current} {word}".strip()
            if self.width(trial, size, bold) <= max_width or not current:
                current = trial
            else:
                lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines or [""]


# --------------------------------------------------------------- صدا ---


class Sounds:
    """افکت‌های صوتی؛ اگر دستگاه صدا نبود، برنامه بدون صدا کار می‌کند."""

    NAMES = ("click", "toggle", "open", "run", "success", "error", "shutter", "tick", "notify")

    def __init__(self, muted: bool = False) -> None:
        self.enabled = False
        self.muted = muted
        self.bank: dict[str, "pygame.mixer.Sound"] = {}
        try:
            pygame.mixer.pre_init(44100, -16, 1, 512)
            pygame.mixer.init()
            self.enabled = True
        except Exception:
            return

        folder = LOCAL_BASE_DIR / "assets" / "sounds"
        for name in self.NAMES:
            path = folder / f"{name}.wav"
            if path.is_file():
                try:
                    sound = pygame.mixer.Sound(str(path))
                    sound.set_volume(0.55)
                    self.bank[name] = sound
                except Exception:
                    pass

    def play(self, name: str) -> None:
        if not self.enabled or self.muted:
            return
        sound = self.bank.get(name)
        if sound:
            try:
                sound.play()
            except Exception:
                pass

    def toggle_mute(self) -> bool:
        self.muted = not self.muted
        return self.muted


# ------------------------------------------------------------- شکل‌ها ---


def rounded(surface, rect, radius, color, width: int = 0) -> None:
    pygame.draw.rect(surface, color, rect, width=width, border_radius=int(radius))


def shadow(surface, rect, radius, spread: int = 10, alpha: int = 55) -> None:
    """سایه نرم زیر کارت (چند لایه با شفافیت کم)."""
    layer = pygame.Surface((rect.width + spread * 2, rect.height + spread * 2), pygame.SRCALPHA)
    for i in range(spread, 0, -2):
        a = int(alpha * (1 - i / spread) ** 1.4)
        if a <= 0:
            continue
        box = pygame.Rect(spread - i, spread - i + 3, rect.width + i * 2, rect.height + i * 2)
        pygame.draw.rect(layer, (0, 0, 0, a), box, border_radius=int(radius + i))
    surface.blit(layer, (rect.x - spread, rect.y - spread))


def gradient_rect(size, color_a, color_b) -> "pygame.Surface":
    """مستطیل با گرادیان عمودی."""
    w, h = size
    surf = pygame.Surface((w, h))
    ca, cb = hex_rgb(color_a), hex_rgb(color_b)
    for y in range(h):
        t = y / max(1, h - 1)
        pygame.draw.line(surf, mix(ca, cb, t), (0, y), (w, y))
    return surf


def draw_ring(
    surface,
    center,
    radius: int,
    progress: float,
    color,
    track_color,
    width: int = 6,
    start: float = 90.0,
) -> None:
    """حلقه شمارش معکوس."""
    box = pygame.Rect(0, 0, radius * 2, radius * 2)
    box.center = center
    pygame.draw.circle(surface, track_color, center, radius, width)
    progress = max(0.0, min(1.0, progress))
    if progress <= 0.001:
        return
    steps = max(3, int(72 * progress))
    for i in range(steps):
        a0 = math.radians(start - 360 * progress * i / steps)
        a1 = math.radians(start - 360 * progress * (i + 1) / steps)
        p0 = (center[0] + radius * math.cos(a0), center[1] - radius * math.sin(a0))
        p1 = (center[0] + radius * math.cos(a1), center[1] - radius * math.sin(a1))
        pygame.draw.line(surface, color, p0, p1, width)
    angle = math.radians(start - 360 * progress)
    tip = (center[0] + radius * math.cos(angle), center[1] - radius * math.sin(angle))
    pygame.draw.circle(surface, color, tip, max(2, width // 2 + 1))


def draw_spinner(surface, center, radius: int, angle: float, color, width: int = 4) -> None:
    """نشانگر چرخان برای کارهای در حال انجام."""
    steps = 24
    for i in range(steps):
        a0 = math.radians(angle - 300 * i / steps)
        a1 = math.radians(angle - 300 * (i + 1) / steps)
        alpha = 1 - i / steps
        base = hex_rgb(color) if isinstance(color, str) else color
        col = mix(base, (24, 24, 20), 1 - alpha)
        p0 = (center[0] + radius * math.cos(a0), center[1] - radius * math.sin(a0))
        p1 = (center[0] + radius * math.cos(a1), center[1] - radius * math.sin(a1))
        pygame.draw.line(surface, col, p0, p1, width)
# ============================================================== رابط کاربری ===

WIN_W, WIN_H = 1060, 730
HEADER_H = 88
TABS_H = 60
FOOTER_H = 48
PAD = 18

TABS = [
    ("main", "عملیات"),
    ("collab", "ایجنت همکار"),
    ("codes", "کتابخانه کدها"),
    ("changes", "تغییرات"),
]


class App:
    """پنجره اصلی — همه اجزا با pygame کشیده می‌شوند."""

    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption(f"{APP_TITLE} — نسخه {APP_VERSION}")
        self.screen = pygame.display.set_mode((WIN_W, WIN_H), pygame.RESIZABLE)
        self.clock = pygame.time.Clock()
        self.fonts = Fonts()

        self.settings = load_settings()
        self.theme_name = self.settings.get("theme", "dark")
        if self.theme_name not in THEMES:
            self.theme_name = "dark"
        self.c = THEMES[self.theme_name]

        self.sounds = Sounds(muted=bool(self.settings.get("muted", False)))
        self.events: queue.Queue = queue.Queue()
        self.log_lines: list[str] = []

        self.running = True
        self.busy: str | None = None
        self.tab = "main"
        self.scroll = {key: 0.0 for key, _ in TABS}
        self.scroll_target = {key: 0.0 for key, _ in TABS}
        self.view_rect = pygame.Rect(0, 0, 0, 0)

        self.mouse = (-100, -100)
        self.hits: list[tuple[pygame.Rect, object]] = []
        self.modal: dict | None = None
        self.toast: dict | None = None
        self.focus_field = None
        self.caret_on = True
        self.caret_t = 0.0
        self.t0 = time.monotonic()

        self.switch_pos = 1.0 if self.settings.get("auto") else 0.0
        self.auto_next = 0.0
        self.auto_auto_armed = False

        self.status = {"internet": None, "drive": None, "repo": None, "collab": None}
        self.status_note = {"internet": "…", "drive": "…", "repo": "…", "collab": "…"}

        self.codes_index: list[dict] = []
        self.codes_loaded_at = 0.0
        self._last_version: str | None = None
        self._busy_started = 0.0
        self._spinner = 0.0

        ensure_codes_dir()
        self._scan_codes()
        self.log(f"به {APP_TITLE} خوش آمدید — نسخه {to_fa(APP_VERSION)}")
        self.log(f"پوشه کدها: {get_desktop_dir() / CODES_FOLDER_NAME}")
        self.log("حالت دستی — هیچ کاری بدون اجازه تو انجام نمی‌شود.")
        self._start_status_monitor()
        if self.settings.get("auto"):
            self._arm_auto()

    # ----------------------------------------------------------- کمکی‌ها ---

    def c_(self, key: str):
        """رنگ از کلید تم یا کد رنگ مستقیم."""
        if isinstance(key, str) and key.startswith("#"):
            return hex_rgb(key)
        return hex_rgb(self.c[key])

    def log(self, message: str) -> None:
        stamp = f"{tehran_now():%H:%M:%S}"
        for line in str(message).splitlines() or [""]:
            self.log_lines.append(f"{stamp}  {line}")
        del self.log_lines[:-500]

    def post(self, fn) -> None:
        """اجرای کار در ترد رابط کاربری."""
        self.events.put(fn)

    def toast_msg(self, text: str, kind: str = "ok") -> None:
        self.toast = {"text": text, "kind": kind, "until": time.monotonic() + 3.5}

    def report_error(self, context: str, detail: str = "") -> None:
        path = write_error(context, detail)
        self.log(f"🗂 خطا ذخیره شد: {path.name}" if path else "⚠️ ذخیره خطا ممکن نشد.")
        if path:
            self.toast_msg("خطا در logs/errors ذخیره شد", "error")
        else:
            self.toast_msg("خطا ثبت شد", "error")

    def hit(self, rect, callback) -> None:
        self.hits.append((pygame.Rect(rect), callback))

    def hover(self, rect) -> bool:
        return pygame.Rect(rect).collidepoint(self.mouse)

    # ------------------------------------------------------- متن‌نویسی ---

    def text(self, value, pos, size=13, color=None, bold=False, align="right", valign="top"):
        color = self.c_(color) if isinstance(color, str) else (color or self.c_("text"))
        surf = self.fonts.render(str(value), size, color, bold)
        rect = surf.get_rect()
        x, y = pos
        if align == "right":
            rect.topright = (x, y)
        elif align == "center":
            rect.midtop = (x, y)
        else:
            rect.topleft = (x, y)
        if valign == "center":
            rect.y = y - rect.h // 2
        elif valign == "bottom":
            rect.bottom = y
        self.screen.blit(surf, rect)
        return rect

    def paragraph(self, value, rect, size=11, color=None, bold=False, gap=6) -> int:
        """متن چندخطی راست‌چین؛ ارتفاع مصرف‌شده را برمی‌گرداند."""
        lines: list[str] = []
        for raw in str(value).split("\n"):
            if not raw.strip():
                lines.append("")
            else:
                lines.extend(self.fonts.wrap(raw, size, rect.width, bold))
        y = rect.top
        for line in lines:
            if line:
                self.text(line, (rect.right, y), size, color, bold, align="right")
            y += self.fonts.get(size, bold).get_height() + gap - 4
        return y - rect.top

    def ellipsis(self, value: str, size: int, max_width: int, bold: bool = False) -> str:
        if self.fonts.width(value, size, bold) <= max_width:
            return value
        cut = value
        while cut and self.fonts.width(cut + "…", size, bold) > max_width:
            cut = cut[:-1]
        return cut + "…"

    # ------------------------------------------------------------ ویجت‌ها ---

    def card(self, rect, radius=16, fill=None, border=True, elevate=True) -> pygame.Rect:
        rect = pygame.Rect(rect)
        if elevate:
            shadow(self.screen, rect, radius, spread=12, alpha=42 if self.theme_name == "dark" else 26)
        rounded(self.screen, rect, radius, hex_rgb(fill or self.c["surface"]))
        if border:
            rounded(self.screen, rect, radius, self.c_("border"), width=1)
        return rect

    def button(
        self,
        rect,
        label,
        on_click,
        *,
        kind="secondary",
        icon=None,
        size=13,
        bold=True,
        enabled=True,
        radius=12,
        sub=None,
    ):
        rect = pygame.Rect(rect)
        hovered = enabled and self.hover(rect)

        if kind == "primary":
            base = self.c_("accent")
            bg = lighten(base, 0.08) if hovered else base
            fg = self.c_("bg") if self.theme_name == "dark" else (255, 255, 255)
            bd = None
        elif kind == "danger":
            bg = self.c_("danger_soft") if hovered else self.c_("surface2")
            fg = self.c_("danger")
            bd = self.c_("danger")
        elif kind == "ghost":
            bg = self.c_("surface2") if hovered else None
            fg = self.c_("text") if hovered else self.c_("text_dim")
            bd = None
        else:  # secondary
            bg = self.c_("surface2") if not hovered else lighten(self.c_("surface2"), 0.07)
            fg = self.c_("text")
            bd = self.c_("border_strong")

        if not enabled:
            bg = self.c_("surface2")
            fg = self.c_("text_dim")

        if bg is not None:
            rounded(self.screen, rect, radius, bg)
        if bd is not None:
            rounded(self.screen, rect, radius, bd, width=1)

        icon_w = 0
        if icon:
            icon_w = self.icon(icon, rect.x + 16, rect.centery, 11, fg, align="left")
        label_room = rect.width - 28 - icon_w
        shown = self.ellipsis(label, size, label_room, bold)
        sub_color = mix(self.c["accent"], self.c["bg"], 0.5) if kind == "primary" else self.c_("text_dim")
        if sub:
            self.text(shown, (rect.right - 16, rect.centery - 10), size, fg, bold, align="right")
            self.text(
                self.ellipsis(sub, 10, label_room, False),
                (rect.right - 16, rect.centery + 7),
                10, sub_color, align="right",
            )
        else:
            self.text(shown, (rect.right - 16, rect.centery), size, fg, bold, align="right", valign="center")

        if enabled and on_click:
            self.hit(rect, lambda: (self.sounds.play("click"), on_click()))
        return rect

    def icon(self, name, x, y, size, color, align="left") -> int:
        """آیکون‌های برداری ساده."""
        col = hex_rgb(color) if isinstance(color, str) else color
        if align == "right":
            x -= size
        if name == "camera":
            body = pygame.Rect(x, y - size * 0.6, size * 2, size * 1.25)
            rounded(self.screen, body, 3, col, width=max(1, size // 6))
            pygame.draw.rect(self.screen, col, (x + size * 0.55, y - size * 0.95, size * 0.6, size * 0.4))
            pygame.draw.circle(self.screen, col, (int(x + size), int(y)), int(size * 0.42), max(1, size // 6))
            return int(size * 2)
        if name == "list":
            for i in range(3):
                top = y - size * 0.7 + i * size * 0.7
                pygame.draw.circle(self.screen, col, (int(x + size * 0.25), int(top + size * 0.22)), 2)
                pygame.draw.line(
                    self.screen, col, (x + size * 0.6, top + size * 0.22),
                    (x + size * 1.9, top + size * 0.22), max(1, size // 7),
                )
            return int(size * 2)
        if name == "play":
            pygame.draw.polygon(
                self.screen, col,
                [(x, y - size * 0.75), (x, y + size * 0.75), (x + size * 1.3, y)],
            )
            return int(size * 1.3)
        if name == "download":
            pygame.draw.line(self.screen, col, (x + size * 0.6, y - size * 0.8), (x + size * 0.6, y + size * 0.4), max(2, size // 5))
            pygame.draw.polygon(
                self.screen, col,
                [
                    (x + size * 0.15, y + size * 0.15),
                    (x + size * 1.05, y + size * 0.15),
                    (x + size * 0.6, y + size * 0.85),
                ],
            )
            pygame.draw.line(self.screen, col, (x, y + size * 1.1), (x + size * 1.2, y + size * 1.1), max(2, size // 5))
            return int(size * 1.3)
        if name == "refresh":
            pygame.draw.circle(self.screen, col, (int(x + size * 0.7), int(y)), int(size * 0.7), max(2, size // 5))
            pygame.draw.polygon(
                self.screen, col,
                [
                    (x + size * 0.85, y - size * 0.95),
                    (x + size * 1.55, y - size * 0.55),
                    (x + size * 0.85, y - size * 0.15),
                ],
            )
            return int(size * 1.6)
        if name == "sound":
            pygame.draw.polygon(
                self.screen, col,
                [(x, y - size * 0.35), (x + size * 0.35, y - size * 0.35),
                 (x + size * 0.85, y - size * 0.8), (x + size * 0.85, y + size * 0.8),
                 (x + size * 0.35, y + size * 0.35), (x, y + size * 0.35)],
            )
            return int(size * 0.9)
        if name == "mute":
            pygame.draw.polygon(
                self.screen, col,
                [(x, y - size * 0.35), (x + size * 0.35, y - size * 0.35),
                 (x + size * 0.85, y - size * 0.8), (x + size * 0.85, y + size * 0.8),
                 (x + size * 0.35, y + size * 0.35), (x, y + size * 0.35)],
            )
            pygame.draw.line(self.screen, col, (x + size * 1.1, y - size * 0.4), (x + size * 1.7, y + size * 0.4), 2)
            pygame.draw.line(self.screen, col, (x + size * 1.7, y - size * 0.4), (x + size * 1.1, y + size * 0.4), 2)
            return int(size * 1.8)
        if name == "sun":
            pygame.draw.circle(self.screen, col, (int(x + size * 0.6), int(y)), int(size * 0.42))
            for i in range(8):
                a = math.radians(i * 45)
                p0 = (x + size * 0.6 + math.cos(a) * size * 0.62, y + math.sin(a) * size * 0.62)
                p1 = (x + size * 0.6 + math.cos(a) * size * 0.85, y + math.sin(a) * size * 0.85)
                pygame.draw.line(self.screen, col, p0, p1, 2)
            return int(size * 1.5)
        if name == "moon":
            pygame.draw.circle(self.screen, col, (int(x + size * 0.65), int(y)), int(size * 0.62), 2)
            pygame.draw.circle(self.screen, self.c_("surface"), (int(x + size * 0.95), int(y - size * 0.2)), int(size * 0.55))
            return int(size * 1.5)
        if name == "check":
            pygame.draw.lines(
                self.screen, col, False,
                [(x, y), (x + size * 0.4, y + size * 0.45), (x + size * 1.1, y - size * 0.5)],
                max(2, size // 4),
            )
            return int(size * 1.2)
        if name == "x":
            pygame.draw.line(self.screen, col, (x, y - size * 0.5), (x + size, y + size * 0.5), 2)
            pygame.draw.line(self.screen, col, (x + size, y - size * 0.5), (x, y + size * 0.5), 2)
            return int(size)
        return 0

    def chip(self, x, y, label, active=False, color=None, size=11) -> int:
        """چیپ گرد؛ عرض مصرف‌شده را برمی‌گرداند."""
        w = self.fonts.width(label, size, True) + 22
        rect = pygame.Rect(0, 0, w, 24)
        rect.topleft = (x, y)
        col = self.c_(color) if color else self.c_("accent")
        bg = mix(self.c["surface2"], col, 0.22) if active else self.c_("surface2")
        bd = mix(self.c["border_strong"], col, 0.55) if active else self.c_("border")
        rounded(self.screen, rect, 12, bg)
        rounded(self.screen, rect, 12, bd, width=1)
        self.text(label, (rect.centerx, rect.top + 5), size, col if active else self.c_("text_dim"), True, align="center")
        return w

    def status_dot(self, x, y, kind: str, label: str, note: str) -> None:
        """چراغ وضعیت با برچسب."""
        colors = {
            "ok": self.c_("ok"),
            "bad": self.c_("danger"),
            "wait": self.c_("border_strong"),
        }
        col = colors.get(kind, self.c_("border_strong"))
        pygame.draw.circle(self.screen, mix(self.c["surface"], col, 0.35), (x, y), 7)
        pygame.draw.circle(self.screen, col, (x, y), 4)
        self.text(label, (x + 12, y), 10, self.c_("text_dim"), True, align="left", valign="center")
        w = self.fonts.width(label, 10, True)
        self.text(note, (x + 16 + w, y), 9, col if kind != "wait" else self.c_("text_dim"), align="left", valign="center")

    # ------------------------------------------------------------ هدر و تب‌ها ---

    def draw_header(self, w: int) -> None:
        c = self.c
        rect = pygame.Rect(0, 0, w, HEADER_H)
        pygame.draw.rect(self.screen, self.c_("surface"), rect)
        pygame.draw.line(self.screen, self.c_("border"), (0, HEADER_H - 1), (w, HEADER_H - 1))

        # لوگو
        logo = pygame.Rect(PAD, 18, 52, 52)
        grad = gradient_rect((52, 52), self.c["accent"], self.c["accent_strong"])
        mask = pygame.Surface((52, 52), pygame.SRCALPHA)
        pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=16)
        grad.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        self.screen.blit(grad, logo)
        self.text("WA", (logo.centerx, logo.top + 16), 16, "#ffffff" if self.theme_name == "light" else self.c_("bg"), True, align="center")

        # برند
        self.text(APP_TITLE, (logo.right + 12, 21), 17, self.c_("text"), True, align="left")
        self.text(
            f"نسخه {to_fa(APP_VERSION)}  ·  شناسه {build_info()['commit']}",
            (logo.right + 12, 46), 10, self.c_("text_dim"), align="left",
        )

        # ساعت و تاریخ
        now = tehran_now()
        jy, jm, jd = jalali_parts(now)
        clock_x = w - PAD - 224
        self.text(f"{to_fa(f'{now:%H:%M:%S}')}", (clock_x, 18), 22, self.c_("text"), True, align="left")
        self.text(
            f"{to_fa(str(jd))} {FA_MONTHS[jm - 1]} {to_fa(str(jy))}",
            (clock_x, 52), 11, self.c_("text_dim"), align="left",
        )

        # دکمه‌های گوشه
        mute_icon = "mute" if self.sounds.muted else "sound"
        self.icon_button(
            pygame.Rect(w - PAD - 96, 26, 36, 36), mute_icon, self.action_toggle_sound
        )
        theme_icon = "sun" if self.theme_name == "dark" else "moon"
        self.icon_button(
            pygame.Rect(w - PAD - 52, 26, 36, 36), theme_icon, self.action_toggle_theme
        )

    def icon_button(self, rect, icon, on_click, *, active=False) -> None:
        rect = pygame.Rect(rect)
        hovered = self.hover(rect)
        bg = self.c_("surface2") if not hovered else lighten(self.c_("surface2"), 0.09)
        rounded(self.screen, rect, 10, bg)
        rounded(self.screen, rect, 10, self.c_("border_strong"), width=1)
        col = self.c_("accent") if active else (self.c_("text") if hovered else self.c_("text_dim"))
        self.icon(icon, rect.centerx - 8, rect.centery, 9, col)
        self.hit(rect, lambda: (self.sounds.play("click"), on_click()))

    def draw_tabs(self, w: int) -> None:
        bar = pygame.Rect(0, HEADER_H, w, TABS_H)
        pygame.draw.rect(self.screen, self.c_("bg"), bar)

        pills = pygame.Rect(PAD, HEADER_H + 10, min(620, w - 2 * PAD), 40)
        rounded(self.screen, pills, 20, self.c_("surface2"))
        rounded(self.screen, pills, 20, self.c_("border"), width=1)

        self.tab_rects: dict[str, pygame.Rect] = {}
        gap = 4
        avail = pills.width - 10 - gap * (len(TABS) - 1)
        each = avail // len(TABS)
        x = pills.right - 5 - each
        for key, label in TABS:
            rect = pygame.Rect(x, pills.top + 5, each, pills.height - 10)
            active = key == self.tab
            hovered = self.hover(rect) and not active
            if active:
                rounded(self.screen, rect, 16, self.c_("accent"))
            elif hovered:
                rounded(self.screen, rect, 16, lighten(self.c_("surface2"), 0.06))
            fg = (self.c_("bg") if self.theme_name == "dark" else (255, 255, 255)) if active else (
                self.c_("text") if hovered else self.c_("text_dim")
            )
            self.text(label, (rect.centerx, rect.centery - 8), 12, fg, True, align="center")
            self.tab_rects[key] = rect
            self.hit(rect, lambda k=key: self.switch_tab(k))
            x -= each + gap

        # شمارنده کدهای اجرانشده داخل تب «کتابخانه کدها»
        pending = sum(1 for item in self.codes_index if not item["ran"])
        if pending and "codes" in self.tab_rects:
            tab_rect = self.tab_rects["codes"]
            badge = pygame.Rect(0, 0, 22, 18)
            badge.midright = (tab_rect.right - 6, tab_rect.centery)
            rounded(self.screen, badge, 9, self.c_("warn"))
            self.text(
                to_fa(str(pending)), (badge.centerx, badge.top + 2), 9,
                self.c_("bg"), True, align="center",
            )

    def draw_footer(self, w: int, h: int) -> None:
        rect = pygame.Rect(0, h - FOOTER_H, w, FOOTER_H)
        pygame.draw.rect(self.screen, self.c_("surface"), rect)
        pygame.draw.line(self.screen, self.c_("border"), (0, rect.top), (w, rect.top))

        y = rect.centery
        x = PAD + 4
        for key, label in (
            ("internet", "اینترنت"),
            ("drive", "گوگل درایو"),
            ("repo", "مخزن مادر"),
            ("collab", "مخزن همکار"),
        ):
            state = self.status.get(key)
            kind = "wait" if state is None else ("ok" if state else "bad")
            self.status_dot(x, y, kind, label, self.status_note.get(key, ""))
            x += 22 + self.fonts.width(label, 10, True) + 8 + self.fonts.width(self.status_note.get(key, ""), 9) + 26

        status_text = self.busy or ("حالت خودکار" if self.settings.get("auto") else "حالت دستی")
        self.text(status_text, (w - PAD, y), 10, self.c_("text_dim"), True, align="right", valign="center")

    # ---------------------------------------------------------- قاب محتوا ---

    def begin_content(self, w: int, h: int) -> int:
        """آماده‌سازی ناحیه اسکرول‌شونده؛ بالای محتوا را برمی‌گرداند."""
        self.view_rect = pygame.Rect(
            PAD, HEADER_H + TABS_H, w - 2 * PAD, h - HEADER_H - TABS_H - FOOTER_H
        )
        self.screen.set_clip(self.view_rect)
        offset = self.scroll[self.tab]
        return int(self.view_rect.top + 4 - offset)

    def end_content(self, content_height: int) -> None:
        self.screen.set_clip(None)
        visible = self.view_rect.height - 8
        max_scroll = max(0, content_height - visible)
        self.scroll[self.tab] = max(0.0, min(self.scroll[self.tab], max_scroll))
        self.scroll_target[self.tab] = self.scroll[self.tab]

        # نوار اسکرول باریک
        if max_scroll > 0:
            track = pygame.Rect(self.view_rect.right - 3, self.view_rect.top + 4, 4, visible)
            rounded(self.screen, track, 2, self.c_("surface2"))
            frac = visible / (content_height or 1)
            h_thumb = max(30, int(visible * frac))
            pos = self.scroll[self.tab] / max_scroll if max_scroll else 0
            thumb = pygame.Rect(track.x, int(track.top + (track.height - h_thumb) * pos), 4, h_thumb)
            rounded(self.screen, thumb, 2, self.c_("border_strong"))

    # -------------------------------------------------------------- تب‌ها ---

    def draw(self) -> None:
        w, h = self.screen.get_size()
        self.hits = []
        self.screen.fill(self.c_("bg"))

        self.draw_header(w)
        self.draw_tabs(w)

        top = self.begin_content(w, h)
        height = getattr(self, f"draw_{self.tab}")(self.view_rect, top)
        self.end_content(height)

        self.draw_footer(w, h)
        if self.toast:
            self.draw_toast(w)
        if self.modal:
            self.draw_modal(w, h)

    # -------------------------------------------------------- تب «عملیات» ---

    def draw_main(self, view, top) -> int:
        w = view.width
        y = top

        # --- کارت حالت خودکار ---
        card = pygame.Rect(view.left, y, w, 104 if self.settings.get("auto") else 92)
        self.card(card)
        self.text("حالت اجرا", (card.right - 18, card.top + 16), 13, self.c_("text"), True)
        self.text(
            "خودکار" if self.settings.get("auto") else "دستی",
            (card.right - 18, card.top + 40), 22,
            self.c_("accent") if self.settings.get("auto") else self.c_("text_dim"), True,
        )
        hint = (
            "هر ۱۰ ثانیه مخزن همکار بررسی می‌شود؛ کد تازه خودکار دانلود و اجرا می‌شود."
            if self.settings.get("auto")
            else "هیچ کاری بدون اجازه‌ی تو انجام نمی‌شود؛ برای هر مرحله تأیید می‌گیرد."
        )
        self.text(
            self.ellipsis(hint, 10, card.width - 330),
            (card.right - 18, card.top + 68 if self.settings.get("auto") else card.top + 66),
            10, self.c_("text_dim"),
        )

        self.switch(
            pygame.Rect(card.right - 300, card.centery - 16, 64, 32),
            self.settings.get("auto"),
            self.action_toggle_auto,
        )

        # تایمر دایره‌ای
        if self.settings.get("auto"):
            remaining = max(0.0, self.auto_next - time.monotonic())
            progress = 1 - remaining / max(1, SYNC_POLL_SECONDS)
            center = (card.left + 58, card.centery)
            draw_ring(
                self.screen, center, 30, progress,
                self.c_("accent") if remaining > 3 else self.c_("warn"),
                self.c_("surface2"), width=5,
            )
            if self.busy:
                draw_spinner(self.screen, center, 15, self._spinner, self.c_("accent"))
            else:
                self.text(
                    to_fa(str(int(math.ceil(remaining)))),
                    (center[0], center[1] - 10), 18, self.c_("text"), True, align="center",
                )
                self.text("ثانیه", (center[0], center[1] + 14), 9, self.c_("text_dim"), align="center")
        y += card.height + 12

        # --- کارت دکمه‌های اصلی ---
        card = pygame.Rect(view.left, y, w, 96)
        self.card(card)
        half = (card.width - 36 - 12) // 2
        self.button(
            pygame.Rect(card.right - 18 - half, card.top + 16, half, 64),
            "گرفتن اسکرین‌شات",
            self.action_capture,
            kind="primary", icon="camera", size=14,
            sub=f"باز کردن {LMARENA_URL.replace('https://www.', '')} و عکس پس از ۵ ثانیه",
        )
        self.button(
            pygame.Rect(card.left + 18, card.top + 16, half, 64),
            "گزارش برنامه‌های باز",
            self.action_report,
            icon="list", size=14,
            sub="فهرست پنجره‌های باز ویندوز در logs",
        )
        y += card.height + 12

        # --- کارت لاگ ---
        remain = max(180, view.bottom - y - 10)
        card = pygame.Rect(view.left, y, w, remain)
        self.card(card)
        self.text("گزارش زنده", (card.right - 18, card.top + 14), 12, self.c_("text"), True)
        self.text(
            to_fa(str(len(self.log_lines))) + " خط",
            (card.left + 18, card.top + 15), 10, self.c_("text_dim"), align="left",
        )
        self.draw_log(pygame.Rect(card.left + 14, card.top + 42, card.width - 28, card.height - 56))
        return y + card.height + 10

    def draw_log(self, rect) -> None:
        inner = rect.inflate(-16, -12)
        rounded(self.screen, rect, 12, self.c_("surface2"))
        rounded(self.screen, rect, 12, self.c_("border"), width=1)

        size = 10
        line_h = self.fonts.get(size).get_height() + 2
        wrapped: list[tuple[str, tuple]] = []
        for line in self.log_lines[-120:]:
            color = self.c_("text")
            if "❌" in line or "خطا" in line or "⚠️" in line:
                color = self.c_("danger")
            elif "✅" in line or "📥" in line or "🎉" in line:
                color = self.c_("ok")
            elif "▶️" in line:
                color = self.c_("accent")
            for piece in self.fonts.wrap(line, size, inner.width):
                wrapped.append((piece, color))

        room = max(1, inner.height // line_h)
        start = max(0, len(wrapped) - room)
        self.screen.set_clip(rect.inflate(0, -6))
        yy = inner.top
        for piece, color in wrapped[start:]:
            self.text(piece, (inner.right, yy), size, color, align="right")
            yy += line_h

    # -------------------------------------------------- تب «ایجنت همکار» ---

    def draw_collab(self, view, top) -> int:
        y = top
        y = self.draw_repo_card(view, y, "mother", "مخزن ایجنت مادر", "نسخه تازه‌ی خود برنامه از این مخزن گرفته می‌شود.")
        y = self.draw_repo_card(view, y, "collab", "مخزن ایجنت همکار", "فایل‌های پایتون این مخزن در CODES ذخیره و اجرا می‌شوند.")

        card = pygame.Rect(view.left, y, view.width, 82)
        self.card(card)
        self.button(
            pygame.Rect(card.right - 18 - 170, card.top + 18, 170, 46),
            "بررسی مخزن همکار", self.action_check_collab,
            kind="primary", icon="download", size=12,
        )
        self.button(
            pygame.Rect(card.right - 18 - 170 - 12 - 170, card.top + 18, 170, 46),
            "اجرای کدهای جدید", self.action_run_new,
            icon="play", size=12,
        )
        info = f"حالت {'خودکار' if self.settings.get('auto') else 'دستی'}"
        if self.busy:
            info = self.busy
        self.text(info, (card.left + 18, card.top + 26), 11, self.c_("text_dim"), align="left")
        pending = sum(1 for item in self.codes_index if not item["ran"])
        self.text(
            f"{to_fa(str(pending))} کد اجرانشده",
            (card.left + 18, card.top + 46), 10, self.c_("warn") if pending else self.c_("text_dim"), align="left",
        )
        y += card.height + 12

        card = pygame.Rect(view.left, y, view.width, 196)
        self.card(card)
        self.text("چطور کار می‌کند", (card.right - 18, card.top + 14), 12, self.c_("text"), True)
        steps = [
            "۱) ایجنت همکار فایل .py را در مخزن خودش می‌گذارد.",
            "۲) دکمه «بررسی مخزن همکار» فایل‌ها را در پوشه CODES روی دسکتاپ می‌گذارد.",
            "۳) دکمه «اجرای کدهای جدید» آن‌ها را اجرا و نتیجه را در logs گوگل درایو می‌نویسد.",
            "۴) هر کدی که قبلاً اجرا شده، در تب «کتابخانه کدها» با دکمه پخش دوباره قابل اجراست.",
        ]
        yy = card.top + 44
        for step in steps:
            self.text(self.ellipsis(step, 11, card.width - 60), (card.right - 18, yy), 11, self.c_("text_dim"))
            yy += 26
        return y + card.height + 10

    def draw_repo_card(self, view, y: int, prefix: str, title: str, hint: str) -> int:
        card = pygame.Rect(view.left, y, view.width, 158)
        self.card(card)
        self.text(title, (card.right - 18, card.top + 14), 12, self.c_("text"), True)
        self.text(self.ellipsis(hint, 9, card.width - 60), (card.right - 18, card.top + 36), 9, self.c_("text_dim"))
        self.button(
            pygame.Rect(card.left + 18, card.bottom - 52, 92, 34),
            "ذخیره", lambda p=prefix: self.action_save_repo(p),
            size=11,
        )
        labels = (("owner", "مالک"), ("repo", "مخزن"), ("branch", "شاخه"))
        x = card.right - 18
        widths = (160, 170, 240)
        for (key, label), fw in zip(labels, widths):
            x -= fw + 10
            field = pygame.Rect(x, card.top + 84, fw, 34)
            self.text(label, (field.right, card.top + 66), 9, self.c_("text_dim"))
            self.input_field(field, f"{prefix}_{key}")
        return y + card.height + 12

    # -------------------------------------------------- تب «کتابخانه کدها» ---

    def draw_codes(self, view, top) -> int:
        y = top
        card = pygame.Rect(view.left, y, view.width, 72)
        self.card(card)
        self.text("کتابخانه کدها", (card.right - 18, card.top + 14), 13, self.c_("text"), True)
        self.text(
            f"پوشه: {get_desktop_dir() / CODES_FOLDER_NAME}",
            (card.right - 18, card.top + 38), 9, self.c_("text_dim"),
        )
        self.button(
            pygame.Rect(card.left + 18, card.top + 18, 120, 36),
            "به‌روزرسانی", self.action_scan_codes, icon="refresh", size=11,
        )
        self.text(
            to_fa(str(len(self.codes_index))) + " فایل",
            (card.left + 150, card.top + 30), 10, self.c_("text_dim"), align="left",
        )
        y += card.height + 12

        if not self.codes_index:
            card = pygame.Rect(view.left, y, view.width, 150)
            self.card(card)
            self.text("هنوز کدی در پوشه CODES نیست", (card.centerx, card.top + 46), 13, self.c_("text_dim"), True, align="center")
            self.text(
                "از تب «ایجنت همکار» دکمه بررسی مخزن را بزنید.",
                (card.centerx, card.top + 76), 11, self.c_("text_dim"), align="center",
            )
            return y + card.height + 10

        for item in self.codes_index:
            card = pygame.Rect(view.left, y, view.width, 76)
            hovered = self.hover(card)
            self.card(card, fill=self.c["surface"] if not hovered else lighten(self.c["surface"], 0.03))
            accent = self.c_("ok") if item["ok"] else (self.c_("danger") if item["ok"] is False else self.c_("border_strong"))
            rounded(self.screen, pygame.Rect(card.right - 4, card.top + 14, 4, card.height - 28), 2, accent)

            # دکمه پخش
            play_rect = pygame.Rect(card.left + 16, card.centery - 19, 38, 38)
            self.play_button(play_rect, lambda p=item["path"]: self.action_run_single(p))

            self.text(self.ellipsis(item["name"], 12, card.width - 260), (card.right - 20, card.top + 14), 12, self.c_("text"), True)
            meta = item["meta"]
            self.text(self.ellipsis(meta, 9, card.width - 260), (card.right - 20, card.top + 40), 9, self.c_("text_dim"))
            chips_x = card.left + 74
            for label, color, active in item["chips"]:
                chips_x += self.chip(chips_x, card.top + 26, label, active=active, color=color) + 6
            y += card.height + 10
        return y + 6

    def play_button(self, rect, on_click) -> None:
        rect = pygame.Rect(rect)
        hovered = self.hover(rect)
        col = self.c_("accent") if not hovered else lighten(self.c_("accent"), 0.12)
        pygame.draw.circle(self.screen, mix(self.c["surface2"], col, 0.35), rect.center, rect.width // 2)
        pygame.draw.circle(self.screen, col, rect.center, rect.width // 2, 2)
        self.icon(
            "play", rect.centerx - 5, rect.centery, 7,
            self.c_("bg") if self.theme_name == "dark" else (255, 255, 255),
        )
        self.hit(rect, lambda: (self.sounds.play("click"), on_click()))

    # -------------------------------------------------------- تب «تغییرات» ---

    def draw_changes(self, view, top) -> int:
        lines: list[tuple[str, str, bool]] = []
        lines.append((f"نسخه در حال اجرا: {APP_VERSION}", "text", True))
        lines.append((f"ساخته‌شده: {build_info()['date']} — {build_info()['time']} تهران", "text_dim", False))
        lines.append(("", "text", False))
        for version, date, items in CHANGELOG:
            lines.append((f"نسخه {version} — {date}", "accent", True))
            for entry in items:
                lines.append((f"• {entry}", "text_dim", False))
            lines.append(("", "text", False))

        card = pygame.Rect(view.left, top, view.width, 60 + len(lines) * 24)
        self.card(card)
        yy = card.top + 18
        for txt, color, bold in lines:
            if txt:
                self.text(self.ellipsis(txt, 11, card.width - 50), (card.right - 20, yy), 11, self.c_(color), bold)
            yy += 24
        return card.bottom + 10

    # --------------------------------------------------------- کنترل‌ها ---

    def switch(self, rect, value: bool, on_click) -> None:
        rect = pygame.Rect(rect)
        self.switch_pos += ((1.0 if value else 0.0) - self.switch_pos) * 0.28
        on = self.switch_pos > 0.5
        track_col = mix(self.c["surface2"], self.c["accent"], self.switch_pos)
        rounded(self.screen, rect, rect.height // 2, track_col)
        rounded(self.screen, rect, rect.height // 2, self.c_("accent") if on else self.c_("border_strong"), width=1)
        pad = 4
        r = rect.height // 2 - pad
        cx = int(rect.left + pad + r + (rect.width - 2 * pad - 2 * r) * self.switch_pos)
        pygame.draw.circle(self.screen, self.c_("surface"), (cx, rect.centery), r)
        self.hit(rect, lambda: (self.sounds.play("toggle"), on_click()))

    def input_field(self, rect, key: str) -> None:
        rect = pygame.Rect(rect)
        if not hasattr(self, "field_values"):
            self.field_values = {}
        if key not in self.field_values:
            self.field_values[key] = str(self.settings.get(key, ""))
        focused = self.focus_field == key
        rounded(self.screen, rect, 10, self.c_("surface2"))
        rounded(
            self.screen, rect, 10,
            self.c_("accent") if focused else self.c_("border_strong"),
            width=2 if focused else 1,
        )
        value = self.field_values[key]
        shown = value if self.fonts.width(value, 10) < rect.width - 20 else "…" + value[-28:]
        self.text(shown, (rect.left + 10, rect.centery), 10, self.c_("text"), align="left", valign="center")
        if focused and self.caret_on:
            cx = rect.left + 12 + self.fonts.width(shown, 10)
            pygame.draw.line(self.screen, self.c_("accent"), (cx, rect.top + 8), (cx, rect.bottom - 8), 2)
        self.hit(rect, lambda: self.focus_on(key))

    def focus_on(self, key: str) -> None:
        self.focus_field = key
        self.sounds.play("click")

    # ------------------------------------------------------- رندر کمکی ---

    def draw_toast(self, w: int) -> None:
        toast = self.toast or {}
        remaining = toast.get("until", 0) - time.monotonic()
        if remaining <= 0:
            self.toast = None
            return
        alpha = int(255 * min(1.0, remaining / 0.6))
        color = self.c_("danger") if toast.get("kind") == "error" else self.c_("ok")
        width = min(w - 80, self.fonts.width(toast.get("text", ""), 11, True) + 60)
        rect = pygame.Rect(0, 0, width, 38)
        rect.midtop = (w // 2, HEADER_H + TABS_H + 8)
        layer = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(layer, with_alpha(self.c["surface"], alpha), layer.get_rect(), border_radius=12)
        pygame.draw.rect(layer, with_alpha(color, alpha), layer.get_rect(), width=1, border_radius=12)
        self.screen.blit(layer, rect)
        self.text(toast.get("text", ""), (rect.centerx, rect.centery - 7), 11, with_alpha(color, alpha), True, align="center")

    def draw_modal(self, w: int, h: int) -> None:
        veil = pygame.Surface((w, h), pygame.SRCALPHA)
        veil.fill((0, 0, 0, 130))
        self.screen.blit(veil, (0, 0))

        modal = self.modal or {}
        box = pygame.Rect(0, 0, min(560, w - 80), 250)
        box.center = (w // 2, h // 2)
        shadow(self.screen, box, 18, spread=16, alpha=90)
        rounded(self.screen, box, 18, self.c_("surface"))
        rounded(self.screen, box, 18, self.c_("border_strong"), width=1)

        self.text(modal.get("title", ""), (box.right - 24, box.top + 20), 14, self.c_("text"), True)
        text_rect = pygame.Rect(box.left + 24, box.top + 52, box.width - 48, box.height - 130)
        self.paragraph(modal.get("text", ""), text_rect, 11, self.c_("text_dim"))

        self.button(
            pygame.Rect(box.right - 24 - 130, box.bottom - 58, 130, 38),
            modal.get("yes_label", "بله"), self._modal_yes, kind="primary", size=12,
        )
        self.button(
            pygame.Rect(box.right - 24 - 130 - 12 - 110, box.bottom - 58, 110, 38),
            "انصراف", self._modal_no, size=12,
        )

    def modal_ask(self, title: str, message: str, on_yes) -> None:
        self.sounds.play("notify")
        self.modal = {"title": title, "text": message, "on_yes": on_yes}

    def _modal_yes(self) -> None:
        action = (self.modal or {}).get("on_yes")
        self.modal = None
        self.sounds.play("click")
        if action:
            action()

    def _modal_no(self) -> None:
        self.modal = None
        self.sounds.play("click")
        self.log("⏹ لغو شد.")

    # ------------------------------------------------------------- رفتار ---

    def collab_info(self) -> tuple[str, str, str]:
        return (
            self.settings.get("collab_owner", "").strip(),
            self.settings.get("collab_repo", "").strip(),
            self.settings.get("collab_branch", "").strip(),
        )

    def mother_info(self) -> tuple[str, str, str]:
        return (
            self.settings.get("mother_owner", "").strip(),
            self.settings.get("mother_repo", "").strip(),
            self.settings.get("mother_branch", "").strip(),
        )

    def collab_ready(self) -> bool:
        return all(self.collab_info())

    def switch_tab(self, key: str) -> None:
        if self.tab == key:
            return
        self.tab = key
        self.focus_field = None
        self.sounds.play("click")
        if key == "codes":
            self._scan_codes()

    def action_toggle_theme(self) -> None:
        self.theme_name = "light" if self.theme_name == "dark" else "dark"
        self.c = THEMES[self.theme_name]
        self.settings["theme"] = self.theme_name
        save_settings(self.settings)
        self.log(f"🎨 تم {'تاریک' if self.theme_name == 'dark' else 'روشن'} شد.")

    def action_toggle_sound(self) -> None:
        muted = self.sounds.toggle_mute()
        self.settings["muted"] = muted
        save_settings(self.settings)
        self.log("🔇 صدا خاموش شد." if muted else "🔊 صدا روشن شد.")
        if not muted:
            self.sounds.play("toggle")

    def action_toggle_auto(self) -> None:
        self.settings["auto"] = not self.settings.get("auto")
        save_settings(self.settings)
        if self.settings["auto"]:
            self.sounds.play("success")
            self.log("⚡ حالت خودکار روشن شد — بررسی و اجرا بدون پرسیدن.")
            self._arm_auto()
            self.toast_msg("حالت خودکار روشن شد")
        else:
            self.log("🔒 حالت دستی — هیچ کاری بدون اجازه تو انجام نمی‌شود.")
            self.toast_msg("حالت دستی شد")

    def _arm_auto(self) -> None:
        self.auto_next = time.monotonic() + SYNC_POLL_SECONDS

    # --------------------------------------------------------- دکمه‌ها ---

    def action_capture(self) -> None:
        if self.busy:
            return
        self.sounds.play("open")
        self._start_job("گرفتن اسکرین‌شات", self._job_capture)

    def action_report(self) -> None:
        if self.busy:
            return
        self.sounds.play("run")
        self._start_job("گرفتن گزارش", self._job_report)

    def action_scan_codes(self) -> None:
        self._scan_codes()
        self.sounds.play("click")
        self.toast_msg("فهرست کدها به‌روز شد")

    def action_check_collab(self) -> None:
        if self.busy:
            return
        if not self.collab_ready():
            self.toast_msg("اول مخزن همکار را تنظیم و ذخیره کن", "error")
            return
        self.sounds.play("download" if False else "open")
        self._start_job("بررسی مخزن همکار", lambda: self._job_fetch(manual=not self.settings["auto"]))

    def action_run_new(self) -> None:
        if self.busy:
            return
        self.sounds.play("run")
        self._start_job("اجرای کدهای جدید", lambda: self._job_run_new(manual=not self.settings["auto"]))

    def action_run_single(self, path: Path) -> None:
        if self.busy:
            return
        self.sounds.play("run")
        self.log(f"▶️ اجرای دوباره {path.name}")
        self._start_job(path.name, lambda: self._job_run_single(path))

    def action_save_repo(self, prefix: str) -> None:
        values = getattr(self, "field_values", {})
        owner = values.get(f"{prefix}_owner", "").strip()
        repo = values.get(f"{prefix}_repo", "").strip()
        branch = values.get(f"{prefix}_branch", "").strip()
        if "/" in owner:
            owner, _, rest = owner.partition("/")
            repo = repo or rest
        self.settings[f"{prefix}_owner"] = owner
        self.settings[f"{prefix}_repo"] = repo
        self.settings[f"{prefix}_branch"] = branch or "main"
        save_settings(self.settings)
        self.sounds.play("success")
        name = "مادر" if prefix == "mother" else "همکار"
        self.log(f"💾 مخزن {name} ذخیره شد: {owner}/{repo} @ {self.settings[f'{prefix}_branch']}")
        self.toast_msg("ذخیره شد")

    # ------------------------------------------------------------ کارها ---

    def _start_job(self, label: str, job) -> None:
        self.busy = label
        self._busy_started = time.monotonic()

        def runner() -> None:
            try:
                job()
            except Exception as exc:  # noqa: BLE001
                detail = traceback.format_exc()
                self.post(lambda d=detail, l=label, e=exc: self.report_error(f"خطا در «{l}»: {e}", d))
                self.post(lambda: self.sounds.play("error"))
            finally:
                self.post(self._end_job)

        threading.Thread(target=runner, daemon=True).start()

    def _end_job(self) -> None:
        self.busy = None
        self._scan_codes()
        if self.settings.get("auto"):
            self._arm_auto()

    def _job_capture(self) -> None:
        self.log(f"📸 باز کردن {LMARENA_URL} در کروم…")
        try:
            note = open_in_chrome(LMARENA_URL)
            self.log(f"   {note}")
        except Exception as exc:  # noqa: BLE001
            self.log(f"   ⚠️ {exc}")
        self.log(f"   صبر {PAGE_LOAD_SECONDS} ثانیه برای کامل شدن صفحه…")
        time.sleep(PAGE_LOAD_SECONDS)
        dest, on_drive = resolve_screenshot_dir()
        path = take_screenshot(dest)
        self.post(lambda: self.sounds.play("shutter"))
        where = "گوگل درایو" if on_drive else "دسکتاپ (درایو در دسترس نبود)"
        self.log(f"✅ اسکرین‌شات ذخیره شد → {path}")
        self.log(f"   محل: {where}")
        self.post(lambda: self.toast_msg("اسکرین‌شات گرفته شد"))

    def _job_report(self) -> None:
        self.log("📋 خواندن فهرست پنجره‌های باز…")
        windows = collect_open_windows()
        report = format_windows_report(windows)
        dest, on_drive = resolve_report_dir()
        path = save_report(report, dest)
        self.log(f"✅ گزارش ذخیره شد ({len(windows)} پنجره) → {path.name}")
        if not on_drive:
            self.log("   ⚠️ گوگل درایو در دسترس نبود؛ روی دسکتاپ ذخیره شد.")
        self.post(lambda: self.sounds.play("success"))
        self.post(lambda: self.toast_msg("گزارش ذخیره شد"))

    def _job_fetch(self, manual: bool) -> None:
        owner, repo, branch = self.collab_info()
        self.log(f"📥 بررسی {owner}/{repo} @ {branch}")
        data = repo_zip(owner, repo, branch)
        if not data:
            self.post(lambda: self._set_status("collab", False, "قطع"))
            self.log(f"❌ دریافت از {owner}/{repo} ممکن نشد.")
            self.post(lambda: self.sounds.play("error"))
            self.post(lambda: self.report_error(
                "دریافت مخزن ایجنت همکار ممکن نشد",
                f"آدرس: {owner}/{repo} @ {branch}\n"
                "احتمال: قطع بودن اینترنت، فیلتر بودن گیت‌هاب، یا اشتباه بودن نام مخزن/شاخه.",
            ))
            return

        files = extract_py_files(data)
        self.post(lambda: self._set_status("collab", True, f"{len(files)} فایل"))
        if not files:
            self.log("📭 در مخزن همکار هیچ فایل پایتونی نیست.")
            self.post(lambda: self.toast_msg("فایل پایتونی پیدا نشد", "error"))
            return

        codes_dir = ensure_codes_dir()
        new_files: dict[str, bytes] = {}
        for name, content in files.items():
            target = codes_dir / name
            try:
                if target.exists() and target.read_bytes() == content:
                    continue
            except OSError:
                pass
            new_files[name] = content

        if not new_files:
            self.log("✅ فایل جدیدی نبود — پوشه CODES به‌روز است.")
            self.post(lambda: self.toast_msg("پوشه CODES به‌روز است"))
            return

        self.log(f"🆕 {len(new_files)} فایل تازه: {', '.join(sorted(new_files))}")

        def deliver() -> None:
            written = 0
            for name, content in new_files.items():
                try:
                    (codes_dir / name).write_bytes(content)
                    written += 1
                except OSError as exc:
                    self.log(f"⚠️ نوشتن {name} ممکن نشد: {exc}")
            self.log(f"📥 {written} فایل در پوشه CODES ذخیره شد.")
            self.post(lambda: self._after_deliver(written))

        if manual:
            listing = "\n".join(f"• {name}" for name in sorted(new_files))
            self.post(lambda: self.modal_ask(
                "دانلود کدهای جدید",
                f"{len(new_files)} فایل تازه در مخزن همکار هست:\n{listing}\n\nدر پوشه CODES ذخیره شود؟",
                lambda: self.post(deliver),
            ))
        else:
            deliver()  # در حالت خودکار بی‌درنگ و بدون پرسیدن

    def _after_deliver(self, written: int) -> None:
        self.sounds.play("success")
        self.toast_msg(f"{written} فایل دانلود شد")
        self._scan_codes()

    def _job_run_new(self, manual: bool) -> None:
        codes_dir = ensure_codes_dir()
        state = load_codes_state()
        pending = []
        for path in sorted(codes_dir.glob("*.py")):
            try:
                if state.get(path.name, {}).get("hash") == short_hash(path.read_bytes()):
                    continue
            except OSError:
                continue
            pending.append(path)

        if not pending:
            self.log("✅ کد جدیدی برای اجرا نیست.")
            self.post(lambda: self.toast_msg("کد جدیدی نیست"))
            return

        def run_all() -> None:
            self._run_paths(pending)

        if manual:
            listing = "\n".join(f"• {p.name}" for p in pending)
            self.post(lambda: self.modal_ask(
                "اجرای کدها",
                f"{len(pending)} کد آماده اجراست:\n{listing}\n\nاجرا شود؟",
                lambda: self.post(run_all),
            ))
        else:
            run_all()

    def _job_run_single(self, path: Path) -> None:
        self._run_paths([path], force=True)

    def _run_paths(self, paths: list[Path], force: bool = False) -> None:
        self.post(lambda: self.sounds.play("run"))
        for path in paths:
            self.log(f"▶️ اجرای {path.name}")
            ok, name, text = run_code_job(path)
            for line in text.splitlines()[-8:]:
                self.log(f"   {line}")
            self.log(f"{'✅ پایان' if ok else '❌ خطا در'} {name}")
            self.post(lambda o=ok: self.sounds.play("success" if o else "error"))
        self.post(lambda: self.toast_msg("اجرا تمام شد"))
        self.post(self._scan_codes)

    # ------------------------------------------------- کدها و وضعیت‌ها ---

    def _scan_codes(self) -> None:
        codes_dir = get_desktop_dir() / CODES_FOLDER_NAME
        state = load_codes_state()
        items: list[dict] = []
        try:
            files = sorted(codes_dir.glob("*.py"))
        except OSError:
            files = []
        for path in files:
            try:
                size = path.stat().st_size
            except OSError:
                size = 0
            info = state.get(path.name, {})
            ran = bool(info)
            ok = info.get("ok") if ran else None
            chips: list[tuple[str, str, bool]] = []
            if ran:
                chips.append(("اجرا شده", "ok", True))
                code = info.get("exit_code")
                chips.append((f"خروج {to_fa(str(code))}", "ok" if code == 0 else "danger", True))
            else:
                chips.append(("اجرا نشده", "warn", True))
            if ran:
                meta = (
                    f"{info.get('ran_at', '?')}  ·  {to_fa(str(info.get('duration_s', '?')))} ثانیه"
                    f"  ·  {human_size(size)}"
                )
            else:
                meta = f"اجرا نشده  ·  {human_size(size)}"
            items.append(
                {"name": path.name, "path": path, "meta": meta, "chips": chips, "ran": ran, "ok": ok}
            )
        self.codes_index = items
        self.codes_loaded_at = time.monotonic()

    def _set_status(self, key: str, ok: bool, note: str) -> None:
        self.status[key] = ok
        self.status_note[key] = note

    def _start_status_monitor(self) -> None:
        def loop() -> None:
            while True:
                internet = check_internet()
                self.post(lambda: self._set_status("internet", internet, "وصل" if internet else "قطع"))
                if internet:
                    ok, note = check_google_drive()
                    self.post(lambda: self._set_status("drive", ok, "آماده" if ok else "نیست"))
                else:
                    self.post(lambda: self._set_status("drive", False, "نیست"))
                time.sleep(STATUS_CHECK_SECONDS)

        threading.Thread(target=loop, daemon=True).start()

    # ------------------------------------------------------------ آپدیت ---

    def check_app_update(self, manual: bool = False) -> bool:
        owner, repo, branch = self.mother_info()
        data = repo_zip(owner, repo, branch)
        if not data:
            self.post(lambda: self._set_status("repo", False, "قطع"))
            return False
        version_bytes = extract_file(data, GITHUB_VERSION_FILE)
        version = version_bytes.decode("utf-8", errors="replace").strip() if version_bytes else "?"
        self._last_version = version
        self.post(lambda: self._set_status("repo", True, version[:9]))

        remote = extract_file(data, "app.py")
        if not remote:
            return False
        try:
            if remote == Path(__file__).resolve().read_bytes():
                return False
        except OSError:
            return False

        def apply() -> None:
            self._update_app(data, version)

        if manual or self.settings.get("auto"):
            self.post(lambda: self.modal_ask(
                "نسخه تازه برنامه",
                f"نسخه {version} روی مخزن مادر هست.\nنصب شود و برنامه دوباره باز شود؟",
                apply,
            ))
        return True

    def _update_app(self, data: bytes, version: str) -> None:
        remote = extract_file(data, "app.py")
        if not remote:
            return
        here = Path(__file__).resolve()
        import py_compile
        import tempfile

        try:
            with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as fh:
                fh.write(remote.decode("utf-8", errors="replace"))
                temp_path = fh.name
            py_compile.compile(temp_path, doraise=True)
            Path(temp_path).unlink(missing_ok=True)
        except Exception as exc:  # noqa: BLE001
            self.log(f"⚠️ نسخه جدید سالم نیست، اعمال نشد: {exc}")
            self.report_error("نسخه جدید برنامه سالم نبود", traceback.format_exc())
            return

        try:
            BACKUP_DIR.mkdir(parents=True, exist_ok=True)
            backup = BACKUP_DIR / f"app.backup-{datetime.now():%Y%m%d-%H%M%S}.py"
            backup.write_bytes(here.read_bytes())
            here.write_bytes(remote)
        except OSError as exc:
            self.log(f"⚠️ نوشتن نسخه جدید ممکن نشد: {exc}")
            self.report_error("نوشتن نسخه جدید ممکن نشد", str(exc))
            return

        try:
            import json

            STAMP_FILE.parent.mkdir(parents=True, exist_ok=True)
            STAMP_FILE.write_text(
                json.dumps(
                    {"version": version, "date": jalali_date(tehran_now()), "time": f"{tehran_now():%H:%M}"},
                    ensure_ascii=False, indent=2,
                ),
                encoding="utf-8",
            )
        except OSError:
            pass

        self.log(f"🔄 برنامه بروز شد (نسخه {version}) — پشتیبان: {backup.name}")
        self.log("   راه‌اندازی مجدد…")
        time.sleep(1.2)
        try:
            subprocess.Popen([sys.executable, str(here)])
        except OSError:
            pass
        os._exit(0)

    # -------------------------------------------------------- حلقه اصلی ---

    def handle_event(self, event) -> None:
        if event.type == pygame.QUIT:
            self.running = False
            return
        if event.type == pygame.VIDEORESIZE:
            self.screen = pygame.display.set_mode((max(760, event.w), max(560, event.h)), pygame.RESIZABLE)
            return
        if event.type == pygame.MOUSEMOTION:
            self.mouse = event.pos
            return
        if event.type == pygame.MOUSEWHEEL:
            key = self.tab
            self.scroll_target[key] = max(0.0, self.scroll_target[key] - event.y * 70)
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.mouse = event.pos
            for rect, callback in reversed(self.hits):
                if rect.collidepoint(event.pos):
                    if callback:
                        callback()
                    return
            self.focus_field = None
            return
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if self.modal:
                    self.modal = None
                self.focus_field = None
                return
            if self.focus_field:
                key = self.focus_field
                value = self.field_values.get(key, "")
                if event.key == pygame.K_BACKSPACE:
                    self.field_values[key] = value[:-1]
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_TAB):
                    self.focus_field = None
                elif event.unicode and event.unicode.isprintable() and len(value) < 80:
                    self.field_values[key] = value + event.unicode
            return

    def run(self) -> None:
        try:
            pygame.key.start_text_input()
        except Exception:
            pass
        while self.running:
            dt = self.clock.tick(60) / 1000.0
            for event in pygame.event.get():
                self.handle_event(event)
            self.update(dt)
            self.draw()
            pygame.display.flip()
        pygame.quit()

    def update(self, dt: float) -> None:
        # کارهای معلق از تردها
        try:
            while True:
                fn = self.events.get_nowait()
                try:
                    fn()
                except Exception as exc:  # noqa: BLE001
                    self.log(f"⚠️ خطا در به‌روزرسانی رابط: {exc}")
                    self.report_error("خطا در به‌روزرسانی رابط", traceback.format_exc())
        except queue.Empty:
            pass

        self.caret_t += dt
        if self.caret_t >= 0.55:
            self.caret_t = 0.0
            self.caret_on = not self.caret_on

        self._spinner = (self._spinner + dt * 240) % 360

        for key in self.scroll:
            if key == self.tab:
                self.scroll[key] += (self.scroll_target[key] - self.scroll[key]) * min(1.0, dt * 14)

        # زمان‌بند حالت خودکار
        if self.settings.get("auto"):
            remaining = self.auto_next - time.monotonic()
            if 0 < remaining <= 3.2:
                if int(remaining * 2) != getattr(self, "_last_tick", -1):
                    self._last_tick = int(remaining * 2)
                    if int(remaining * 2) % 2 == 0:
                        self.sounds.play("tick")
            if remaining <= 0 and not self.busy:
                self.auto_next = time.monotonic() + SYNC_POLL_SECONDS
                self._start_job("دور خودکار", self._auto_cycle)

    def _auto_cycle(self) -> None:
        self._job_fetch(manual=False)
        self._job_run_new(manual=False)
        self.check_app_update(manual=False)


# ------------------------------------------------------------------ شروع ---


def main() -> None:
    enable_dpi_awareness()
    if pygame is None:
        message = (
            "کتابخانه pygame نصب نیست.\n\n"
            "فایل run.bat را اجرا کنید تا خودکار نصب شود،\n"
            "یا این دستور را بزنید:\n"
            "    pip install pygame arabic-reshaper python-bidi"
        )
        write_error("pygame نصب نیست", message)
        if IS_WINDOWS:
            try:
                ctypes.windll.user32.MessageBoxW(0, message, "Windows Agent", 0x10)
            except Exception:
                pass
        print(message)
        return

    try:
        app = App()
        app.run()
    except Exception:
        detail = traceback.format_exc()
        path = write_error("خطای اجرای برنامه", detail)
        where = str(path) if path else "ذخیره نشد"
        try:
            if IS_WINDOWS:
                ctypes.windll.user32.MessageBoxW(
                    0, f"برنامه با خطا بسته شد.\n\nجزئیات:\n{where}", "Windows Agent", 0x10
                )
        except Exception:
            pass
        traceback.print_exc()


if __name__ == "__main__":
    main()
