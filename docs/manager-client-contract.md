# قرارداد اتصال `manager_client.py` به ایجنت مدیریت

این سند قرارداد Agent با Management API رسمی Vercel است؛ بدون خودبه‌روزرسانی و بدون نوشتن فایل کنار `app.py`. جزئیات مهاجرت و outbox تصویر در [`vercel-management-migration.md`](vercel-management-migration.md) آمده است.

## مرز مسئولیت چهار ایجنت

1. **ایجنت ویندوز:** برنامه‌ی در حال اجرا روی ویندوز؛ مجری فرمان، فرستنده‌ی Heartbeat، رخداد، نتیجه و metadata فایل‌ها.
2. **ایجنت مادر:** سازنده و تنها نگهدارنده‌ی کد پایه‌ی ایجنت ویندوز (`app.py` و `run.bat`).
3. **ایجنت همکار:** نویسنده‌ی `job_*.py`؛ بدون دسترسی به کد پایه‌ی ایجنت ویندوز.
4. **ایجنت مدیریت:** سایت `https://windows-agent-management.vercel.app`؛ پایش و فرماندهی ویندوز، بدون تغییر خودکار کد پایه‌ی ایجنت ویندوز.

## کار موردنیاز از ایجنت مادر

### ۱. ماژول مستقل

فایل `manager_client.py` را فقط با کتابخانه‌ی استاندارد Python بساز. فایل نباید داده‌ای کنار `app.py` ذخیره کند. پس از تأیید کاربر، فقط این قلاب اختیاری در انتهای `Api.__init__` قرار گیرد:

```python
try:
    import manager_client
    manager_client.start(self)
except ImportError:
    pass
```

`start(api)` باید idempotent باشد و فقط یک نخ `daemon=True` راه‌اندازی کند. هیچ عملیات شبکه‌ای در Main Thread یا `get_state()` انجام نشود.

### ۲. پیکربندی و Secret

- مسیر: `%LOCALAPPDATA%\Windows-Agent\manager_secret.bin`
- محتوا: JSON شامل `base_url` و `agent_key`
- رمزنگاری: DPAPI با `CryptProtectData`/`CryptUnprotectData` و `CRYPTPROTECT_UI_FORBIDDEN`
- هیچ کلیدی در log، UI، GitHub، URL یا فایل کنار `app.py` نوشته نشود.
- کلید از تب «کلید ایجنت» سایت ساخته می‌شود.

نمونه‌ی محتوای قبل از رمزنگاری:

```json
{
  "base_url": "https://windows-agent-management.vercel.app/api/agent",
  "agent_key": "wam_agent_..."
}
```

همه‌ی درخواست‌ها:

```http
Authorization: Bearer <agent_key>
Content-Type: application/json
```

### ۳. Heartbeat

هر ۳۰ ثانیه و بلافاصله پس از start:

```http
POST /heartbeat
```

```json
{
  "agentId": "windows-agent-alibatel-main",
  "name": "ایجنت ویندوز اصلی",
  "platform": "windows",
  "version": "1.7-22",
  "commit": "شناسه‌ی واقعی Git HEAD در زمان اجرا",
  "status": "online",
  "capabilities": {
    "check_collab": true,
    "run_new": true,
    "run_single": true,
    "take_screenshot": true,
    "open_report": true,
    "telegram_queue": true,
    "command_plane": true,
    "database_automations": true,
    "d1_automations": true,
    "vercel_blob_screenshot_upload": true,
    "google_drive_artifacts": false,
    "emergency_stop_all": true
  },
  "state": {
    "manager_base": "vercel",
    "auto_mode": false,
    "busy": null,
    "internet": true,
    "drive": false
  },
  "message": "Windows Agent آماده است"
}
```

از helper شبکه‌ی موجود مادر (`_http_post_json`) با timeout پنج ثانیه و proxy/TLS fallback استفاده شود. خطای شبکه نباید UI یا job runner را متوقف کند. backoff پیشنهادی: ۵، ۱۵، ۳۰ و سپس ۶۰ ثانیه.

### ۴. Poll تست اتصال

هر پنج ثانیه، یا وقتی پاسخ Heartbeat مقدار `pendingConnectionTests > 0` داشت:

```http
GET /connection-test
```

پاسخ بدون تست:

```json
{"test": null, "retryAfterSeconds": 5}
```

پاسخ دارای تست:

```json
{
  "test": {
    "id": "act_...",
    "type": "connection_test",
    "message": "سلام ایجنت ویندوز؛ لطفاً پیام تست را به ایجنت مدیریت برگردان.",
    "expectedReply": "سلام ایجنت مدیریت.",
    "expiresAt": "..."
  }
}
```

برای پاسخ، متن باید دقیقاً همان `expectedReply` باشد:

```http
POST /connection-test
```

```json
{
  "testId": "act_...",
  "message": "سلام ایجنت مدیریت."
}
```

پس از HTTP 200، در پنل محلی با `api.log` ثبت شود: «تست اتصال ایجنت مدیریت موفق بود». پاسخ هر `testId` فقط یک بار ارسال شود؛ شناسه‌های پاسخ‌داده‌شده در حافظه یا state موجود نگه‌داری شوند.

### ۵. وضعیت UI محلی

بدون کار شبکه‌ای در `get_state()`، فقط متغیرهای RAM را به وضعیت برگردان:

```python
api.status["manager"] = True  # یا False
api.status_note["manager"] = "وصل"  # «قطع»، «کلید نامعتبر»، «در انتظار»
```

در توقف برنامه، Event نخ set شود. نخ باید `event.wait(seconds)` استفاده کند و daemon باشد.

### ۶. محدودیت‌ها

- `manager_client.py` حق تغییر یا Pull خودکار `app.py` را ندارد.
- هیچ فایل یا secret کنار `app.py` ساخته نشود.
- فعلاً فقط Heartbeat و تست اتصال پیاده‌سازی شود؛ اجرای فرمان‌های عملیاتی مرحله‌ی بعد و بر اساس حالت دستی/خودکار خواهد بود.
- پاسخ‌های 401 یعنی کلید غیرفعال/منقضی است؛ retry سریع نکن و وضعیت «کلید نامعتبر» نشان بده.
- پاسخ 403 یعنی scope لازم روی کلید فعال نیست.
- همه‌ی timestampها در payload به صورت UTC/ISO باشند؛ نمایش محلی جلالی/تهران بماند.

## معیار پذیرش

1. سایت در صفحه دیتابیس، Heartbeat ایجنت را حداکثر ۳۰ ثانیه پس از اجرا نشان دهد.
2. با زدن «شروع تست اتصال»، Windows Agent درخواست را حداکثر پنج ثانیه بعد دریافت کند.
3. پاسخ دقیق «سلام ایجنت مدیریت.» در Management API ثبت و وضعیت سایت «اتصال برقرار» شود.
4. بعد از غیرفعال‌کردن کلید، Heartbeat و تست با HTTP 401 رد شوند.
5. نبود اینترنت یا سایت، UI و اجرای jobهای ویندوز را مختل نکند.
