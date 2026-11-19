# WHITEBOARD — منصة رسم ووايت بورد self-hosted

منصة وايت بورد عربية (RTL) بثيم داكن: ترسم بالماوس أو باللمس، تضيف أشكال ونصوص وملاحظات،
تحرّك/تكبّر/تدوّر، والبورد بيتحفظ تلقائيًا على السيرفر مع رابط مشاركة للقراءة.

- **Backend:** FastAPI + SQLAlchemy + SQLite (WAL) — نفس أسلوب Atlas، ويخدم الفرونت من نفس العملية.
- **Frontend:** React 19 + Vite 7 + Tailwind 4 + **Fabric.js 6**.

```
whiteboard/
├── backend/            # API + static SPA host
│   ├── app/            # config · database · models · schemas · routers/boards · spa · main
│   ├── tests/          # pytest (40 tests)
│   └── requirements.txt
├── frontend/           # React + Vite + Tailwind + Fabric
│   └── src/editor/     # engine.ts (كل منطق الكانفس) · useWhiteboard · Toolbar · StylePanel · TopBar
└── scripts/            # serve.sh · dev.sh
```

## التشغيل السريع (بدون docker — التغليف مسؤولية ياسين)

```bash
cd backend
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt

cd ../frontend
npm install && npm run build

cd ../backend
WB_STATIC_DIR=../frontend/dist ./.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8094
# افتح http://127.0.0.1:8094
```

أو بس:

```bash
./scripts/serve.sh          # build + serve على 8094
./scripts/dev.sh            # backend :8094 (--reload) + vite :5174 مع proxy
```

## الإعدادات (env — كلها اختيارية للتطوير)

| المتغير | الافتراضي | المعنى |
|---|---|---|
| `WB_DATABASE_URL` | `sqlite:///./whiteboard.db` | مسار قاعدة البيانات (WAL + busy_timeout 15s) |
| `WB_STATIC_DIR` | `../frontend/dist` | مكان بناء الواجهة اللي يتخدم من نفس العملية |
| `WB_CORS_ORIGINS` | `localhost:5173` | مسموح به في وضع التطوير بس |
| `WB_MAX_DOC_BYTES` | `4194304` | سقف حجم مستند البورد (4MB) |
| `WB_MAX_BOARDS` | `500` | سقف عدد البوردات |

مفيش أسرار في الكود؛ ملف `.env.example` موجود كمرجع.

## API

| Method | Path | الوظيفة |
|---|---|---|
| `GET` | `/api/health` | حالة السيرفر + الـDB |
| `GET` | `/api/boards` | قائمة البوردات (بدون `doc` — خفيفة للأداء) |
| `POST` | `/api/boards` | إنشاء بورد (`name`, `color`, `doc?`) |
| `GET` | `/api/boards/{id}` | بورد كامل بالمستند |
| `PATCH` | `/api/boards/{id}` | حفظ/تعديل — `doc` + `version` (تعارض ⇒ **409**) |
| `DELETE` | `/api/boards/{id}` | حذف |
| `POST` | `/api/boards/{id}/share` | إنشاء/إرجاع توكن المشاركة (idempotent) |
| `DELETE` | `/api/boards/{id}/share` | إلغاء التوكن |
| `GET` | `/api/boards/{id}/thumb` | صورة مصغّرة PNG |
| `GET` | `/api/shared/{token}` | البورد للقراءة فقط عبر التوكن |

**الحفظ التلقائي:** الواجهة بتبعت `PATCH` بعد ~2 ثانية من آخر تعديل مع `version` الأخيرة.
لو حد تاني كتب قبلك، السيرفر بيرجّع `409` ومعه نسخة السيرفر الحالية، والواجهة بتعرض
مربع تعارض فيه اختيارين: تحمّل نسخة السيرفر، أو تكتب نسختك فوقها.

## الاختبارات

```bash
cd backend && ./.venv/bin/python -m pytest      # 40 passed
./.venv/bin/ruff check app tests                # All checks passed
cd frontend && npm test                         # 12 passed (node --test)
npm run build                                   # tsc -b + vite build
```

التغطية: CRUD · autosave/versioning · تعارض 409 · سقف حجم المستند · مشاركة/إلغاء/توكن غلط ·
thumbnails · استمرارية البيانات. الفرونت: `normalizeDoc` (12 حالة) — التنظيف/الإصلاح قبل التحميل.

### التحقق إن البورد بيرجع بعد الـrefresh (AC-13)

`frontend/src/editor/normalize.ts` بينضّف المستند قبل ما يدخل fabric: بيفكّ الـJSON المتضاعف،
بيرمي العناصر اللي fabric مايعرفش يرسمها (ويبلّغ بيها بدل ما يضيّع البورد كله)، بيصلّح الأرقام
اللي بتبقى `NaN`، وبيرجّع `expected/loaded/dropped`.

`engine.load()` بعد كده بيتأكد إن عدد عناصر الكانفس == عدد عناصر الـdoc؛ ولو fabric رفض الدفعة،
بيعمل محاولة عنصر-بعنصر (عنصر تالف = شكل واحد ضايع، مش البورد كله). المستند اللي مارجعش 1:1
بيطلع toast، والحفظ بيتوقف لحد ما الصفحة تتحدّث (عشان مايمسحش اللي محفوظ).

فحص حقيقي في متصفح (headless CDP، من غير أي dependency):

```bash
node scripts/verify-load.mjs --url http://127.0.0.1:8193
# 1) بورد موجود: عدد عناصر الكانفس == عدد عناصر الـdoc
# 2) يرسم مستطيل بالماوس → يستنى الـautosave → reload → يتأكد إنه رجع
# --load-only  : أول فحص بس (آمن على نسخة إنتاج للقراءة فقط)
# CHROME_BIN=/path/to/chrome  لو المتصفح مش في مسار معروف
```

### التحديث الحيّ (polling كل 3 ثواني — v1)

المحرر بيسأل `GET /api/boards/{id}` كل `POLL_MS` ولو `version` على السيرفر أكبر وانت مش بتعدّل،
بيحمّل المشهد الجديد تلقائيًا. لو عندك تعديل غير محفوظ بيظهر toast بدل ما يتلغي شغلك.

## أدوات المحرر

قلم · ممحاة (object eraser) · مستطيل · دائرة · مثلث · سهم · نص · ملاحظة لاصقة · صورة · تحديد · يد.
تحديد: تحريك + تحجيم من المقابض + دوران + تكرار/نسخ/لصق/حذف.
تكبير بعجلة الماوس + pinch على الموبايل + pan بأداة اليد أو Space.
Undo/Redo، خلفية نقط، تصدير PNG، نسخ كصورة، اختصارات لوحة المفاتيح.

## اللي مش هنا (خارج نطاقي)

Docker/deploy على `${BIND_IP}:8093` — ياسين (Task WB-5).
