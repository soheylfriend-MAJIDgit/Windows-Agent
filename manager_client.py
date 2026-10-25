# -*- coding: utf-8 -*-
"""کلاینت پس‌زمینه‌ی اتصال Windows Agent به ایجنت مدیریت (Cloudflare Control Plane & D1 Automations).

این ماژول کاملاً مستقل از ``app.py`` و فقط با کتابخانه‌ی استاندارد پایتون نوشته شده است.

مرز امنیتی و قرارداد اتوماسیون‌ها:
  - کدهای اتوماسیون (``job_*.py``) که از کاتالوگ Cloudflare D1 دریافت و اجرا می‌شوند،
    تحت هیچ شرایطی مجاز به تغییر کد پایه Windows Agent (``app.py``, ``manager_client.py``, ``run.bat``)،
    خواندن فایل کلید ``manager_secret.bin`` یا دست‌کاری فایل‌های شخصی خارج از حوزه‌ی کاری خود نیستند.
  - کلید دائمی مدیریت (Bearer Key) و اسرار DPAPI هرگز در متغیرهای محیطی (Environment) زیرفرآیند
    اتوماسیون قرار نمی‌گیرند.

وظایف ماژول:
  ۱. ذخیره‌ی امن ``base_url`` و ``agent_key`` با Windows DPAPI در:
     ``%LOCALAPPDATA%\\Windows-Agent\\manager_secret.bin``
  ۲. ارسال Heartbeat بلافاصله پس از شروع و سپس هر ۳۰ ثانیه به ``POST /heartbeat``
     همراه با ``capabilities.command_plane = True`` و ``capabilities.d1_automations = True``
  ۳. بررسی تست اتصال هر ۵ ثانیه از ``GET /connection-test`` و پاسخ خودکار با
     ``expectedReply`` بدون تغییر (``سلام ایجنت مدیریت.``) به ``POST /connection-test``
  ۴. دریافت فرمان‌های مجاز از ``POST /commands/claim``:
     - ``run_automation``: دریافت مستقیم نسخه‌ی کد از کاتالوگ Cloudflare D1
       (``GET /api/agent/automations/{automationId}/versions/{versionId}``)، بررسی دقیق SHA-256،
       ذخیره در فضای کاری موقت مختص همان فرمان و اجرا بدون هیچ وابستگی به Git یا GitHub
     - ``run_arena_prompt`` و ``sync_and_run_job``: حفظ سازگاری عقب‌رو برای Rollback
  ۵. رعایت سیاست محلی دستی/خودکار Windows Agent (گرفتن تأیید محلی در حالت دستی پیش از اجرا)
  ۶. اجرای زیرفرآیند در Process Group مستقل، خواندن غیرمسدودکننده‌ی stdout با نخ و صف جدا،
     پایش لغو (``GET /commands/{id}`` هر <= ۱.۵ ثانیه)، ``timeoutSeconds``، ``noProgressSeconds`` و
     توقف کامل درخت فرآیند با ``taskkill /PID <pid> /T /F`` پس از بررسی زمان شروع و نام اجرایی فرآیند
  ۷. ثبت مرحله‌به‌مرحله‌ی رخدادها در ``POST /commands/{id}/events`` و ذخیره‌ی تصویرها فقط در
     Google Drive همراه با ارسال فراداده (بدون هیچ بایت تصویر یا Base64) به ``POST /commands/{id}/artifacts``.
"""

from __future__ import annotations

import base64
import ctypes
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import re
import shutil
import signal
import ssl
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

DEFAULT_BASE_URL = "https://windows-agent-management-cloudflare.soheylfriend.workers.dev/api/agent"
DEFAULT_AGENT_ID = "windows-agent-alibatel-main"
DEFAULT_AGENT_NAME = "ایجنت ویندوز اصلی"
DEFAULT_EXPECTED_REPLY = "سلام ایجنت مدیریت."

HEARTBEAT_INTERVAL = 30.0
POLL_INTERVAL = 5.0
COMMAND_CLAIM_INTERVAL = 3.0
CONFIRM_POLL_INTERVAL = 2.0
RUNNING_CONTROL_POLL_INTERVAL = 1.2
HTTP_TIMEOUT = 5.0
BACKOFF_STEPS = (5.0, 15.0, 30.0, 60.0)
MAX_FEEDBACK_ATTEMPTS = 3

# تنظیمات فاز ۴: PaddleOCR محلی و تاب‌آوری قطعی شبکه
OCR_HELPER_TIMEOUT = 45.0
NETWORK_RECHECK_INTERVAL = 60.0
MAX_NETWORK_OUTAGE_SECONDS = 1800.0
LOCAL_VISION_SUBDIR = "vision"
OCR_ALLOWED_ENV_KEYS = ("WINDOWS_AGENT_OCR_PYTHON", "WINDOWS_AGENT_OCR_HELPER")

ALLOWED_COMMAND_TYPES = frozenset({"run_automation", "run_arena_prompt", "sync_and_run_job"})
FORBIDDEN_PAYLOAD_KEYS = frozenset({"shell", "cmd", "command", "script", "code", "executable", "args", "argv"})
FORBIDDEN_ENV_KEYS = frozenset({
    "AGENT_KEY",
    "WAM_AGENT_KEY",
    "MANAGER_AGENT_KEY",
    "MANAGER_SECRET",
    "AUTHORIZATION",
    "GITHUB_TOKEN",
    "GH_TOKEN",
    "CLOUDFLARE_API_TOKEN",
})

JOB_NAME_RE = re.compile(r"^job_[A-Za-z0-9_]+\.py$")
AUTOMATION_ID_RE = re.compile(r"^auto_[A-Za-z0-9_-]{4,60}$")
VERSION_ID_RE = re.compile(r"^av_[A-Za-z0-9_-]{4,60}$")
SHA256_HEX_RE = re.compile(r"^[0-9a-fA-F]{64}$")

ARENA_REQUIRED_STAGES = (
    "policy_check",
    "waiting_confirmation",
    "repository_sync_started",
    "repository_sync_finished",
    "process_started",
    "arena_process_detected",
    "arena_window_ready",
    "prompt_located",
    "prompt_typed",
    "prompt_submitted",
    "response_waiting",
    "result_uploaded",
    "completed",
)

OBSERVABLE_SCREENSHOT_STAGES = frozenset({
    "process_started",
    "arena_process_detected",
    "arena_window_ready",
    "prompt_located",
    "prompt_typed",
    "prompt_submitted",
    "response_waiting",
    "result_uploaded",
    "completed",
})

IS_WINDOWS = os.name == "nt"


def _resolve_state_dir() -> Path:
    if IS_WINDOWS:
        appdata = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        base = Path(appdata) if appdata else (Path.home() / "AppData" / "Local")
    else:
        xdg = os.environ.get("XDG_STATE_HOME")
        base = Path(xdg) if xdg else (Path.home() / ".local" / "state")
    folder = base / "Windows-Agent"
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return folder


STATE_DIR = _resolve_state_dir()
SECRET_FILE = STATE_DIR / "manager_secret.bin"
ACTIVE_COMMAND_FILE = STATE_DIR / "active_command.json"
WORKSPACES_DIR = STATE_DIR / "cmd_workspaces"
VISION_DIR = STATE_DIR / LOCAL_VISION_SUBDIR


def utc_iso_now() -> str:
    """زمان فعلی به فرمت دقیق UTC ISO-8601 با میلی‌ثانیه و پسوند Z."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


# ------------------------------------------------ رمزنگاری DPAPI ویندوز ---

CRYPTPROTECT_UI_FORBIDDEN = 0x01


if IS_WINDOWS:
    from ctypes import wintypes

    class _DATA_BLOB(ctypes.Structure):
        _fields_ = [
            ("cbData", wintypes.DWORD),
            ("pbData", ctypes.POINTER(ctypes.c_char)),
        ]

    class _FILETIME(ctypes.Structure):
        _fields_ = [
            ("dwLowDateTime", wintypes.DWORD),
            ("dwHighDateTime", wintypes.DWORD),
        ]

    _crypt32 = ctypes.windll.crypt32
    _kernel32 = ctypes.windll.kernel32

    _crypt32.CryptProtectData.argtypes = [
        ctypes.POINTER(_DATA_BLOB),
        wintypes.LPCWSTR,
        ctypes.POINTER(_DATA_BLOB),
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(_DATA_BLOB),
    ]
    _crypt32.CryptProtectData.restype = wintypes.BOOL

    _crypt32.CryptUnprotectData.argtypes = [
        ctypes.POINTER(_DATA_BLOB),
        ctypes.POINTER(wintypes.LPWSTR),
        ctypes.POINTER(_DATA_BLOB),
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(_DATA_BLOB),
    ]
    _crypt32.CryptUnprotectData.restype = wintypes.BOOL

    _kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    _kernel32.LocalFree.restype = ctypes.c_void_p


def _make_blob(data: bytes) -> "_DATA_BLOB":
    buf = ctypes.create_string_buffer(data, len(data))
    blob = _DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    blob._buf = buf
    return blob


def dpapi_encrypt(raw: bytes) -> bytes:
    """رمزنگاری بایت‌ها با Windows DPAPI (مختص همان کاربر ویندوز)."""
    if not IS_WINDOWS:
        return b"DPAPI_SIM:" + base64.b64encode(raw)

    in_blob = _make_blob(raw)
    out_blob = _DATA_BLOB()
    ok = _crypt32.CryptProtectData(
        ctypes.byref(in_blob),
        "WindowsAgentManagerSecret",
        None,
        None,
        None,
        CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(out_blob),
    )
    if not ok:
        raise OSError("CryptProtectData failed")
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        if out_blob.pbData:
            _kernel32.LocalFree(ctypes.cast(out_blob.pbData, ctypes.c_void_p))


def dpapi_decrypt(enc: bytes) -> bytes:
    """رمزگشایی بایت‌های ذخیره‌شده با Windows DPAPI."""
    if not IS_WINDOWS:
        if enc.startswith(b"DPAPI_SIM:"):
            return base64.b64decode(enc[len(b"DPAPI_SIM:"):])
        raise ValueError("Invalid non-Windows secret format")

    in_blob = _make_blob(enc)
    out_blob = _DATA_BLOB()
    ok = _crypt32.CryptUnprotectData(
        ctypes.byref(in_blob),
        None,
        None,
        None,
        None,
        CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(out_blob),
    )
    if not ok:
        raise OSError("CryptUnprotectData failed")
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        if out_blob.pbData:
            _kernel32.LocalFree(ctypes.cast(out_blob.pbData, ctypes.c_void_p))


# -------------------------------------------- مدیریت پیکربندی و Secret ---

def normalize_base_url(url: str | None) -> str:
    """نرمال‌سازی آدرس پایه‌ی API ایجنت مدیریت به فرم ``https://.../api/agent``."""
    raw = str(url or "").strip()
    if not raw:
        return DEFAULT_BASE_URL
    raw = raw.rstrip("/")
    for suffix in ("/ping", "/heartbeat", "/connection-test", "/commands/claim", "/commands"):
        if raw.endswith(suffix):
            raw = raw[: -len(suffix)].rstrip("/")
    if not raw.endswith("/api/agent"):
        if raw.endswith("/api"):
            raw = raw + "/agent"
        else:
            raw = raw + "/api/agent"
    return raw


def mask_key(agent_key: str | None) -> str:
    """نمایش امن پیشوند کلید بدون افشای کلید کامل."""
    key = str(agent_key or "").strip()
    if not key:
        return ""
    if len(key) <= 24:
        return key[:8] + "…"
    return key[:24] + "…"


def _extract_key_tag(agent_key: str) -> str:
    m = re.search(r"ak_([A-Za-z0-9_-]{4,16})", agent_key or "")
    if m:
        return m.group(1)[:8].lower()
    return hashlib.sha256((agent_key or "").encode("utf-8")).hexdigest()[:8]


def parse_config_input(base_url: str | None, key_or_json: str | None) -> tuple[str, str]:
    """ورودی کاربر (کلید خام یا JSON کپی‌شده از سایت مدیریت) را به (base_url, agent_key) تبدیل می‌کند."""
    raw_text = str(key_or_json or "").strip()
    url_candidate = str(base_url or "").strip()

    if raw_text.startswith("{"):
        try:
            parsed = json.loads(raw_text)
            if isinstance(parsed, dict):
                raw_text = str(parsed.get("agent_key") or parsed.get("key") or "").strip()
                if parsed.get("base_url"):
                    url_candidate = str(parsed.get("base_url")).strip()
        except ValueError:
            pass

    if raw_text.lower().startswith("bearer "):
        raw_text = raw_text[7:].strip()

    return normalize_base_url(url_candidate), raw_text


def save_secret(base_url: str | None, key_or_json: str | None, agent_id: str | None = None) -> dict:
    """ذخیره‌ی امن ``base_url`` و ``agent_key`` با DPAPI در ``manager_secret.bin``."""
    norm_url, clean_key = parse_config_input(base_url, key_or_json)
    if not clean_key:
        existing = load_secret()
        if existing and existing.get("agent_key"):
            clean_key = existing["agent_key"]
        else:
            raise ValueError("کلید ایجنت (agent_key) وارد نشده است.")

    if len(clean_key) < 12 or " " in clean_key:
        raise ValueError("ساختار کلید ایجنت معتبر نیست.")

    payload = {
        "base_url": norm_url,
        "agent_key": clean_key,
        "agent_id": str(agent_id or DEFAULT_AGENT_ID).strip() or DEFAULT_AGENT_ID,
        "updated_at": time.time(),
    }
    raw_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    enc_bytes = dpapi_encrypt(raw_bytes)

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp_path = SECRET_FILE.with_suffix(".tmp")
    tmp_path.write_bytes(enc_bytes)
    tmp_path.replace(SECRET_FILE)

    return {
        "base_url": norm_url,
        "key_prefix": mask_key(clean_key),
        "has_key": True,
    }


