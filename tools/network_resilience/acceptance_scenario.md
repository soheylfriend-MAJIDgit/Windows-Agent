# سناریوی پذیرش Network Resilience روی Windows واقعی

## هدف و ایمنی

این سناریو مستقل از `network_resilience=true` است؛ ابزار ثبت نتایج را می‌توان حتی وقتی قابلیت خاموش است اجرا کرد. ابزار هیچ شبکه‌ای را قطع نمی‌کند، هیچ کلیک/کلیدی نمی‌فرستد و هیچ پرامپتی ارسال نمی‌کند. اپراتور باید آزمون را روی یک اجرای Arena آزمایشیِ بی‌خطر انجام دهد و مقادیر را خودش ثبت کند. از پرامپت کاری/شخصی استفاده نکن.

تا وقتی آزمون local-cancel از خود UI در شرایط قطع شبکه ممکن نشده، marker نهایی عمداً قابل‌ساخت نیست. برای این hook هنوز فقط diff پیشنهادی `app.py` ارائه می‌شود و نباید آن را بدون اجازه اعمال کرد.

## ترتیب آزمون واقعی

1. برنامه‌ی Windows Agent را از `run.bat` باز کن و مطمئن شو نسخه/کامیت بالای پنجره با این شاخه یکی است.
2. برای اجرای آزمایشی از یک Arena session خالی و پرامپت بی‌خطر استفاده کن. در برنامه، job محلیِ ازپیش‌همگام‌شده‌ی `job_arena.py` را از کتابخانه‌ی محلی `CODES` اجرا کن (نه از صف/سایت مدیریت؛ اگر نسخه‌ی محلی موجود نیست، آزمایش را متوقف کن و ابتدا روش اجرای مستقل را هماهنگ کن). پیش از شروع، مرورگر را در صفحه‌ی ورودی قرار بده؛ اجرای آزمایش به قابلیت `network_resilience` وابسته نیست.
3. **قطع پیش از تعامل:** درست قبل از شروع job اینترنت را در Windows قطع کن. اجرای job را آغاز کن. ساعت شروع و وضعیت Offline را ثبت کن. هیچ click، keypress یا Enter از طرف job نباید رخ دهد.
4. **یک چرخه کامل:** دست‌کم ۶۰ ثانیه اتصال را قطع نگه دار. در طول این مدت شمار کلیک/کلید/Enter تولیدشده توسط خود job باید صفر باشد؛ UIA event، Enter کورکورانه، feedback و prompt retry هم ممنوع است.
5. **ادامه امن و ارسال یکتا:** اتصال را برگردان. job باید از آخرین checkpoint امن ادامه دهد، بدون ارسال کورکورانه‌ی Enter. شمار واقعی promptهای submit‌شده را در گزارش ثبت کن؛ باید دقیقاً ۱ باشد.
6. **no-progress:** outage نباید به‌عنوان no-progress مصرف شود یا باعث termination اشتباه شود. timeout کلی ایمنی مستقل باقی می‌ماند.
7. **عملیات غیرقابل‌بازیابی:** در یک اجرای جداگانه، عملیات را در checkpointی آزمایش کن که بعد از reconnect قابل ادامه نیست. انتظار: یک status نهایی `failed` با علت دقیق، بدون feedback یا prompt تکراری.
8. **لغو محلی در outage:** بعد از اعمال hook محلی با مجوز جداگانه، هنگام قطع کامل اینترنت لغو را از خود UI انجام بده. زمان از درخواست لغو تا توقف process tree باید حداکثر ۲ ثانیه باشد. لغو سایت به‌تنهایی در قطع کامل اینترنت کافی نیست.
9. فقط اگر تمام موارد بالا واقعاً روی Windows و در اجرای زنده موفق شدند، فایل recorder را اجرا کن و اندازه‌گیری‌ها را وارد کن:

```powershell
cd <مسیر مخزن Windows-Agent>
py -3 tools\network_resilience\record_acceptance.py
```

Recorder برای هر آزمون تأیید جداگانه می‌گیرد، مقادیر outage، UI actions، prompt send count، final failure status و local-cancel time را کنترل می‌کند، و برای هرکدام یک فایل screenshot/log از اپراتور می‌خواهد. فایل‌ها (هرکدام حداکثر ۱۲ MiB، مجموعاً ۸۰ MiB) با SHA-256 در گزارش ثبت و در `logs\\network_resilience_tests` کپی می‌شوند. این ثبت **operator-attested** است: ابزار Windows UI، شبکه یا محتوای evidence را مستقلاً تحلیل نمی‌کند؛ بنابراین پاسخ نادرست اپراتور همچنان قابل جعل است و این محدودیت باید در پذیرش سازمانی لحاظ شود.

## فایل‌های نتیجه و readiness marker

- گزارش: `<Windows-Agent-DB>\logs\network_resilience_tests\network_acceptance_<id>.json` (یا همان fallback امن Desktop\logs که برنامه استفاده می‌کند).
- marker: `%LOCALAPPDATA%\Windows-Agent\network_ready.json`
- Heartbeat فقط وقتی marker، گزارش/hash، build/version فعلی، همه‌ی نتایج و preflight زنده‌ی احرازشده و دارای schema مستند `GET /connection-test` معتبر باشند، `network_resilience=true` می‌فرستد. marker برای build قبلی یا marker ناقص/دست‌کاری‌شده پذیرفته نمی‌شود.
- اجرای recorder روی غیر Windows، پاسخ منفی، outage کمتر از ۶۰ ثانیه، هر input هنگام outage، تعداد ارسال غیر از ۱، status غیر از `failed` برای failure case، یا لغو بیش از ۲ ثانیه‌ای، marker نمی‌سازد.

## حذف marker و Rollback

برای غیرفعال‌کردن قابلیت و پاک‌کردن marker و گزارش آزمون، در ویندوز اجرا کن:

```powershell
py -3 tools\network_resilience\record_acceptance.py --rollback
```

یا BAT مستقل:

```text
tools\network_resilience\record_acceptance.bat --rollback
```

حذف marker باعث می‌شود Heartbeat در نوبت بعدی `network_resilience=false` اعلام کند. این rollback فقط پوشه‌ی `network_resilience_tests` و `network_ready.json` داخل LocalAppData را حذف می‌کند؛ به `app.py`، برنامه یا داده‌های کاربر دست نمی‌زند.
