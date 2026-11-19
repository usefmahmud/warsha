# warsha

> A crew of AI agents that builds, reviews, and ships its own tools on a single server.

## What's inside

```
apps/
  atlas/        Project & ticket platform (Jira/Trello-like) — FastAPI + React + SQLite
  todo/         Minimal task app — FastAPI + React
  whiteboard/   Collaborative canvas — Fabric.js + FastAPI
docs/
  atlas.md          Functional spec + API surface
  whiteboard.md     Canvas spec + acceptance criteria
  architecture.md   How one process serves API + SPA
  team.md           How the crew works (ticket-first delivery)
```

## Products

| Product | What it does |
|---|---|
| **Atlas** | Projects → tickets → states, comments, @mentions, activity log, per-agent API keys |
| **TODO** | Add / complete / filter tasks with a full RTL Arabic UI |
| **Whiteboard** | Draw with mouse or touch, shapes, move/resize/rotate, text, sticky notes, autosave, PNG export |

## How the crew works

1. Every piece of work becomes a **ticket** on Atlas — not a chat message.
2. The agent that owns it moves the ticket itself: `start → review → done`.
3. Delivery means **two artifacts**: a written report *and* an updated ticket.
4. Anything that changes the host (install, deploy, new port, data move) is the owner's call.

## Stack

- **Backend:** FastAPI · SQLAlchemy · SQLite (WAL) · JWT auth
- **Frontend:** React · Vite · Tailwind · full RTL support
- **Deploy:** Docker Compose · one container per app (API serves the built SPA) · healthchecks
- **Network:** bound to a private interface; never exposed publicly

## Run locally

```bash
# Atlas
cd apps/atlas
cp .env.example .env        # set a secret key
docker compose up -d --build

# TODO
cd apps/todo && docker compose up -d --build

# Whiteboard
cd apps/whiteboard && docker compose up -d --build
```

Each app binds through `${BIND_IP}` — set it in `.env` to the interface you want:

```dotenv
BIND_IP=127.0.0.1
```

## Rules

- **No secrets in the repo** — `.env` is ignored, `.env.example` only.
- **No data in the repo** — `data/` and `*.db` are ignored.
- **One process, one port** — the API serves the SPA; no CORS, no reverse proxy needed.
- **Tests before claims** — every feature ships with a runnable test command.

## The crew

Full cards with photos and self-written bios: **[CONTRIBUTORS.md](CONTRIBUTORS.md)**

| Agent | Role |
|---|---|
| **Hakim** | Coordination — decomposes work, dispatches, reviews deliveries |
| **Layla** | Personal organisation — schedules, reminders, daily planning |
| **Salim** | Research & verification — every number carries a source |
| **Maryam** | Product — specs, acceptance criteria, delivery review |
| **Omar** | Engineering — backend, frontend, tests |
| **Yassin** | Infrastructure — Docker, deploys, backups, monitoring |

---

Licence: MIT
