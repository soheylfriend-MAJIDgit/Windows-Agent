# -*- coding: utf-8 -*-
"""Create the LocalAppData build stamp consumed by app.py; writes no files beside app.py."""
from __future__ import annotations
import json
import os
from pathlib import Path
import subprocess
from datetime import datetime, timezone, timedelta

TEHRAN = timezone(timedelta(hours=3, minutes=30))

def gregorian_to_jalali(gy: int, gm: int, gd: int) -> tuple[int, int, int]:
    g_d_m = [0,31,59,90,120,151,181,212,243,273,304,334]
    gy2, gm2, gd2 = gy - 1600, gm - 1, gd - 1
    day = 365 * gy2 + (gy2 + 3)//4 - (gy2 + 99)//100 + (gy2 + 399)//400
    day += g_d_m[gm2] + gd2
    if gm > 2 and ((gy % 4 == 0 and gy % 100 != 0) or gy % 400 == 0):
        day += 1
    day -= 79
    n = day // 12053
    day %= 12053
    jy = 979 + 33*n + 4*(day//1461)
    day %= 1461
    if day >= 366:
        jy += (day - 1)//365
        day = (day - 1)%365
    if day < 186:
        jm, jd = 1 + day//31, 1 + day%31
    else:
        jm, jd = 7 + (day-186)//30, 1 + (day-186)%30
    return jy, jm, jd

def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    state = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local")) / "Windows-Agent"
    stamp = state / "build_stamp.json"
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), "log", "-1", "--format=%h%x1f%ct%x1f%s"],
            capture_output=True, text=True, timeout=5, check=True,
        ).stdout.strip()
        commit, epoch, subject = out.split("\x1f", 2)
        moment = datetime.fromtimestamp(int(epoch), TEHRAN)
        jy, jm, jd = gregorian_to_jalali(moment.year, moment.month, moment.day)
        state.mkdir(parents=True, exist_ok=True)
        tmp = stamp.with_suffix(".tmp")
        tmp.write_text(json.dumps({
            "version": commit,
            "date": f"{jy:04d}/{jm:02d}/{jd:02d}",
            "time": moment.strftime("%H:%M"),
            "subject": subject[:70],
        }, ensure_ascii=False), encoding="utf-8")
        tmp.replace(stamp)
        print(f"ساخت: {commit} | آخرین کامیت: {jy:04d}/{jm:02d}/{jd:02d} {moment:%H:%M} تهران")
        return 0
    except Exception as exc:
        print(f"هشدار: شناسه‌ی کامیت از Git خوانده نشد؛ مقدار تعبیه‌شده نمایش داده می‌شود ({exc})")
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
