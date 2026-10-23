# -*- coding: utf-8 -*-
"""
job_0001_hello.py — اولین کار آزمایشی از طریق Arena Bridge
=========================================================

این فایل را Arena در پوشه `bridge/codes` گوگل درایو می‌گذارد.
ناظر (bridge_watcher.pyw) آن را اجرا می‌کند و خروجی را در پوشه `out`
می‌نویسد تا Arena بتواند بخواند.

هدف: بررسی محیط سیستم و صحت اتصال.
"""

from __future__ import annotations

import os
import platform
import shutil
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

TEHRAN = timezone(timedelta(hours=3, minutes=30), "Tehran")
now = datetime.now(TEHRAN)

print("سلام! این اولین کد اجراشده از طریق پل Arena است.")
print("=" * 60)
print(f"زمان تهران: {now:%Y-%m-%d %H:%M:%S}")
print(f"پایتون: {sys.version.split()[0]}")
print(f"مسیر پایتون: {sys.executable}")
print(f"سیستم: {platform.platform()}")
print(f"پوشه جاری: {os.getcwd()}")
print(f"نام کاربری ویندوز: {os.environ.get('USERNAME', '?')}")
print(f"نام کامپیوتر: {os.environ.get('COMPUTERNAME', '?')}")
print(f"منطقه زمانی سیستم: {datetime.now().astimezone().tzname()}")
print()

print("--- بررسی مسیرهای مهم ---")
paths = {
    "ریشه گوگل درایو (C:\\Users\\alibatel\\My Drive)": r"C:\Users\alibatel\My Drive",
    "پوشه پروژه (Windows-Agent-DB)": r"C:\Users\alibatel\My Drive\Windows-Agent-DB",
    "پوشه اسکرین‌شات": r"C:\Users\alibatel\My Drive\Windows-Agent-DB\ScreenShots",
    "پوشه گزارش‌ها": r"C:\Users\alibatel\My Drive\Windows-Agent-DB\logs",
    "پوشه پل (bridge)": r"C:\Users\alibatel\My Drive\Windows-Agent-DB\bridge",
    "ریپوی Windows-Agent": r"C:\Users\alibatel\Desktop\Windows-Agent",
    "My Drive روی درایو G": r"G:\My Drive",
}
for label, raw in paths.items():
    path = Path(raw)
    exists = "هست" if path.is_dir() else "نیست"
    print(f"{label}: {exists}  ←  {raw}")
print()

try:
    bridge = Path(r"C:\Users\alibatel\My Drive\Windows-Agent-DB\bridge")
    if bridge.is_dir():
        print("--- محتوای پوشه bridge ---")
        for item in sorted(bridge.iterdir()):
            kind = "پوشه" if item.is_dir() else "فایل"
            print(f"  {kind}: {item.name}")
        print()
except OSError as exc:
    print(f"خواندن پوشه bridge ممکن نشد: {exc}")

try:
    total, used, free = shutil.disk_usage("C:\\")
    print("--- فضای دیسک C: ---")
    print(f"کل: {total / 2**30:.1f} گیگابایت")
    print(f"آزاد: {free / 2**30:.1f} گیگابایت")
    print()
except OSError:
    pass

print("--- کتابخانه‌های مورد نیاز ---")
for module in ("PIL", "tkinter", "jdatetime"):
    try:
        __import__(module)
        print(f"  {module}: نصب است")
    except ImportError:
        print(f"  {module}: نصب نیست")
print()

Path("hello_from_arena.txt").write_text(
    f"این فایل را job اول در {now:%Y-%m-%d %H:%M:%S} ساخت.\n"
    "اگر این را می‌بینی، پل Arena درست کار می‌کند.\n",
    encoding="utf-8",
)
print("فایل hello_from_arena.txt ساخته شد.")
print("پایان job.")
