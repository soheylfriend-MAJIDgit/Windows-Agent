# نصب ایزوله PaddleOCR و وضعیت Arena Bridge 7

## وضعیت فعلی و محدودیت‌های تأیید

ماژول‌ها و installer مستقل در `tools/vision/` آماده شده‌اند. آن‌ها محیط ایزوله را فقط در `%LOCALAPPDATA%\Windows-Agent\vision` می‌سازند؛ هیچ تغییری در `app.py` داده نشده است. در این checkout، اجرای Windows، دانلود مدل‌های Paddle و آزمون واقعی UI/قطع شبکه ممکن نیست. به همین دلیل `arena_vision_ocr` و `network_resilience` در Heartbeat عمداً `false` می‌مانند تا آزمون‌های واقعی روی ویندوز تکمیل شوند. این دو قابلیت را به‌صورت دستی `true` نکنید.

مدل‌ها در اولین نصب نیاز به دانلود دارند. برای دریافت آن‌ها باید کاربر آگاهانه دستور زیر را اجرا کند؛ این دستور هرگز از startup یا Heartbeat فراخوانی نمی‌شود:

```powershell
python tools\vision\install_vision.py --install-packages
```

نصب CPU با نسخه‌های pin شده در `tools/vision/requirements-vision.txt` در venv ایزوله انجام می‌شود. pip با timeout شبکه‌ی ۱۸۰ ثانیه و ۱۲ retry اجرا می‌شود و تا سه بار کل نصب را تلاش می‌کند؛ cache و venv در شکست پاک نمی‌شوند. اگر دانلود قطع شد، همان `install_vision.bat` را دوباره اجرا کنید؛ نیازی به حذف دستی پوشه نیست. در همان اجرای آگاهانه، fixture محلی ساخته و مدل warm-up می‌شود. بعد از آن، آزمون self-test را با قطع اینترنت اجرا کنید:

```powershell
$root = Join-Path $env:LOCALAPPDATA 'Windows-Agent\vision'
& "$root\.venv\Scripts\python.exe" "$root\paddle_ocr_helper.py" --selftest --offline --json
```

نمونه‌ی شکل JSON مورد انتظار (مقادیر واقعی مختص هر تصویر/مدل است):

```json
{"ok":true,"engine":"paddleocr","items":[{"text":"Was this task successful?","confidence":0.97,"bounds":[470,790,1420,855]}]}
```

stdout helper فقط یک JSON UTF-8 است؛ پیام‌های کتابخانه و خطا به stderr می‌روند. Helper ورودی URL، UNC و Base64 را رد می‌کند، تصویر یا متن را به شبکه نمی‌فرستد و فایل ورودی را حذف نمی‌کند. `--offline` تلاش‌های اتصال سوکت را مسدود می‌کند.

## فایل‌های نصب/runtime

- نصب‌کننده و requirements در مخزن: `tools/vision/install_vision.py`, `tools/vision/requirements-vision.txt`
- Helper منبع در مخزن: `tools/vision/paddle_ocr_helper.py`
- Runtime پس از نصب: `%LOCALAPPDATA%\Windows-Agent\vision\paddle_ocr_helper.py`
- Venv: `%LOCALAPPDATA%\Windows-Agent\vision\.venv`
- مدل و cache: `%LOCALAPPDATA%\Windows-Agent\vision\models` و `cache`

هنگام اجرای `job_arena.py` از مسیر D1، manager قبل از اجرا مسیرهای absolute را بررسی می‌کند، reparse/symlink فراری را رد می‌کند، helper را با سقف ۴۵ ثانیه و process group مستقل برای self-test اجرا می‌کند و فقط دو متغیر مسیر OCR را به subprocess Arena تزریق می‌کند. اگر preflight شکست بخورد، فرمان با `ocr_preflight_failed` متوقف می‌شود. مسیر اصلی UI Automation دست‌نخورده می‌ماند؛ job Bridge 7 باید OCR را تنها fallback قرار دهد.

## مرحله‌ی تکمیلی موردنیاز روی Windows

قبل از آن‌که مدیریت Arena را به‌عنوان آماده اعلام کنید، موارد زیر باید روی همان Windows Agent واقعی انجام و خروجی/مدارک ثبت شوند:

1. Python، PaddlePaddle و PaddleOCR version واقعی (`python.exe -c "import paddle,paddleocr; ..."`)؛ بررسی سازگاری بسته‌ها با نسخه و معماری ویندوز. اگر `libpaddle.pyd` با پیام `DLL load failed` مواجه شد، helper پیش از import مسیرهای DLL مجزای `paddle/libs` و کتابخانه‌های عددی را به DLL search path همین پردازش اضافه و نصب را بدون دانلود مدل بررسی می‌کند. `install_vision.bat` نیز Microsoft Visual C++ x64 Runtime را بررسی می‌کند و در صورت نیاز با رضایت جداگانه از دامنه‌ی رسمی Microsoft می‌گیرد؛ امضای Authenticode قبل از اجرا بررسی می‌شود و نصب ممکن است تأیید مدیر سیستم بخواهد.
2. نصب با رضایت کاربر، دانلود یک‌باره مدل، warm-up و اجرای self-test بعد از قطع اینترنت؛ عبارت `Was this task successful?` باید از تصویر واقعی پیدا شود.
3. آزمون UIA موفق و UIA ناموفق با OCR و guard نوار آدرس؛ اطمینان از نبود کلیک تکراری.
4. قطع شبکه قبل از تایپ و هنگام انتظار پاسخ، بازگشت پس از چرخه ۶۰ثانیه‌ای و اثبات ارسال دقیقاً یک‌باره.
5. لغو از سایت و لغو محلی طی حداکثر ۲ ثانیه؛ پایش process tree و no-progress timer حین قطعی.
6. شکست واقعی OCR، timeout helper، حفظ تصویر ورودی و failure تمیز.
7. آزمون شبکه/فایروال یا packet capture روی Windows ثابت کند هیچ بایت تصویر/متن OCR به سرویس بیرونی ارسال نمی‌شود.
8. rollback:

```powershell
python tools\vision\install_vision.py --rollback
```

این دستور فقط پوشه `vision` را حذف می‌کند؛ به `app.py`، پوشه برنامه یا داده‌های کاربر دست نمی‌زند.

در صورت خطای import بومی Paddle، نصب‌کننده پیش از دانلود مدل یک اسکن ایستا از جدول import فایل‌های DLL اجرا می‌کند و فیلد `missingDlls` را در گزارش خطا می‌آورد. این گزارش برای تشخیص dependency واقعی است؛ تا وقتی علت پیدا و روی Windows رفع نشده، اجرای دوباره‌ی حدسی یا فعال‌کردن capabilityها توصیه نمی‌شود.

تا تکمیل این فهرست، capabilityهای `arena_vision_ocr` و `network_resilience` باید `false` بمانند و Manager Arena نباید پرامپت را صف کند. به‌ویژه UI اصلی هنوز برای لغو محلی در زمان قطع شبکه hook ندارد؛ اضافه‌کردن hook به `app.py` بدون مجوز جداگانه مجاز نیست.
