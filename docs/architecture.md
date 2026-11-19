# Architecture — one process, one port

Every app in this repo follows the same shipping rule: **the API process serves the built SPA**.

```
┌───────────────────────────────┐
│  container (one app)          │
│                               │
│  FastAPI ── /api/*            │
│      │                        │
│      └── /assets/*, /{path}   │  → index.html (SPA fallback)
└───────────────────────────────┘
              │
        volume: /data (SQLite)
```

Why:

- one container per app → no sidecar, no reverse proxy, no CORS configuration
- the catch-all route is mounted **last** and skips `/api/*`
- the root route returns `index.html` when a build exists, otherwise JSON (dev mode)
- healthcheck hits `/api/health` every 30 s; `restart: unless-stopped`

## Environment

Each app reads its own prefix (`ATLAS_`, `TODO_`, `WB_`) and a database URL pointing at a
mounted volume, so a container restart never loses data.

## Network

Ports are published only on a private interface — set `BIND_IP` in `.env`.
Going public is an explicit decision, not a default.

## Operational notes

- `docker compose create && docker compose start` is equivalent to `up -d` and is friendlier
  to supervisors that treat long-running foreground commands as a hang.
- Secrets live in `.env` (mode `600`), never in the image and never in git.
- Backups: a nightly archive of the app data directory; restore is a file copy back.
