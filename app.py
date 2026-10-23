# -*- coding: utf-8 -*-
"""
Windows Agent — نسخه ۱.۶
------------------------
رابط کاربری وب‌محور با pywebview (HTML + CSS + JS)

  ۱) مغز ایجنت: کلید دستی/خودکار، تایمر دایره‌ای، آمار کدها
  ۲) ایجنت مادر / ایجنت همکار / ایجنت مدیریت
  ۳) کتابخانه کدها با دکمه پخش برای اجرای مجدد
  ۴) اسکرین‌شات‌ها و گزارش زنده
  ۵) اسکرین‌شات صفحه و گزارش برنامه‌های باز ویندوز

معماری: بک‌اند پایتون (همین فایل) + یک وب‌سرور محلی روی ۱۲۷.۰.۰.۱
که صفحه را در یک پنجره‌ی WebView2 نشان می‌دهد. هیچ فایلی کنار برنامه نوشته نمی‌شود.

نحوه اجرا: فایل run.bat را دوبار کلیک کنید (کتابخانه‌های لازم را خودش نصب می‌کند).
"""

from __future__ import annotations

import ctypes
import os
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
APP_VERSION = "1.6"

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
#  تاریخچه‌ی نسخه‌ها در سمت رابط کاربری است: assets/ui/app.js → CHANGELOG
# ------------------------------------------------------------------

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
    "theme": "dark",        # dark یا light — پیش‌فرض تاریک
    "theme_set_v16": False,  # یک‌بار در نسخه ۱.۶ تم روی تاریک تنظیم می‌شود
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
                return True, "مسیر در دسترس است"
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



# =============================================================== سرور محلی ===
#
#  یک وب‌سرور کوچک روی ۱۲۷.۰.۰.۱ که سه چیز را سرو می‌کند:
#    /            → assets/ui/index.html
#    /ui/...      → فایل‌های رابط (css/js)
#    /fonts/...   → فونت وزیرمتن
#    /sounds/...  → افکت‌های صوتی
#    /shots/...   → اسکرین‌شات‌ها (فقط تصویر، مسیر امن)
#  بقیه‌ی مسیرها ۴۰۴ می‌شوند. هیچ‌چیز بیرون از این‌ها سرو نمی‌شود.

import mimetypes
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

UI_DIR = LOCAL_BASE_DIR / "assets" / "ui"
UI_INDEX = UI_DIR / "index.html"
ASSETS_DIR = LOCAL_BASE_DIR / "assets"

_SAFE_NAME = re.compile(r"^[A-Za-z0-9_.\-]+$")
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}


class _Handler(BaseHTTPRequestHandler):
    server_version = "WindowsAgentUI/1.6"

    def log_message(self, *_args) -> None:  # بی‌صدا
        pass

    # ---------------------------------------------------------------- کمکی ---

    def _send(self, status: int, body: bytes, ctype: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _file(self, path: Path, ctype: str | None = None) -> None:
        try:
            body = path.read_bytes()
        except OSError:
            self._send(404, b"not found", "text/plain; charset=utf-8")
            return
        if ctype is None:
            ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
                ctype += "; charset=utf-8"
        self._send(200, body, ctype)

    def _safe_child(self, root: Path, name: str) -> Path | None:
        if not _SAFE_NAME.match(name):
            return None
        target = (root / name).resolve()
        try:
            target.relative_to(root.resolve())
        except ValueError:
            return None
        return target

    # ------------------------------------------------------------------ GET ---

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]

        if path in ("/", "/index.html"):
            self._file(UI_INDEX, "text/html; charset=utf-8")
            return

        if path.startswith("/ui/"):
            target = self._safe_child(UI_DIR, path[4:])
            if target:
                self._file(target)
                return
            self._send(404, b"not found", "text/plain; charset=utf-8")
            return

        if path.startswith("/fonts/"):
            target = self._safe_child(ASSETS_DIR / "fonts", path[7:])
            if target:
                self._file(target, "font/ttf")
                return
            self._send(404, b"not found", "text/plain; charset=utf-8")
            return

        if path.startswith("/sounds/"):
            target = self._safe_child(ASSETS_DIR / "sounds", path[8:])
            if target:
                self._file(target, "audio/wav")
                return
            self._send(404, b"not found", "text/plain; charset=utf-8")
            return

        if path.startswith("/shots/"):
            shots_dir, _ = resolve_screenshot_dir()
            target = self._safe_child(Path(shots_dir), path[7:])
            if target and target.suffix.lower() in IMAGE_EXT:
                self._file(target)
                return
            self._send(404, b"not found", "text/plain; charset=utf-8")
            return

        self._send(404, b"not found", "text/plain; charset=utf-8")


