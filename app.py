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
APP_VERSION = "0.5"

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

LMARENA_URL = "https://lmarena.ai"

# بعد از باز شدن کروم چند ثانیه صبر کنیم تا صفحه کامل لود شود
PAGE_LOAD_SECONDS = 5

# پیشوند نام فایل اسکرین‌شات
SCREENSHOT_PREFIX = "lmarena"

# ------------------------------------------------------------------
#  مسیرهای ذخیره (همه داخل گوگل درایو)
# ------------------------------------------------------------------
# پوشه اصلی پروژه روی گوگل درایو (Drive for Desktop)
DRIVE_BASE_DIR = r"C:\Users\alibatel\My Drive\Windows-Agent-DB"

# اسکرین‌شات‌ها  →  ...\Windows-Agent-DB\ScreenShots
SCREENSHOT_DIR = DRIVE_BASE_DIR + r"\ScreenShots"

# گزارش‌های txt  →  ...\Windows-Agent-DB\logs
REPORT_DIR = DRIVE_BASE_DIR + r"\logs"

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


def build_info() -> dict:
    """اطلاعات ساخت: اگر مخزن گیت موجود باشد از آن، وگرنه از مقادیر ثابت."""
    info = {
        "commit": BUILD_COMMIT,
        "subject": BUILD_SUBJECT,
        "date": BUILD_DATE_JALALI,
        "time": BUILD_TIME_TEHRAN,
        "dirty": False,
        "source": "embedded",
    }
    base = Path(__file__).resolve().parent
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
        self.busy = False

        root.title(f"{APP_TITLE} — نسخه {APP_VERSION} ({build_info()['commit']})")
        root.geometry("760x560")
        root.minsize(640, 460)
        root.configure(bg="#f4f6fb")

        base_font = ("Segoe UI", 10)
        self.font_normal = base_font
        self.font_button = ("Segoe UI", 11, "bold")

        self._build_ui()
        self.root.after(120, self._drain_log_queue)
        self._start_status_monitor()

        self.log(f"به Windows Agent خوش آمدید — نسخه {APP_VERSION}")
        self.log(
            f"نسخه در حال اجرا: کامیت {self.build['commit']} "
            f"| تاریخ ساخت {self.build['date']} ساعت {self.build['time']} تهران"
        )
        self.log(f"فایل در حال اجرا: {Path(__file__).resolve()}")
        self.log("دکمه اول: باز کردن lmarena در کروم و گرفتن اسکرین‌شات.")
        self.log("دکمه دوم: گزارش برنامه‌های باز ویندوز.")
        self.log("تب «آخرین تغییرات» تاریخچه نسخه‌ها را نشان می‌دهد.")
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

        stamp = (
            f"نسخه {to_fa(APP_VERSION)}  ·  کامیت {self.build['commit']}"
            f"{' (تغییرات ذخیره‌نشده)' if self.build['dirty'] else ''}"
        )
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

        tk.Label(
            lamps_bar,
            text="وضعیت زنده",
            font=("Segoe UI", 8),
            fg="#6b7691",
            bg="#e8edf7",
        ).pack(side="right", padx=14)

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
            text="📸  باز کردن lmarena و گرفتن اسکرین‌شات",
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

        # ------------------------- پاصفحه -------------------------
        footer = tk.Label(
            self.root,
            text=f"فایل در حال اجرا: {Path(__file__).resolve()}",
            font=("Segoe UI", 8),
            fg="#6b7691",
            bg=bg,
        )
        footer.pack(pady=(0, 6))

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
        self._run_task("باز کردن lmarena و گرفتن اسکرین‌شات", self._job_capture)

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