def load_secret() -> dict | None:
    """خواندن و رمزگشایی ``manager_secret.bin``. اگر وجود نداشته باشد ``None`` برمی‌گرداند."""
    if not SECRET_FILE.exists():
        return None
    try:
        enc_bytes = SECRET_FILE.read_bytes()
        if not enc_bytes:
            return None
        raw_bytes = dpapi_decrypt(enc_bytes)
        data = json.loads(raw_bytes.decode("utf-8"))
        if not isinstance(data, dict):
            return None
        agent_key = str(data.get("agent_key") or "").strip()
        if not agent_key:
            return None
        return {
            "base_url": normalize_base_url(data.get("base_url")),
            "agent_key": agent_key,
            "agent_id": str(data.get("agent_id") or DEFAULT_AGENT_ID).strip() or DEFAULT_AGENT_ID,
        }
    except Exception:
        return None


def clear_secret() -> None:
    """حذف فایل کلید ذخیره‌شده."""
    try:
        if SECRET_FILE.exists():
            SECRET_FILE.unlink()
    except OSError:
        pass


def has_secret() -> bool:
    return load_secret() is not None


# ------------------------------------ پاک‌سازی اطلاعات حساس از لاگ ---

_REDACT_PATTERNS = (
    (re.compile(r"wam_agent_[A-Za-z0-9._\-]+"), "wam_agent_[REDACTED]"),
    (re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s\"']+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-]{16,}"), r"\1[REDACTED]"),
    (re.compile(r"\b\d{8,12}:[A-Za-z0-9_\-]{30,}\b"), "[TELEGRAM_TOKEN_REDACTED]"),
    (re.compile(r"(?i)(cookie\s*[:=]\s*)[^\r\n]+"), r"\1[REDACTED]"),
    (re.compile(r"[A-Za-z]:\\Users\\[^\\/\s\"']+"), r"%USERPROFILE%"),
)


def redact_sensitive(text: str | None, max_len: int = 1800) -> str:
    """حذف هرگونه کلید، توکن، هدر Authorization و مسیر کامل کاربر پیش از ارسال به D1."""
    cleaned = str(text or "")
    for pattern, repl in _REDACT_PATTERNS:
        cleaned = pattern.sub(repl, cleaned)
    cleaned = cleaned.strip()
    if len(cleaned) > max_len:
        cleaned = cleaned[: max_len - 1] + "…"
    return cleaned


# ------------------------------------ شبکه با Proxy و TLS Fallback ---

def _system_proxy() -> str | None:
    try:
        import app as _app
        return _app._system_proxy()
    except Exception:
        pass
    for key in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy", "ALL_PROXY"):
        val = os.environ.get(key)
        if val:
            return val
    return None


def _request_once(
    method: str,
    url: str,
    agent_key: str,
    payload: dict | None,
    timeout: float,
    insecure: bool,
) -> tuple[bool, int, dict, bool]:
    """یک تلاش HTTP (GET یا POST). خروجی: (ok, status_code, data_dict, cert_problem)."""
    handlers: list = []
    proxy = _system_proxy()
    if proxy:
        handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    if insecure:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        handlers.append(urllib.request.HTTPSHandler(context=ctx))
    else:
        try:
            import certifi  # type: ignore
            ctx = ssl.create_default_context(cafile=certifi.where())
            handlers.append(urllib.request.HTTPSHandler(context=ctx))
        except Exception:
            pass

    opener = urllib.request.build_opener(*handlers)
    headers = {
        "Authorization": f"Bearer {agent_key}",
        "Accept": "application/json",
        "User-Agent": "Windows-Agent/1.8 (Windows NT 10.0; Win64; x64)",
    }
    body_bytes = None
    if payload is not None:
        headers["Content-Type"] = "application/json; charset=utf-8"
        body_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    req = urllib.request.Request(url, data=body_bytes, headers=headers, method=method)
    try:
        with opener.open(req, timeout=timeout) as resp:
            code = getattr(resp, "status", 200) or 200
            raw = resp.read().decode("utf-8", "replace")
            try:
                parsed = json.loads(raw or "{}")
            except ValueError:
                parsed = {"raw": raw[:400]}
            if not isinstance(parsed, dict):
                parsed = {"data": parsed}
            return (200 <= code < 300), int(code), parsed, False
    except urllib.error.HTTPError as exc:
        code = int(getattr(exc, "code", 500) or 500)
        try:
            raw_err = exc.read().decode("utf-8", "replace")
            parsed = json.loads(raw_err or "{}")
        except (ValueError, OSError):
            parsed = {}
        if not isinstance(parsed, dict):
            parsed = {}
        return False, code, parsed, False
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", None)
        if isinstance(reason, ssl.SSLError) or "CERTIFICATE_VERIFY_FAILED" in str(exc):
            return False, 0, {"error": str(reason or exc)}, True
        return False, 0, {"error": str(reason or exc)}, False
    except (ssl.SSLError, OSError) as exc:
        if isinstance(exc, ssl.SSLError) or "CERTIFICATE_VERIFY_FAILED" in str(exc):
            return False, 0, {"error": str(exc)}, True
        return False, 0, {"error": str(exc)}, False


def _http_json(
    method: str,
    url: str,
    agent_key: str,
    payload: dict | None = None,
    timeout: float = HTTP_TIMEOUT,
) -> tuple[bool, int, dict]:
    """فراخوانی HTTP با پشتیبانی از پروکسی ویندوز و تلاش مجدد بدون بررسی گواهی در صورت خطای TLS."""
    ok, code, data, cert_problem = _request_once(method, url, agent_key, payload, timeout, False)
    if not cert_problem:
        return ok, code, data
    ok2, code2, data2, _ = _request_once(method, url, agent_key, payload, timeout, True)
    if isinstance(data2, dict):
        data2["_tls_insecure"] = True
    return ok2, code2, data2


# ------------------------------------ اعتبارسنجی امنیتی فرمان و مسیر ---

def _get_codes_dir() -> Path:
    try:
        import app as _app
        return _app.ensure_codes_dir()
    except Exception:
        desktop = Path.home() / "Desktop"
        codes = desktop / "CODES"
        codes.mkdir(parents=True, exist_ok=True)
        return codes


def _get_screenshots_dir() -> Path:
    try:
        import app as _app
        folder, _ = _app.resolve_screenshot_dir()
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        return folder
    except Exception:
        folder = Path.home() / "Desktop" / "ScreenShots"
        folder.mkdir(parents=True, exist_ok=True)
        return folder


def _create_command_workspace(cmd_id: str) -> Path:
    """ایجاد پوشه‌ی کاری موقت و ایزوله برای فرمان در ``%LOCALAPPDATA%\\Windows-Agent\\cmd_workspaces``."""
    safe_cmd = re.sub(r"[^A-Za-z0-9_-]", "_", cmd_id or "cmd")[:60]
    ws = (WORKSPACES_DIR / safe_cmd).resolve()
    ws.mkdir(parents=True, exist_ok=True)
    return ws


def validate_command_security(cmd: dict, codes_dir: Path | None = None) -> tuple[bool, str, Path | None, str]:
    """بررسی allowlist نوع فرمان، نبود فیلدهای اجرایی آزاد و صحت ساختار فرمان.

    خروجی: ``(ok, job_name, resolved_job_path, reject_reason)``
    """
    if not isinstance(cmd, dict):
        return False, "", None, "ساختار فرمان نامعتبر است."

    cmd_type = str(cmd.get("type") or "").strip()
    if cmd_type not in ALLOWED_COMMAND_TYPES:
        return False, "", None, f"نوع فرمان «{cmd_type}» در allowlist مجاز نیست."

    payload = cmd.get("payload")
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        return False, "", None, "فیلد payload باید یک شیء JSON باشد."

    forbidden_found = FORBIDDEN_PAYLOAD_KEYS.intersection(payload.keys())
    if forbidden_found:
        return False, "", None, f"فیلدهای غیرمجاز در payload: {', '.join(sorted(forbidden_found))}"

    if cmd_type == "run_arena_prompt":
        job_name = str(payload.get("jobName") or cmd.get("jobName") or "job_arena.py").strip()
        if job_name != "job_arena.py":
            return False, job_name, None, "فرمان run_arena_prompt فقط مجاز به اجرای job_arena.py است."
    else:
        job_name = str(payload.get("jobName") or cmd.get("jobName") or "").strip()

    if not job_name or "/" in job_name or "\\" in job_name or ".." in job_name or ":" in job_name:
        return False, job_name, None, f"نام فایل کار «{job_name}» شامل کاراکترهای مسیر غیرمجاز است."

    if not JOB_NAME_RE.match(job_name):
        return False, job_name, None, f"نام فایل «{job_name}» با الگوی مجاز job_*.py مطابقت ندارد."

    if cmd_type == "run_automation":
        auto_id = str(payload.get("automationId") or "").strip()
        ver_id = str(payload.get("versionId") or "").strip()
        ver_num = payload.get("version")
        sha256_hex = str(payload.get("sourceSha256") or "").strip()
        endpoint = str(payload.get("sourceEndpoint") or "").strip()
        src_truth = str(payload.get("sourceOfTruth") or "cloudflare_d1").strip()

        if not AUTOMATION_ID_RE.match(auto_id):
            return False, job_name, None, "شناسه اتوماسیون (automationId) معتبر نیست."
        if not VERSION_ID_RE.match(ver_id):
            return False, job_name, None, "شناسه نسخه اتوماسیون (versionId) معتبر نیست."
        if not isinstance(ver_num, int) or isinstance(ver_num, bool) or ver_num < 1:
            return False, job_name, None, "شماره نسخه اتوماسیون (version) معتبر نیست."
        if not SHA256_HEX_RE.match(sha256_hex):
            return False, job_name, None, "فرمت هش SHA-256 کد اتوماسیون معتبر نیست."
        if src_truth != "cloudflare_d1":
            return False, job_name, None, f"منبع کد اتوماسیون ({src_truth}) مجاز نیست؛ فقط cloudflare_d1 پذیرفته می‌شود."
        expected_endpoint = f"/api/agent/automations/{auto_id}/versions/{ver_id}"
        if (
            not endpoint.startswith("/api/agent/automations/")
            or "://" in endpoint
            or endpoint.startswith("//")
            or ".." in endpoint
            or "\\" in endpoint
            or "?" in endpoint
            or "#" in endpoint
            or endpoint != expected_endpoint
        ):
            return False, job_name, None, "آدرس sourceEndpoint غیرمجاز است؛ فقط مسیر نسبی دقیق اتوماسیون در D1 مجاز است."

    base_codes = (codes_dir or _get_codes_dir()).resolve()
    candidate = (base_codes / job_name).resolve()
    if candidate.parent != base_codes:
        return False, job_name, None, "مسیر فایل خارج از پوشه مجاز Desktop\\CODES است."

    return True, job_name, candidate, ""


# ------------------------------------ مدیریت فرآیند و توقف ایمن Tree ---

def _get_process_start_marker(pid: int) -> float | None:
    """زمان شروع فرآیند را برای جلوگیری از تصاحب مجدد PID (PID reuse) برمی‌گرداند."""
    if pid <= 0:
        return None
    if IS_WINDOWS:
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = _kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
        if not handle:
            return None
        try:
            creation = _FILETIME()
            exit_t = _FILETIME()
            kernel_t = _FILETIME()
            user_t = _FILETIME()
            ok = _kernel32.GetProcessTimes(
                handle,
                ctypes.byref(creation),
                ctypes.byref(exit_t),
                ctypes.byref(kernel_t),
                ctypes.byref(user_t),
            )
            if not ok:
                return None
            ticks = (int(creation.dwHighDateTime) << 32) | int(creation.dwLowDateTime)
            return (ticks - 116444736000000000) / 10_000_000.0
        finally:
            _kernel32.CloseHandle(handle)
    else:
        stat_path = Path(f"/proc/{pid}/stat")
        if not stat_path.exists():
            return None
        try:
            raw = stat_path.read_text(encoding="utf-8", errors="ignore")
            after_comm = raw.rsplit(")", 1)[-1].split()
            return float(after_comm[19])
        except Exception:
            return None


def _get_process_exe_name(pid: int) -> str:
    """نام فایل اجرایی فرآیند را برای بررسی هویت PID برمی‌گرداند."""
    if pid <= 0:
        return ""
    if IS_WINDOWS:
        try:
            import app as _app
            return (_app._process_name(pid) or "").lower()
        except Exception:
            return ""
    else:
        comm_path = Path(f"/proc/{pid}/comm")
        try:
            return comm_path.read_text(encoding="utf-8", errors="ignore").strip().lower()
        except Exception:
            return ""


def is_tracked_process_alive(pid: int, expected_marker: float | None) -> bool:
    """بررسی می‌کند آیا فرآیند با همان PID، همان زمان شروع و مفسر پایتون هنوز زنده است."""
    if pid <= 0:
        return False
    current_marker = _get_process_start_marker(pid)
    if current_marker is None:
        return False
    if expected_marker is not None and abs(current_marker - expected_marker) > 2.0:
        return False
    exe_name = _get_process_exe_name(pid)
    if exe_name and "python" not in exe_name:
        return False
    return True


def spawn_job_process(
    job_path: Path,
    cwd_dir: Path,
    extra_env: dict[str, str] | None = None,
) -> subprocess.Popen:
    """اجرای فایل کار در Process Group مستقل با محیط پاک‌سازی‌شده (بدون هیچ کلید مدیریتی)."""
    env = {
        k: v
        for k, v in os.environ.items()
        if (
            k.upper() not in FORBIDDEN_ENV_KEYS
            and not k.upper().startswith("WAM_AGENT_")
            and k.upper() not in OCR_ALLOWED_ENV_KEYS
        )
    }
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    if isinstance(extra_env, dict):
        for key in OCR_ALLOWED_ENV_KEYS:
            val = extra_env.get(key)
            if isinstance(val, str) and val.strip():
                env[key] = val.strip()

    kwargs: dict = {
        "cwd": str(cwd_dir),
        "stdout": subprocess.PIPE,
        "stderr": subprocess.STDOUT,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "env": env,
    }
    if IS_WINDOWS:
        flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200) | getattr(
            subprocess, "CREATE_NO_WINDOW", 0x08000000
        )
        kwargs["creationflags"] = flags
    else:
        kwargs["start_new_session"] = True

    return subprocess.Popen([sys.executable, "-u", str(job_path)], **kwargs)


