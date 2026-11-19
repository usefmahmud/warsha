# Atlas — الواجهة (React + Vite + Tailwind، RTL كامل)

واجهة إدارة المشاريع والتذاكر، بتتكلم مع نفس الـAPI على نفس الأصل تحت `/api` مع
**Bearer token** (JWT من `/api/auth/login`) بيتخزن في `localStorage` تحت `atlas.token`.

## الشاشات

| الشاشة | المسار | إيه فيها |
|---|---|---|
| Login | `/login` | إيميل + باسورد، رسالة خطأ من الباك إند نفسه |
| المشاريع | `/projects` | كروت المشاريع + إنشاء مشروع (key/name/desc/color) |
| Board | `/p/:projectKey/board` | 6 أعمدة (backlog → blocked) + **drag & drop** بيحفظ `position` + فلاتر مسؤول/أولوية |
| List | `/p/:projectKey/list` | جدول + بحث (debounce) + فلاتر حالة/أولوية/مسؤول + ترتيب |
| My Work | `/my` | تذاكري مجمّعة بالحالة + منشنز لسه مقريتهاش |
| Ticket | `/p/:projectKey/t/:key` · `/t/:key` | وصف + تغيير حالة/أولوية + كومنتات + **@mention autocomplete** + تايم لاين نشاط |

## التشغيل

```bash
cd ~/ai-team/projects/atlas/frontend
npm install
npm run dev        # http://localhost:5173  (proxy /api → 127.0.0.1:8000)
npm run build      # tsc -b && vite build → dist/
npm run preview    # http://localhost:4173  (نفس الـproxy)
```

- `VITE_API_BASE` — افتراضي `/api`. غيّرها لو الـAPI على أصل مختلف.
- `VITE_PROXY_TARGET` — افتراضي `http://127.0.0.1:8000` (سيرفر uvicorn المحلي للتطوير/الـpreview).

## ملاحظات معمارية

- **`src/api/client.ts`** — كل الـfetch في مكان واحد: token، أخطاء موحّدة (`ApiError` بـ`code`/`message`/`request_id`)، وأي 401 بيطلّع الجلسة.
- **`src/api/normalize.ts`** — الـbackend ماشي في نسختين من الـschema (`full_name`/`name`، `description`/`description_md`، `position`/`board_position`، `members_count`/`member_count`، `archived_at`/`is_archived`)؛ الـadapters بتقبل الشكلين والشاشات بتشوف شكل واحد بس.
- **`src/api/types.ts`** — عقد الـUI (مطابق لـ`app/schemas.py`).
- **`src/auth.tsx`** — `AuthProvider` بيتحقق من التوكن عند الإقلاع بـ`GET /api/auth/me`.
- **`src/lib/useAsync.ts`** — fetch hook صغير: reload + بيحتفظ بالبيانات القديمة أثناء التحديث.
- **Drag & drop** بـnative HTML5 (من غير مكتبة): بيحسب `position` بين الجيران (sparse floats) وبعدين `POST /api/tickets/{ref}/transition`.
- **RTL** من `index.html` (`dir="rtl" lang="ar"`) + خصائص منطقية (`ms-*`, `me-*`, `border-s`) عشان مفيش أي `left/right` مثبت.

## نتيجة آخر تحقق (E2E حقيقي على uvicorn محلي)

- Login ✅ · Projects ✅ · Board + drag&drop (اتحفظ على السيرفر: `status=in_progress`) ✅
- List + بحث/فلاتر/ترتيب ✅ · My Work + منشن ✅ · Ticket + كومنت + @mention (عمل notification للمنشن) ✅
- `npm run build` نظيف · `tsc --noEmit` نظيف · صفر أخطاء console في كل الشاشات
