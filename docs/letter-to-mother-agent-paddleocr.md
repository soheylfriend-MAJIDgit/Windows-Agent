# نامه اجرایی به ایجنت مادر — افزودن PaddleOCR محلی و تاب‌آوری قطع اینترنت

ایجنت مادر محترم،

برای پایدارکردن مسیر ارسال پرامپت به Arena، سایت مدیریت قرارداد Arena Bridge 7 را آماده کرده است. این نسخه UI Automation را مسیر اصلی نگه می‌دارد و فقط هنگام نیاز از PaddleOCR محلی برای پیدا کردن متن و مختصات استفاده می‌کند. همچنین هنگام قطع اینترنت باید هیچ تعامل تازه‌ای با UI انجام نشود؛ برنامه ۶۰ ثانیه صبر می‌کند، دوباره اتصال را می‌سنجد و پس از برگشت اتصال ادامه می‌دهد.

این تغییر متعلق به کد پایه Windows Agent و `manager_client.py` است. سایت مدیریت اجازه ندارد `app.py` را خودکار تغییر دهد. هیچ فایل runtime، مدل، محیط مجازی، لاگ یا تصویر نیز نباید کنار `app.py` نوشته شود.

## خروجی مورد انتظار

پس از پیاده‌سازی و تست واقعی، Heartbeat باید این قابلیت‌ها را اعلام کند:

```json
{
  "capabilities": {
    "command_plane": true,
    "d1_automations": true,
    "arena_vision_ocr": true,
    "network_resilience": true,
    "ocr_engine": "paddleocr",
    "ocr_local_only": true
  }
}
```

تا پیش از آماده‌شدن واقعی هر دو قابلیت، مقدار آن‌ها را `true` نفرست. سایت مدیریت برای پرامپت Arena وجود `arena_vision_ocr` و `network_resilience` را اجباری بررسی می‌کند.

## ۱. نصب ایزوله PaddleOCR

1. محیط مجازی مستقل بساز؛ مسیر پیشنهادی:

```text
%LOCALAPPDATA%\Windows-Agent\vision\.venv
```

2. مدل‌ها و cache فقط زیر این مسیر باشند:

```text
%LOCALAPPDATA%\Windows-Agent\vision\models
%LOCALAPPDATA%\Windows-Agent\vision\cache
```

3. وابستگی‌های CPU سازگار `paddlepaddle` و `paddleocr` را در همان venv نصب کن. نسخه‌های نهایی سازگار را در فایل requirements مخزن مادر pin کن؛ نصب نباید به Python اصلی برنامه یا محیط کاربر نشت کند.
4. اولین دریافت مدل با اطلاع کاربر انجام شود. پس از نصب اولیه، OCR باید بدون اینترنت کار کند.
5. هیچ تصویر یا متن OCR به سرویس ابری ارسال نشود.
6. uninstall/rollback باید فقط پوشه `vision` را حذف یا غیرفعال کند و به `app.py` یا داده‌های کاربر دست نزند.

## ۲. helper محلی OCR

یک helper مستقل بساز و نسخه runtime آن را زیر مسیر زیر قرار بده:

```text
%LOCALAPPDATA%\Windows-Agent\vision\paddle_ocr_helper.py
```

رابط اجباری:

```powershell
"%LOCALAPPDATA%\Windows-Agent\vision\.venv\Scripts\python.exe" `
  "%LOCALAPPDATA%\Windows-Agent\vision\paddle_ocr_helper.py" `
  --image "C:\path\screen.png" --json
```

stdout فقط یک JSON UTF-8 معتبر برگرداند:

```json
{
  "ok": true,
  "engine": "paddleocr",
  "items": [
    {
      "text": "What would you like to do?",
      "confidence": 0.97,
      "bounds": [470, 790, 1420, 855]
    }
  ]
}
```

قواعد:

- `bounds` به‌ترتیب `[left, top, right, bottom]` و برحسب مختصات Virtual Screen ویندوز باشد.
- confidence عدد بین صفر و یک باشد.
- خروجی debug، progress و warning به stderr برود؛ stdout را آلوده نکند.
- مسیر تصویر فقط local باشد؛ URL، base64 و network input ممنوع است.
- helper حداکثر طی ۴۵ ثانیه پاسخ بدهد و در timeout کل process tree آن بسته شود.
- متن‌های انگلیسی رابط Arena اولویت دارند: `What would you like to do?`, `Was this task successful?`, `Yes`, `No`.
- مدل یک‌بار warm-up شود و cache مدل حفظ شود. اگر معماری worker دائمی انتخاب شد، فقط local IPC محدود به همان کاربر ویندوز مجاز است.
- فایل ورودی پس از پردازش توسط helper حذف نشود؛ lifecycle آن با job است.

## ۳. تزریق محدود environment به فرمان Arena

فقط برای subprocess اتوماسیون و بدون قرار دادن secret، این دو متغیر را اضافه کن:

```text
WINDOWS_AGENT_OCR_PYTHON=%LOCALAPPDATA%\Windows-Agent\vision\.venv\Scripts\python.exe
WINDOWS_AGENT_OCR_HELPER=%LOCALAPPDATA%\Windows-Agent\vision\paddle_ocr_helper.py
```

پیش از اجرای `job_arena.py`:

1. هر دو مسیر باید absolute، موجود و زیر `%LOCALAPPDATA%\Windows-Agent\vision` باشند.
2. symlink/reparse point خروجی از این ریشه پذیرفته نشود.
3. یک self-test روی تصویر fixture محلی اجرا شود.
4. اگر self-test شکست خورد، فرمان پیش از اجرای job با stage=`ocr_preflight_failed` و level=`fatal` متوقف شود.
5. توکن مدیریت، DPAPI secret، Telegram token یا Cookie هرگز در environment اتوماسیون قرار نگیرد.