def terminate_tree(
    proc: subprocess.Popen | None,
    expected_marker: float | None = None,
    timeout_seconds: float = 20.0,
) -> bool:
    """توقف درخت فرآیند با taskkill یا process group، با سقف زمانی اختیاری."""
    if proc is None:
        return False
    if proc.poll() is not None:
        return True

    deadline = max(0.1, float(timeout_seconds))
    started = time.monotonic()
    pid = int(proc.pid)
    if expected_marker is not None and not is_tracked_process_alive(pid, expected_marker):
        return False

    if IS_WINDOWS:
        try:
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                text=True,
                timeout=max(0.1, min(15.0, deadline * 0.75)),
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except Exception:
            pass
    else:
        try:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

    remaining = max(0.0, deadline - (time.monotonic() - started))
    if remaining > 0:
        try:
            proc.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            try:
                proc.kill()
            except Exception:
                pass
    else:
        try:
            proc.kill()
        except Exception:
            pass
    return True


# ------------------------------------ PaddleOCR محلی ایزوله و بررسی Preflight ---

_vision_override_python: Path | None = None
_vision_override_helper: Path | None = None
_vision_initialized_once: bool = False


def get_default_vision_paths(vision_root: Path | None = None) -> tuple[Path, Path, Path]:
    """مسیرهای استاندارد مفسر پایتون، فایل helper و فیکسچر تست در ``%LOCALAPPDATA%\\Windows-Agent\\vision``."""
    root = vision_root or VISION_DIR
    if IS_WINDOWS:
        py_path = root / ".venv" / "Scripts" / "python.exe"
    else:
        py_path = root / ".venv" / "bin" / "python"
    helper_path = root / "paddle_ocr_helper.py"
    fixture_path = root / "cache" / "selftest_fixture.png"
    return py_path, helper_path, fixture_path


def _vision_install_marker_ready() -> bool:
    """نصب‌کننده فقط پس از self-test آفلاین موفق marker می‌نویسد؛ آن را برای Heartbeat می‌خوانیم."""
    py_path, helper_path, fixture_path = get_default_vision_paths()
    marker = VISION_DIR / "vision_ready.json"
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("ok") is not True or not data.get("testedAt"):
            return False
        for path in (py_path, helper_path, fixture_path):
            safe, _ = _is_path_safely_inside_vision(path)
            if not safe:
                return False
        return True
    except Exception:
        return False


def _clear_vision_install_marker() -> None:
    try:
        (VISION_DIR / "vision_ready.json").unlink(missing_ok=True)
    except OSError:
        pass


def set_vision_path_overrides(
    ocr_python: str | Path | None = None,
    ocr_helper: str | Path | None = None,
) -> None:
    """تنظیم مسیرهای جایگزین OCR (برای تست‌های Preflight، Symlink و Timeout)."""
    global _vision_override_python, _vision_override_helper
    _vision_override_python = Path(ocr_python) if ocr_python is not None else None
    _vision_override_helper = Path(ocr_helper) if ocr_helper is not None else None


def ensure_vision_runtime_initialized(force: bool = False) -> dict:
    """راه‌اندازی اولیه‌ی پوشه ایزوله ``%LOCALAPPDATA%\\Windows-Agent\\vision`` بدون نوشتن هیچ فایلی کنار ``app.py``."""
    global _vision_initialized_once
    if _vision_initialized_once and not force:
        py_p, hlp_p, fix_p = get_default_vision_paths()
        return {
            "ok": py_p.exists() and hlp_p.exists() and fix_p.exists(),
            "vision_root": str(VISION_DIR),
            "ocr_python": str(py_p),
            "ocr_helper": str(hlp_p),
            "fixture": str(fix_p),
        }

    try:
        from tools.vision.install_vision import ensure_vision_runtime
        res = ensure_vision_runtime(install_packages=False, log_fn=lambda *_a, **_k: None)
        _vision_initialized_once = True
        return res
    except Exception as exc:
        return {
            "ok": False,
            "vision_root": str(VISION_DIR),
            "error": str(exc),
        }


def _is_path_safely_inside_vision(candidate: Path, vision_root: Path | None = None) -> tuple[bool, str]:
    """بررسی امنیتی مسیر OCR: باید مطلق، موجود و دقیقاً داخل ``%LOCALAPPDATA%\\Windows-Agent\\vision`` باشد (بدون Symlink/Reparse به بیرون)."""
    root = (vision_root or VISION_DIR).resolve()
    raw_str = str(candidate or "").strip()
    if not raw_str:
        return False, "مسیر فایل OCR خالی است."

    if not candidate.is_absolute():
        return False, f"مسیر فایل OCR باید مطلق (Absolute) باشد: {candidate}"

    # بررسی عدم وجود اجزای .. در مسیر خام
    if ".." in candidate.parts:
        return False, f"مسیر فایل OCR نباید شامل '..' باشد: {candidate}"

    # بررسی Symlink / Reparse point روی خود فایل یا پوشه‌های والد
    def _is_reparse(path: Path) -> bool:
        try:
            if path.is_symlink():
                return True
            if IS_WINDOWS:
                import ctypes
                attrs = ctypes.windll.kernel32.GetFileAttributesW(str(path))
                if attrs == 0xFFFFFFFF:
                    return False
                return bool(attrs & 0x400)  # FILE_ATTRIBUTE_REPARSE_POINT
            is_junction = getattr(path, "is_junction", None)
            return bool(is_junction()) if callable(is_junction) else False
        except Exception:
            return False

    try:
        if _is_reparse(candidate):
            target = candidate.resolve()
            if not target.is_relative_to(root):
                return False, f"استفاده از Symlink/Reparse به خارج از پوشه مجاز vision رد شد: {candidate} -> {target}"
            return False, f"فایل اجرایی/اسکریپت OCR نباید Symlink/Reparse باشد: {candidate}"
    except OSError as exc:
        return False, f"خطا در بررسی Symlink مسیر OCR: {exc}"

    if not candidate.exists() or not candidate.is_file():
        return False, f"فایل مورد نیاز OCR وجود ندارد: {candidate}"

    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        return False, f"خطا در بازگشایی مسیر واقعی OCR: {exc}"

    if not resolved.is_relative_to(root) or root not in resolved.parents:
        return False, f"مسیر فایل OCR خارج از پوشه مجاز {root} است: {resolved}"

    # بررسی والدها بین resolved و root برای اطمینان از نبود Reparse/Symlink به بیرون
    cur = candidate
    while cur != cur.parent and cur != root:
        if _is_reparse(cur):
            target = cur.resolve()
            if not target.is_relative_to(root):
                return False, f"یکی از پوشه‌های والد OCR از نوع Symlink/Reparse خارج‌شونده است: {cur} -> {target}"
            return False, f"یکی از پوشه‌های والد OCR از نوع Symlink/Reparse است: {cur}"
        cur = cur.parent

    return True, ""


def invoke_local_ocr(
    image_path: str | Path,
    ocr_python: Path | None = None,
    ocr_helper: Path | None = None,
    timeout: float = OCR_HELPER_TIMEOUT,
    offline: bool = True,
) -> tuple[bool, dict, str]:
    """اجرای امن ``paddle_ocr_helper.py`` با سقف زمانی <= ۴۵ ثانیه و توقف درخت فرآیند در صورت Timeout."""
    def_py, def_hlp, _ = get_default_vision_paths()
    py_exe = ocr_python or _vision_override_python or def_py
    hlp_script = ocr_helper or _vision_override_helper or def_hlp

    ok_py, err_py = _is_path_safely_inside_vision(py_exe)
    if not ok_py:
        return False, {}, err_py

    ok_hlp, err_hlp = _is_path_safely_inside_vision(hlp_script)
    if not ok_hlp:
        return False, {}, err_hlp

    img_p = Path(str(image_path or "").strip())
    existed_before = img_p.exists() and img_p.is_file()

    bounded_timeout = max(0.2, min(float(timeout or OCR_HELPER_TIMEOUT), OCR_HELPER_TIMEOUT))

    clean_env = {
        k: v
        for k, v in os.environ.items()
        if k.upper() not in FORBIDDEN_ENV_KEYS and not k.upper().startswith("WAM_AGENT_")
    }
    clean_env["PYTHONIOENCODING"] = "utf-8"
    clean_env["PYTHONUTF8"] = "1"
    if offline:
        clean_env["WINDOWS_AGENT_OCR_OFFLINE"] = "1"

    cmd_args = [str(py_exe), "-u", str(hlp_script), "--image", str(image_path), "--json"]
    if offline:
        cmd_args.append("--offline")

    kwargs: dict = {
        "cwd": str(VISION_DIR),
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "env": clean_env,
    }
    if IS_WINDOWS:
        flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200) | getattr(
            subprocess, "CREATE_NO_WINDOW", 0x08000000
        )
        kwargs["creationflags"] = flags
    else:
        kwargs["start_new_session"] = True

    proc = subprocess.Popen(cmd_args, **kwargs)
    start_marker = _get_process_start_marker(int(proc.pid))
    try:
        stdout_raw, stderr_raw = proc.communicate(timeout=bounded_timeout)
    except subprocess.TimeoutExpired:
        terminate_tree(proc, start_marker)
        return (
            False,
            {"timedOut": True, "pid": proc.pid},
            f"اجرای PaddleOCR محلی پس از {bounded_timeout} ثانیه دچار Timeout شد و درخت فرآیند متوقف گردید.",
        )

    if existed_before and not img_p.exists():
        return False, {}, "خطای امنیتی: فایل تصویر ورودی نباید توسط helper حذف شود."

    raw_out = (stdout_raw or "").strip()
    if not raw_out:
        err_tail = (stderr_raw or "").strip()[-300:]
        return False, {}, f"خروجی JSON از paddle_ocr_helper دریافت نشد (exit={proc.returncode}): {err_tail}"

    try:
        parsed = json.loads(raw_out)
    except ValueError as exc:
        return False, {}, f"خروجی stdout در paddle_ocr_helper یک JSON معتبر نیست: {exc}"

    if not isinstance(parsed, dict):
        return False, {}, "ساختار JSON خروجی paddle_ocr_helper باید یک شیء دیکشنری باشد."

    if proc.returncode != 0 or not parsed.get("ok"):
        err_msg = str(parsed.get("error") or (stderr_raw or "").strip() or f"exit code {proc.returncode}")
        return False, parsed, err_msg

    if parsed.get("engine") != "paddleocr":
        return False, parsed, f"موتور OCR نامعتبر است: {parsed.get('engine')}"

    items = parsed.get("items")
    if not isinstance(items, list):
        return False, parsed, "فیلد items در خروجی OCR باید لیست باشد."

    for item in items:
        if not isinstance(item, dict):
            return False, parsed, "هر آیتم در items باید دیکشنری باشد."
        txt = item.get("text")
        conf = item.get("confidence")
        bounds = item.get("bounds")
        if not isinstance(txt, str) or not txt.strip():
            return False, parsed, "فیلد text در آیتم OCR معتبر نیست."
        if not isinstance(conf, (int, float)) or not (0.0 <= float(conf) <= 1.0):
            return False, parsed, f"مقدار confidence خارج از بازه [0, 1] است: {conf}"
        if (
            not isinstance(bounds, list)
            or len(bounds) != 4
            or not all(isinstance(v, (int, float)) for v in bounds)
        ):
            return False, parsed, f"مختصات bounds باید آرایه ۴تایی [left, top, right, bottom] باشد: {bounds}"

    return True, parsed, ""


def verify_vision_preflight(
    ocr_python: Path | None = None,
    ocr_helper: Path | None = None,
    timeout: float = 15.0,
) -> tuple[bool, dict, str]:
    """بررسی Preflight پیش از اجرای ``job_arena.py``: صحت مسیرها، عدم فرار با Symlink و اجرای Self-test روی تصویر تست محلی."""
    def _failed(details: dict, message: str) -> tuple[bool, dict, str]:
        with _lock:
            _runtime_info["arena_vision_ocr_ready"] = False
        _clear_vision_install_marker()
        return False, details, message

    def_py, def_hlp, fixture_path = get_default_vision_paths()
    py_exe = ocr_python or _vision_override_python or def_py
    hlp_script = ocr_helper or _vision_override_helper or def_hlp

    ok_py, err_py = _is_path_safely_inside_vision(py_exe)
    if not ok_py:
        return _failed({"ocr_python": str(py_exe), "ocr_helper": str(hlp_script)}, err_py)

    ok_hlp, err_hlp = _is_path_safely_inside_vision(hlp_script)
    if not ok_hlp:
        return _failed({"ocr_python": str(py_exe), "ocr_helper": str(hlp_script)}, err_hlp)

    if not fixture_path.exists():
        return _failed({}, "تصویر فیکسچر OCR موجود نیست؛ نصب ایزوله را با tools/vision/install_vision.py --install-packages تکمیل کنید.")

    ok_run, ocr_data, err_run = invoke_local_ocr(
        fixture_path,
        ocr_python=py_exe,
        ocr_helper=hlp_script,
        timeout=timeout,
        offline=True,
    )
    if not ok_run:
        return _failed(
            {"ocr_python": str(py_exe), "ocr_helper": str(hlp_script)},
            f"تست اولیه (Self-test) PaddleOCR محلی ناموفق بود: {err_run}",
        )

    items = ocr_data.get("items") or []
    if not items:
        return _failed(
            {"ocr_python": str(py_exe), "ocr_helper": str(hlp_script)},
            "خروجی Self-test در PaddleOCR محلی خالی بود (هیچ متنی تشخیص داده نشد).",
        )

    info = {
        "engine": "paddleocr",
        "localOnly": True,
        "ocr_python": str(py_exe.resolve()),
        "ocr_helper": str(hlp_script.resolve()),
        "itemsCount": len(items),
        "sample": items[:4],
    }
    with _lock:
        _runtime_info["arena_vision_ocr_ready"] = True
        _runtime_info["ocr_engine"] = "paddleocr"
        _runtime_info["ocr_local_only"] = True
    return True, info, ""


