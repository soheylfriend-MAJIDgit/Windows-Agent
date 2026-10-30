# قرارداد صف فرمان و پایش زنده Windows Agent

این قرارداد مرحله‌ی دوم اتصال `manager_client.py` است. اعمال آن به `app.py` فقط با تأیید کاربر و توسط ایجنت مادر انجام می‌شود. سایت مدیریت هیچ کد پایه‌ای را بازنویسی یا Pull نمی‌کند.

## اصل امنیتی

- فرمان shell یا Python آزاد وجود ندارد. `type` فقط از allowlist محلی پذیرفته شود:
  - `run_arena_prompt`: Sync مخزن همکار و اجرای دقیق `job_arena.py`
  - `sync_and_run_job`: Sync مخزن همکار و اجرای دقیق `payload.jobName`
- `jobName` باید با `^job_[A-Za-z0-9_]+\.py$` تطبیق کند، بدون `/`، `\\` یا `..`، و پس از `resolve()` داخل پوشه‌ی شناخته‌شده‌ی `Desktop\\CODES` بماند.
- `payload` آرگومان shell، مسیر اجرایی، URL دلخواه یا قطعه کد نیست.
- کلید Bearer فقط در DPAPI بماند. تصویر از multipart authenticated API می‌رود؛ secret و image bytes در event/result JSON ارسال نشوند.
- `requiresConfirmation: true` یعنی اجرای فرمان باید از همان سیاست فعلی Windows Agent عبور کند: در حالت دستی، UI محلی تأیید می‌گیرد؛ در حالت خودکار، همان سیاست محلی اجازه‌ی ادامه می‌دهد. سایت حق تغییر این mode را ندارد.

## اعلام آمادگی و چرخه‌ی Poll

نسخه‌ای که این قرارداد را کامل پیاده کرده باید در Heartbeat مقدار `capabilities.command_plane=true` بفرستد. سایت فقط برای چنین نسخه‌ای فرمان می‌سازد؛ بنابراین client قدیمی هیچ فرمان اجرا‌نشدنی در صف ایجاد نمی‌کند.

نخ daemon اتصال، وقتی job دیگری در حال اجرا نیست، هر سه ثانیه درخواست زیر را می‌فرستد:

```http
POST /commands/claim
Authorization: Bearer <key>
Content-Type: application/json
```

پاسخ بدون کار:

```json
{"command":null,"serverTime":"...","pollAfterSeconds":3}
```

فرمان دریافتی شامل `id`, `type`, `payload`, `requiresConfirmation`, `timeoutSeconds`, `noProgressSeconds` و `autoStopOnAnomaly` است. هر لحظه فقط یک فرمان اجرا شود. شناسه‌ی فرمان در RAM به عنوان `busy` نگه‌داری شود.

## ماشین حالت

ترتیب مجاز:

```text
pending → claimed → waiting_confirmation → running → succeeded
                 ↘ running → failed | cancelled | timed_out
                 ↘ rejected
```

ارسال وضعیت:

```http
POST /commands/{commandId}
```

```json
{
  "status": "running",
  "seq": 4,
  "stage": "process_started",
  "message": "job_arena.py با PID 4128 آغاز شد.",
  "result": {}
}
```

در حالت دستی، پیش از نمایش تأیید محلی `waiting_confirmation` ارسال شود. رد کاربر `rejected` است. نتیجه‌ی نهایی می‌تواند metadata کوتاه مثل `exitCode`, `durationSeconds` و `driveFolderId` داشته باشد؛ stdout کامل یا تصویر در این فیلد قرار نگیرد.

هر درخواست state تکراری idempotent تلقی شود. `seq` رخدادهای Windows Agent برای هر فرمان صعودی و در بازه‌ی ۲ تا ۱٬۰۰۰٬۰۰۰ باشد.

## رخدادهای مرحله‌ای

```http
POST /commands/{commandId}/events
```

```json
{
  "seq": 5,
  "stage": "arena_window_ready",
  "level": "info",
  "message": "پنجره Arena پیدا و فعال شد.",
  "occurredAt": "2026-10-25T10:21:39.184Z",
  "data": {"elapsedMs": 1830}
}
```

سطح‌ها: `debug`, `info`, `warning`, `error`, `fatal`. پیام حداکثر ۲۰۰۰ نویسه و data حداکثر ۲۴KB باشد. برای توقف فوری مبتنی بر تشخیص محلی، `level=fatal` یا `data.autoStop=true` بفرستید. سرور `cancelRequested=true` برمی‌گرداند.

مرحله‌های حداقلی `run_arena_prompt`:

1. `policy_check`
2. `waiting_confirmation` (فقط دستی)
3. `repository_sync_started` / `repository_sync_finished`
4. `process_started`
5. `arena_process_detected`
6. `arena_window_ready`
7. `prompt_located`
8. `prompt_typed`
9. `prompt_submitted`
10. `response_waiting`
11. `result_uploaded`
12. `completed`

برای هر مرحله‌ی قابل مشاهده screenshot گرفته شود. خطاهای catchable در `job_arena.py` باید با حداکثر سه تلاش به همکار بازخورد دهند؛ متن بازخورد از همکار بخواهد رخدادهای Management API و Screenshotهای دارای Upload موفق در گالری را بررسی و کد را اصلاح یا بازنویسی کند. لاگ کامل در Arena تایپ نشود.

