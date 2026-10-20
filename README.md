# Campus Pilot

Campus Pilot is a FastAPI + React starter for campus information, events, news, timetables, navigation, and Lost & Found workflows. It uses MySQL in Docker, SQLAlchemy/Alembic, JWT authentication, and a Vite frontend.

## Current behavior and data requirements

The app does not ship fabricated college facts, events, schedules, campus coordinates, or walking paths. Public information stays empty until an authorized administrator adds verified records. With `OPENAI_API_KEY` configured, the assistant uses the OpenAI API only to classify intent; all record retrieval, route calculation, authorization, and report submission remain deterministic backend operations. Without a key, conservative intent rules are used. Verified knowledge documents are retrieved by token overlap; unsupported questions are explicitly declined.

The API includes authenticated registration/login, user profile lookup, event/news reads, timetable retrieval, shortest-path routing over administrator-entered campus pathways, chat conversation history, Lost & Found submissions and validated image uploads, admin event/news/timetable/location/path/report/user-role APIs, audit records, and a WebSocket notification stream for administrators.

## Run with Docker Compose

1. Copy `.env.example` to `.env` for Compose and set unique database passwords and a long random `JWT_SECRET_KEY`. Copy `backend/.env.example` to `backend/.env` for local non-Docker development.
2. From the repository root, run:

   ```sh
   docker compose up --build
   ```

3. Open `http://localhost:5173`. The API docs are at `http://localhost:8000/docs`.
4. Create the first administrator in another terminal:

   ```sh
   docker compose exec backend python -m app.create_admin
   ```

Never use the Compose development passwords or the built-in development JWT key outside a local setup. User registration creates student accounts; admin privileges are granted only from the backend using the bootstrap command or by an existing administrator.

## Run locally

### Backend

Python 3.12 is recommended. Docker Compose uses MySQL. For local development, use SQLite as described below; no MySQL server is required.

For a local PowerShell setup using SQLite (no MySQL required), run these commands from the repository root:

```sh
cd D:\CP\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
```

In `.env`, set `DATABASE_URL=sqlite:///./campus_pilot.db` and replace `JWT_SECRET_KEY` with a random secret at least 32 characters long. Save the file, then run:

```sh
alembic upgrade head
uvicorn app.main:app --reload
```

Keep the virtual environment activated when running backend commands. If PowerShell blocks activation, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in that terminal and activate it again.

Create an administrator with `python -m app.create_admin`. The local upload directory is private application storage and is not served as a static path.

### Frontend

```sh
cd frontend
npm install
npm run dev
```

Vite proxies `/api` to `http://localhost:8000`. `npm run build` creates a production bundle.

## Configure campus records

Use the authenticated admin APIs documented in Swagger:

- `POST /api/v1/admin/departments`
- `POST /api/v1/admin/campus/locations`
- `POST /api/v1/admin/campus/paths`
- `POST /api/v1/admin/timetable`
- `POST /api/v1/admin/events` and `PATCH /api/v1/admin/events/{id}`
- `POST /api/v1/admin/news`
- `GET /api/v1/admin/lost-found/reports` and `PATCH /api/v1/admin/lost-found/reports/{id}`
- `GET /api/v1/admin/users` and `PATCH /api/v1/admin/users/{id}/role`

Only published events/news are visible to students. Naive event date-times entered by administrators are interpreted in `COLLEGE_TIMEZONE`; timezone-aware API values are normalized to UTC. Routes are only returned when the stored pathway graph connects the selected locations. Timetable records require the user's department, semester, and section; configure academic sections and timetable entries before students set their own matching profile.

## Security / production notes

- Passwords use Argon2id hashing; API access uses short-lived signed bearer tokens.
- Admin authorization is enforced in backend dependencies, not only in the UI.
- Lost & Found report access is owner-checked; image bytes are inspected with Pillow and stored outside the frontend's public directory.
- Login, registration, chatbot, and image endpoints use per-IP rate limits. This in-process limiter is for a single development instance; configure equivalent limits at a trusted proxy/API gateway for multi-worker production.
- WebSocket notifications require the client to send its bearer token after connecting.
- AI intent classification is optional. Set `OPENAI_API_KEY` only when permitted by your institution; user text and a short conversation history are sent to the configured OpenAI model for classification. The model has no database tools and cannot authorize or execute operations.
- Set HTTPS/WSS, restrictive trusted origins, strong secrets, backups, and production object storage before deployment. The sample deployment is development infrastructure, not a production hardening profile.
- Alembic schema versioning is configured. Review generated migrations for every schema change before production deployment.

## Tests

From `backend`, run `pytest`. The API and model layers can be tested with a disposable SQLite database; production deployments should use MySQL integration tests as well. From `frontend`, run `npm test` for the Vitest/React Testing Library suite.