def is_vision_ready() -> bool:
    """آیا PaddleOCR محلی واقعاً آماده و از بررسی Preflight عبور کرده است؟"""
    ok, _, _ = verify_vision_preflight(timeout=10.0)
    return ok


# ------------------------------------ تاب‌آوری قطعی شبکه (Network Resilience) ---

_network_probe_override = None
_network_recheck_interval: float = NETWORK_RECHECK_INTERVAL
_local_cancel_event = threading.Event()
_local_cancel_reason: str = ""
_local_cancel_requested_at: float = 0.0


def set_network_probe_override(probe_fn, recheck_interval: float | None = None) -> None:
    """تنظیم تابع شبیه‌ساز وضعیت شبکه و فاصله‌ی بررسی مجدد (برای تست‌های خودکار قطعی و وصل مجدد اینترنت)."""
    global _network_probe_override, _network_recheck_interval
    _network_probe_override = probe_fn
    if recheck_interval is not None:
        _network_recheck_interval = max(0.05, float(recheck_interval))
    else:
        _network_recheck_interval = NETWORK_RECHECK_INTERVAL


def request_local_cancel(reason: str = "توقف فوری توسط کاربر در ویندوز") -> bool:
    """درخواست لغو محلی فوری و idempotent؛ حتی هنگام قطعی کامل اینترنت."""
    global _local_cancel_reason, _local_cancel_requested_at
    with _lock:
        if _local_cancel_event.is_set():
            return False
        _local_cancel_reason = str(reason or "توقف فوری توسط کاربر در ویندوز")
        _local_cancel_requested_at = time.monotonic()
        _local_cancel_event.set()
    return True


def clear_local_cancel() -> None:
    """پاک کردن پرچم لغو محلی پیش از شروع فرمان جدید."""
    global _local_cancel_reason, _local_cancel_requested_at
    with _lock:
        _local_cancel_reason = ""
        _local_cancel_requested_at = 0.0
        _local_cancel_event.clear()


def probe_network_health(base_url: str, agent_key: str, timeout: float = HTTP_TIMEOUT) -> bool:
    """بررسی سبک و سریع سلامت ارتباط با API ایجنت مدیریت با Timeout محدود."""
    if _network_probe_override is not None:
        try:
            return bool(_network_probe_override(base_url, agent_key))
        except Exception:
            return False

    bounded = max(0.5, min(float(timeout or HTTP_TIMEOUT), HTTP_TIMEOUT))
    ok, code, _ = _http_json("GET", f"{base_url}/connection-test", agent_key, None, timeout=bounded)
    if ok or code in (200, 401, 403, 404, 409):
        return True
    return False


def is_network_resilience_ready() -> bool:
    """قابلیت تنها پس از آزمون انتهابه‌انتها در Windows واقعی اعلام می‌شود.

    پیاده‌سازی پایش API مدیریت موجود است؛ تا وقتی pause/resume امنِ UI و آزمون لغو محلی
    با Arena Bridge 7 روی Windows واقعی تأیید نشده، capability عمداً false می‌ماند.
    """
    return bool(_runtime_info.get("network_resilience_ready", False)) and callable(probe_network_health) and (_network_recheck_interval > 0)


# ------------------------------------ وضعیت حافظه و نخ پس‌زمینه ---

_lock = threading.Lock()
_worker_thread: threading.Thread | None = None
_stop_event = threading.Event()
_wake_event = threading.Event()
_api_ref = None
_confirm_handler = None

_answered_test_ids: set[str] = set()
_active_command_id: str | None = None

_runtime_info: dict = {
    "configured": False,
    "base_url": DEFAULT_BASE_URL,
    "key_prefix": "",
    "agent_id": DEFAULT_AGENT_ID,
    "last_heartbeat_at": "",
    "last_test_at": "",
    "last_test_id": "",
    "last_test_reply": "",
    "active_command_id": None,
    "last_command_id": "",
    "last_command_status": "",
    "last_error": "",
    "arena_vision_ocr_ready": False,
    "network_resilience_ready": False,
    "ocr_engine": "paddleocr",
    "ocr_local_only": True,
}


def set_confirm_handler(handler) -> None:
    """تنظیم تابع تأیید محلی سفارشی (برای تست‌های خودکار یا مودال اختصاصی)."""
    global _confirm_handler
    _confirm_handler = handler


def _now_tehran_str(api) -> str:
    try:
        import app as _app
        now = _app.tehran_now()
        return f"{_app.jalali_date(now)} {now:%H:%M:%S}"
    except Exception:
        return time.strftime("%Y-%m-%d %H:%M:%S")


def _set_manager_status(api, connected: bool, note: str, error_msg: str = "") -> None:
    with _lock:
        _runtime_info["last_error"] = error_msg
    if api is not None:
        try:
            api.status["manager"] = bool(connected)
            api.status_note["manager"] = note
        except Exception:
            pass


def get_view_state() -> dict:
    """اطلاعات غیرحساس وضعیت کلاینت مدیریت برای نمایش در UI (بدون هیچ کار شبکه‌ای یا دیسکی سنگین)."""
    with _lock:
        view = dict(_runtime_info)
        view["local_cancel_requested"] = _local_cancel_event.is_set()
        return view


def _refresh_secret_cache(api) -> dict | None:
    cfg = load_secret()
    with _lock:
        if cfg:
            _runtime_info["configured"] = True
            _runtime_info["base_url"] = cfg["base_url"]
            _runtime_info["key_prefix"] = mask_key(cfg["agent_key"])
            _runtime_info["agent_id"] = cfg.get("agent_id") or DEFAULT_AGENT_ID
        else:
            _runtime_info["configured"] = False
            _runtime_info["base_url"] = DEFAULT_BASE_URL
            _runtime_info["key_prefix"] = ""
            _runtime_info["agent_id"] = DEFAULT_AGENT_ID
    if not cfg:
        _set_manager_status(api, False, "در انتظار کلید", "")
    return cfg


NETWORK_READY_SCHEMA = 1
NETWORK_READY_MARKER = STATE_DIR / "network_ready.json"
NETWORK_TEST_KEYS = (
    "drop_before_ui",
    "waited_full_cycle",
    "zero_ui_actions_offline",
    "safe_resume",
    "single_prompt_send",
    "no_false_no_progress",
    "unrecoverable_failed_cleanly",
    "local_cancel_under_2s",
)


def _network_report_root() -> Path | None:
    """Use the app's Google Drive logs folder (or its normal Desktop\\logs fallback)."""
    try:
        import app as _app
        root, _drive_used = _app.resolve_report_dir()
        return Path(root) / "network_resilience_tests"
    except Exception:
        return None


def _network_ready_marker_valid(api=None) -> bool:
    """Accept only a recent Windows live-acceptance report bound to this build and intact report hash."""
    try:
        if NETWORK_READY_MARKER.is_symlink() or not NETWORK_READY_MARKER.is_file():
            return False
        marker = json.loads(NETWORK_READY_MARKER.read_text(encoding="utf-8"))
        if sys.platform != "win32":
            return False
        if not isinstance(marker, dict) or marker.get("schemaVersion") != NETWORK_READY_SCHEMA:
            return False
        if marker.get("status") != "passed" or marker.get("platform") != "win32":
            return False
        tests = marker.get("tests")
        if not isinstance(tests, dict) or set(tests) != set(NETWORK_TEST_KEYS):
            return False
        if any(tests.get(key) is not True for key in NETWORK_TEST_KEYS):
            return False
        version_path = Path(__file__).resolve().parent / "version.txt"
        current_version = version_path.read_text(encoding="utf-8").strip()
        if marker.get("appVersion") != current_version:
            return False
        current_commit = ""
        if api is not None:
            current_commit = str((getattr(api, "build", None) or {}).get("commit") or "")
        if not current_commit or marker.get("buildCommit") != current_commit:
            return False
        created = datetime.fromisoformat(str(marker.get("createdAt") or "").replace("Z", "+00:00"))
        age_seconds = (datetime.now(timezone.utc) - created.astimezone(timezone.utc)).total_seconds()
        if created.tzinfo is None or age_seconds < -60 or age_seconds > 30 * 86400:
            return False
        report_name = str(marker.get("reportName") or "")
        if not re.fullmatch(r"network_acceptance_[A-Za-z0-9_-]+\.json", report_name):
            return False
        configured_root = _network_report_root()
        if configured_root is None:
            return False
        report_root = configured_root.resolve()
        report_candidate = report_root / report_name
        if report_candidate.is_symlink():
            return False
        report_path = report_candidate.resolve()
        if report_path.parent != report_root or not report_path.is_file():
            return False
        raw = report_path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != marker.get("reportSha256"):
            return False
        report = json.loads(raw.decode("utf-8"))
        if (
            not isinstance(report, dict)
            or report.get("schemaVersion") != NETWORK_READY_SCHEMA
            or report.get("status") != "passed"
            or report.get("platform") != "win32"
            or report.get("appVersion") != current_version
            or report.get("buildCommit") != current_commit
            or report.get("reportId") != marker.get("reportId")
            or report.get("createdAt") != marker.get("createdAt")
            or report.get("tests") != tests
        ):
            return False
        evidence = report.get("evidence")
        if not isinstance(evidence, dict) or any(key not in evidence for key in NETWORK_TEST_KEYS):
            return False
        evidence_dir_name = f"network_acceptance_{report.get('reportId')}_evidence"
        if not re.fullmatch(r"network_acceptance_[0-9a-f]{32}_evidence", evidence_dir_name):
            return False
        evidence_dir_candidate = report_root / evidence_dir_name
        if evidence_dir_candidate.is_symlink():
            return False
        evidence_dir = evidence_dir_candidate.resolve()
        if evidence_dir.parent != report_root or not evidence_dir.is_dir():
            return False
        total_evidence_bytes = 0
        for key in NETWORK_TEST_KEYS:
            item = evidence.get(key)
            if not isinstance(item, dict):
                return False
            filename = str(item.get("file") or "")
            if not re.fullmatch(re.escape(evidence_dir_name) + "/" + re.escape(key) + r"\.[a-z0-9]{1,8}", filename):
                return False
            evidence_candidate = report_root / filename
            if evidence_candidate.is_symlink():
                return False
            evidence_path = evidence_candidate.resolve()
            if evidence_path.parent != evidence_dir or not evidence_path.is_file():
                return False
            size = evidence_path.stat().st_size
            if size <= 0 or size > 12 * 1024 * 1024 or size != int(item.get("sizeBytes", -1)):
                return False
            total_evidence_bytes += size
            if hashlib.sha256(evidence_path.read_bytes()).hexdigest() != item.get("sha256"):
                return False
        if total_evidence_bytes > 80 * 1024 * 1024:
            return False
        obs = report.get("observations") if isinstance(report.get("observations"), dict) else {}
        offline_seconds = float(obs.get("offlineSeconds", 0))
        local_cancel_seconds = float(obs.get("localCancelSeconds", 99))
        if not math.isfinite(offline_seconds) or offline_seconds < NETWORK_RECHECK_INTERVAL:
            return False
        if not math.isfinite(local_cancel_seconds) or not 0 <= local_cancel_seconds <= 2.0:
            return False
        if int(obs.get("uiActionsDuringOutage", -1)) != 0 or int(obs.get("promptSendCount", 0)) != 1:
            return False
        if obs.get("unrecoverableFinalStatus") != "failed":
            return False
        return True
    except Exception:
        return False


def _network_preflight_ok(cfg: dict, api=None) -> bool:
    """Require a valid Windows acceptance marker and a fresh authenticated Manager API probe."""
    if not _network_ready_marker_valid(api):
        return False
    ok, code, data = _http_json("GET", f"{cfg['base_url']}/connection-test", cfg["agent_key"], None, timeout=2.5)
    # Require an authenticated successful response matching the documented endpoint schema;
    # 401/403/404 must never count as a healthy preflight.
    return bool(ok and 200 <= code < 300 and isinstance(data, dict) and "test" in data)


def _build_heartbeat_payload(api, agent_id: str) -> dict:
    try:
        version = (Path(__file__).resolve().parent / "version.txt").read_text(encoding="utf-8").strip() or "unknown"
    except OSError:
        version = "unknown"
    commit = ""
    auto_mode = False
    busy = None
    internet = True
    drive = True

    with _lock:
        active_cmd = _active_command_id

    if api is not None:
        try:
            b = getattr(api, "build", None) or {}
            version = str(b.get("version") or version)
            commit = str(b.get("commit") or "")
            auto_mode = bool((getattr(api, "settings", None) or {}).get("auto", False))
            busy = active_cmd or getattr(api, "busy", None)
            st = getattr(api, "status", None) or {}
            internet = bool(st.get("internet", True))
            drive = bool(st.get("drive", True))
        except Exception:
            busy = active_cmd
    else:
        busy = active_cmd

    vision_ready = bool(_runtime_info.get("arena_vision_ocr_ready", False)) or _vision_install_marker_ready()
    network_ready = bool(is_network_resilience_ready())
    return {
        "agentId": agent_id,
        "name": DEFAULT_AGENT_NAME,
        "platform": "windows",
        "version": version,
        "commit": commit,
        "status": "online",
        "capabilities": {
            "check_collab": True,
            "run_new": True,
            "run_single": True,
            "take_screenshot": True,
            "open_report": True,
            "telegram_queue": True,
            "command_plane": True,
            "d1_automations": True,
            # OCR تا پس از نصب/گرم‌سازی و self-test آفلاین واقعی true نمی‌شود.
            "arena_vision_ocr": vision_ready,
            "network_resilience": network_ready,
            "ocr_engine": "paddleocr",
            "ocr_local_only": True,
        },
        "state": {
            "auto_mode": auto_mode,
            "busy": busy,
            "internet": internet,
            "drive": drive,
        },
        "message": f"در حال اجرای فرمان {active_cmd}" if active_cmd else "Windows Agent آماده است",
    }


