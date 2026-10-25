# DevTrack

A developer productivity platform: manage projects, track tasks and bugs on a Kanban board, plan sprints, and get analytics, burndown charts and auto-generated summaries. Syncs with GitHub.

**Stack:** Django 5 + Django REST Framework, JWT auth (SimpleJWT), PostgreSQL (SQLite by default), React 18 + Vite.

## Features

| | |
|---|---|
| **Kanban board** | Drag cards between columns and reorder them; positions persist. Filter by sprint, assignee, type. |
| **Tasks, stories, bugs** | Priorities, story points, due dates, assignees, comments, per-task keys like `DEV-12`. |
| **Role-based access** | Per-project roles: *viewer* (read), *developer* (edit tasks), *maintainer* (sprints, members, GitHub), *owner* (delete project). Non-members get a 404, so projects aren't discoverable. |
| **Sprints** | Plan, start (snapshots committed points), complete (unfinished work goes to backlog or the next sprint). |
| **Analytics** | Completion, open bugs, overdue work, weekly activity, velocity, burndown vs ideal, per-person contribution. |
| **Automatic summaries** | Weekly project summary with a green/amber/red health call, and a sprint report. Both copy as Markdown. Template-based, so deterministic and instant. |
| **GitHub integration** | Import issues as tasks (label `bug` → bug), mirror commits, link commits that mention `KEY-12` to that task. Manual sync and signed webhooks (`issues`, `push`) for real-time updates. |
| **Activity feed** | Audit trail of who changed what. |

## Run it

Requires Python 3.11+ and Node 18+.

```bash
# 1. Backend  (http://localhost:8000)
cd backend
python -m venv ../.venv && ../.venv/Scripts/activate     # Windows; use `source ../.venv/bin/activate` elsewhere
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo            # optional: demo project + users
python manage.py runserver

# 2. Frontend (http://localhost:5173), in another terminal
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 and sign in with `demo` / `devtrack-demo-1` (also `alice`, `bob`, `carol`, who have different roles), or register a new account.

The Vite dev server proxies `/api` to Django, so no CORS configuration is needed in development.

### Configuration (environment variables)

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | SQLite file | e.g. `postgres://user:pass@localhost:5432/devtrack` |
| `DJANGO_SECRET_KEY` | insecure dev key | **Set this in production.** |
| `DJANGO_DEBUG` | `1` | Set `0` in production. |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma separated. |
| `GITHUB_TOKEN` | none | Needed for private repos; raises GitHub rate limits. |

## Tests

```bash
cd backend && python manage.py test     # 55 tests, ~1s
```

They cover authentication, every role boundary (viewer/developer/maintainer/owner/outsider), Kanban reordering, sprint lifecycle, analytics maths, the generated summaries, GitHub sync (with a mocked client) and webhook signature verification.

## API overview

All endpoints are under `/api/` and need `Authorization: Bearer <access token>` unless noted.

```
POST /auth/register/            (public)        POST /auth/token/   POST /auth/token/refresh/
GET  /auth/me/                                  GET  /auth/users/?q=
CRUD /projects/                                 GET/POST /projects/{id}/members/
PATCH|DELETE /projects/{id}/members/{user_id}/
CRUD /sprints/?project=                         POST /sprints/{id}/start|complete/
CRUD /tasks/?project=&sprint=&status=&type=&assignee=&search=&ordering=
POST /tasks/{id}/move/  {status, position}      GET/POST /tasks/{id}/comments/
GET  /activity/?project=
GET  /projects/{id}/analytics/                  GET /projects/{id}/summary/?days=7
GET  /sprints/{id}/report/
POST /integrations/projects/{id}/sync/          GET /integrations/projects/{id}/commits/
POST /integrations/projects/{id}/webhook/       (public, HMAC-signed by GitHub)
```

## Layout

```
backend/
  config/         settings, root urls
  accounts/       registration, JWT, user lookup
  projects/       Project, Membership (roles), Sprint, access helpers, seed_demo command
  tasks/          Task, Comment, Activity; Kanban move endpoint
  analytics/      services.py (numbers), reports.py (generated summaries)
  integrations/   GitHub client, sync service, webhook
frontend/src/
  pages/          Board, Backlog, Sprints, Insights, Settings
  components/     TaskModal, SVG charts (no chart library), Markdown renderer
```

## Design notes and limits

- **Roles are per project**, not global, and enforced in the API (the UI only hides buttons).
- **Burndown uses `completed_at`**, which the model keeps in sync with status, so moving a card out of Done un-completes it.
- **Velocity uses snapshots** taken at sprint start/finish, so numbers stay correct after unfinished work is moved.
- **GitHub sync never overwrites local edits**: for tasks already imported it only syncs open/closed state and title.
- **No pagination** on list endpoints yet; fine for a team-sized project, add `PageNumberPagination` before using it on very large ones.
- Production serving (gunicorn + static hosting for `npm run build`) isn't set up.
