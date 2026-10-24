# -*- coding: utf-8 -*-
"""کلاینت پس‌زمینه‌ی اتصال Windows Agent به ایجنت مدیریت (Cloudflare Control Plane).

این ماژول کاملاً مستقل از ``app.py`` و فقط با کتابخانه‌ی استاندارد پایتون نوشته شده است.
وظایف:
  ۱. ذخیره‌ی امن ``base_url`` و ``agent_key`` با Windows DPAPI در:
     ``%LOCALAPPDATA%\\Windows-Agent\\manager_secret.bin``
  ۲. ارسال Heartbeat بلافاصله پس از شروع و سپس هر ۳۰ ثانیه به ``POST /heartbeat``
  ۳. بررسی تست اتصال هر ۵ ثانیه از ``GET /connection-test`` و پاسخ خودکار با
     ``expectedReply`` بدون تغییر (``سلام ایجنت مدیریت.``) به ``POST /connection-test``
  ۴. به‌روزرسانی وضعیت در حافظه (RAM) روی ``api.status["manager"]`` و ``api.status_note["manager"]``
     بدون هیچ عملیات شبکه‌ای در نخ اصلی یا ``get_state()``.
"""

from __future__ import annotations

import base64
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import ssl
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
HTTP_TIMEOUT = 5.0
BACKOFF_STEPS = (5.0, 15.0, 30.0, 60.0)

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


# ------------------------------------------------ رمزنگاری DPAPI ویندوز ---

CRYPTPROTECT_UI_FORBIDDEN = 0x01


if IS_WINDOWS:
    from ctypes import wintypes

    class _DATA_BLOB(ctypes.Structure):
        _fields_ = [
            ("cbData", wintypes.DWORD),
            ("pbData", ctypes.POINTER(ctypes.c_char)),
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
    blob._buf = buf  # نگه‌داشتن مرجع تا پایان فراخوانی
    return blob


def dpapi_encrypt(raw: bytes) -> bytes:
    """رمزنگاری بایت‌ها با Windows DPAPI (مختص همان کاربر ویندوز)."""
    if not IS_WINDOWS:
        # جایگزین محلی فقط برای محیط تست غیر ویندوز
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
    for suffix in ("/ping", "/heartbeat", "/connection-test"):
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
        # اگر کاربر فقط آدرس را تغییر داده و کلید قبلی موجود است، کلید قبلی را حفظ کن
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
        "User-Agent": "Windows-Agent/1.7 (Windows NT 10.0; Win64; x64)",
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


# ------------------------------------ وضعیت حافظه و نخ پس‌زمینه ---

_lock = threading.Lock()
_worker_thread: threading.Thread | None = None
_stop_event = threading.Event()
_wake_event = threading.Event()
_api_ref = None

_answered_test_ids: set[str] = set()
_runtime_info: dict = {
    "configured": False,
    "base_url": DEFAULT_BASE_URL,
    "key_prefix": "",
    "agent_id": DEFAULT_AGENT_ID,
    "last_heartbeat_at": "",
    "last_test_at": "",
    "last_test_id": "",
    "last_test_reply": "",
    "last_error": "",
}


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
        return dict(_runtime_info)


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


def _build_heartbeat_payload(api, agent_id: str) -> dict:
    version = "1.7-4"
    commit = ""
    auto_mode = False
    busy = None
    internet = True
    drive = True

    if api is not None:
        try:
            b = getattr(api, "build", None) or {}
            version = str(b.get("version") or version)
            commit = str(b.get("commit") or "")
            auto_mode = bool((getattr(api, "settings", None) or {}).get("auto", False))
            busy = getattr(api, "busy", None)
            st = getattr(api, "status", None) or {}
            internet = bool(st.get("internet", True))
            drive = bool(st.get("drive", True))
        except Exception:
            pass

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
        },
        "state": {
            "auto_mode": auto_mode,
            "busy": busy,
            "internet": internet,
            "drive": drive,
        },
        "message": "Windows Agent آماده است",
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
    """ارسال یک Heartbeat به ``POST /heartbeat``."""
    cfg = cfg or _refresh_secret_cache(api)
    if not cfg:
        return False, 0, {"error": "کلید تنظیم نشده است"}

    base_url = cfg["base_url"]
    agent_key = cfg["agent_key"]
    agent_id = cfg.get("agent_id") or DEFAULT_AGENT_ID
    payload = _build_heartbeat_payload(api, agent_id)

    ok, code, data = _http_json("POST", f"{base_url}/heartbeat", agent_key, payload, timeout=HTTP_TIMEOUT)

    # اگر کلید عوض شده و شناسه‌ی قبلی به کلید قدیمی وصل بوده (HTTP 409)، شناسه را با تگ کلید یکتا کن
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
        # 409 یعنی همین تست قبلاً بسته شده است؛ دوباره ارسال نشود
        with _lock:
            _answered_test_ids.add(test_id)
            if len(_answered_test_ids) > 200:
                # جلوگیری از رشد نامحدود در حافظه
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


def _worker_loop() -> None:
    """حلقه‌ی پس‌زمینه‌ی Heartbeat (هر ۳۰ ثانیه) و Poll تست اتصال (هر ۵ ثانیه)."""
    last_hb = 0.0
    last_poll = 0.0
    hb_interval = HEARTBEAT_INTERVAL
    backoff_idx = 0
    auth_blocked = False

    while not _stop_event.is_set():
        api = _api_ref
        cfg = _refresh_secret_cache(api)

        if not cfg:
            # کلیدی ثبت نشده؛ منتظر بمان تا کاربر کلید را ذخیره کند
            _wake_event.wait(5.0)
            _wake_event.clear()
            last_hb = 0.0
            last_poll = 0.0
            backoff_idx = 0
            auth_blocked = False
            continue

        if auth_blocked:
            # طبق قرارداد: در صورت HTTP 401 یا 403، تلاش سریع نکن تا کلید تعویض یا بیدار شود
            woke = _wake_event.wait(60.0)
            _wake_event.clear()
            if woke:
                auth_blocked = False
                last_hb = 0.0
                last_poll = 0.0
                backoff_idx = 0
            continue

        now = time.monotonic()
        need_hb = (last_hb == 0.0) or ((now - last_hb) >= hb_interval)
        need_poll = (last_poll == 0.0) or ((now - last_poll) >= POLL_INTERVAL)

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
                    backoff_idx = 0
                continue
            else:
                backoff_idx = 0

        # محاسبه‌ی زمان خواب تا نوبت بعدی (حداکثر ۱ ثانیه برای پاسخ‌گویی سریع به wake/stop)
        now2 = time.monotonic()
        next_hb_in = max(0.1, hb_interval - (now2 - last_hb))
        next_poll_in = max(0.1, POLL_INTERVAL - (now2 - last_poll))
        sleep_for = min(1.0, next_hb_in, next_poll_in)
        if _wake_event.wait(sleep_for):
            _wake_event.clear()
            last_hb = 0.0
            last_poll = 0.0
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
    """بیدار کردن فوری نخ پس‌زمینه برای ارسال آنی Heartbeat و بررسی تست اتصال."""
    _wake_event.set()


if __name__ == "__main__":
    # ابزار خط فرمان اختیاری (بدون input() و کاملاً غیرتعاملی)
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
                },
                ensure_ascii=False,
            )
        )