def _extract_error_message(data: dict, code: int) -> str:
    err = data.get("error")
    if isinstance(err, dict):
        msg = str(err.get("message") or err.get("code") or "")
        if msg:
            return msg
    elif isinstance(err, str) and err:
        return err
    return f"HTTP {code}" if code else "خطای شبکه"


def _extract_error_code(data: dict) -> str:
    err = data.get("error")
    if isinstance(err, dict):
        return str(err.get("code") or "")
    return ""


def send_heartbeat_once(api, cfg: dict | None = None) -> tuple[bool, int, dict]:
    """ارسال یک Heartbeat به ``POST /heartbeat`` همراه با ``command_plane=True`` و ``d1_automations=True``."""
    cfg = cfg or _refresh_secret_cache(api)
    if not cfg:
        return False, 0, {"error": "کلید تنظیم نشده است"}

    base_url = cfg["base_url"]
    agent_key = cfg["agent_key"]
    agent_id = cfg.get("agent_id") or DEFAULT_AGENT_ID
    # network_resilience stays disabled until a valid Windows acceptance marker and live authenticated preflight both pass.
    network_preflight = _network_preflight_ok(cfg, api)
    with _lock:
        _runtime_info["network_resilience_ready"] = network_preflight
    payload = _build_heartbeat_payload(api, agent_id)

    ok, code, data = _http_json("POST", f"{base_url}/heartbeat", agent_key, payload, timeout=HTTP_TIMEOUT)

    if not ok and code == 409 and _extract_error_code(data) == "agent_id_key_conflict":
        scoped_id = f"windows-agent-alibatel-{_extract_key_tag(agent_key)}"
        payload["agentId"] = scoped_id
        ok, code, data = _http_json("POST", f"{base_url}/heartbeat", agent_key, payload, timeout=HTTP_TIMEOUT)
        if ok:
            try:
                save_secret(base_url, agent_key, agent_id=scoped_id)
                with _lock:
                    _runtime_info["agent_id"] = scoped_id
            except Exception:
                pass

    if ok:
        stamp = _now_tehran_str(api)
        with _lock:
            _runtime_info["last_heartbeat_at"] = stamp
            _runtime_info["last_error"] = ""
        _set_manager_status(api, True, "وصل", "")
        return True, code, data

    if code == 401:
        _set_manager_status(api, False, "کلید نامعتبر", _extract_error_message(data, code))
    elif code == 403:
        _set_manager_status(api, False, "دسترسی ناکافی", _extract_error_message(data, code))
    else:
        _set_manager_status(api, False, "قطع", _extract_error_message(data, code))
    return False, code, data


def poll_connection_test_once(api, cfg: dict | None = None) -> tuple[bool, int, dict]:
    """بررسی ``GET /connection-test`` و در صورت وجود تست، ارسال پاسخ به ``POST /connection-test``."""
    cfg = cfg or _refresh_secret_cache(api)
    if not cfg:
        return False, 0, {"error": "کلید تنظیم نشده است"}

    base_url = cfg["base_url"]
    agent_key = cfg["agent_key"]

    ok, code, data = _http_json("GET", f"{base_url}/connection-test", agent_key, None, timeout=HTTP_TIMEOUT)
    if not ok:
        if code == 401:
            _set_manager_status(api, False, "کلید نامعتبر", _extract_error_message(data, code))
        elif code == 403:
            _set_manager_status(api, False, "دسترسی ناکافی", _extract_error_message(data, code))
        else:
            _set_manager_status(api, False, "قطع", _extract_error_message(data, code))
        return False, code, data

    _set_manager_status(api, True, "وصل", "")
    test_obj = data.get("test")
    if not isinstance(test_obj, dict):
        return True, code, data

    test_id = str(test_obj.get("id") or "").strip()
    if not test_id:
        return True, code, data

    with _lock:
        if test_id in _answered_test_ids:
            return True, code, {"already_answered": True, "testId": test_id}

    expected_reply = test_obj.get("expectedReply")
    if not isinstance(expected_reply, str) or not expected_reply:
        expected_reply = DEFAULT_EXPECTED_REPLY

    reply_payload = {
        "testId": test_id,
        "message": expected_reply,
    }
    ok_post, code_post, data_post = _http_json(
        "POST", f"{base_url}/connection-test", agent_key, reply_payload, timeout=HTTP_TIMEOUT
    )
    if ok_post or code_post == 409:
        with _lock:
            _answered_test_ids.add(test_id)
            if len(_answered_test_ids) > 200:
                oldest = next(iter(_answered_test_ids))
                _answered_test_ids.discard(oldest)
            if ok_post:
                _runtime_info["last_test_at"] = _now_tehran_str(api)
                _runtime_info["last_test_id"] = test_id
                _runtime_info["last_test_reply"] = expected_reply
                _runtime_info["last_error"] = ""
        if ok_post and api is not None:
            try:
                api.log("تست اتصال ایجنت مدیریت موفق بود")
            except Exception:
                pass
        return ok_post, code_post, data_post

    if code_post == 401:
        _set_manager_status(api, False, "کلید نامعتبر", _extract_error_message(data_post, code_post))
    elif code_post == 403:
        _set_manager_status(api, False, "دسترسی ناکافی", _extract_error_message(data_post, code_post))
    return False, code_post, data_post


# ------------------------------------ API صف فرمان و پایش زنده (Command Plane) ---

def _save_active_command_marker(cmd_id: str, pid: int, start_marker: float | None, job_name: str, seq: int) -> None:
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "command_id": cmd_id,
            "pid": pid,
            "start_marker": start_marker,
            "job_name": job_name,
            "seq": seq,
            "saved_at": utc_iso_now(),
        }
        tmp = ACTIVE_COMMAND_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        tmp.replace(ACTIVE_COMMAND_FILE)
    except OSError:
        pass


def _clear_active_command_marker() -> None:
    try:
        if ACTIVE_COMMAND_FILE.exists():
            ACTIVE_COMMAND_FILE.unlink()
    except OSError:
        pass


def recover_stale_command_if_any(api, cfg: dict | None = None) -> None:
    """بازیابی پس از ری‌استارت: اگر فرمان قبلی زنده نیست، رخداد crash و وضعیت failed گزارش می‌شود."""
    if not ACTIVE_COMMAND_FILE.exists():
        return
    cfg = cfg or _refresh_secret_cache(api)
    if not cfg:
        return
    try:
        info = json.loads(ACTIVE_COMMAND_FILE.read_text(encoding="utf-8"))
    except Exception:
        _clear_active_command_marker()
        return

    cmd_id = str(info.get("command_id") or "").strip()
    pid = int(info.get("pid") or 0)
    marker = info.get("start_marker")
    seq = max(2, int(info.get("seq") or 2) + 1)

    if not cmd_id:
        _clear_active_command_marker()
        return

    if pid > 0 and is_tracked_process_alive(pid, marker):
        return

    base_url = cfg["base_url"]
    agent_key = cfg["agent_key"]
    msg = "فرآیند اجرای فرمان پس از راه‌اندازی مجدد Windows Agent زنده نبود (توقف غیرمنتظره)."
    _http_json(
        "POST",
        f"{base_url}/commands/{cmd_id}/events",
        agent_key,
        {
            "seq": seq,
            "stage": "crash_recovery",
            "level": "fatal",
            "message": msg,
            "occurredAt": utc_iso_now(),
            "data": {"pid": pid, "autoStop": True},
        },
        timeout=HTTP_TIMEOUT,
    )
    _http_json(
        "POST",
        f"{base_url}/commands/{cmd_id}",
        agent_key,
        {
            "status": "failed",
            "seq": seq + 1,
            "stage": "crash_recovery",
            "message": msg,
            "error": msg,
            "result": {"recoveredAfterRestart": True, "pid": pid},
        },
        timeout=HTTP_TIMEOUT,
    )
    _clear_active_command_marker()


class _CommandSession:
    """مدیریت چرخه‌ی کامل یک فرمان دریافتی از ایجنت مدیریت."""

    def __init__(self, api, cfg: dict, cmd: dict) -> None:
        self.api = api
        self.base_url = cfg["base_url"]
        self.agent_key = cfg["agent_key"]
        self.cmd = cmd
        self.cmd_id = str(cmd.get("id") or "").strip()
        self.cmd_type = str(cmd.get("type") or "").strip()
        self.payload = cmd.get("payload") if isinstance(cmd.get("payload"), dict) else {}
        self.timeout_seconds = max(5.0, min(3600.0, float(cmd.get("timeoutSeconds") or 600.0)))
        self.no_progress_seconds = max(5.0, min(self.timeout_seconds, float(cmd.get("noProgressSeconds") or 120.0)))
        self.auto_stop_on_anomaly = bool(cmd.get("autoStopOnAnomaly", True))
        self.requires_confirmation = bool(cmd.get("requiresConfirmation", True))
        self.seq = 1
        self.cancel_requested = False
        self.cancel_reason = ""
        self.emitted_stages: set[str] = set()
        self.last_progress_mono = time.monotonic()
        self.network_paused = False
        self.network_pause_started: float | None = None
        self.last_network_probe = 0.0

    def next_seq(self) -> int:
        self.seq = min(999_999, self.seq + 1)
        return self.seq

    def mark_progress(self) -> None:
        self.last_progress_mono = time.monotonic()

    def emit_event(
        self,
        stage: str,
        message: str,
        level: str = "info",
        data: dict | None = None,
        take_shot: bool = False,
    ) -> bool:
        """ثبت یک رخداد مرحله‌ای در ``POST /commands/{id}/events`` و در صورت نیاز گرفتن اسکرین‌شات."""
        seq = self.next_seq()
        self.emitted_stages.add(stage)
        self.mark_progress()
        clean_msg = redact_sensitive(message, 1900)
        safe_data = data if isinstance(data, dict) else {}

        body = {
            "seq": seq,
            "stage": stage,
            "level": level if level in ("debug", "info", "warning", "error", "fatal") else "info",
            "message": clean_msg,
            "occurredAt": utc_iso_now(),
            "data": safe_data,
        }
        ok, _, resp = _http_json(
            "POST",
            f"{self.base_url}/commands/{self.cmd_id}/events",
            self.agent_key,
            body,
            timeout=HTTP_TIMEOUT,
        )
        if ok and isinstance(resp, dict) and resp.get("cancelRequested"):
            self.cancel_requested = True

        if take_shot or stage in OBSERVABLE_SCREENSHOT_STAGES:
            self.capture_stage_screenshot(stage)

        self.poll_control()
        return ok

    def update_state(
        self,
        status: str,
        stage: str,
        message: str,
        error: str | None = None,
        result: dict | None = None,
    ) -> tuple[bool, int, dict]:
        """به‌روزرسانی وضعیت فرمان در ``POST /commands/{id}``."""
        seq = self.next_seq()
        self.emitted_stages.add(stage)
        body: dict = {
            "status": status,
            "seq": seq,
            "stage": stage,
            "message": redact_sensitive(message, 950),
        }
        if error is not None:
            body["error"] = redact_sensitive(error, 3800)
        if result is not None:
            body["result"] = result
        return _http_json(
            "POST",
            f"{self.base_url}/commands/{self.cmd_id}",
            self.agent_key,
            body,
            timeout=HTTP_TIMEOUT,
        )

    def poll_control(self) -> bool:
        """بررسی لغو محلی بی‌درنگ، سپس دریافت کنترل از سرور با timeout کوتاه."""
        if _local_cancel_event.is_set():
            with _lock:
                self.cancel_reason = _local_cancel_reason or "لغو محلی توسط کاربر ویندوز"
            self.cancel_requested = True
            return True
        ok, _, data = _http_json(
            "GET",
            f"{self.base_url}/commands/{self.cmd_id}",
            self.agent_key,
            None,
            timeout=0.6,
        )
        if ok and isinstance(data, dict):
            if data.get("cancelRequested"):
                self.cancel_requested = True
                self.cancel_reason = str(data.get("cancelReason") or "درخواست توقف از سایت مدیریت")
            t_sec = data.get("timeoutSeconds")
            if isinstance(t_sec, (int, float)) and t_sec >= 5:
                self.timeout_seconds = float(t_sec)
            np_sec = data.get("noProgressSeconds")
            if isinstance(np_sec, (int, float)) and np_sec >= 5:
                self.no_progress_seconds = float(np_sec)
            if "autoStopOnAnomaly" in data:
                self.auto_stop_on_anomaly = bool(data.get("autoStopOnAnomaly"))
        return self.cancel_requested

    def capture_stage_screenshot(self, stage: str) -> Path | None:
        """گرفتن اسکرین‌شات، ذخیره فقط در Google Drive (یا پوشه اسکرین‌شات) و ارسال فراداده بدون بایت به D1."""
        shots_dir = _get_screenshots_dir()
        utc_stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
        safe_stage = re.sub(r"[^A-Za-z0-9_-]", "_", stage)[:40]
        target_name = f"{utc_stamp}_{safe_stage}.png"
        target_path = shots_dir / target_name

        saved_path: Path | None = None
        try:
            import app as _app
            raw_shot = _app.take_screenshot(shots_dir)
            raw_path = Path(raw_shot)
            if raw_path.exists():
                try:
                    raw_path.replace(target_path)
                    saved_path = target_path
                except OSError:
                    saved_path = raw_path
                    target_name = raw_path.name
        except Exception:
            saved_path = None

        if saved_path is None or not saved_path.exists():
            return None

        try:
            size_bytes = int(saved_path.stat().st_size)
        except OSError:
            size_bytes = 0

        digest = hashlib.sha256(f"{self.cmd_id}:{stage}:{target_name}".encode("utf-8")).hexdigest()[:16]
        artifact_id = f"art_{digest}"

        # هیچ بایت تصویر یا Base64 در این payload وجود ندارد؛ فقط فراداده ارسال می‌شود
        artifact_body = {
            "artifactId": artifact_id,
            "kind": "screenshot",
            "stage": stage,
            "name": target_name,
            "localPath": f"ScreenShots/{target_name}",
            "driveFileId": None,
            "driveUrl": None,
            "mimeType": "image/png",
            "size": size_bytes,
            "occurredAt": utc_iso_now(),
        }
        ok, _, resp = _http_json(
            "POST",
            f"{self.base_url}/commands/{self.cmd_id}/artifacts",
            self.agent_key,
            artifact_body,
            timeout=HTTP_TIMEOUT,
        )
        if ok and isinstance(resp, dict) and resp.get("cancelRequested"):
            self.cancel_requested = True
        self.mark_progress()
        return saved_path