def start_ui_server() -> tuple[ThreadingHTTPServer, int]:
    """سرور محلی رابط را روی یک پورت آزاد بالا می‌آورد."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    server.daemon_threads = True
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, port


# ============================================================== پل پایتون↔JS ===
#
#  همه‌ی متدهای این کلاس از سمت جاوااسکریپت با window.pywebview.api صدا زده
#  می‌شوند و باید دیکشنری قابل تبدیل به JSON برگردانند.

POLL_SECONDS = 0.7


class Api:
    """کارهای برنامه؛ رابط کاربری فقط این‌ها را صدا می‌زند."""

    def __init__(self) -> None:
        self.settings = load_settings()
        # نسخه ۱.۶ با تم تاریک شروع می‌شود؛ بعد از آن انتخاب کاربر می‌ماند.
        if not self.settings.get("theme_set_v16"):
            self.settings["theme"] = "dark"
            self.settings["theme_set_v16"] = True
            save_settings(self.settings)
        self.lock = threading.Lock()
        self.log_lines: list[str] = []
        self.busy: str | None = None
        self.events: list[dict] = []
        self.status: dict[str, bool | None] = {
            "internet": None, "drive": None, "repo": None, "collab": None,
        }
        self.status_note = {"internet": "…", "drive": "…", "repo": "…", "collab": "…"}
        self._watch_stop = threading.Event()
        self._watch_running = False
        self.auto_next = 0.0
        # شناسنامه‌ی ساخت یک‌بار خوانده می‌شود (git در هر ۰.۷ ثانیه اجرا نشود)
        self.build = build_info()
        self._shots_cache: list[dict] = []
        self._shots_at = 0.0
        self._paths_cache: dict = {}
        self._paths_at = 0.0
        self._scan_codes()
        self._start_status_monitor()
        if self.settings.get("auto"):
            self._arm_watch()

        self.log(f"به ایجنت ویندوز خوش آمدید — نسخه {to_fa(APP_VERSION)}")
        self.log(f"پوشه کدها: {get_desktop_dir() / CODES_FOLDER_NAME}")
        self.log("حالت دستی — هیچ کاری بدون اجازه تو انجام نمی‌شود.")
        m_owner, m_repo, m_branch = self.mother_info()
        c_owner, c_repo, c_branch = self.collab_info()
        self.log(f"مخزن مادر: {m_owner}/{m_repo} @ {m_branch}")
        self.log(f"مخزن همکار: {c_owner}/{c_repo} @ {c_branch}")
        self.log("برنامه خودکار به‌روزرسانی نمی‌شود (به‌روزرسانی دستی از گیت‌هاب).")

    # ------------------------------------------------------------ کمکی‌ها ---

    def log(self, message: str) -> None:
        stamp = f"{tehran_now():%H:%M:%S}"
        with self.lock:
            for line in (str(message).splitlines() or [""]):
                self.log_lines.append(f"{stamp}  {line}" if line else stamp)
            del self.log_lines[:-500]

    def emit(self, event_type: str, **data) -> None:
        """یک رویداد برای رابط کاربری (صدا، پیام، مشغول/آزاد)."""
        with self.lock:
            self.events.append({"type": event_type, **data})
            del self.events[:-60]

    def sound(self, name: str) -> None:
        self.emit("sound", name=name)

    def toast(self, text: str, kind: str = "ok") -> None:
        self.emit("toast", text=text, kind=kind)

    def report_error(self, context: str, detail: str = "") -> None:
        path = write_error(context, detail)
        self.log(f"🗂 خطا ذخیره شد: {path.name}" if path else "⚠️ ذخیره خطا ممکن نشد.")
        self.toast("خطا در logs/errors ذخیره شد", "error")

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

    # --------------------------------------------------------------- وضعیت ---

    def get_state(self) -> dict:
        """وضعیت کامل برای رسم صفحه (JS هر ۰.۷ ثانیه صدا می‌زند)."""
        with self.lock:
            logs = list(self.log_lines[-300:])
            events = list(self.events)
            self.events.clear()

        auto = bool(self.settings.get("auto"))
        remaining = max(0.0, self.auto_next - time.time()) if auto else 0.0

        return {
            "version": APP_VERSION,
            "version_fa": to_fa(APP_VERSION),
            "build": self.build.get("commit", "—"),
            "build_date": to_fa(self.build.get("date", "—")),
            "build_time": to_fa(self.build.get("time", "—")),
            "build_subject": self.build.get("subject", ""),
            "build_source": self.build.get("source_label", ""),
            "now": int(time.time() * 1000),
            "theme": self.settings.get("theme", "dark"),
            "muted": bool(self.settings.get("muted", False)),
            "auto": auto,
            "busy": self.busy,
            "auto_remaining": round(remaining, 1),
            "auto_total": SYNC_POLL_SECONDS,
            "logs": logs,
            "events": events,
            "status": {
                key: {
                    "state": "wait" if value is None else ("ok" if value else "bad"),
                    "note": self.status_note.get(key, ""),
                }
                for key, value in self.status.items()
            },
            "codes": self.codes_index,
            "shots": self._cached_shots(),
            "mother": dict(zip(("owner", "repo", "branch"), self.mother_info())),
            "collab": dict(zip(("owner", "repo", "branch"), self.collab_info())),
            "paths": self._cached_paths(),
            "auto_accept": auto,   # در حالت خودکار هیچ‌وقت اجازه نمی‌گیرد
        }

    def _cached_shots(self) -> list[dict]:
        """فهرست تصویرها را حداکثر هر ۳ ثانیه یک‌بار از دیسک می‌خواند."""
        if time.time() - self._shots_at >= 3.0:
            self._shots_cache = self._shots_index()
            self._shots_at = time.time()
        return self._shots_cache

    def _cached_paths(self) -> dict:
        """مسیرها هر ۱۵ ثانیه تازه می‌شوند (درایو ممکن است دیر وصل شود)."""
        if not self._paths_cache or time.time() - self._paths_at >= 15.0:
            self._paths_cache = {
                "codes": str(get_desktop_dir() / CODES_FOLDER_NAME),
                "logs": str(resolve_report_dir()[0]),
                "shots": str(resolve_screenshot_dir()[0]),
                "errors": str(error_dir()),
                "state": str(STATE_DIR),
            }
            self._paths_at = time.time()
        return self._paths_cache

    def _refresh_shots(self) -> None:
        self._shots_cache = self._shots_index()
        self._shots_at = time.time()

    def _shots_index(self) -> list[dict]:
        folder = Path(resolve_screenshot_dir()[0])
        items: list[dict] = []
        try:
            files = [
                p for p in folder.iterdir()
                if p.suffix.lower() in IMAGE_EXT and _SAFE_NAME.match(p.name)
            ]
            files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        except OSError:
            files = []
        for path in files[:60]:
            try:
                stat = path.stat()
            except OSError:
                continue
            items.append(
                {
                    "name": path.name,
                    "url": f"/shots/{path.name}",
                    "size": human_size(stat.st_size),
                    "when": f"{jalali_date(tehran_now())} — {datetime.fromtimestamp(stat.st_mtime):%H:%M}",
                }
            )
        return items

    def _scan_codes(self) -> None:
        """فهرست فایل‌های پایتون پوشه CODES + وضعیت اجرا."""
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
            items.append(
                {
                    "name": path.name,
                    "stem": path.stem,
                    "size": human_size(size),
                    "ran": ran,
                    "ok": ok,
                    "status": "ok" if ok else ("error" if ran else "pending"),
                    "ran_at": info.get("ran_at", ""),
                    "duration": to_fa(str(info.get("duration_s", "—"))) if ran else "—",
                    "exit_code": to_fa(str(info.get("exit_code", "—"))) if ran else "—",
                }
            )
        self.codes_index = items

    # ---------------------------------------------------------- دکمه‌ها ---

    def toggle_auto(self) -> dict:
        enabled = not bool(self.settings.get("auto"))
        self.settings["auto"] = enabled
        save_settings(self.settings)
        if enabled:
            self.sound("success")
            self.log("⚡ حالت خودکار روشن شد — بررسی و اجرا بدون پرسیدن.")
            self.toast("حالت خودکار روشن شد")
            self._arm_watch()
        else:
            self.log("🔒 حالت دستی — هیچ کاری بدون اجازه تو انجام نمی‌شود.")
            self.toast("حالت دستی شد")
            self._watch_stop.set()
        return self.get_state()

    def set_theme(self, theme: str) -> dict:
        if theme in ("dark", "light"):
            self.settings["theme"] = theme
            save_settings(self.settings)
        return self.get_state()

    def set_muted(self, muted: bool) -> dict:
        self.settings["muted"] = bool(muted)
        save_settings(self.settings)
        self.log("🔇 صدا خاموش شد." if muted else "🔊 صدا روشن شد.")
        return self.get_state()

    def save_repo(self, prefix: str, owner: str, repo: str, branch: str) -> dict:
        if prefix not in ("mother", "collab"):
            return self.get_state()
        owner = (owner or "").strip()
        repo = (repo or "").strip()
        branch = (branch or "").strip()
        if "/" in owner:
            owner, _, rest = owner.partition("/")
            repo = repo or rest
        self.settings[f"{prefix}_owner"] = owner
        self.settings[f"{prefix}_repo"] = repo
        self.settings[f"{prefix}_branch"] = branch or "main"
        save_settings(self.settings)
        name = "مادر" if prefix == "mother" else "همکار"
        self.log(f"💾 مخزن {name} ذخیره شد: {owner}/{repo} @ {branch}")
        self.sound("success")
        self.toast("ذخیره شد")
        return self.get_state()

    def clear_log(self) -> dict:
        with self.lock:
            self.log_lines.clear()
        self.toast("گزارش پاک شد")
        return self.get_state()

    def open_path(self, which: str) -> dict:
        """باز کردن پوشه یا فایل با برنامه‌ی پیش‌فرض ویندوز."""
        targets = {
            "codes": get_desktop_dir() / CODES_FOLDER_NAME,
            "logs": resolve_report_dir()[0],
            "shots": resolve_screenshot_dir()[0],
            "errors": error_dir(),
            "state": STATE_DIR,
        }
        target = targets.get(which)
        if target is None:
            return self.get_state()
        try:
            if IS_WINDOWS:
                os.startfile(str(target))  # type: ignore[attr-defined]
            else:
                subprocess.Popen(["xdg-open", str(target)])
        except Exception as exc:  # noqa: BLE001
            self.log(f"⚠️ باز کردن ممکن نشد: {exc}")
        return self.get_state()

    def open_shot(self, name: str) -> dict:
        if not _SAFE_NAME.match(name or ""):
            return self.get_state()
        path = Path(resolve_screenshot_dir()[0]) / name
        try:
            if IS_WINDOWS:
                os.startfile(str(path))  # type: ignore[attr-defined]
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as exc:  # noqa: BLE001
            self.log(f"⚠️ باز کردن تصویر ممکن نشد: {exc}")
        return self.get_state()

    def check_collab(self, confirmed: bool = False) -> dict:
        """بررسی مخزن همکار. در حالت دستی اول اجازه می‌گیرد."""
        if self.busy:
            return {"need_confirm": False, "state": self.get_state()}
        if not self.collab_ready():
            self.toast("اول مخزن همکار را تنظیم و ذخیره کن", "error")
            return self.get_state()

        if not confirmed and not self.settings.get("auto"):
            return {
                "need_confirm": True,
                "title": "بررسی مخزن همکار",
                "message": "مخزن ایجنت همکار بررسی شود؟ اگر کد تازه‌ای باشد، دانلود می‌شود.",
                "action": "check_collab",
            }

        self._start_job("بررسی مخزن همکار", self._job_fetch)
        return self.get_state()

    def run_new(self, confirmed: bool = False) -> dict:
        pending = [c for c in self.codes_index if not c["ran"]]
        if not pending:
            self.toast("کد جدیدی برای اجرا نیست")
            return self.get_state()

        if not confirmed and not self.settings.get("auto"):
            names = "، ".join(c["name"] for c in pending[:6])
            return {
                "need_confirm": True,
                "title": "اجرای کدهای جدید",
                "message": f"{len(pending)} کد آماده اجراست:\n{names}\n\nاجرا شود؟",
                "action": "run_new",
            }

        self._start_job("اجرای کدهای جدید", self._job_run_new)
        return self.get_state()

    def run_single(self, name: str, confirmed: bool = False) -> dict:
        if not _SAFE_NAME.match(name or ""):
            return self.get_state()
        if self.busy:
            return self.get_state()

        if not confirmed and not self.settings.get("auto"):
            return {
                "need_confirm": True,
                "title": "اجرای دوباره",
                "message": f"کد «{name}» دوباره اجرا شود؟",
                "action": "run_single",
                "arg": name,
            }

        path = get_desktop_dir() / CODES_FOLDER_NAME / name
        if not path.is_file():
            self.toast("فایل پیدا نشد", "error")
            return self.get_state()
        self._start_job(name, lambda: self._job_run_single(path))
        return self.get_state()

    def take_screenshot(self, confirmed: bool = False) -> dict:
        if self.busy:
            return self.get_state()
        if not confirmed and not self.settings.get("auto"):
            return {
                "need_confirm": True,
                "title": "گرفتن اسکرین‌شات",
                "message": f"{LMARENA_URL} در کروم باز شود و بعد از ۵ ثانیه عکس گرفته شود؟",
                "action": "take_screenshot",
            }
        self._start_job("گرفتن اسکرین‌شات", self._job_capture)
        return self.get_state()

    def open_report(self, confirmed: bool = False) -> dict:
        if self.busy:
            return self.get_state()
        if not confirmed and not self.settings.get("auto"):
            return {
                "need_confirm": True,
                "title": "گزارش برنامه‌های باز",
                "message": "فهرست پنجره‌های باز ویندوز گرفته و در logs ذخیره شود؟",
                "action": "open_report",
            }
        self._start_job("گرفتن گزارش", self._job_report)
        return self.get_state()

    def rescan_codes(self) -> dict:
        self._scan_codes()
        self.toast("فهرست کدها به‌روز شد")
        return self.get_state()

    # ------------------------------------------------------------ کارها ---

    def _start_job(self, label: str, job) -> None:
        self.busy = label
        self.emit("busy", label=label)

        def runner() -> None:
            try:
                job()
            except Exception as exc:  # noqa: BLE001
                detail = traceback.format_exc()
                self.report_error(f"خطا در «{label}»: {exc}", detail)
                self.sound("error")
            finally:
                self.busy = None
                self.emit("idle")
                self._scan_codes()
                self._refresh_shots()
                if self.settings.get("auto"):
                    self._arm_watch()

        threading.Thread(target=runner, daemon=True).start()

    def _job_capture(self) -> None:
        self.log(f"📸 باز کردن {LMARENA_URL} در کروم…")
        try:
            self.log(f"   {open_in_chrome(LMARENA_URL)}")
        except Exception as exc:  # noqa: BLE001
            self.log(f"   ⚠️ {exc}")
        self.log(f"   صبر {PAGE_LOAD_SECONDS} ثانیه برای کامل شدن صفحه…")
        time.sleep(PAGE_LOAD_SECONDS)
        dest, on_drive = resolve_screenshot_dir()
        path = take_screenshot(dest)
        self.sound("shutter")
        self.log(f"✅ اسکرین‌شات ذخیره شد → {path}")
        self.log(f"   محل: {'گوگل درایو' if on_drive else 'دسکتاپ (درایو در دسترس نبود)'}")
        self.toast("اسکرین‌شات گرفته شد")

    def _job_report(self) -> None:
        self.log("📋 خواندن فهرست پنجره‌های باز…")
        windows = collect_open_windows()
        dest, on_drive = resolve_report_dir()
        path = save_report(format_windows_report(windows), dest)
        self.log(f"✅ گزارش ذخیره شد ({len(windows)} پنجره) → {path.name}")
        if not on_drive:
            self.log("   ⚠️ گوگل درایو در دسترس نبود؛ روی دسکتاپ ذخیره شد.")
        self.sound("success")
        self.toast("گزارش ذخیره شد")

    def _job_fetch(self) -> None:
        owner, repo, branch = self.collab_info()
        self.log(f"📥 بررسی {owner}/{repo} @ {branch}")
        data = repo_zip(owner, repo, branch)
        if not data:
            self.status["collab"] = False
            self.status_note["collab"] = "قطع"
            self.log(f"❌ دریافت از {owner}/{repo} ممکن نشد.")
            self.sound("error")
            self.report_error(
                "دریافت مخزن ایجنت همکار ممکن نشد",
                f"آدرس: {owner}/{repo} @ {branch}\n"
                "احتمال: قطع بودن اینترنت، فیلتر بودن گیت‌هاب، یا اشتباه بودن نام مخزن/شاخه.",
            )
            return

        files = extract_py_files(data)
        self.status["collab"] = True
        self.status_note["collab"] = f"{len(files)} فایل"
        if not files:
            self.log("📭 در مخزن همکار هیچ فایل پایتونی نیست.")
            self.toast("فایل پایتونی پیدا نشد", "error")
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
            self.toast("پوشه CODES به‌روز است")
            return

        written = 0
        for name, content in new_files.items():
            try:
                (codes_dir / name).write_bytes(content)
                written += 1
            except OSError as exc:
                self.log(f"⚠️ نوشتن {name} ممکن نشد: {exc}")

        self.log(f"🆕 {', '.join(sorted(new_files))}")
        self.log(f"📥 {written} فایل در پوشه CODES ذخیره شد.")
        self.sound("success")
        self.toast(f"{written} فایل دانلود شد")
        self._scan_codes()

        if self.settings.get("auto"):
            self._job_run_new()

    def _job_run_new(self) -> None:
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
            self.toast("کد جدیدی نیست")
            return
        self._run_paths(pending)

    def _job_run_single(self, path: Path) -> None:
        self.log(f"▶️ اجرای دوباره {path.name}")
        self._run_paths([path])

    def _run_paths(self, paths: list[Path]) -> None:
        self.sound("run")
        for path in paths:
            self.log(f"▶️ اجرای {path.name}")
            ok, name, text = run_code_job(path)
            for line in text.splitlines()[-8:]:
                self.log(f"   {line}")
            self.log(f"{'✅ پایان' if ok else '❌ خطا در'} {name}")
            self.sound("success" if ok else "error")
        self.toast("اجرا تمام شد")
        self._scan_codes()

    # -------------------------------------------- حلقه خودکار و وضعیت‌ها ---

    def _arm_watch(self) -> None:
        self.auto_next = time.time() + SYNC_POLL_SECONDS
        if self._watch_running:
            return
        self._watch_running = True
        self._watch_stop.clear()

        def loop() -> None:
            while not self._watch_stop.is_set():
                if not self.settings.get("auto"):
                    break
                if self.busy is None and time.time() >= self.auto_next:
                    if self.busy is None:
                        self._start_job("دور خودکار", self._auto_cycle)
                self._watch_stop.wait(0.5)
            self._watch_running = False

        threading.Thread(target=loop, daemon=True).start()

    def _auto_cycle(self) -> None:
        self._job_fetch()

    def _start_status_monitor(self) -> None:
        def loop() -> None:
            while True:
                internet = check_internet()
                self.status["internet"] = internet
                self.status_note["internet"] = "وصل" if internet else "قطع"
                if internet:
                    ok, _note = check_google_drive()
                    self.status["drive"] = ok
                    self.status_note["drive"] = "آماده" if ok else "نیست"
                else:
                    self.status["drive"] = False
                    self.status_note["drive"] = "نیست"
                time.sleep(STATUS_CHECK_SECONDS)

        threading.Thread(target=loop, daemon=True).start()


# ------------------------------------------------------------------ شروع ---

def main() -> None:
    enable_dpi_awareness()

    try:
        import webview
    except ImportError:
        message = (
            "کتابخانه pywebview نصب نیست.\n\n"
            "فایل run.bat را اجرا کنید تا خودکار نصب شود،\n"
            "یا این دستور را بزنید:\n"
            "    pip install pywebview\n"
        )
        write_error("pywebview نصب نیست", message)
        if IS_WINDOWS:
            try:
                ctypes.windll.user32.MessageBoxW(0, message, "ایجنت ویندوز", 0x10)
            except Exception:
                pass
        print(message)
        return

    if not UI_INDEX.is_file():
        message = f"فایل رابط کاربری پیدا نشد:\n{UI_INDEX}"
        write_error("فایل رابط کاربری نیست", message)
        if IS_WINDOWS:
            try:
                ctypes.windll.user32.MessageBoxW(0, message, "ایجنت ویندوز", 0x10)
            except Exception:
                pass
        return

    server, port = start_ui_server()
    api = Api()
    url = f"http://127.0.0.1:{port}/"

    options = dict(
        title="ایجنت ویندوز — پنل ویندوز",
        url=url,
        js_api=api,
        width=1180,
        height=820,
        min_size=(900, 600),
        background_color="#161511",
        text_select=False,
        confirm_close=False,
        resizable=True,
    )

    # پنجره در حالت بزرگ (پرِ صفحه) باز می‌شود ولی اندازه‌اش قابل تغییر است.
    # اگر نسخه‌ی نصب‌شده‌ی pywebview این گزینه‌ها را نداشت، به حالت ساده برمی‌گردیم.
    window = None
    for extra in ({"maximized": True}, {"fullscreen": True}, {}):
        try:
            window = webview.create_window(**{**options, **extra})
            break
        except TypeError:
            continue
    if window is None:
        window = webview.create_window(**options)

    def on_loaded() -> None:
        try:
            window.evaluate_js("document.documentElement.dataset.ready='1';")
        except Exception:
            pass

    try:
        webview.start(on_loaded, private_mode=False, storage_path=str(STATE_DIR / "webview"))
    except Exception as exc:  # noqa: BLE001
        detail = traceback.format_exc()
        path = write_error("اجرای پنجره WebView ممکن نشد", detail)
        message = (
            "پنجره برنامه باز نشد.\n\n"
            "روی ویندوز، برنامه به «WebView2 Runtime» نیاز دارد.\n"
            "آن را از این آدرس نصب کن و دوباره تلاش کن:\n"
            "https://developer.microsoft.com/microsoft-edge/webview2/\n\n"
            f"جزئیات: {path or exc}"
        )
        if IS_WINDOWS:
            try:
                ctypes.windll.user32.MessageBoxW(0, message, "ایجنت ویندوز", 0x10)
            except Exception:
                pass
        traceback.print_exc()
    finally:
        try:
            server.shutdown()
        except Exception:
            pass


if __name__ == "__main__":
    main()
