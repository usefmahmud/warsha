# Atlas — projects & tickets

Self-hosted issue tracker built for a crew of agents and one human owner.
Projects hold tickets; tickets carry state, priority, assignee, comments, mentions and a full audit trail.

## Core model

| Entity | Key fields |
|---|---|
| `users` | username, email, name, role (`owner` / `admin` / `member`), colour |
| `projects` | key (e.g. `ATL`), name, description, archived_at |
| `project_members` | project, user, role (`lead` / `member`) |
| `tickets` | key (`ATL-12`), title, description, type, priority, status, assignee, reporter, labels, due_date, estimate, parent_id |
| `comments` | ticket, author, markdown body, mentions |
| `activity` | ticket, actor, action, payload, timestamp |
| `notifications` | user, kind (`mention` / `assignment` / `status`), read_at |
| `api_keys` | user, name, hashed key — one per agent |

## Ticket states

```
backlog → todo → in_progress → review → done
                    ↘ blocked ↗
```

Transitions are validated server-side; an illegal move returns `422`.

## API surface (50 routes)

- `POST /api/auth/register|login|logout` · `GET/PATCH /api/auth/me`
- `GET/POST /api/projects` · `GET/PATCH /api/projects/{ref}` · archive/unarchive
- `GET/POST /api/projects/{ref}/tickets` · `GET /api/projects/{ref}/board`
- `GET/PATCH/DELETE /api/tickets/{ref}` · `POST /api/tickets/{ref}/transition`
- `GET/POST /api/tickets/{ref}/comments` · `GET /api/tickets/{ref}/activity`
- `GET/POST /api/tickets/{ref}/labels` · subtasks via `parent_id`
- `GET /api/me/work` · `GET /api/me/mentions` · `GET /api/notifications`
- `GET/POST /api/users/{id}/api-keys`
- **Agent API** (header `X-API-Key`): `GET /api/agent/me`, `GET /api/agent/my-tickets`,
  `POST /api/agent/tickets`, `PATCH /api/agent/tickets/{ref}`,
  `POST /api/agent/tickets/{ref}/transition`, `POST /api/agent/tickets/{ref}/comments`

OpenAPI is served at `/api/openapi.json`.

## Notes

- Ticket numbers are per-project and allocated inside a transaction (`UNIQUE(project_id, number)`).
- `If-Match` / `version` guards against silent last-write-wins.
- SQLite in WAL mode; every write path is short and retried on contention.
- UI is Arabic RTL; API is language-neutral.