def _ask_local_confirmation(session: _CommandSession, job_name: str) -> str:
    """در حالت دستی، از کاربر تأیید محلی می‌گیرد و هم‌زمان هر ۲ ثانیه لغو فرمان را Poll می‌کند.

    خروجی: ``"approved"`` | ``"rejected"`` | ``"cancelled"``
    """
    if _confirm_handler is not None:
        decision_box: dict = {"done": False, "approved": False}

        def _run_custom() -> None:
            try:
                decision_box["approved"] = bool(_confirm_handler(session.cmd, job_name))
            except Exception:
                decision_box["approved"] = False
            decision_box["done"] = True

        threading.Thread(target=_run_custom, daemon=True).start()
        while not decision_box["done"] and not _stop_event.is_set():
            if _local_cancel_event.is_set() or session.poll_control():
                return "cancelled"
            time.sleep(min(0.2, CONFIRM_POLL_INTERVAL))
        return "approved" if decision_box["approved"] else "rejected"

    if not IS_WINDOWS:
        return "rejected"

    decision_win: dict = {"done": False, "approved": False}
    title = "ایجنت ویندوز — تأیید اجرای فرمان مدیریت"
    cmd_title = str(session.cmd.get("title") or session.cmd_type)
    text = (
        f"یک فرمان از طرف سایت «ایجنت مدیریت» دریافت شد:\n\n"
        f"عنوان: {cmd_title}\n"
        f"نوع فرمان: {session.cmd_type}\n"
        f"فایل هدف: {job_name}\n"
        f"شناسه: {session.cmd_id}\n\n"
        f"چون برنامه در «حالت دستی» است، بدون اجازه تو اجرا نمی‌شود.\n"
        f"آیا اجازه می‌دهی این فرمان الان اجرا شود؟"
    )

    def _show_msgbox() -> None:
        MB_YESNO = 0x00000004
        MB_ICONQUESTION = 0x00000020
        MB_TOPMOST = 0x00040000
        MB_SETFOREGROUND = 0x00010000
        IDYES = 6
        try:
            ans = ctypes.windll.user32.MessageBoxW(
                0,
                text,
                title,
                MB_YESNO | MB_ICONQUESTION | MB_TOPMOST | MB_SETFOREGROUND,
            )
            decision_win["approved"] = (ans == IDYES)
        except Exception:
            decision_win["approved"] = False
        decision_win["done"] = True

    threading.Thread(target=_show_msgbox, daemon=True).start()
    while not decision_win["done"] and not _stop_event.is_set():
        if _local_cancel_event.is_set() or session.poll_control():
            return "cancelled"
        session.mark_progress()
        time.sleep(CONFIRM_POLL_INTERVAL)

    if session.cancel_requested:
        return "cancelled"
    return "approved" if decision_win["approved"] else "rejected"


def _fetch_and_prepare_d1_automation(
    api,
    session: _CommandSession,
    job_name: str,
) -> tuple[str, Path | None, Path | None, str]:
    """دریافت کد اتوماسیون از D1 API، راستی‌آزمایی SHA-256 و نوشتن در فضای کاری موقت فرمان (بدون Git).

    خروجی: ``(status_tag, script_path, workspace_dir, error_reason)``
    که ``status_tag`` یکی از ``"ok"`` | ``"rejected"`` | ``"failed"`` | ``"cancelled"`` است.
    """
    payload = session.payload
    auto_id = str(payload.get("automationId") or "").strip()
    ver_id = str(payload.get("versionId") or "").strip()
    ver_num = int(payload.get("version") or 0)
    expected_sha256 = str(payload.get("sourceSha256") or "").strip().lower()
    endpoint = str(payload.get("sourceEndpoint") or "").strip()

    session.emit_event(
        "d1_source_fetch_started",
        f"دریافت نسخه {ver_num} اتوماسیون {job_name} از کاتالوگ Cloudflare D1…",
        level="info",
        data={"automationId": auto_id, "versionId": ver_id, "version": ver_num},
    )
    if job_name == "job_arena.py":
        session.emitted_stages.add("repository_sync_started")

    if session.cancel_requested:
        return "cancelled", None, None, "لغو توسط سایت مدیریت"

    # ساخت آدرس کامل از روی sourceEndpoint نسبی تاییدشده
    rel_after_agent = endpoint[len("/api/agent"):]
    fetch_url = f"{session.base_url}{rel_after_agent}"

    ok, code, data = _http_json("GET", fetch_url, session.agent_key, None, timeout=HTTP_TIMEOUT)
    if not ok:
        err_msg = _extract_error_message(data, code)
        return "failed", None, None, f"دریافت کد اتوماسیون از D1 ناموفق بود ({err_msg})."

    resp_auto_id = str(data.get("automationId") or "").strip()
    resp_ver_id = str(data.get("versionId") or "").strip()
    resp_ver_num = data.get("version")
    resp_job_name = str(data.get("jobName") or "").strip()
    resp_sha256 = str(data.get("sourceSha256") or "").strip().lower()
    source_code = data.get("sourceCode")

    if (
        resp_auto_id != auto_id
        or resp_ver_id != ver_id
        or int(resp_ver_num or -1) != ver_num
        or resp_job_name != job_name
        or not JOB_NAME_RE.match(resp_job_name)
    ):
        return (
            "rejected",
            None,
            None,
            "مشخصات اتوماسیون/نسخه/نام فایل برگشتی از D1 با فرمان تطابق ندارد.",
        )

    if not isinstance(source_code, str) or not source_code.strip():
        return "rejected", None, None, "متن کد Python برگشتی از D1 خالی یا نامعتبر است."

    actual_sha256 = hashlib.sha256(source_code.encode("utf-8")).hexdigest().lower()
    if resp_sha256 != expected_sha256 or actual_sha256 != expected_sha256:
        return (
            "rejected",
            None,
            None,
            f"عدم تطابق SHA-256 کد اتوماسیون (انتظار: {expected_sha256[:12]}…، محاسبه‌شده: {actual_sha256[:12]}…).",
        )

    workspace_dir = _create_command_workspace(session.cmd_id)
    script_path = (workspace_dir / job_name).resolve()
    if script_path.parent != workspace_dir.resolve():
        shutil.rmtree(workspace_dir, ignore_errors=True)
        return "rejected", None, None, "مسیر فایل در فضای کاری موقت معتبر نیست."

    script_bytes = source_code.encode("utf-8")
    script_path.write_bytes(script_bytes)

    # به‌روزرسانی کپی نمایشی در Desktop\CODES برای دیده‌شدن در کتابخانه کدها (بدون هیچ فایل کنار app.py)
    try:
        codes_dir = _get_codes_dir().resolve()
        mirror_path = (codes_dir / job_name).resolve()
        if mirror_path.parent == codes_dir:
            mirror_path.write_bytes(script_bytes)
            if api is not None:
                try:
                    api._scan_codes()
                except Exception:
                    pass
    except Exception:
        pass

    session.emit_event(
        "d1_source_verified",
        f"کد {job_name} (نسخه {ver_num}) از D1 دریافت و صحت SHA-256 ({actual_sha256[:12]}…) تأیید شد.",
        level="info",
        data={
            "automationId": auto_id,
            "versionId": ver_id,
            "version": ver_num,
            "jobName": job_name,
            "sourceSha256": actual_sha256,
            "sizeBytes": len(script_bytes),
        },
    )
    if job_name == "job_arena.py":
        session.emitted_stages.add("repository_sync_finished")

    return "ok", script_path, workspace_dir, ""


def _sync_collab_repository(api, session: _CommandSession, job_name: str) -> tuple[bool, Path | None, str]:
    """همگام‌سازی مخزن ایجنت همکار (مسیر قدیمی Git-based برای سازگاری عقب‌رو)."""
    session.emit_event(
        "repository_sync_started",
        f"شروع دریافت آخرین نسخه‌ی مخزن ایجنت همکار برای {job_name}…",
        level="info",
    )
    if session.cancel_requested:
        return False, None, "لغو توسط سایت مدیریت"

    codes_dir = _get_codes_dir()
    target_path = (codes_dir / job_name).resolve()

    try:
        import app as _app
        owner, repo, branch = ("soheylfriend-MAJIDgit", "Windows-Agent-hamkar", "arena/beecb74c-windows-agent-hamkar")
        if api is not None:
            try:
                c_owner, c_repo, c_branch = api.collab_info()
                if c_owner and c_repo and c_branch:
                    owner, repo, branch = c_owner, c_repo, c_branch
            except Exception:
                pass

        zip_bytes = _app.repo_zip(owner, repo, branch)
        if zip_bytes:
            py_files = _app.extract_py_files(zip_bytes)
            for name, content in py_files.items():
                if JOB_NAME_RE.match(name):
                    dest = (codes_dir / name).resolve()
                    if dest.parent == codes_dir.resolve():
                        dest.write_bytes(content)
            if api is not None:
                try:
                    api._scan_codes()
                except Exception:
                    pass
        elif not target_path.exists():
            return False, None, f"دریافت مخزن همکار ({owner}/{repo}) ممکن نشد و فایل {job_name} در CODES نیست."
    except Exception as exc:
        if not target_path.exists():
            return False, None, f"خطا در همگام‌سازی مخزن همکار: {exc}"

    if not target_path.exists():
        return False, None, f"فایل {job_name} پس از همگام‌سازی در پوشه CODES پیدا نشد."

    session.emit_event(
        "repository_sync_finished",
        f"مخزن ایجنت همکار همگام شد؛ فایل {job_name} آماده اجراست.",
        level="info",
        data={"jobName": job_name, "sizeBytes": target_path.stat().st_size},
    )
    return True, target_path, ""


def _advance_arena_stages_from_line(session: _CommandSession, line: str) -> None:
    """تشخیص مرحله‌های ``job_arena.py`` از خروجی استاندارد با حفظ ترتیب."""
    ordered_before: dict[str, tuple[str, ...]] = {
        "arena_process_detected": (),
        "arena_window_ready": ("arena_process_detected",),
        "prompt_located": ("arena_process_detected", "arena_window_ready"),
        "prompt_typed": ("arena_process_detected", "arena_window_ready", "prompt_located"),
        "prompt_submitted": ("arena_process_detected", "arena_window_ready", "prompt_located", "prompt_typed"),
        "response_waiting": (
            "arena_process_detected",
            "arena_window_ready",
            "prompt_located",
            "prompt_typed",
            "prompt_submitted",
        ),
        "result_uploaded": (
            "arena_process_detected",
            "arena_window_ready",
            "prompt_located",
            "prompt_typed",
            "prompt_submitted",
            "response_waiting",
        ),
    }

    stage_labels = {
        "arena_process_detected": "فرآیند مرورگر و صفحه Arena شناسایی شد.",
        "arena_window_ready": "پنجره Arena آماده و تمام‌صفحه شد.",
        "prompt_located": "کادر ورودی پرامپت در صفحه Arena پیدا شد.",
        "prompt_typed": "متن پرامپت داخل کادر چت Arena قرار گرفت.",
        "prompt_submitted": "پرامپت در Arena ارسال شد.",
        "response_waiting": "در انتظار ثبت پاسخ و پایدار شدن صفحه Arena…",
        "result_uploaded": "اسکرین‌شات و نتیجه در پوشه Google Drive ذخیره شد.",
    }

    detected: list[str] = []
    if "صفحه Arena در مرورگر باز شد" in line or "در حال باز کردن لینک Arena" in line:
        detected.append("arena_process_detected")
    if "تمام‌صفحه" in line or "ARENA_MAXIMIZED" in line or ("صبر " in line and "بارگذاری کامل صفحه" in line):
        detected.append("arena_window_ready")
    if "کادر چت" in line and ("کلیک شد" in line or "پیدا" in line or "تشخیص" in line):
        detected.append("prompt_located")
    if "ARENA_TEXT_VERIFIED" in line or "ARENA_VALUE_VERIFIED" in line or "ARENA_PASTE_VERIFIED" in line:
        detected.append("prompt_typed")
    if "ARENA_SENT_VERIFIED" in line or "ارسال پیام تأیید شد" in line:
        detected.extend(["prompt_typed", "prompt_submitted"])
    if "پیش از اسکرین‌شات" in line:
        detected.append("response_waiting")
    if "اسکرین‌شات ذخیره شد" in line:
        detected.append("result_uploaded")

    for st in detected:
        for prereq in ordered_before.get(st, ()):
            if prereq not in session.emitted_stages:
                session.emit_event(prereq, stage_labels[prereq], level="info", take_shot=True)
        if st not in session.emitted_stages:
            session.emit_event(st, stage_labels[st], level="info", take_shot=True)


