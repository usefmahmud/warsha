# Atlas — Backend (FastAPI)

منصة إدارة مشاريع وتيكتس self-hosted للفريق — **v1 (MVP)**.
الـbackend مبني على `PRD.md` (v1.0): نفس المسارات، أسماء الحقول، أكواد الأخطاء،
قواعد الحالات، وبصمة `request_id` في كل رد.

> **الحالة:** ✅ 94 اختبار pytest بيعدّوا · ✅ smoke test E2E حقيقي مع إعادة تشغيل · ✅ `ruff` نضيف.
> **النشر (Docker/nginx/بورت) مش هنا** — ده TASK-2026-021 عند ياسين.

## Stack

| المكوّن | الاختيار | السبب |
|---|---|---|
| Web | FastAPI 0.163 + uvicorn | OpenAPI على `/docs` و`/api/openapi.json` |
| ORM | SQLAlchemy 2.1 (sync) | تنقّل مباشر لـ Postgres |
| DB | SQLite + **WAL** + `foreign_keys=ON` + `busy_timeout=15s` | كاتب واحد متسلسل، قراءات متزامنة |
| IDs | UUID4 من التطبيق (String(36)) | نفس الـschema على Postgres (PRD §6.3) |
| Auth | JWT HS256 (12h) + bcrypt | مفيش passlib |
| Agent | `X-API-Key: atl_<prefix>_<secret>` مخزّن **sha256** | PRD AC-04.5 |
| Tests | pytest + TestClient (94) | concurrency test بـ20 thread |
| Python | 3.14 (متوافق مع 3.12+) | venv محلي `.venv` |

## تشغيل سريع

```bash
cd ~/ai-team/projects/atlas/backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

export ATLAS_SECRET_KEY="$(python -c 'import secrets;print(secrets.token_urlsafe(48))')"
export ATLAS_DATABASE_URL="sqlite:///./atlas.db"

.venv/bin/python -m app.cli seed-agents      # owner + 6 وكلاء (باسوردات مرة واحدة)
.venv/bin/python -m app.cli seed-demo        # مشروع ATL + 4 تيكتس + ليبلز (اختياري)
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8080
```

- Docs: `http://<host>:8080/docs` · Health: `GET /api/health` (و`/health` للـhealthcheck) · Meta: `GET /api/meta`
- البورت النهائي من `INFRA.md` (ياسين) — الكود مابيفترضش بورت.

### الاختبارات والفحص

```bash
.venv/bin/python -m pytest          # 94 passed
.venv/bin/ruff check app tests      # All checks passed
bash scripts/smoke.sh               # E2E على بورت 18080 (DB مؤقتة)
```

## متغيرات البيئة

| المتغير | افتراضي | ملاحظات |
|---|---|---|
| `ATLAS_SECRET_KEY` | — (ephemeral في dev) | **إلزامي في production** وإلا التطبيق يرفض يقلع |
| `ATLAS_ENV` | `development` | `production` / `test` |
| `ATLAS_DATABASE_URL` | `sqlite:///./atlas.db` | Docker: `sqlite:////data/atlas.db` |
| `ATLAS_ACCESS_TOKEN_EXPIRE_MINUTES` | `720` | 12 ساعة (PRD Q2) |
| `ATLAS_ALLOW_REGISTRATION` | `true` | production: `false` (التسجيل الذاتي بيقفل بعد أول حساب أساسًا) |
| `ATLAS_CORS_ORIGINS` | `http://localhost:5173,…` | مفصولة بفواصل |
| `ATLAS_RATE_LIMIT_PER_MINUTE` | `300` | per token/IP (PRD §7.1) |
| `ATLAS_LOGIN_ATTEMPTS_PER_MINUTE` | `5` | 429 + `Retry-After` (AC-01.4) |
| `ATLAS_ALLOW_PRIVATE_WEBHOOKS` | `false` | يفتح webhooks لـ127.0.0.1/10.x (AC-21.4) |

مفيش أسرار في الكود: المفاتيح بتتخزن sha256، والـsecret من env.

## جدول البيانات (13 جدول)

`users · api_keys · projects · project_members · labels · tickets · ticket_labels ·
comments · mentions · activity · notifications · attachments · webhooks`

الفهارس الإلزامية (PRD §6.2) موجودة: `(project_id, number)` و`(project_id, client_ref)`
unique، `(project_id, status, board_position)`، `(assignee_id, status)`، `(project_id, updated_at)`،
`(parent_id)`، `(due_date, status)`، `(ticket_id, created_at)`، `(user_id, read_at, created_at)`.

