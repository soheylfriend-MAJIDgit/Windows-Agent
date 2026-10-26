# کنترل مستقیم Google Drive (بدون Drive Desktop mirror)

## چه چیزی عوض می‌شود

`drive_control_transport.py` فایل‌های عملیاتی را مستقیماً از Google Drive API می‌خواند؛ پوشه‌ی محلی Drive Desktop دیگر منبع فرمان نیست. هر ۳ ثانیه، در صورت سالم‌بودن OAuth/API، از فایل‌های دارای **ID ثابت** در پوشه‌ی زیر poll می‌کند:

- پوشه: `1jOlamQWCNbr38-KgvOmA94CdWQwNg1OC`
- `COMMAND.json`: `1ypV2HwqTSwXQhTRIYuEAuB080JIu-KaE`
- `PAYLOAD.py`: `1RFVLgm0p7RJuNhZJ48j8pwPR6WIMeiUs`
- `CONTROL.txt`: `1B9w519L3nCkAnwjnt1t98TE_ZZOQBvzg`
- `STATUS.json` خروجی فعلی: `1fXrUnxuZPdAcO3dtmR4bndSKYjl8SxZM`
- `RESULT.json`: `1wyyEFvFjHaAB-YgD8z2R9IxDJbNYtq_u`
- `STDOUT.txt`: `1_OTvRJTJsNAJ3fixxZLAYWa1Ph19XVye`
- `STDERR.txt`: `1VLf0mElbvE-TuVSPG8Od2JbnubQLwdcX`

فایل‌های خروجی با `files.update` روی همان ID نوشته می‌شوند؛ transport هیچ فایل عملیاتی جدیدی نمی‌سازد. برای شروع payload هر دو شرط لازم است: `CONTROL.txt=play` در Drive **و** حالت خودکارِ محلی برنامه روشن باشد؛ حالت دستی یا وضعیت Drive برابر `pause`، اجرا را متوقف می‌کند. فایل‌هایی که محتوایشان تغییر کند، با version/MD5 دوباره بررسی می‌شوند. payload فقط پس از تأیید envelope، `issuedAt`/`expiresAt`، `commandId` یکتا، revision صعودی، action و تطبیق SHA-256 اجرا می‌شود. نتیجه‌ی هر `commandId:revision` در `%LOCALAPPDATA%\Windows-Agent\drive_control_state.json` ثبت می‌شود تا پس از restart دوباره اجرا نشود.

## راه‌اندازی OAuth ـ فقط با اقدام دستی مالک

این transport تا زمانی که مالک یک‌بار OAuth را به‌صورت تعاملی تکمیل نکند شروع نمی‌شود. در Google Cloud Console:

1. Google Drive API را برای پروژه‌ی خود فعال کن.
2. OAuth consent screen را تکمیل و یک OAuth client از نوع **Desktop app / Installed app** بساز.
3. فایل client JSON را روی خود Windows Agent دریافت کن. آن را در Git، Google Drive، log یا چت قرار نده.
4. مطمئن شو `CONTROL.txt` آنلاین هنوز `pause` دارد؛ همین مقدار fail-closed است و اجازه‌ی اجرای payload نمی‌دهد.
5. `run.bat` را یک‌بار اجرا کن تا برنامه و وابستگی‌های معمول آماده باشند، سپس برنامه را ببند.
6. در Windows با همان حساب کاربری که Agent را اجرا می‌کند، اجرا کن. اگر کتابخانه‌های اختیاری Google نصب نیستند، BAT ابتدا برای دانلودشان از PyPI اجازه می‌گیرد:

```bat
tools\drive_control\authorize.bat "C:\مسیر\client_secret_desktop.json"
```

مرورگر برای رضایت OAuth باز می‌شود. پس از پایان، credential/refresh token با DPAPI فقط در `%LOCALAPPDATA%\Windows-Agent\drive_control_oauth.bin` ذخیره می‌شود. setup در شروع برنامه اجرا نمی‌شود و هیچ توکنی در log یا Drive نوشته نمی‌شود. اگر OAuth لغو شود، منقضی/باطل شود یا API در دسترس نباشد، payload اجرا نمی‌شود.

7. برنامه را دوباره از `run.bat` باز کن. Controller باید در `STATUS.json` آنلاین وضعیت `paused` یا `waiting` را ثبت کند؛ در این مرحله هیچ dialogی نباید ظاهر شود چون `CONTROL.txt` برابر `pause` است.
8. فقط وقتی آماده‌ی آزمون زنده‌ای، در Google Drive وب خودت `CONTROL.txt` را به `play` تغییر بده. اجرای فرمان جدید حداکثر در چرخه‌ی poll بعدی آغاز می‌شود. برای توقف شروع فرمان‌های تازه آن را به `pause` تغییر بده. `stop` درخت payload جاری را می‌بندد و transport را متوقف می‌کند؛ پس از تغییر دوباره به `play`، برنامه را restart کن تا poller دوباره شروع شود. اگر `pause` هنگام payload جاری برسد، آن payload به‌صورت fail-closed متوقف و برای جلوگیری از replay ثبت نهایی می‌شود؛ برای اجرای مجدد یک commandId/revision تازه صادر کن.

## حفاظت و شکست امن

- خطای OAuth، timeout، API failure، پاسخ ناقص، فایل در حال تغییر، ID ناشناخته، hash نامطابق یا CONTROL نامعتبر، همگی fail-closed هستند؛ خطای ارتباط هنگام اجرای payload هم در اولین بررسی بعدی موجب توقف درخت فرایند می‌شود.
- یک فرمان فقط یک بار برای هر `commandId:revision` اجرا می‌شود. اگر Controller هنگام اجرای یک فرمان بسته شود، آن فرمان `interrupted` ثبت می‌شود و خودکار replay نمی‌شود؛ برای تلاش تازه revision/commandId جدید لازم است.
- payload در پوشه‌ی موقت `%LOCALAPPDATA%\Windows-Agent\drive_control_*` اجرا می‌شود؛ هیچ `COMMAND.json` یا `PAYLOAD.py` از Drive Desktop کپی نمی‌شود.
- OAuth Drive scope امکان خواندن/نوشتن فایل‌های Drive را می‌دهد؛ آن را فقط برای حسابی فعال کن که مالک، فایل‌ها و اثر اجرای payload به آن اعتماد دارد. این transport، endpoint اجرای کد است، نه sandbox برای کد ناشناس.
- برای خاموش‌کردن، برنامه را ببند و فایل `%LOCALAPPDATA%\Windows-Agent\drive_control_oauth.bin` را از Windows حذف کن؛ سپس transport با نبود credential شروع نمی‌شود. برای revoke کامل، دسترسی app را هم از Google Account → Security → Third-party access لغو کن.

## محدودیت آزمون این patch

آزمون‌های محلی از fake Drive API استفاده می‌کنند؛ این محیط نه Google OAuth مالک را دارد و نه به `googleapis.com` دسترسی خروجی. بنابراین دریافت واقعی فایل، OAuth زنده، latency 3–5 ثانیه، نشست interactive ویندوز و نمایش dialog هنوز باید روی همان Windows Agent تأیید شود. فایل آنلاین فعلی `CONTROL.txt` مقدار `pause` دارد؛ کد را عمداً اجرا یا آن را تغییر نده.