def _deliver_bounded_failure_feedback(
    session: _CommandSession,
    job_name: str,
    error_summary: str,
    stdout_lines: list[str],
) -> dict:
    """در صورت شکست ``job_arena.py``، حداکثر ۳ بار تلاش می‌کند بازخورد مبتنی بر شواهد Drive ثبت کند."""
    joined_out = "\n".join(stdout_lines)
    if "بازخورد اجرای ناموفق به ایجنت همکار ارسال شد" in joined_out:
        return {"feedbackSent": True, "handledByJob": True, "attempts": 1}

    shot_path = session.capture_stage_screenshot("failure_evidence")
    err_path = None
    try:
        import app as _app
        err_path = _app.write_error(
            f"شکست اجرای {job_name} ({session.cmd_id})",
            f"{error_summary}\n\nخروجی:\n{redact_sensitive(joined_out, 3000)}",
        )
    except Exception:
        pass

    evidence = []
    if err_path:
        evidence.append(str(err_path.name))
    if shot_path:
        evidence.append(str(shot_path.name))

    attempts = 0
    sent = False
    for attempt in range(1, MAX_FEEDBACK_ATTEMPTS + 1):
        attempts = attempt
        ok = session.emit_event(
            "failure_feedback",
            (
                f"تلاش {attempt} از {MAX_FEEDBACK_ATTEMPTS}: از ایجنت همکار خواسته شد گزارش خطا و "
                f"اسکرین‌شات‌های Google Drive ({'، '.join(evidence) or 'logs/ScreenShots'}) را بررسی و کد را اصلاح کند."
            ),
            level="warning",
            data={
                "attempt": attempt,
                "maxAttempts": MAX_FEEDBACK_ATTEMPTS,
                "evidenceFiles": evidence,
            },
        )
        if ok:
            sent = True
            break
        time.sleep(0.5)

    return {"feedbackSent": sent, "handledByJob": False, "attempts": attempts, "evidenceFiles": evidence}


def execute_claimed_command(api, cfg: dict, cmd: dict) -> str:
    """اجرای کامل یک فرمان ادعاشده طبق ماشین حالت و قوانین امنیتی (D1 یا Git-legacy)."""
    global _active_command_id
    session = _CommandSession(api, cfg, cmd)
    cmd_id = session.cmd_id
    if not cmd_id:
        return "invalid"

    with _lock:
        _active_command_id = cmd_id
        _runtime_info["active_command_id"] = cmd_id
        _runtime_info["last_command_id"] = cmd_id
        _runtime_info["last_command_status"] = "claimed"

    if api is not None:
        try:
            api.busy = f"فرمان مدیریت ({cmd_id})"
            api.log(f"📥 فرمان جدید از ایجنت مدیریت دریافت شد: {cmd.get('title') or session.cmd_type} ({cmd_id})")
        except Exception:
            pass

    cmd_workspace: Path | None = None
    try:
        # ۱. بررسی امنیتی allowlist، ساختار payload و مسیر
        codes_dir = _get_codes_dir()
        sec_ok, job_name, job_path, reject_reason = validate_command_security(cmd, codes_dir)
        if not sec_ok or job_path is None:
            session.emit_event("policy_check", f"رد امنیتی فرمان: {reject_reason}", level="fatal")
            session.update_state(
                "rejected",
                "policy_check",
                reject_reason,
                error=reject_reason,
                result={"rejected": True, "reason": reject_reason},
            )
            with _lock:
                _runtime_info["last_command_status"] = "rejected"
            return "rejected"

        auto_mode = False
        if api is not None:
            try:
                auto_mode = bool((getattr(api, "settings", None) or {}).get("auto", False))
            except Exception:
                auto_mode = False

        session.emit_event(
            "policy_check",
            f"بررسی امنیتی و سیاست اجرا انجام شد (نوع: {session.cmd_type}، فایل: {job_name}، حالت محلی: {'خودکار' if auto_mode else 'دستی'}).",
            level="info",
            data={"commandType": session.cmd_type, "jobName": job_name, "autoMode": auto_mode},
        )
        if session.cancel_requested:
            session.update_state("cancelled", "cancelled", session.cancel_reason or "فرمان پیش از شروع لغو شد.")
            with _lock:
                _runtime_info["last_command_status"] = "cancelled"
            return "cancelled"

        # ۲. رعایت حالت دستی/خودکار محلی Windows Agent
        if not auto_mode and session.requires_confirmation:
            session.update_state(
                "waiting_confirmation",
                "waiting_confirmation",
                "در انتظار تأیید محلی کاربر روی ویندوز…",
            )
            session.emit_event(
                "waiting_confirmation",
                "پنجره تأیید محلی برای کاربر نمایش داده شد؛ منتظر پاسخ کاربر هستیم…",
                level="info",
            )
            decision = _ask_local_confirmation(session, job_name)
            if decision == "cancelled":
                session.update_state("cancelled", "cancelled", session.cancel_reason or "فرمان در زمان انتظار تأیید لغو شد.")
                with _lock:
                    _runtime_info["last_command_status"] = "cancelled"
                return "cancelled"
            if decision != "approved":
                msg_rej = "کاربر در پنل ویندوز اجرای این فرمان را رد کرد."
                session.emit_event("waiting_confirmation", msg_rej, level="warning")
                session.update_state("rejected", "waiting_confirmation", msg_rej, error=msg_rej)
                with _lock:
                    _runtime_info["last_command_status"] = "rejected"
                return "rejected"
        else:
            session.emit_event(
                "waiting_confirmation",
                "حالت خودکار محلی فعال است؛ اجرا طبق تنظیم کاربر ادامه می‌یابد.",
                level="info",
            )

        # ۳. آماده‌سازی کد: مسیر جدید D1 (بدون Git) یا مسیر قدیمی همگام‌سازی مخزن
        run_cwd = codes_dir
        if session.cmd_type == "run_automation":
            prep_status, synced_path, cmd_workspace, prep_err = _fetch_and_prepare_d1_automation(api, session, job_name)
            if session.cancel_requested or prep_status == "cancelled":
                session.update_state("cancelled", "cancelled", session.cancel_reason or "فرمان حین دریافت از D1 لغو شد.")
                with _lock:
                    _runtime_info["last_command_status"] = "cancelled"
                return "cancelled"
            if prep_status == "rejected":
                session.emit_event("d1_hash_verification", prep_err, level="fatal", data={"autoStop": True})
                session.update_state(
                    "rejected",
                    "d1_hash_verification",
                    prep_err,
                    error=prep_err,
                    result={"rejected": True, "reason": prep_err},
                )
                with _lock:
                    _runtime_info["last_command_status"] = "rejected"
                return "rejected"
            if prep_status != "ok" or synced_path is None:
                session.emit_event("d1_source_fetch_started", prep_err, level="fatal", data={"autoStop": True})
                session.update_state("failed", "d1_source_fetch_started", prep_err, error=prep_err)
                with _lock:
                    _runtime_info["last_command_status"] = "failed"
                return "failed"
            if cmd_workspace is not None:
                run_cwd = cmd_workspace
        else:
            sync_ok, synced_path, sync_err = _sync_collab_repository(api, session, job_name)
            if session.cancel_requested:
                session.update_state("cancelled", "cancelled", session.cancel_reason or "فرمان حین همگام‌سازی لغو شد.")
                with _lock:
                    _runtime_info["last_command_status"] = "cancelled"
                return "cancelled"
            if not sync_ok or synced_path is None:
                session.emit_event("repository_sync_finished", sync_err, level="fatal", data={"autoStop": True})
                session.update_state("failed", "repository_sync_finished", sync_err, error=sync_err)
                with _lock:
                    _runtime_info["last_command_status"] = "failed"
                return "failed"

        # ۴. برای Arena فقط: PaddleOCR محلی باید از self-test آفلاین عبور کند.
        arena_ocr_enabled = (job_name == "job_arena.py")
        arena_env: dict[str, str] = {}
        if arena_ocr_enabled:
            ok_ocr, ocr_info, ocr_error = verify_vision_preflight(timeout=15.0)
            if not ok_ocr:
                session.emit_event(
                    "ocr_preflight_failed",
                    f"PaddleOCR محلی آماده نشد؛ فرمان Arena پیش از اجرا متوقف شد: {ocr_error}",
                    level="fatal",
                    data={"engine": "paddleocr", "localOnly": True},
                )
                session.update_state(
                    "failed",
                    "ocr_preflight_failed",
                    "PaddleOCR محلی آماده نیست. پس از نصب دستی و self-test موفق، دوباره تلاش کنید.",
                    error=ocr_error,
                    result={"engine": "paddleocr", "localOnly": True},
                )
                with _lock:
                    _runtime_info["last_command_status"] = "failed"
                return "failed"
            ocr_python = str(ocr_info["ocr_python"])
            ocr_helper = str(ocr_info["ocr_helper"])
            # دو مسیر فقط در subprocess اتوماسیون Arena تزریق می‌شوند؛ هیچ secretی وجود ندارد.
            arena_env = {
                "WINDOWS_AGENT_OCR_PYTHON": ocr_python,
                "WINDOWS_AGENT_OCR_HELPER": ocr_helper,
            }
            session.emit_event(
                "ocr_ready",
                "PaddleOCR محلی آماده است.",
                level="info",
                data={"engine": "paddleocr", "localOnly": True},
            )

        # ۵. شروع فرآیند در Process Group مستقل
        proc = spawn_job_process(synced_path, run_cwd, extra_env=arena_env)
        pid = int(proc.pid)
        start_marker = _get_process_start_marker(pid)
        started_mono = time.monotonic()
        _save_active_command_marker(cmd_id, pid, start_marker, job_name, session.seq)

        session.update_state(
            "running",
            "process_started",
            f"اجرای {job_name} با PID {pid} آغاز شد.",
        )
        session.emit_event(
            "process_started",
            f"فرآیند {job_name} با شناسه PID {pid} در گروه مستقل راه‌اندازی شد.",
            level="info",
            data={"pid": pid, "jobName": job_name},
            take_shot=True,
        )

        # ۵. نخ خواننده‌ی غیرمسدودکننده‌ی stdout
        out_queue: queue.Queue[str | None] = queue.Queue()

        def _stdout_reader() -> None:
            try:
                assert proc.stdout is not None
                for raw_line in iter(proc.stdout.readline, ""):
                    out_queue.put(raw_line)
            except Exception:
                pass
            finally:
                out_queue.put(None)

        threading.Thread(target=_stdout_reader, name=f"cmd-stdout-{cmd_id}", daemon=True).start()

        stdout_lines: list[str] = []
        eof_reached = False
        last_control_poll = time.monotonic()
        fatal_anomaly_reason: str | None = None
        timed_out_reason: str | None = None
        is_arena_job = (session.cmd_type == "run_arena_prompt") or (job_name == "job_arena.py")

        while True:
            drained = 0
            while drained < 40:
                try:
                    item = out_queue.get_nowait()
                except queue.Empty:
                    break
                drained += 1
                if item is None:
                    eof_reached = True
                    break
                line = item.rstrip("\r\n")
                if not line:
                    continue
                stdout_lines.append(line)
                if len(stdout_lines) > 400:
                    del stdout_lines[:-400]
                session.mark_progress()

                clean_line = redact_sensitive(line, 1200)
                if is_arena_job:
                    _advance_arena_stages_from_line(session, clean_line)

                if "ARENA_NO_BROWSER" in clean_line and "arena_process_detected" in session.emitted_stages:
                    fatal_anomaly_reason = "پنجره مرورگر Arena در میانه اجرا ناپدید شد."
                elif "ARENA_TEXT_MISSING" in clean_line or "ARENA_SEND_UNCERTAIN" in clean_line:
                    session.emit_event("stdout_warning", clean_line, level="warning")
                else:
                    session.emit_event("stdout", clean_line, level="info")

                if fatal_anomaly_reason and session.auto_stop_on_anomaly:
                    break

            if fatal_anomaly_reason and session.auto_stop_on_anomaly:
                terminate_tree(proc, start_marker)
                session.emit_event(
                    "fatal_anomaly",
                    fatal_anomaly_reason,
                    level="fatal",
                    data={"autoStop": True},
                    take_shot=True,
                )
                break

            now_mono = time.monotonic()
            elapsed = now_mono - started_mono
            idle_secs = now_mono - session.last_progress_mono

            # پایش سبک مستقل Manager؛ job_arena.py خودش URL Arena را جداگانه می‌سنجد.
            if now_mono - session.last_network_probe >= 5.0:
                session.last_network_probe = now_mono
                manager_online = probe_network_health(session.base_url, session.agent_key, timeout=0.75)
                if not manager_online and not session.network_paused:
                    session.network_paused = True
                    session.network_pause_started = now_mono
                    session.emit_event(
                        "network_paused",
                        "ارتباط با API ایجنت مدیریت قطع است؛ شمارش بی‌پیشرفتی متوقف شد. job باید تا بازگشت اینترنت هیچ تعامل تازه‌ای با Arena نکند.",
                        level="warning",
                        data={"retryAfterSeconds": NETWORK_RECHECK_INTERVAL},
                    )
                elif manager_online and session.network_paused:
                    outage = max(0.0, now_mono - (session.network_pause_started or now_mono))
                    session.network_paused = False
                    session.network_pause_started = None
                    session.last_progress_mono += outage
                    session.emit_event(
                        "network_resumed",
                        "ارتباط با API مدیریت برگشت؛ اجرای job از آخرین مرحله امن ادامه می‌یابد.",
                        level="info",
                        data={"outageSeconds": round(outage, 1)},
                    )

            if elapsed > session.timeout_seconds:
                timed_out_reason = f"زمان اجرای فرمان از سقف مجاز ({int(session.timeout_seconds)} ثانیه) گذشت."
                terminate_tree(proc, start_marker)
                session.emit_event(
                    "timeout",
                    timed_out_reason,
                    level="fatal",
                    data={"timeoutSeconds": session.timeout_seconds, "autoStop": True},
                    take_shot=True,
                )
                break

            if not session.network_paused and idle_secs > session.no_progress_seconds:
                timed_out_reason = f"به مدت {int(session.no_progress_seconds)} ثانیه هیچ پیشرفتی از فرآیند ثبت نشد."
                terminate_tree(proc, start_marker)
                session.emit_event(
                    "no_progress",
                    timed_out_reason,
                    level="fatal",
                    data={"noProgressSeconds": session.no_progress_seconds, "autoStop": True},
                    take_shot=True,
                )
                break

            if (now_mono - last_control_poll) >= RUNNING_CONTROL_POLL_INTERVAL:
                session.poll_control()
                last_control_poll = time.monotonic()
                _save_active_command_marker(cmd_id, pid, start_marker, job_name, session.seq)

            if _local_cancel_event.is_set():
                with _lock:
                    local_reason = _local_cancel_reason or "لغو محلی از پنل ویندوز هنگام قطع اینترنت"
                session.cancel_requested = True
                session.cancel_reason = local_reason

            if session.cancel_requested or _stop_event.is_set():
                if _local_cancel_event.is_set():
                    with _lock:
                        requested_at = _local_cancel_requested_at or time.monotonic()
                    remaining = max(0.1, 2.0 - (time.monotonic() - requested_at))
                    terminate_tree(proc, start_marker, timeout_seconds=remaining)
                else:
                    terminate_tree(proc, start_marker)
                break

            if proc.poll() is not None and eof_reached and out_queue.empty():
                break

            time.sleep(0.1)

        exit_code = proc.poll()
        if exit_code is None:
            terminate_tree(proc, start_marker)
            exit_code = proc.poll()

        duration_s = round(time.monotonic() - started_mono, 2)
        _clear_active_command_marker()

        try:
            import app as _app
            dest_dir, _ = _app.resolve_report_dir()
            Path(dest_dir).mkdir(parents=True, exist_ok=True)
            report_file = Path(dest_dir) / f"{synced_path.stem}_result.txt"
            report_file.write_text(
                f"فرمان مدیریت: {cmd_id}\nفایل: {job_name}\nکد خروج: {exit_code}\nمدت: {duration_s}s\n\n"
                + "\n".join(stdout_lines),
                encoding="utf-8",
            )
        except Exception:
            pass

        result_meta: dict = {
            "exitCode": exit_code,
            "durationSeconds": duration_s,
            "jobName": job_name,
        }
        if session.cmd_type == "run_automation":
            result_meta["automationId"] = session.payload.get("automationId")
            result_meta["versionId"] = session.payload.get("versionId")
            result_meta["version"] = session.payload.get("version")
            result_meta["sourceSha256"] = session.payload.get("sourceSha256")

        # ۶. تعیین وضعیت نهایی و ثبت در D1
        if session.cancel_requested or _stop_event.is_set():
            reason = session.cancel_reason or "توسط کاربر یا سایت مدیریت متوقف شد."
            session.emit_event("cancelled", f"فرآیند متوقف شد: {reason}", level="warning", take_shot=True)
            session.update_state("cancelled", "cancelled", reason, error=reason, result=result_meta)
            with _lock:
                _runtime_info["last_command_status"] = "cancelled"
            return "cancelled"

        if timed_out_reason:
            session.update_state("timed_out", "timed_out", timed_out_reason, error=timed_out_reason, result=result_meta)
            with _lock:
                _runtime_info["last_command_status"] = "timed_out"
            return "timed_out"

        if fatal_anomaly_reason or exit_code != 0:
            err_msg = fatal_anomaly_reason or f"فرآیند {job_name} با کد خروج غیرصفر ({exit_code}) پایان یافت."
            session.emit_event(
                "process_failed",
                err_msg,
                level="fatal",
                data={"exitCode": exit_code, "autoStop": True},
                take_shot=True,
            )
            fb_info = {}
            if is_arena_job:
                fb_info = _deliver_bounded_failure_feedback(session, job_name, err_msg, stdout_lines)
            session.update_state(
                "failed",
                "failed",
                err_msg,
                error=err_msg,
                result={**result_meta, **fb_info},
            )
            with _lock:
                _runtime_info["last_command_status"] = "failed"
            return "failed"

        if is_arena_job:
            for st in ARENA_REQUIRED_STAGES:
                if st != "completed" and st not in session.emitted_stages:
                    session.emit_event(st, f"مرحله {st} تکمیل شد.", level="info", take_shot=True)

        session.emit_event(
            "completed",
            f"اجرای {job_name} با موفقیت در {duration_s} ثانیه کامل شد.",
            level="info",
            data=result_meta,
            take_shot=True,
        )
        session.update_state(
            "succeeded",
            "completed",
            f"فرمان {job_name} با موفقیت اجرا شد.",
            result=result_meta,
        )
        with _lock:
            _runtime_info["last_command_status"] = "succeeded"
        if api is not None:
            try:
                api.log(f"✅ فرمان ایجنت مدیریت با موفقیت انجام شد: {job_name} ({cmd_id})")
            except Exception:
                pass
        return "succeeded"

    finally:
        if cmd_workspace is not None:
            shutil.rmtree(cmd_workspace, ignore_errors=True)
        _clear_active_command_marker()
        with _lock:
            _active_command_id = None
            _runtime_info["active_command_id"] = None
        if api is not None:
            try:
                if getattr(api, "busy", None) == f"فرمان مدیریت ({cmd_id})":
                    api.busy = None
            except Exception:
                pass
        clear_local_cancel()