## Screenshot در Management API

Screenshot واقعی هر مرحله ابتدا در پوشه‌ی execution زیر `%LOCALAPPDATA%\\Windows-Agent\\screenshot_uploads` ذخیره و با Pillow فشرده/resize می‌شود تا فایل از ۴ MiB کمتر باشد. سپس صف پایدار شبکه‌ای، بدون Agent Key در manifest، این multipart را به `POST /screenshots` می‌فرستد:

```text
file, commandId, executionId, agentId, stage, name, occurredAt, width, height
```

موفقیت فقط HTTP 201 همراه JSON معتبر و `screenshot.id` پذیرفته می‌شود. هیچ Blob token یا URL خام Blob در Agent نیست؛ فقط `contentUrl` نسبی پاسخ در رویداد موفق ثبت می‌شود. شکست موقت Upload، تعامل Arena را تکرار نمی‌کند؛ صف با backoff محلی حفظ و warning گزارش می‌شود. Screenshot، Report یا فایل کنترل تازه به Google Drive یا `/commands/{commandId}/artifacts` ارسال نمی‌شود.

## لغو، timeout و توقف فرایند

در تمام زمان‌های زیر کنترل فرمان Poll شود:

```http
GET /commands/{commandId}
```

- هنگام انتظار تأیید: هر ۲ ثانیه
- هنگام اجرای subprocess: حداکثر هر ۱٫۵ ثانیه
- بلافاصله پس از هر رخداد یا artifact

پاسخ شامل `cancelRequested`, `cancelReason`, `timeoutSeconds`, `noProgressSeconds` است.

فرایند job با process group مستقل ساخته شود. در Windows:

```python
proc = subprocess.Popen(
    [sys.executable, "-u", str(job_path)],
    cwd=str(codes_dir),
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    encoding="utf-8",
    errors="replace",
    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
)
```

تابع توقف الزامی:

```python
def terminate_tree(proc):
    if proc.poll() is not None:
        return
    subprocess.run(
        ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
        capture_output=True,
        text=True,
        timeout=15,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
```

سه ساعت مستقل پایش شوند:

- `timeoutSeconds`: از آغاز `running`
- `noProgressSeconds`: از آخرین stdout، stage یا screenshot موفق
- cancel سایت: از پاسخ کنترل

در timeout محلی، `timed_out`؛ در cancel، `cancelled`؛ در fatal anomaly، process tree فوراً متوقف و `failed` ارسال شود. اگر API در دسترس نبود، timeout و تشخیص محلی همچنان باید عمل کنند. خواندن stdout در نخ/queue جدا انجام شود تا Poll لغو هیچ‌وقت پشت `readline()` مسدود نشود.

## تشخیص crash و رفتار غیرعادی

موارد زیر حداقل باید رخداد `error`/`fatal` بسازند:

- خروج subprocess با exit code غیرصفر
- ناپدیدشدن process یا پنجره‌ی Arena پیش از مرحله‌ی مورد انتظار
- traceback یا الگوی fatal در خروجی
- عدم پیشرفت
- timeout
- شکست متوالی Screenshot upload (warning؛ اگر ادامه امن نیست fatal)
- ناسازگاری job path یا command type (reject پیش از اجرا)

stdout/stderr به صورت chunkهای محدود و پاک‌سازی‌شده گزارش شود؛ secret، token، Cookie، Authorization و مسیر کامل کاربر redaction شوند. تاریخ رخداد در سرور ثبت می‌شود و UI آن را شمسی/تهران نشان می‌دهد.

## بازیابی پس از crash خود manager_client

- وضعیت، events و metadata در Management API/Postgres باقی می‌مانند؛ byteهای Screenshot فقط در Blob server-side نگه‌داری می‌شود.
- پس از restart، client فرمان `claimed`/`running` قبلی را کورکورانه دوباره اجرا نکند.
- heartbeat وضعیت `busy` را گزارش کند.
- اگر process قبلی واقعاً زنده نیست، رخداد crash و state=`failed` ارسال شود.
- اگر فرایند با PID و command marker معتبر زنده است، فقط مانیتور آن از سر گرفته شود؛ هرگز PID صرف را بدون بررسی executable/start-time تصاحب نکنید.

## معیار پذیرش

1. با submit پرامپت/اجرای دوباره، modal بلافاصله با command ID باز شود.
2. حالت دستی Windows Agent منتظر تأیید محلی و حالت خودکار بدون دخالت سایت ادامه دهد.
3. timeline، timestamp، warning/error/fatal، وضعیت نهایی و metadata تصویرها پس از reload قابل بازیابی باشند.
4. تصویر به صورت Base64 در event/result JSON قرار نگیرد؛ Blob فقط از مسیر `/screenshots` و server-side نوشته شود.
5. توقف سایت حداکثر در دو ثانیه دیده و کل process tree متوقف شود.
6. timeout، no-progress و fatal anomaly اجرای فعال را متوقف کنند.
7. command type یا job path خارج allowlist هرگز اجرا نشود.