رخداد موفق:

```json
{
  "stage": "ocr_ready",
  "level": "info",
  "message": "PaddleOCR محلی آماده است.",
  "data": {"engine":"paddleocr","localOnly":true}
}
```

## ۴. پایش قطع اینترنت

پایش اتصال باید در `manager_client.py` و مستقل از UI اصلی انجام شود:

1. پیش از claim/download و در طول اجرای فرمان، دسترسی به API مدیریت با request سبک و timeout محدود سنجیده شود.
2. job Arena نیز دسترسی مستقیم به URL Arena را می‌سنجد؛ manager نباید نتیجه یک endpoint را به‌جای دیگری فرض کند.
3. در اولین قطعی:
   - stage=`network_paused`
   - level=`warning`
   - هیچ click، keypress، Enter، بازخورد شکست یا اجرای دوباره‌ای آغاز نشود.
4. دقیقاً ۶۰ ثانیه صبر کن و دوباره بررسی کن.
5. تا وقتی اتصال برنگشته همین چرخه ادامه یابد؛ loop سریع ممنوع است.
6. بعد از اتصال:
   - stage=`network_resumed`
   - level=`info`
   - ادامه از آخرین مرحله امن، نه اجرای کورکورانه Enter یا ارسال دوباره پرامپت.
7. زمان قطعی نباید به‌عنوان no-progress anomaly محاسبه شود، ولی timeout کلی ایمنی همچنان باید سقف مستقل و قابل‌تعریف داشته باشد.
8. cancel کاربر در زمان قطعی باید محلی و حداکثر طی دو ثانیه process tree را متوقف کند؛ برای cancel منتظر اینترنت نمان.
9. اگر اتصال برگشت ولی عملیات قابل بازیابی نبود، بدون ارسال feedback تکراری، process را متوقف و status=`failed` با علت دقیق ثبت کن.
10. اگر خود subprocess exit code غیرصفر داد و شبکه برقرار بود، شکست واقعی است و نباید به قطعی اینترنت نسبت داده شود.

## ۵. حفظ نقش‌ها و فایل‌ها

- `app.py` را خودکار تغییر نده.
- اگر hook تازه‌ای لازم است، diff جداگانه ارائه کن و پیش از اعمال از کاربر اجازه بگیر.
- فایل helper و installer در زیرپوشه مستقل مخزن مادر نگهداری شوند؛ runtime آن‌ها فقط زیر LocalAppData نصب شود.
- هیچ فایل تولیدی کنار `app.py` نوشته نشود.
- کد D1 و ایجنت همکار حق تغییر `manager_client.py`، helper OCR یا فایل‌های پایه را ندارند.
- GitHub Desktop و کنترل انسانی روش به‌روزرسانی کد پایه باقی می‌ماند.

## ۶. تست‌های پذیرش اجباری

1. **OCR آفلاین:** اینترنت را پس از دانلود مدل قطع کن؛ fixture شامل `Was this task successful?` باید با bounds معتبر پیدا شود.
2. **UIA موفق:** وقتی UI Automation عنصر را پیدا می‌کند، OCR فقط پشتیبان باشد و کلیک تکراری ایجاد نکند.
3. **UIA ناموفق/OCR موفق:** عنصر UIA مخفی یا ناشناخته باشد؛ OCR مختصات composer را بدهد و job همان را با guard نوار آدرس استفاده کند.
4. **قطع قبل از تایپ:** اینترنت قطع شود؛ حداقل ۶۰ ثانیه هیچ click/key/Enter رخ ندهد؛ پس از اتصال ادامه دهد.
5. **قطع هنگام انتظار پاسخ:** timer پاسخ در مدت قطعی مصرف نشود؛ پس از برگشت، انتظار `Was this task successful?` ادامه یابد.
6. **قطع و cancel:** در زمان قطعی از سایت توقف بزن؛ process tree حداکثر دو ثانیه‌ای متوقف شود.
7. **شکست واقعی OCR:** helper خراب/timeout شود؛ UIA همچنان اجازه مسیر اصلی را بدهد، ولی اگر هر دو روش شکست خوردند فرمان واضح و محدود متوقف شود.
8. **عدم ارسال دوباره:** پس از بازیابی شبکه بررسی کن یک پرامپت فقط یک بار ارسال شده باشد.
9. **حریم خصوصی:** با مانیتور شبکه ثابت کن تصویر OCR از دستگاه خارج نمی‌شود.
10. **rollback:** غیرفعال‌کردن دو capability و حذف پوشه vision باید بدون تغییر `app.py` ممکن باشد.

## ۷. گزارش تحویل به ایجنت مدیریت

پیش از اینکه کاربر دوباره پرامپت Arena بفرستد، این موارد را گزارش کن:

- branch و commit مخزن مادر
- فایل‌های تغییرکرده
- تأیید صریح اینکه `app.py` تغییر نکرده است؛ یا اگر hook لازم شد، diff و مجوز کاربر
- نسخه Python، PaddleOCR و PaddlePaddle
- مسیر runtime helper و venv
- نمونه JSON self-test
- Heartbeat واقعی شامل چهار capability اصلی
- نتیجه ده تست پذیرش بالا
- روش rollback

تا وقتی این گزارش و Heartbeat واقعی آماده نشده، `arena_vision_ocr=true` یا `network_resilience=true` اعلام نکن.
