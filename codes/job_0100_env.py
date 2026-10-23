# -*- coding: utf-8 -*-
"""job_0100_env.py — گزارش محیط سیستم (اولین کد از مسیر گیت‌هاب)"""
import os, platform, sys, shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path

TEHRAN = timezone(timedelta(hours=3, minutes=30))
now = datetime.now(TEHRAN)
print("گزارش محیط — از مسیر گیت‌هاب رسید")
print("=" * 50)
print("زمان تهران:", now.strftime("%Y-%m-%d %H:%M:%S"))
print("پایتون:", sys.version.split()[0])
print("سیستم:", platform.platform())
print("کاربر:", os.environ.get("USERNAME", "?"))
print("کامپیوتر:", os.environ.get("COMPUTERNAME", "?"))
print()
for label, path in [
    ("User-Interface", r"C:\Users\alibatel\My Drive\Windows-Agent-DB\User-Interface"),
    ("Codes", r"C:\Users\alibatel\My Drive\Windows-Agent-DB\Codes"),
    ("ScreenShots", r"C:\Users\alibatel\My Drive\Windows-Agent-DB\ScreenShots"),
    ("logs", r"C:\Users\alibatel\My Drive\Windows-Agent-DB\logs"),
]:
    print(f"{label}: {'هست' if Path(path).is_dir() else 'نیست'}")
try:
    total, used, free = shutil.disk_usage("C:\\")
    print(f"\nفضای آزاد C: {free / 2**30:.1f} گیگابایت")
except OSError:
    pass
print("\nپایان.")
