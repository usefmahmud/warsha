# TODO — قائمة مهام بسيطة (FastAPI + React)

مشروع Atlas — Project key: **TODO**.
Backend واحد بيقدّم الـAPI **والـSPA** من نفس البورت، RTL كامل، تصميم داكن.

```
todo/
├── backend/          FastAPI + SQLAlchemy + SQLite (WAL)
│   ├── app/          config · database · models · schemas · errors · spa · main
│   ├── app/routers/  todos.py (CRUD + toggle + filters)
│   └── tests/        pytest (38 test)
└── frontend/         React 19 + Vite 7 + Tailwind 4 (RTL)
    └── src/          App.tsx · api.ts · types.ts · components/ · lib/
```

## تشغيل سريع

```bash
# 1) backend deps (مرة واحدة)
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 2) frontend build (مرة واحدة، أو بعد أي تعديل في الواجهة)
cd ../frontend
npm install
npm run build          # tsc --noEmit && vite build  → frontend/dist

# 3) شغّل السيرفر (بيقدّم الـAPI + الواجهة مع بعض)
cd ../backend
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8093
```

بعدها افتح **http://127.0.0.1:PORT/** — الواجهة، والـdocs على **/docs**، والصحة على **/api/health**.

### تطوير الواجهة (hot reload)

```bash
cd frontend && npm run dev          # http://localhost:5174 — بيعمل proxy لـ /api على 8093
```

## الاختبارات

```bash
cd backend && .venv/bin/python -m pytest          # 38 passed
```

كل test بياخد قاعدة SQLite مؤقتة خاصة بيه (drop/create قبل كل واحد) — مش بيلمس `todo.db`.

## API

Base: `/api` — الأخطاء كلها بنفس الشكل:
`{"error": {"code": "...", "message": "...", "details": [...], "request_id": "req_..."}}`

| Method | Path | الوظيفة |
|---|---|---|
| GET | `/api/health` **و** `/health` | صحة السيرفر + نوع الـDB (`/health` alias للـcontainer healthcheck) |
| GET | `/api/meta` | إصدار + ليفلات الأولوية بالعربي |
| GET | `/api/todos` | قائمة — فلاتر: `done=true\|false`, `q=` (بحث في العنوان والملاحظات), `priority=low\|normal\|high`, `limit` |
| POST | `/api/todos` | إنشاء — `{title*, notes?, priority?, due_date?}` → 201 |
| GET | `/api/todos/{id}` | مهمة واحدة |
| PATCH | `/api/todos/{id}` | تعديل جزئي (`title/notes/done/priority/due_date`)، جسم فاضي → 422 `EMPTY_PATCH` |
| DELETE | `/api/todos/{id}` | حذف → 204 |
| POST | `/api/todos/{id}/toggle` | قلب حالة الإنجاز |

**شكل القائمة:** `{items: [...], count, open_count, done_count}` — العدادات دايمًا على البورد كله، مش على النتيجة المفلترة.
**الترتيب:** المفتوح الأول ← أولوية عالية ← الأحدث إنشاءً.

### فاليديشن
- `title`: بعد trim لازم 1..200 حرف (فاضي/مسافات → 422، > 200 → 422).
- `priority`: `low` | `normal` | `high` بس.
- `due_date`: `YYYY-MM-DD` أو `null`.
- حقول زيادة في الـbody → 422 (extra="forbid").
- مفاتيح مجهولة → 404 بنفس الـenvelope، و**مش** بترجع الـSPA.

### مثال curl

```bash
curl -s -X POST http://127.0.0.1:PORT/api/todos \
  -H 'Content-Type: application/json' \
  -d '{"title":"اشتري لبن","priority":"high"}'

curl -s -X POST http://127.0.0.1:PORT/api/todos/<id>/toggle
curl -s "http://127.0.0.1:PORT/api/todos?done=false&q=لبن"
curl -s -X DELETE http://127.0.0.1:PORT/api/todos/<id> -o /dev/null -w '%{http_code}\n'
```

## إعدادات البيئة (اختياري، prefix `TODO_`)

| متغير | افتراضي | ملاحظات |
|---|---|---|
| `TODO_DATABASE_URL` | `sqlite:///./todo.db` | SQLite + WAL |
| `TODO_STATIC_DIR` | `../frontend/dist` | مسار build الواجهة |
| `TODO_CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | comma-separated |
| `TODO_ENV` | `development` | |
| `TODO_SQL_ECHO` | `false` | لوج SQL |

## ملاحظات

- الـSPA بيتعمله mount من نفس عملية الـFastAPI (زي Atlas): `/assets/*` ستاتيك، وأي مسار تاني بيرجع `index.html`.
- لو `frontend/dist` مش موجود، السيرفر بيلوج warning وبيشتغل API-only (الاختبارات بتستغل ده).
- التصميم داكن بنفس هوية Atlas (ink/brand) بخطوط عربية sys­tem — من غير أي CDN.