def wait_for_manager_network(api, cfg: dict) -> bool:
    """تا بازگشت API مدیریت هر ۶۰ ثانیه صبر می‌کند؛ لغو محلی در <=۲ ثانیه پذیرفته می‌شود."""
    announced = False
    while not _stop_event.is_set():
        if _local_cancel_event.is_set():
            return False
        if probe_network_health(cfg["base_url"], cfg["agent_key"], timeout=2.0):
            if announced:
                try:
                    api.log("اتصال ایجنت مدیریت برگشت؛ ادامه از آخرین مرحله امن")
                except Exception:
                    pass
            return True
        if not announced and api is not None:
            try:
                api.log("اتصال ایجنت مدیریت قطع است؛ تعامل تازه‌ای با Arena آغاز نمی‌شود")
            except Exception:
                pass
        announced = True
        _local_cancel_event.wait(NETWORK_RECHECK_INTERVAL)
    return False


def claim_and_run_once(api, cfg: dict | None = None) -> tuple[bool, str]:
    """اگر برنامه مشغول نیست، اتصال را می‌سنجد، سپس یک فرمان را claim و اجرا می‌کند."""
    cfg = cfg or _refresh_secret_cache(api)
    if not cfg:
        return False, "no_secret"

    if not probe_network_health(cfg["base_url"], cfg["agent_key"], timeout=2.0):
        return False, "network_error"

    if api is not None and getattr(api, "busy", None) is not None:
        return True, "busy"
    with _lock:
        if _active_command_id is not None:
            return True, "busy"

    # Reset a previous request before claiming; do not clear again after active_command_id is exposed to UI.
    clear_local_cancel()
    ok, code, data = _http_json(
        "POST",
        f"{cfg['base_url']}/commands/claim",
        cfg["agent_key"],
        {},
        timeout=HTTP_TIMEOUT,
    )
    if not ok:
        if code in (401, 403):
            return False, f"auth_{code}"
        return False, "network_error"

    cmd = data.get("command")
    if not isinstance(cmd, dict) or not cmd.get("id"):
        return True, "idle"

    final_status = execute_claimed_command(api, cfg, cmd)
    return True, final_status


def _worker_loop() -> None:
    """حلقه‌ی پس‌زمینه‌ی Heartbeat (۳۰ ثانیه)، تست اتصال (۵ ثانیه) و Claim فرمان (۳ ثانیه)."""
    last_hb = 0.0
    last_poll = 0.0
    last_claim = 0.0
    hb_interval = HEARTBEAT_INTERVAL
    backoff_idx = 0
    auth_blocked = False
    recovered_once = False

    while not _stop_event.is_set():
        api = _api_ref
        cfg = _refresh_secret_cache(api)

        if not cfg:
            _wake_event.wait(5.0)
            _wake_event.clear()
            last_hb = 0.0
            last_poll = 0.0
            last_claim = 0.0
            backoff_idx = 0
            auth_blocked = False
            continue

        if not recovered_once:
            recovered_once = True
            try:
                recover_stale_command_if_any(api, cfg)
            except Exception:
                pass

        if auth_blocked:
            woke = _wake_event.wait(60.0)
            _wake_event.clear()
            if woke:
                auth_blocked = False
                last_hb = 0.0
                last_poll = 0.0
                last_claim = 0.0
                backoff_idx = 0
            continue

        now = time.monotonic()
        need_hb = (last_hb == 0.0) or ((now - last_hb) >= hb_interval)
        need_poll = (last_poll == 0.0) or ((now - last_poll) >= POLL_INTERVAL)
        need_claim = (last_claim == 0.0) or ((now - last_claim) >= COMMAND_CLAIM_INTERVAL)

        if need_hb:
            ok_hb, code_hb, data_hb = send_heartbeat_once(api, cfg)
            last_hb = time.monotonic()
            if ok_hb:
                backoff_idx = 0
                srv_interval = data_hb.get("heartbeatIntervalSeconds")
                if isinstance(srv_interval, (int, float)) and 10 <= srv_interval <= 300:
                    hb_interval = float(srv_interval)
                if int(data_hb.get("pendingConnectionTests") or 0) > 0:
                    need_poll = True
            else:
                if code_hb in (401, 403):
                    auth_blocked = True
                    continue
                delay = BACKOFF_STEPS[min(backoff_idx, len(BACKOFF_STEPS) - 1)]
                backoff_idx += 1
                _wake_event.wait(delay)
                if _wake_event.is_set():
                    _wake_event.clear()
                    last_hb = 0.0
                    last_poll = 0.0
                    last_claim = 0.0
                    backoff_idx = 0
                continue

        if need_poll and not _stop_event.is_set():
            ok_p, code_p, _ = poll_connection_test_once(api, cfg)
            last_poll = time.monotonic()
            if not ok_p:
                if code_p in (401, 403):
                    auth_blocked = True
                    continue
                delay = BACKOFF_STEPS[min(backoff_idx, len(BACKOFF_STEPS) - 1)]
                backoff_idx += 1
                _wake_event.wait(delay)
                if _wake_event.is_set():
                    _wake_event.clear()
                    last_hb = 0.0
                    last_poll = 0.0
                    last_claim = 0.0
                    backoff_idx = 0
                continue
            else:
                backoff_idx = 0

        if need_claim and not _stop_event.is_set():
            ok_c, status_c = claim_and_run_once(api, cfg)
            last_claim = time.monotonic()
            if not ok_c and status_c in ("auth_401", "auth_403"):
                auth_blocked = True
                continue
            if status_c == "network_error" and not probe_network_health(cfg["base_url"], cfg["agent_key"], timeout=2.0):
                _local_cancel_event.wait(NETWORK_RECHECK_INTERVAL)
                if _local_cancel_event.is_set():
                    clear_local_cancel()
                last_hb = 0.0
                last_poll = 0.0
                last_claim = 0.0
                continue
            if status_c not in ("idle", "busy", "no_secret", "network_error"):
                last_hb = 0.0

        now2 = time.monotonic()
        next_hb_in = max(0.1, hb_interval - (now2 - last_hb))
        next_poll_in = max(0.1, POLL_INTERVAL - (now2 - last_poll))
        next_claim_in = max(0.1, COMMAND_CLAIM_INTERVAL - (now2 - last_claim))
        sleep_for = min(1.0, next_hb_in, next_poll_in, next_claim_in)
        if _wake_event.wait(sleep_for):
            _wake_event.clear()
            last_hb = 0.0
            last_poll = 0.0
            last_claim = 0.0
            backoff_idx = 0
            auth_blocked = False


def start(api=None) -> None:
    """راه‌اندازی idempotent کلاینت پس‌زمینه‌ی ایجنت مدیریت (فقط یک نخ daemon=True)."""
    global _worker_thread, _api_ref
    with _lock:
        if api is not None:
            _api_ref = api
        _stop_event.clear()

    cfg = _refresh_secret_cache(_api_ref)
    if cfg and _api_ref is not None:
        try:
            _api_ref.status.setdefault("manager", False)
            if _api_ref.status_note.get("manager") in (None, "", "در حال بررسی…"):
                _api_ref.status_note["manager"] = "در انتظار"
        except Exception:
            pass

    with _lock:
        if _worker_thread is not None and _worker_thread.is_alive():
            _wake_event.set()
            return
        _worker_thread = threading.Thread(
            target=_worker_loop,
            name="manager-client",
            daemon=True,
        )
        _worker_thread.start()


def stop() -> None:
    """توقف نخ پس‌زمینه در زمان بسته شدن برنامه."""
    _stop_event.set()
    _wake_event.set()


def wake() -> None:
    """بیدار کردن فوری نخ پس‌زمینه برای ارسال آنی Heartbeat، تست اتصال و بررسی صف فرمان."""
    _wake_event.set()


if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) >= 2 and args[0] == "--set-key":
        key_arg = args[1]
        url_arg = args[3] if len(args) >= 4 and args[2] == "--base-url" else DEFAULT_BASE_URL
        info = save_secret(url_arg, key_arg)
        print(json.dumps({"ok": True, **info}, ensure_ascii=False))
    elif args and args[0] == "--clear":
        clear_secret()
        print(json.dumps({"ok": True, "cleared": True}, ensure_ascii=False))
    else:
        cfg_now = load_secret()
        print(
            json.dumps(
                {
                    "configured": bool(cfg_now),
                    "secret_file": str(SECRET_FILE),
                    "base_url": cfg_now["base_url"] if cfg_now else DEFAULT_BASE_URL,
                    "key_prefix": mask_key(cfg_now["agent_key"]) if cfg_now else "",
                    "command_plane": True,
                    "d1_automations": True,
                },
                ensure_ascii=False,
            )
        )
