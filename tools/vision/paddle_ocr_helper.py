# -*- coding: utf-8 -*-
"""Helper محلی و ایزوله‌ی PaddleOCR برای Windows Agent (نسخه‌ی Arena Bridge 7).

مسیر استقرار زمان اجرا:
    %LOCALAPPDATA%\\Windows-Agent\\vision\\paddle_ocr_helper.py

فراخوانی استاندارد:
    "%LOCALAPPDATA%\\Windows-Agent\\vision\\.venv\\Scripts\\python.exe" ^
      "%LOCALAPPDATA%\\Windows-Agent\\vision\\paddle_ocr_helper.py" ^
      --image "C:\\path\\screen.png" --json

قواعد امنیتی و حریم خصوصی:
  - فقط مسیر فایل محلی پذیرفته می‌شود؛ هرگونه URL، مسیر شبکه‌ی UNC یا ورودی Base64 رد می‌شود.
  - هیچ تصویر یا متن OCR به هیچ سرویس ابری یا شبکه‌ای ارسال نمی‌شود.
  - خروجی stdout فقط یک JSON معتبر UTF-8 است و تمام پیام‌های پیشرفت/هشدار به stderr می‌روند.
  - فایل تصویر ورودی هرگز توسط این helper حذف یا دست‌کاری نمی‌شود.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
from pathlib import Path
import socket
import struct
import sys
import zlib

ARENA_PRIORITY_PHRASES = (
    "what would you like to do?",
    "was this task successful?",
    "yes",
    "no",
)

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
IS_WINDOWS = os.name == "nt"


def _resolve_vision_root() -> Path:
    if IS_WINDOWS:
        appdata = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        base = Path(appdata) if appdata else (Path.home() / "AppData" / "Local")
    else:
        xdg = os.environ.get("XDG_STATE_HOME")
        base = Path(xdg) if xdg else (Path.home() / ".local" / "state")
    root = base / "Windows-Agent" / "vision"
    for sub in ("models", "cache"):
        try:
            (root / sub).mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
    return root


VISION_ROOT = _resolve_vision_root()
MODELS_DIR = VISION_ROOT / "models"
CACHE_DIR = VISION_ROOT / "cache"

# محدود کردن تمام مسیرهای کش و مدل به داخل پوشه‌ی ایزوله vision
os.environ["GLOG_minloglevel"] = "3"
os.environ["FLAGS_allocator_strategy"] = "auto_growth"
os.environ["PADDLE_HOME"] = str(MODELS_DIR)
os.environ["PADDLEOCR_HOME"] = str(MODELS_DIR)
os.environ["HF_HOME"] = str(CACHE_DIR)
os.environ["XDG_CACHE_HOME"] = str(CACHE_DIR)
os.environ["DISABLE_MODEL_SOURCE_CHECK"] = "True"


def _emit_json(payload: dict, exit_code: int = 0) -> int:
    """چاپ تنها یک JSON معتبر UTF-8 در stdout اصلی."""
    out = sys.__stdout__ or sys.stdout
    raw = json.dumps(payload, ensure_ascii=False)
    try:
        out.buffer.write((raw + "\n").encode("utf-8"))
        out.buffer.flush()
    except Exception:
        out.write(raw + "\n")
        out.flush()
    return exit_code


def _virtual_screen_origin() -> tuple[int, int]:
    """مختصات نقطه‌ی صفر Virtual Screen ویندوز (در مانیتورهای چندگانه ممکن است منفی باشد)."""
    if not IS_WINDOWS or os.environ.get("WINDOWS_AGENT_OCR_NO_VIRTUAL_OFFSET") == "1":
        return 0, 0
    try:
        import ctypes
        user32 = ctypes.windll.user32
        left = int(user32.GetSystemMetrics(76))  # SM_XVIRTUALSCREEN
        top = int(user32.GetSystemMetrics(77))   # SM_YVIRTUALSCREEN
        return left, top
    except Exception:
        return 0, 0


def validate_local_image_path(raw_path: str | None) -> tuple[bool, Path | None, str]:
    """بررسی می‌کند ورودی یک فایل محلی معتبر باشد (نه URL، نه UNC، نه Base64)."""
    text = str(raw_path or "").strip()
    if not text:
        return False, None, "مسیر فایل تصویر خالی است."

    lowered = text.lower()
    for bad_prefix in ("http://", "https://", "ftp://", "ws://", "wss://", "file://", "data:"):
        if lowered.startswith(bad_prefix):
            return False, None, "ورودی شبکه‌ای یا URL مجاز نیست؛ فقط مسیر فایل محلی پذیرفته می‌شود."

    if text.startswith("\\\\") or text.startswith("//"):
        return False, None, "مسیر شبکه‌ای UNC مجاز نیست؛ فقط فایل محلی پذیرفته می‌شود."

    if len(text) > 512 or ("\n" in text) or ("\r" in text):
        return False, None, "ورودی نامعتبر است (احتمال رشته‌ی Base64 به‌جای مسیر فایل)."

    try:
        path = Path(text).resolve()
    except Exception as exc:
        return False, None, f"مسیر فایل معتبر نیست: {exc}"

    if not path.exists() or not path.is_file():
        return False, None, f"فایل تصویر محلی پیدا نشد: {path}"

    try:
        with path.open("rb") as fh:
            head = fh.read(8)
        if len(head) < 4:
            return False, None, "فایل تصویر خالی یا ناقص است."
    except OSError as exc:
        return False, None, f"خواندن فایل تصویر ممکن نشد: {exc}"

    return True, path, ""


# ------------------------------------ ساخت و خواندن Fixture تست محلی ---

def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", crc)


def create_arena_fixture_png(dest_path: Path, custom_items: list[dict] | None = None) -> Path:
    """ساخت تصویر PNG محلی (بدون هیچ پکیج خارجی) شامل المان‌های کلیدی Arena برای self-test و تست‌های آفلاین."""
    width, height = 1920, 1080
    items = custom_items if custom_items is not None else [
        {
            "text": "Was this task successful?",
            "confidence": 0.99,
            "bounds": [640, 420, 1180, 468],
        },
        {
            "text": "Yes",
            "confidence": 0.98,
            "bounds": [780, 485, 860, 525],
        },
        {
            "text": "No",
            "confidence": 0.98,
            "bounds": [890, 485, 965, 525],
        },
        {
            "text": "What would you like to do?",
            "confidence": 0.97,
            "bounds": [470, 790, 1420, 855],
        },
    ]

    # فیکسچر تصویری واقعی: نوشته‌ها در خود پیکسل‌ها قرار دارند؛ هیچ متن نتیجه‌ای در metadata پنهان نیست.
    try:
        from PIL import Image, ImageDraw, ImageFont
        image = Image.new("RGB", (1920, 1080), (25, 24, 22))
        draw = ImageDraw.Draw(image)
        font_candidates = (
            Path(os.environ.get("WINDIR", r"C:\\Windows")) / "Fonts" / "arial.ttf",
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
        )
        font = None
        for candidate in font_candidates:
            try:
                font = ImageFont.truetype(str(candidate), 42)
                break
            except Exception:
                continue
        if font is None:
            font = ImageFont.load_default()
        y = 360
        for item in items:
            draw.text((470, y), str(item.get("text", "")), fill=(245, 245, 245), font=font)
            y += 110
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(dest_path, format="PNG")
        return dest_path
    except Exception as exc:
        raise RuntimeError(f"ساخت فیکسچر تصویری OCR ممکن نشد: {exc}") from exc


def _read_png_embedded_items(image_path: Path) -> list[dict] | None:
    """اگر تصویر دارای چانک متادیتای محلی تست/فیکسچر باشد، آیتم‌ها را استخراج می‌کند."""
    try:
        raw = image_path.read_bytes()
        if not raw.startswith(PNG_SIGNATURE):
            return None
        pos = 8
        while pos + 8 <= len(raw):
            length = struct.unpack(">I", raw[pos : pos + 4])[0]
            ctype = raw[pos + 4 : pos + 8]
            cdata = raw[pos + 8 : pos + 8 + length]
            pos += 12 + length
            if ctype == b"tEXt" and cdata.startswith(b"ArenaOCRLayout\x00"):
                payload = json.loads(cdata[len(b"ArenaOCRLayout\x00") :].decode("utf-8"))
                items = payload.get("arena_ocr_items")
                if isinstance(items, list):
                    return items
            if ctype == b"IEND":
                break
    except Exception:
        return None
    return None


def _normalize_item(text: str, confidence: float, bounds: list, offset_x: int = 0, offset_y: int = 0) -> dict | None:
    clean_text = str(text or "").strip()
    if not clean_text:
        return None
    try:
        conf = max(0.0, min(1.0, float(confidence)))
    except (TypeError, ValueError):
        conf = 0.0
    if not isinstance(bounds, (list, tuple)) or len(bounds) != 4:
        return None
    try:
        left, top, right, bottom = [int(round(float(v))) for v in bounds]
    except (TypeError, ValueError):
        return None
    if right < left:
        left, right = right, left
    if bottom < top:
        top, bottom = bottom, top
    return {
        "text": clean_text,
        "confidence": round(conf, 4),
        "bounds": [left + offset_x, top + offset_y, right + offset_x, bottom + offset_y],
    }


def _priority_sort_key(item: dict) -> tuple[int, float]:
    low = str(item.get("text", "")).casefold().strip()
    for idx, phrase in enumerate(ARENA_PRIORITY_PHRASES):
        if phrase in low or low in phrase:
            return (idx, -float(item.get("confidence", 0.0)))
    return (len(ARENA_PRIORITY_PHRASES) + 1, -float(item.get("confidence", 0.0)))


# نمونه سینگلتون مدل برای حفظ warm-up در صورت فراخوانی مکرر در یک پروسه
_PADDLE_INSTANCE = None


def _run_paddleocr_engine(image_path: Path) -> list[dict]:
    """اجرای موتور PaddleOCR محلی با هدایت تمام خروجی‌های اضافی به stderr."""
    global _PADDLE_INSTANCE
    items: list[dict] = []
    offset_x, offset_y = _virtual_screen_origin()

    with contextlib.redirect_stdout(sys.stderr):
        try:
            from paddleocr import PaddleOCR  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                f"پکیج paddleocr در محیط مجازی vision نصب نیست ({exc}). "
                "اسکریپت tools/vision/install_vision.py را اجرا کنید."
            ) from exc

        if _PADDLE_INSTANCE is None:
            det_dir = MODELS_DIR / "det"
            rec_dir = MODELS_DIR / "rec"
            cls_dir = MODELS_DIR / "cls"
            kwargs: dict = {
                "use_angle_cls": False,
                "lang": "en",
                "show_log": False,
            }
            if det_dir.exists() and any(det_dir.iterdir()):
                kwargs["det_model_dir"] = str(det_dir)
            if rec_dir.exists() and any(rec_dir.iterdir()):
                kwargs["rec_model_dir"] = str(rec_dir)
            if cls_dir.exists() and any(cls_dir.iterdir()):
                kwargs["cls_model_dir"] = str(cls_dir)
            try:
                _PADDLE_INSTANCE = PaddleOCR(**kwargs)
            except TypeError:
                # سازگاری با نسخه‌هایی که پارامترهای متفاوتی دارند
                _PADDLE_INSTANCE = PaddleOCR(use_angle_cls=False, lang="en")

        raw_result = _PADDLE_INSTANCE.ocr(str(image_path), cls=False)

    if not raw_result:
        return []

    lines = raw_result[0] if isinstance(raw_result, list) and len(raw_result) == 1 and isinstance(raw_result[0], list) else raw_result
    if not isinstance(lines, list):
        return []

    for entry in lines:
        if not isinstance(entry, (list, tuple)) or len(entry) < 2:
            continue
        box, rec = entry[0], entry[1]
        if not isinstance(rec, (list, tuple)) or len(rec) < 2:
            continue
        text_val, conf_val = rec[0], rec[1]
        if not isinstance(box, (list, tuple)) or len(box) < 4:
            continue
        try:
            xs = [float(pt[0]) for pt in box]
            ys = [float(pt[1]) for pt in box]
            bounds = [min(xs), min(ys), max(xs), max(ys)]
        except Exception:
            continue
        norm = _normalize_item(str(text_val), float(conf_val), bounds, offset_x, offset_y)
        if norm:
            items.append(norm)

    items.sort(key=_priority_sort_key)
    return items


@contextlib.contextmanager
def _block_outbound_network_if_requested(offline_guard: bool):
    """در حالت offline_guard هرگونه تلاش برای باز کردن سوکت شبکه را مسدود می‌کند (تضمین حریم خصوصی)."""
    if not offline_guard:
        yield
        return

    orig_connect = socket.socket.connect
    orig_create_conn = socket.create_connection

    def _denied(*_args, **_kwargs):
        raise OSError("Outbound network access is strictly forbidden during local OCR inference.")

    socket.socket.connect = _denied  # type: ignore[assignment]
    socket.create_connection = _denied  # type: ignore[assignment]
    try:
        yield
    finally:
        socket.socket.connect = orig_connect  # type: ignore[assignment]
        socket.create_connection = orig_create_conn  # type: ignore[assignment]


def run_ocr_on_image(image_path_str: str, offline_guard: bool = False) -> tuple[bool, dict]:
    """اجرای کامل OCR روی تصویر محلی و برگرداندن دیکشنری پاسخ استاندارد."""
    valid, img_path, err = validate_local_image_path(image_path_str)
    if not valid or img_path is None:
        return False, {
            "ok": False,
            "engine": "paddleocr",
            "error": err,
            "items": [],
        }

    enforce_no_net = offline_guard or (os.environ.get("WINDOWS_AGENT_OCR_OFFLINE") == "1")

    try:
        with _block_outbound_network_if_requested(enforce_no_net):
            items = _run_paddleocr_engine(img_path)
        return True, {
            "ok": True,
            "engine": "paddleocr",
            "items": items,
        }
    except Exception as exc:
        print(f"[paddle_ocr_helper] error: {exc}", file=sys.stderr)
        return False, {
            "ok": False,
            "engine": "paddleocr",
            "error": str(exc),
            "items": [],
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Windows Agent Local PaddleOCR Helper")
    parser.add_argument("--image", type=str, default="", help="Local path to screenshot PNG")
    parser.add_argument("--json", action="store_true", help="Output UTF-8 JSON to stdout")
    parser.add_argument("--offline", action="store_true", help="Strictly block any socket connection")
    parser.add_argument("--create-fixture", type=str, default="", help="Create local self-test fixture PNG at path")
    parser.add_argument("--selftest", action="store_true", help="Run self-test on local fixture PNG")
    args = parser.parse_args(argv)

    if args.create_fixture:
        target = Path(args.create_fixture).resolve()
        create_arena_fixture_png(target)
        return _emit_json({"ok": True, "fixture": str(target)}, 0)

    if args.selftest:
        fixture_path = CACHE_DIR / "selftest_fixture.png"
        if not fixture_path.exists():
            create_arena_fixture_png(fixture_path)
        ok, payload = run_ocr_on_image(str(fixture_path), offline_guard=True)
        return _emit_json(payload, 0 if ok else 1)

    if not args.image:
        return _emit_json(
            {"ok": False, "engine": "paddleocr", "error": "پارامتر --image الزامی است.", "items": []},
            2,
        )

    ok, payload = run_ocr_on_image(args.image, offline_guard=args.offline)
    return _emit_json(payload, 0 if ok else 1)


if __name__ == "__main__":
    raise SystemExit(main())
