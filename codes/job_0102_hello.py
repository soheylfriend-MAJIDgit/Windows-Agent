# -*- coding: utf-8 -*-
"""job_0102_hello.py — تست اتصال (این فایل از پوشه codes گیت‌هاب می‌آید)"""
from datetime import datetime, timezone, timedelta
import os, platform, sys

TEHRAN = timezone(timedelta(hours=3, minutes=30))
now = datetime.now(TEHRAN)
print("سلام! این کد از پوشه codes گیت‌هاب روی سیستم اجرا شد.")
print("=" * 56)
print("زمان تهران:", now.strftime("%Y-%m-%d %H:%M:%S"))
print("سیستم:", platform.platform())
print("پایتون:", sys.version.split()[0])
print("کاربر:", os.environ.get("USERNAME", "?"))
print("پوشه جاری:", os.getcwd())
print("پایان.")
