# -*- coding: utf-8 -*-
"""job_0101_open_google.py — باز کردن گوگل در کروم (تست مسیر دریافت کد)"""
import os, subprocess, time
from datetime import datetime, timezone, timedelta
from pathlib import Path

TEHRAN = timezone(timedelta(hours=3, minutes=30))
print("زمان تهران:", datetime.now(TEHRAN).strftime("%Y-%m-%d %H:%M:%S"))

URL = "https://www.google.com"

candidates = [
    Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "Google/Chrome/Application/chrome.exe",
    Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")) / "Google/Chrome/Application/chrome.exe",
    Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
]
chrome = next((str(p) for p in candidates if p.is_file()), None)
print("کروم:", chrome or "پیدا نشد")

if chrome:
    subprocess.Popen([chrome, "--new-window", URL],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("گوگل در کروم باز شد:", URL)
else:
    os.startfile(URL)
    print("با مرورگر پیش‌فرض باز شد:", URL)

time.sleep(2)
print("پایان job.")