## الأدوار (PRD §3.1)

| العملية | owner | admin | member |
|---|:--:|:--:|:--:|
| إنشاء مشروع | ✅ | ✅ | ❌ (`403`) |
| تعديل/أرشفة/أعضاء/ليبلز | ✅ | ✅ | ❌ |
| تيكتس: إنشاء/تعديل/نقل حالة/كومنت | ✅ | ✅ | ✅ |
| `done → *` (إعادة فتح) | ✅ | ✅ | ❌ (`403 REOPEN_FORBIDDEN`) |
| حذف تيكت (soft) | ✅ | ✅ | ❌ |
| إدارة مستخدمين وأدوار | ✅ | ✅ (ماعدا owner) | ❌ |
| API key لنفسه / لغيره | ✅ | ✅ / ❌ | ✅ / ❌ |
| Webhooks | ✅ | ✅ | ❌ |

غير العضو بياخد **404 `PROJECT_NOT_FOUND`** على أي مسار مشروع (منع تسريب الوجود — AC-02.4).

## الحالات والانتقالات (PRD §5.1)

```
backlog · todo · in_progress · review · blocked · done   (ترتيب الأعمدة ثابت)
```

- أي حالة → أي حالة، **ما عدا** `done → *` لمستخدم `member` (`403 REOPEN_FORBIDDEN`).
- `to=blocked` بدون `blocked_reason` (3..500 حرف) → `422 BLOCKED_REASON_REQUIRED`، والسبب بيتسجل في الـactivity وبيتمسح عند الخروج.
- `done` بيحط `closed_at`، والخروج منه بيمسحه.
- إغلاق تيكت ليه subtasks مفتوحة **مسموح** لكن بيرجّع `warnings[]` (AC-10.5/11.4).
- **Optimistic concurrency:** `If-Match: <version>` (أو `version` في الجسم) — لو قديم → `409 CONFLICT_STALE`.

## الترقيم الذرّي (AC-08.3)

`UPDATE projects SET ticket_seq = ticket_seq + 1 … RETURNING ticket_seq` — بيان واحد ذرّي،
+ retry ×3 على `database is locked` → بعدها `503 TRY_AGAIN`، و`UNIQUE(project_id, number)` كشبكة أمان.
اختبار `test_concurrent_creation_has_no_duplicates` بيعمل 20 إنشاء متوازي ويتأكد `1..20` بدون فجوات.
الحذف soft والرقم مايتعادش استخدامه.

## Mentions

- `@username` فقط (`^[a-z0-9_]{3,32}$`)، بعد **استبعاد** fenced code / inline code / روابط markdown.
- صف في `mentions` + إشعار `type=mention` **مرة واحدة لكل (تعليق، مستخدم)**.
- مستخدم غير موجود → بيتجاهل بهدوء. نفس الكاتب → بيتسجل الـmention بدون إشعار.

## شكل الردود

```json
{"items": [...], "total": 87, "limit": 50, "offset": 0}
{"error": {"code": "TICKET_NOT_FOUND", "message": "...", "details": {}, "request_id": "req_7f3a"}}
```

- `code` ثابت UPPERCASE للميكنة، `message` للعرض، `details` اختياري، و`X-Request-Id` في كل رد (وبيتخزن في `activity.request_id`).
- الفلاتر بتقبل تكرار البارامتر (AND) أو قيم مفصولة بفاصلة (OR): `?label=backend,ui&status=todo`.
- الفرز: `?sort=-priority,due_date` (سالب = تنازلي؛ الأولوية بترتيبها المخصص urgent→low، و`due_date` بـnulls last).

## خريطة الـAPI (50 مسار · 68 عملية) — كلها في `/docs`

