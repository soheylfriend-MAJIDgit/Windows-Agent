# -*- coding: utf-8 -*-
"""
Windows Agent — نسخه ۰.۳
------------------------
یک رابط کاربری خیلی ساده با دو دکمه:

  ۱) باز کردن lmarena در کروم و گرفتن اسکرین‌شات از کل صفحه
     (ذخیره در پوشه گوگل درایو)
  ۲) گرفتن گزارش از برنامه‌های باز ویندوز

نحوه اجرا: فایل run.bat را دوبار کلیک کنید.
"""

from __future__ import annotations

import ctypes
import os
import queue
import subprocess
import sys
import threading
import time
import traceback
import webbrowser
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import scrolledtext

# ---------------------------------------------------------------- تنظیمات ---

APP_TITLE = "Windows Agent"
APP_VERSION = "0.3"

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
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
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
        windows.append(
            {
                "title": title,
                "pid": pid.value,
                "process": _process_name(pid.value),
            }
        )
        return True

    user32.EnumWindows(enum_proc(_callback), 0)
    windows.sort(key=lambda item: (item["process"].lower(), item["title"].lower()))
    return windows


def format_windows_report(windows: list[dict]) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    counts: dict[str, int] = {}
    for window in windows:
        counts[window["process"]] = counts.get(window["process"], 0) + 1

    lines = [
        "گزارش برنامه‌های باز ویندوز",
        "=" * 60,
        f"تاریخ: {now}",
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
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    target = dest_dir / f"open_apps_report_{stamp}.txt"
    target.write_text(report_text, encoding="utf-8-sig")
    return target


# ------------------------------------------------------------ رابط کاربری ---

class AgentApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.log_queue: queue.Queue[str] = queue.Queue()
        self.busy = False

        root.title(f"{APP_TITLE} — نسخه {APP_VERSION}")
        root.geometry("760x560")
        root.minsize(640, 460)
        root.configure(bg="#f4f6fb")

        base_font = ("Segoe UI", 10)
        self.font_normal = base_font
        self.font_button = ("Segoe UI", 11, "bold")

        self._build_ui()
        self.root.after(120, self._drain_log_queue)

        self.log("به Windows Agent خوش آمدید.")
        self.log("دکمه اول: باز کردن lmarena در کروم و گرفتن اسکرین‌شات.")
        self.log("دکمه دوم: گزارش برنامه‌های باز ویندوز.")
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
        header = tk.Frame(self.root, bg="#1f2a44", pady=16)
        header.pack(fill="x")
        tk.Label(
            header,
            text="🤖  Windows Agent",
            font=("Segoe UI", 17, "bold"),
            fg="white",
            bg="#1f2a44",
        ).pack()
        tk.Label(
            header,
            text="ابزار ساده‌ی اتوماسیون دسکتاپ ویندوز",
            font=("Segoe UI", 10),
            fg="#c7d0e4",
            bg="#1f2a44",
        ).pack(pady=(4, 0))

        buttons_frame = tk.Frame(self.root, bg="#f4f6fb", pady=18)
        buttons_frame.pack(fill="x", padx=18)

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
            self.root,
            text="  وضعیت  ",
            font=("Segoe UI", 9, "bold"),
            bg="#f4f6fb",
            fg="#3b4763",
            bd=1,
            relief="solid",
        )
        log_frame.pack(fill="both", expand=True, padx=18, pady=(0, 8))

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
        self.log_box.pack(fill="both", expand=True, padx=8, pady=8)
        self.log_box.configure(state="disabled")

        footer = tk.Label(
            self.root,
            text=f"نسخه ۰.۳ — ذخیره در {DRIVE_BASE_DIR}",
            font=("Segoe UI", 9),
            fg="#6b7691",
            bg="#f4f6fb",
        )
        footer.pack(pady=(0, 10))

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
