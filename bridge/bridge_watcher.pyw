# -*- coding: utf-8 -*-
"""
Arena Bridge — ناظر پوشه کد
===========================

این برنامه روی ویندوز اجرا می‌شود و پوشه‌ی `codes` را تماشا می‌کند.
هر فایل پایتونی که با نام `job_*.py` در آن پوشه ظاهر شود را
(پس از اطمینان از کامل شدن دانلود/سینک) اجرا می‌کند و خروجی را
در پوشه‌ی `out` می‌نویسد تا از بیرون خوانده شود.

نکات ایمنی:
  * فقط فایل‌هایی اجرا می‌شوند که نامشان با `job_` شروع شود و در همان پوشه باشند.
  * هر فایل فقط یک بار اجرا می‌شود (وضعیت در state.json نگه داشته می‌شود).
  * اگر فایل `PAUSE.txt` وجود داشته باشد، هیچ کاری اجرا نمی‌شود.
  * همه اتفاقات در `watcher.log` ثبت می‌شود.
  * اجرا با محدودیت زمانی (پیش‌فرض ۱۵ دقیقه) انجام می‌شود.

اجرا: روی START-BRIDGE.bat دوبار کلیک کنید.

اینجا در ریپو فقط نسخه‌ی مرجع است؛ نسخه‌ی اجرایی روی گوگل درایو قرار می‌گیرد:
  C:\\Users\\alibatel\\My Drive\\Windows-Agent-DB\\bridge\\
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ---------------------------------------------------------------- تنظیمات ---

# مسیر ریشه در گوگل درایو (قابل تغییر با متغیر محیطی BRIDGE_BASE برای تست)
BASE = Path(
    os.environ.get("BRIDGE_BASE")
    or r"C:\Users\alibatel\My Drive\Windows-Agent-DB\bridge"
)

CODES = BASE / "codes"           # پوشه ورودی: فایل‌های job_*.py
DONE = CODES / "done"            # فایل‌های اجراشده اینجا منتقل می‌شوند
OUT = BASE / "out"               # نتایج اجرا
STATE = BASE / "state.json"      # حافظه ناظر
PAUSE = BASE / "PAUSE.txt"       # اگر باشد، اجرا متوقف می‌شود
STATUS = BASE / "status.txt"     # نبض ناظر (برای اینکه از بیرون ببینیم زنده است)
LOG = BASE / "watcher.log"       # گزارش کامل

POLL_SECONDS = float(os.environ.get("BRIDGE_POLL", "3"))
SETTLE_SECONDS = float(os.environ.get("BRIDGE_SETTLE", "3"))
MAX_RUNTIME = int(os.environ.get("BRIDGE_MAX_RUNTIME", "900"))

TEHRAN = timezone(timedelta(hours=3, minutes=30), "Tehran")


def now_text() -> str:
    return datetime.now(TEHRAN).strftime("%Y-%m-%d %H:%M:%S")


# ------------------------------------------------------------------ لاگ ----

def log(message: str) -> None:
    line = f"[{now_text()}] {message}"
    print(line, flush=True)
    try:
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def write_status(state: str, extra: str = "") -> None:
    """نبض ناظر را در فایل status.txt می‌نویسد تا از گوگل درایو قابل خواندن باشد."""
    text = (
        f"وضعیت: {state}\n"
        f"زمان (تهران): {now_text()}\n"
        f"پوشه ورودی: {CODES}\n"
        f"پوشه نتایج: {OUT}\n"
        f"تعداد کارهای انجام‌شده: {len(load_state())}\n"
        f"متوقف با PAUSE: {'بله' if PAUSE.exists() else 'خیر'}\n"
        f"{extra}"
    )
    try:
        STATUS.write_text(text, encoding="utf-8")
    except OSError:
        pass


# ---------------------------------------------------------------- حافظه ----

def load_state() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(state: dict) -> None:
    try:
        STATE.write_text(
            json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError:
        pass


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


# ------------------------------------------------------------- اجرای کار ----

def run_job(path: Path) -> None:
    """یک فایل job را اجرا می‌کند و نتیجه را در پوشه out می‌نویسد."""
    name = path.name
    started = time.time()
    result_lines: list[str] = []
    exit_code: int | str = "?"
    stdout_text = ""
    stderr_text = ""

    try:
        job_hash = sha256_of(path)
    except OSError as exc:
        log(f"خواندن فایل ممکن نشد: {name} ({exc})")
        return

    # فایل را به پوشه done منتقل می‌کنیم تا دوباره اجرا نشود
    target = DONE / name
    if target.exists():
        target = DONE / f"{path.stem}__{int(time.time())}.py"
    try:
        path.replace(target)
    except OSError:
        try:
            target.write_bytes(path.read_bytes())
            path.unlink()
        except OSError as exc:
            log(f"انتقال فایل ممکن نشد: {name} ({exc})")
            return

    log(f"▶ شروع اجرا: {name}")
    OUT.mkdir(parents=True, exist_ok=True)

    try:
        completed = subprocess.run(
            [sys.executable, str(target)],
            cwd=str(OUT),
            capture_output=True,
            timeout=MAX_RUNTIME,
            creationflags=(
                subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            ),
        )
        exit_code = completed.returncode
        stdout_text = completed.stdout.decode("utf-8", errors="replace")
        stderr_text = completed.stderr.decode("utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        exit_code = "TIMEOUT"
        stderr_text = f"اجرا بیش از {MAX_RUNTIME} ثانیه طول کشید و متوقف شد."
    except Exception:
        stderr_text = traceback.format_exc()

    duration = time.time() - started

    result_lines += [
        "نتیجه اجرای کد Arena",
        "=" * 60,
        f"فایل: {name}",
        f"شروع: {datetime.fromtimestamp(started, TEHRAN):%Y-%m-%d %H:%M:%S} (تهران)",
        f"مدت: {duration:.1f} ثانیه",
        f"کد خروج: {exit_code}",
        f"پایتون: {sys.version.split()[0]} — {sys.executable}",
        f"هش فایل: {job_hash}",
        "",
        "----- خروجی (stdout) -----",
        stdout_text.rstrip() or "(خالی)",
        "",
        "----- خطاها (stderr) -----",
        stderr_text.rstrip() or "(خالی)",
        "",
    ]
    result_text = "\n".join(result_lines)

    out_name = f"{target.stem}_result.txt"
    try:
        (OUT / out_name).write_text(result_text, encoding="utf-8")
        (OUT / "last_result.txt").write_text(result_text, encoding="utf-8")
    except OSError as exc:
        log(f"نوشتن نتیجه ممکن نشد: {exc}")

    state = load_state()
    state[name] = {
        "hash": job_hash,
        "ran_at": now_text(),
        "duration_s": round(duration, 1),
        "exit_code": exit_code,
    }
    save_state(state)

    log(f"✅ پایان اجرا: {name} (کد خروج {exit_code}) → out/{out_name}")


# --------------------------------------------------------------- حلقه اصلی -

def scan_once(pending: dict[str, tuple[int, float]]) -> None:
    """یک بار پوشه را می‌خواند و کارهای آماده را اجرا می‌کند."""
    if PAUSE.exists():
        return

    state = load_state()
    try:
        candidates = sorted(CODES.glob("job_*.py"))
    except OSError:
        return

    for path in candidates:
        name = path.name
        if name in state:
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue

        previous = pending.get(name)
        now = time.time()
        if previous is None or previous[0] != size:
            # هنوز در حال نوشتن/سینک است؛ منتظر می‌مانیم
            pending[name] = (size, now)
            continue
        if now - previous[1] < SETTLE_SECONDS:
            continue

        pending.pop(name, None)
        run_job(path)


def main() -> None:
    for directory in (BASE, CODES, DONE, OUT):
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            print(f"ساخت پوشه ممکن نشد: {directory} ({exc})", file=sys.stderr)

    log("Arena Bridge راه‌اندازی شد.")
    log(f"پوشه ورودی: {CODES}")
    log(f"پوشه نتایج: {OUT}")
    log(f"فاصله بررسی: {POLL_SECONDS} ثانیه")

    single_pass = "--once" in sys.argv
    pending: dict[str, tuple[int, float]] = {}
    last_status = 0.0

    while True:
        try:
            if time.time() - last_status > 10:
                write_status("در حال اجرا (watcher فعال است)")
                last_status = time.time()
            scan_once(pending)
        except Exception:
            log("خطای غیرمنتظره در حلقه ناظر:")
            log(traceback.format_exc())

        if single_pass:
            # در حالت تست، چند بار پشت سر هم بررسی می‌کنیم تا فایل‌های تازه پردازش شوند
            for _ in range(8):
                scan_once(pending)
                if not pending:
                    break
                time.sleep(0.3)
            break
        time.sleep(POLL_SECONDS)

    write_status("یک بار بررسی شد و خارج شد (حالت --once)")
    log("ناظر خارج شد.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("ناظر با Ctrl+C متوقف شد.")