**Auth** `POST /api/auth/register|login|password|logout` · `GET|PATCH /api/auth/me`
**Users/Keys** `GET|POST /api/users` · `GET|PATCH /api/users/{id}` · `POST /api/users/{id}/deactivate` ·
`GET|POST /api/users/{id}/api-keys` · `DELETE /api/api-keys/{id}`
**Projects** `GET|POST /api/projects` · `GET|PATCH /api/projects/{ref}` · `POST /api/projects/{ref}/archive|unarchive` ·
`GET|POST /api/projects/{ref}/members` · `DELETE /api/projects/{ref}/members/{user_id}` ·
`GET /api/projects/{ref}/board` · `GET|POST /api/projects/{ref}/tickets` · `GET|POST /api/projects/{ref}/labels`
**Tickets** `GET /api/tickets` · `GET|PATCH|DELETE /api/tickets/{ref}` · `POST /api/tickets/{ref}/transition` ·
`GET /api/tickets/{ref}/children|activity|attachments|comments` · `POST /api/tickets/{ref}/attachments|comments|labels` ·
`DELETE /api/tickets/{ref}/labels/{label_id}` · `DELETE /api/attachments/{id}` · `PATCH|DELETE /api/comments/{id}` ·
`PATCH|DELETE /api/labels/{id}`
**Views** `GET /api/me/work|me/mentions|me/projects` · `GET /api/search`
**Notifications** `GET /api/notifications` · `GET /api/notifications/unread_count` · `POST /api/notifications/{id}/read|read-all`
**Agent (API key فقط)** `GET /api/agent/me` · `POST|GET /api/agent/tickets` · `GET|PATCH /api/agent/tickets/{ref}` ·
`POST /api/agent/tickets/{ref}/transition|comments` · `GET /api/agent/my-tickets`
**System** `GET /api/health` · `GET /api/meta` · `GET /api/webhooks` (+CRUD, admin) · `/docs` · `/api/openapi.json`

`{ref}` = `ATL-12` أو UUID التيكت.

### مثال وكيل

```bash
# مفتاح (مرة واحدة)
curl -s -X POST localhost:8080/api/users/$MY_ID/api-keys \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"name":"omar-cli"}'

# إنشاء تيكت (idempotent بـclient_ref)
curl -s -X POST localhost:8080/api/agent/tickets \
  -H "X-API-Key: atl_xxx" -H 'Content-Type: application/json' \
  -d '{"project_key":"ATL","title":"Pagination","priority":"high",
       "description_md":"راجع @maryam","client_ref":"run-42-step-3"}'

# نقل حالة + كومنت
curl -s -X POST localhost:8080/api/agent/tickets/ATL-7/transition \
  -H "X-API-Key: atl_xxx" -H 'Content-Type: application/json' -d '{"to":"in_progress"}'
```

## Webhooks

`POST /api/webhooks {url, events[], project_id?}` → secret مرة واحدة، والـbody موقّع
`X-Atlas-Signature: sha256=<hmac(secret, body)>`. الأحداث: `ticket.created · ticket.updated ·
ticket.status_changed · ticket.assigned · ticket.done · comment.created`.
الدفع في background، مابيفشّلش الطلب؛ 3 محاولات فاشلة → `active=false`؛ وعناوين داخلية مرفوضة (SSRF).

## النسخ الاحتياطي / الاستعادة

```bash
.venv/bin/python scripts/backup.py --db /data/atlas.db --out /backups --keep 7
# backup ok: /backups/atlas-20261117-161259.db (258048 bytes, integrity_check=ok)
```

`sqlite3.Connection.backup()` — آمن والتطبيق شغال، + `PRAGMA integrity_check` قبل النجاح، retention 7 نسخ.
كرون (ياسين): `15 3 * * * cd /srv/atlas/backend && .venv/bin/python scripts/backup.py --db /data/atlas.db --out /backups --keep 7`
الاستعادة: وقّف الخدمة → انسخ النسخة مكان `atlas.db` (وامسح `-wal`/`-shm`) → شغّل.

## ملاحظات لياسين (Docker)

- `uvicorn app.main:app --host 0.0.0.0 --port $PORT` · healthcheck: `GET /api/health` أو `/health`.
- volume على `/data` (DB + `-wal` + `-shm` لازم نفس FS).
- `ATLAS_ENV=production` + `ATLAS_SECRET_KEY` + `ATLAS_ALLOW_REGISTRATION=false`.
- 1 worker يكفي (SQLite كاتب واحد) ≈ 60–90MB RSS.
- الـschema بيتعمل `create_all` عند الإقلاع (idempotent) — مفيش migrations إجبارية في v1.

## حدود v1 (مقصودة) ومخاطر

1. **SQLite كاتب واحد** — كافي لـ7 مستخدمين + polling؛ الترقية لـPostgres بمتغير واحد (نفس الـschema).
2. **مفيش Alembic** — أول تعديل schema بعد الإطلاق محتاج migrations (v1.1).
3. **Realtime = polling 10s** (مفيش WebSocket — خارج النطاق §2.2).
4. **البحث LIKE مع تطبيع عربي** (همزات/تشكيل/تاء مربوطة) بدل FTS5 — يغطي v1، FTS5 تحسين لاحق.
5. **rate limit in-memory** — بيعتمد على worker واحد (مفيش Redis في v1).
6. **مفيش رفع ملفات** — المرفقات لينك فقط (`400 NOT_SUPPORTED_IN_V1`).
