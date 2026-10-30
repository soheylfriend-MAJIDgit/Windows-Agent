# نامه اجرایی به ایجنت مادر — اجرای کدهای اتوماسیون از D1

ایجنت مادر محترم،

سایت مدیریت اکنون کاتالوگ مستقل «کدهای اتوماسیون» را در Cloudflare D1 دارد. از این مرحله، منبع اصلی `job_*.py`های اتوماسیون D1 است و اجرای روزمره آن‌ها نباید به مخزن ایجنت همکار، Git clone، Pull، Commit یا GitHub Desktop وابسته باشد.

کد پایه Windows Agent و `manager_client.py` همچنان متعلق به تو و مخزن مادر است. این درخواست اجازه تغییر خودکار `app.py` را به سایت مدیریت نمی‌دهد.

## تغییر لازم در manager_client.py

1. قرارداد کامل `docs/windows-command-plane.md` را پیاده‌سازی کن.
2. پس از تکمیل واقعی، در Heartbeat اعلام کن:

```json
{"capabilities":{"command_plane":true,"d1_automations":true}}
```

3. command type تازه `run_automation` را به allowlist اضافه کن.
4. هنگام claim این فرمان، فقط داده‌های زیر را معتبر بدان:

```json
{
  "automationId": "auto_...",
  "versionId": "av_...",
  "version": 3,
  "jobName": "job_example.py",
  "sourceSha256": "...",
  "sourceEndpoint": "/api/agent/automations/auto_.../versions/av_...",
  "sourceOfTruth": "cloudflare_d1",
  "executionPolicy": "respect_windows_agent_mode"
}
```

5. `sourceEndpoint` باید relative باشد و دقیقاً زیر `/api/agent/automations/` قرار بگیرد. URL خارجی یا absolute پذیرفته نشود.
6. با همان Bearer key فرمان، GET به endpoint نسخه بزن. پاسخ شامل `sourceCode`, `sourceSha256`, `jobName`, `versionId`, `version` است.
7. پیش از نوشتن یا اجرا:
   - automation/version/jobName پاسخ با فرمان یکسان باشد.
   - `jobName` فقط `^job_[A-Za-z0-9_]+\.py$` باشد.
   - SHA-256 متن UTF-8 دقیقاً با hash پاسخ و hash payload یکسان باشد.
   - mismatch رخداد `fatal` و وضعیت `rejected` ایجاد کند.
8. کد را در workspace موقت مختص command بنویس؛ کنار `app.py` هیچ فایل ساخته نشود.
9. این مسیر نباید مخزن ایجنت همکار را Pull یا Sync کند.
10. اجرای کد از همان سیاست محلی پیروی کند:
    - manual: `waiting_confirmation` و تأیید کاربر
    - automatic: ادامه طبق تنظیم محلی
11. subprocess با process group مستقل اجرا و cancel/timeout/no-progress با توقف کامل process tree اعمال شود.
12. stdout در queue/thread جدا خوانده شود تا Poll لغو مسدود نشود.
13. stageها، خطا، crash و نتیجه در command eventها گزارش شوند.
14. screenshot هر مرحله ابتدا در Google Drive آپلود و فقط metadata آن به D1 ارسال شود.
15. کلید دائمی مدیریت یا DPAPI secret را در environment اتوماسیون قرار نده.
16. طبق تصمیم کاربر، فعلاً sandbox سخت الزامی نیست؛ با این حال در قرارداد و توضیح کد روشن بنویس که اتوماسیون اجازه تغییر کد پایه، خواندن secret یا دست‌کاری فایل‌های شخصی را ندارد.
17. قابلیت‌های قبلی Git-based را برای rollback می‌توان موقتاً نگه داشت، ولی `run_automation` باید کاملاً بدون Git کار کند.

## API دریافت نسخه

```http
GET /api/agent/automations/{automationId}/versions/{versionId}
Authorization: Bearer <windows-agent-key>
```

scope لازم: `commands:read`.

## معیار پذیرش

- فرمان D1 بدون نصب Git روی مسیر اجرا قابل دریافت و اجرا باشد.
- hash خراب یا jobName نامعتبر هرگز اجرا نشود.
- بستن modal اجرا را متوقف نکند؛ توقف دستی سایت حداکثر طی دو ثانیه process tree را خاتمه دهد.
- حالت دستی/خودکار محلی حفظ شود.
- restart/crash نتیجه ناقص را قابل تشخیص نگه دارد.
- هیچ تغییری در `app.py` بدون diff جداگانه و تأیید کاربر اعمال نشود.

قبل از نصب، کد کامل تغییرات، فایل‌های تغییرکرده، تست‌ها و روش rollback را برای بررسی ارائه کن.
