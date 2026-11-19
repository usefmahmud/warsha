# Whiteboard Backend

FastAPI + SQLAlchemy + SQLite (WAL). Serves the JSON API **and** the built SPA from one process
(same convention as Atlas: static mount for `/assets` + SPA fallback for any non-`/api` path).

## Files

| File | Role |
|---|---|
| `app/config.py` | pydantic-settings, `WB_` env prefix |
| `app/database.py` | engine + `PRAGMA journal_mode=WAL`, `foreign_keys`, `busy_timeout=15s` |
| `app/models.py` | `Board` (id, name, color, doc TEXT, thumb, share_token, version, timestamps) |
| `app/schemas.py` | request/response models, `BoardOut` / `BoardSummary` |
| `app/routers/boards.py` | CRUD · autosave with optimistic concurrency · share tokens · thumb |
| `app/spa.py` | mounts `dist/` + SPA fallback |
| `tests/` | 40 pytest cases |

## Run

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
WB_STATIC_DIR=../frontend/dist ./.venv/bin/uvicorn app.main:app --port 8094
```

`GET /docs` للـOpenAPI التفاعلي، و`GET /api/openapi.json` للمخطط.

## Design notes

- **`doc` is TEXT, not JSON**: the scene is whatever the canvas library serialises, stored
  byte-for-byte so a round-trip never loses a property. Validated as a JSON *object* at the edge.
- **Versioning**: `version` starts at 1 and only increments when something actually changed,
  so a no-op autosave doesn't create conflicts for other tabs.
- **Conflict body**: `409` carries `{expected_version, sent_version, board}` so the client can
  offer "reload server copy" or "overwrite" without a second round-trip.
- **Share tokens**: `secrets.token_urlsafe(18)`, unique-indexed, idempotent create, `204` revoke.
  `/api/shared/{token}` is the only read route — there is deliberately no write route under it.
- **Size ceiling**: documents above `WB_MAX_DOC_BYTES` are rejected with `413` before touching
  the database.
