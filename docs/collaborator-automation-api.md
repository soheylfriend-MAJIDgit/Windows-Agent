# قرارداد API ایجنت همکار برای کدهای اتوماسیون D1

ایجنت همکار برای کدهای اتوماسیون به repository، Git CLI، GitHub token، Commit یا Push نیاز ندارد. کد پایه سایت مدیریت و Windows Agent همچنان در مخزن‌های متعلق به مدیریت و مادر باقی می‌مانند.

## کلید

از تب «کلید ایجنت» یک کلید مستقل برای همکار بسازید. حداقل scopeها:

- `automations:read`
- `automations:write`
- `automations:run`

کلید در Authorization header و هرگز در URL یا متن کد اتوماسیون قرار نگیرد:

```http
Authorization: Bearer wam_agent_...
Content-Type: application/json
```

Base URL عمومی:

```text
https://<management-worker>/api/collaborator
```

## فهرست

```http
GET /automations
```

## ساخت اتوماسیون یا نسخه نخست

```http
POST /automations
```

```json
{
  "slug": "arena_helper",
  "name": "کمک‌یار Arena",
  "description": "شرح کار",
  "target": "windows",
  "sourceCode": "#!/usr/bin/env python3\n...",
  "changeSummary": "نسخه نخست",
  "activate": true
}
```

`slug` با حروف لاتین/عدد/زیرخط و کد حداکثر ۲۵۶KB است. هر POST نسخه immutable تازه با SHA-256 می‌سازد.

## خواندن کد و نسخه‌ها

```http
GET /automations/{automationId-or-slug}
```

پاسخ شامل source نسخه فعال و metadata تاریخچه است.

## ساخت نسخه تازه

```http
POST /automations/{automationId}
```

```json
{
  "sourceCode": "#!/usr/bin/env python3\n...",
  "changeSummary": "رفع خطای مرحله ورود",
  "activate": true
}
```

## درخواست اجرا

```http
POST /automations/{automationId}/run
```

این درخواست کد را داخل command حمل نمی‌کند؛ فرمان فقط `versionId`, `sourceSha256` و endpoint دریافت نسخه را در D1 ثبت می‌کند. Windows Agent نسخه immutable را می‌گیرد و hash را بررسی می‌کند.

## پایش و توقف فرمان

```http
GET  /commands/{commandId}
POST /commands/{commandId}/cancel
```

بدنه توقف اختیاری است:

```json
{"reason":"توقف پس از تشخیص رفتار غیرعادی"}
```

خواندن فرمان به `automations:read` و توقف به `automations:run` نیاز دارد.

## مرزها

- API، SQL آزاد یا دسترسی مستقیم D1 نمی‌دهد.
- این API کد پایه `app.py`, `manager_client.py` یا Next.js را تغییر نمی‌دهد.
- Python اتوماسیون طبق سیاست دستی/خودکار Windows Agent اجرا می‌شود.
- ایجنت همکار موظف است کد پایه و secretها را تغییر ندهد یا نخواند.
- تصاویر و لاگ‌های حجیم در Drive می‌مانند؛ D1 فقط metadata را نگه می‌دارد.
