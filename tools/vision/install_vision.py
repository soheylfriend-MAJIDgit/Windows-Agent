# -*- coding: utf-8 -*-
"""نصب، آماده‌سازی، گرم‌سازی (Warm-up) و بازگردانی (Rollback) محیط ایزوله‌ی PaddleOCR.

مسیر نصب ایزوله (خارج از پوشه‌ی برنامه و بدون دست‌کاری Python اصلی):
    %LOCALAPPDATA%\\Windows-Agent\\vision
        ├── .venv\\
        ├── paddle_ocr_helper.py
        ├── models\\
        └── cache\\
            └── selftest_fixture.png

دستورات:
    python tools/vision/install_vision.py --ensure
    python tools/vision/install_vision.py --install-packages
    python tools/vision/install_vision.py --rollback
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import venv

IS_WINDOWS = os.name == "nt"
THIS_DIR = Path(__file__).resolve().parent
HELPER_SOURCE = THIS_DIR / "paddle_ocr_helper.py"
REQUIREMENTS_SOURCE = THIS_DIR / "requirements-vision.txt"


def get_vision_root() -> Path:
    """مسیر ریشه‌ی ایزوله‌ی vision در %LOCALAPPDATA%\\Windows-Agent\\vision."""
    if IS_WINDOWS:
        appdata = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        base = Path(appdata) if appdata else (Path.home() / "AppData" / "Local")
    else:
        xdg = os.environ.get("XDG_STATE_HOME")
        base = Path(xdg) if xdg else (Path.home() / ".local" / "state")
    return base / "Windows-Agent" / "vision"


def get_venv_python(vision_root: Path | None = None) -> Path:
    root = vision_root or get_vision_root()
    if IS_WINDOWS:
        return root / ".venv" / "Scripts" / "python.exe"
    return root / ".venv" / "bin" / "python"


def get_helper_dest(vision_root: Path | None = None) -> Path:
    root = vision_root or get_vision_root()
    return root / "paddle_ocr_helper.py"


def get_fixture_path(vision_root: Path | None = None) -> Path:
    root = vision_root or get_vision_root()
    return root / "cache" / "selftest_fixture.png"


def _create_isolated_venv(venv_dir: Path, log_fn=print) -> Path:
    py_exe = get_venv_python(venv_dir.parent)
    if py_exe.exists():
        return py_exe

    log_fn(f"[vision] ساخت محیط مجازی ایزوله در: {venv_dir}")
    venv_dir.parent.mkdir(parents=True, exist_ok=True)
    try:
        builder = venv.EnvBuilder(with_pip=False, symlinks=False)
        builder.create(str(venv_dir))
    except Exception:
        # در برخی محیط‌ها کپی مستقیم باینری پایتون یا بدون pip
        subprocess.run(
            [sys.executable, "-m", "venv", "--without-pip", str(venv_dir)],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    if not py_exe.exists():
        # اگر venv در محیط خاص ساخته نشد، باینری پایتون را داخل .venv کپی می‌کنیم (بدون سیم‌لینک به بیرون)
        py_exe.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(sys.executable, py_exe)

    return py_exe


def ensure_vision_runtime(install_packages: bool = False, log_fn=print) -> dict:
    """ایجاد ساختار پوشه‌ها، کپی helper، آماده‌سازی .venv و ساخت تصویر فیکسچر self-test."""
    vision_root = get_vision_root()
    models_dir = vision_root / "models"
    cache_dir = vision_root / "cache"
    venv_dir = vision_root / ".venv"

    for folder in (vision_root, models_dir, cache_dir):
        folder.mkdir(parents=True, exist_ok=True)

    helper_dest = get_helper_dest(vision_root)
    if HELPER_SOURCE.exists():
        shutil.copy2(HELPER_SOURCE, helper_dest)

    py_exe = _create_isolated_venv(venv_dir, log_fn=log_fn)

    # ساخت تصویر fixture واقعی وابسته به Pillow فقط پس از نصب بسته‌های isolated.
    fixture_path = get_fixture_path(vision_root)

    if install_packages and REQUIREMENTS_SOURCE.exists():
        if not (3, 9) <= sys.version_info[:2] <= (3, 11):
            return {
                "ok": False,
                "vision_root": str(vision_root),
                "error": (
                    f"Python {sys.version_info.major}.{sys.version_info.minor} برای نسخه‌های pin شده‌ی PaddlePaddle مناسب نیست؛ "
                    "این نصب‌کننده به Python 3.9 تا 3.11 نیاز دارد. نصب را با Python 3.11 اجرا کنید."
                ),
            }
        log_fn(
            "در حال نصب و دانلود اولیه‌ی مدل‌های محلی PaddleOCR در محیط ایزوله "
            f"({vision_root})... پس از این مرحله، تشخیص متن کاملاً آفلاین انجام می‌شود."
        )
        subprocess.run(
            [str(py_exe), "-m", "ensurepip", "--upgrade"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        install_result = None
        pip_args = [
            str(py_exe), "-m", "pip", "install",
            "--disable-pip-version-check",
            "--prefer-binary",
            "--timeout", "180",
            "--retries", "12",
            "--no-warn-script-location",
            "-r", str(REQUIREMENTS_SOURCE),
        ]
        # Large Windows wheels (for example SciPy) may download slowly or stall temporarily.
        # Keep pip's cache between attempts so rerunning the BAT can resume without starting over.
        for attempt in range(1, 4):
            log_fn(f"[vision] pip install attempt {attempt}/3; network timeout is 180 seconds.")
            install_result = subprocess.run(pip_args, check=False)
            if install_result.returncode == 0:
                break
            if attempt < 3:
                log_fn("[vision] Download failed; waiting 8 seconds, then retrying with pip cache preserved.")
                import time
                time.sleep(8)
        if install_result is None or install_result.returncode != 0:
            code = install_result.returncode if install_result is not None else -1
            return {"ok": False, **{
                "vision_root": str(vision_root),
                "ocr_python": str(py_exe),
                "ocr_helper": str(helper_dest),
                "fixture": str(fixture_path),
                "error": (
                    f"pip install failed after 3 attempts (exit code {code}). "
                    "Rerun install_vision.bat when the connection is stable; the isolated venv and pip cache were kept."
                ),
            }}
        fixture_result = subprocess.run(
            [str(py_exe), str(helper_dest), "--create-fixture", str(fixture_path), "--json"],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        if fixture_result.returncode != 0:
            return {"ok": False, "vision_root": str(vision_root), "error": (fixture_result.stderr or fixture_result.stdout)[-1200:]}
        # Check native DLL imports using the helper's explicit Windows DLL search paths before model downloads.
        paddle_probe = subprocess.run(
            [str(py_exe), str(helper_dest), "--check-install", "--json"],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=45,
        )
        try:
            paddle_check = json.loads(paddle_probe.stdout or "{}")
        except ValueError:
            paddle_check = {"ok": False, "error": (paddle_probe.stderr or paddle_probe.stdout)[-1600:]}
        if paddle_probe.returncode != 0 or not paddle_check.get("ok"):
            return {
                "ok": False,
                "vision_root": str(vision_root),
                "error": (
                    "PaddlePaddle native import check failed before model download. "
                    "The helper added its isolated paddle/libs and numerical-library DLL folders. "
                    "Check the VC++ runtime, Windows version, x64 architecture, CPU AVX support and antivirus quarantine. "
                    f"Details: {paddle_check.get('error') or (paddle_probe.stderr or paddle_probe.stdout)[-1600:]}"
                ),
            }
        log_fn(
            f"Native import passed: Paddle {paddle_check.get('paddleVersion')}, "
            f"PaddleOCR {paddle_check.get('paddleocrVersion')}."
        )

        # Explicitly consented one-time model warm-up; no user screenshot or OCR text leaves this machine.
        log_fn("Downloading the initial CPU OCR model. Only model files are fetched; user images/text are not uploaded.")
        warm_result = subprocess.run(
            [str(py_exe), str(helper_dest), "--image", str(fixture_path), "--json"],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        if warm_result.returncode != 0:
            return {"ok": False, "vision_root": str(vision_root), "error": (warm_result.stderr or warm_result.stdout)[-1200:]}
        try:
            warm_payload = json.loads(warm_result.stdout)
        except ValueError:
            return {"ok": False, "vision_root": str(vision_root), "error": "Warm-up did not return valid JSON"}
        if not warm_payload.get("ok") or not warm_payload.get("items"):
            return {"ok": False, "vision_root": str(vision_root), "error": "PaddleOCR warm-up did not detect fixture text", "selftest": warm_payload}

    return {
        "ok": py_exe.exists() and helper_dest.exists() and fixture_path.exists(),
        "vision_root": str(vision_root),
        "ocr_python": str(py_exe),
        "ocr_helper": str(helper_dest),
        "fixture": str(fixture_path),
    }


def rollback_vision_runtime(log_fn=print) -> dict:
    """حذف و غیرفعال‌سازی کامل فقط پوشه‌ی %LOCALAPPDATA%\\Windows-Agent\\vision بدون لمس کد برنامه یا داده‌های کاربر."""
    vision_root = get_vision_root()
    removed = False
    if vision_root.exists():
        shutil.rmtree(vision_root, ignore_errors=False)
        removed = not vision_root.exists()
        log_fn(f"[vision] پوشه‌ی ایزوله vision با موفقیت حذف و غیرفعال شد: {vision_root}")
    else:
        removed = True
        log_fn(f"[vision] پوشه‌ی vision از قبل وجود نداشت: {vision_root}")
    return {
        "ok": removed,
        "vision_root": str(vision_root),
        "removed": removed,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Windows Agent Isolated Vision Installer")
    parser.add_argument("--ensure", action="store_true", help="Ensure isolated vision runtime and fixture exist")
    parser.add_argument("--install-packages", action="store_true", help="Install pinned requirements-vision.txt into isolated .venv")
    parser.add_argument("--rollback", "--uninstall", action="store_true", dest="rollback", help="Remove only %LOCALAPPDATA%\\Windows-Agent\\vision")
    args = parser.parse_args(argv)

    if args.rollback:
        res = rollback_vision_runtime()
        print(json.dumps(res, ensure_ascii=False))
        return 0 if res.get("ok") else 1

    res = ensure_vision_runtime(install_packages=args.install_packages)
    print(json.dumps(res, ensure_ascii=False))
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
