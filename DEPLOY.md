# Deploying NoticePilot GST

NoticePilot is a local-first demo workspace: a FastAPI backend (SQLite +
filesystem storage) and a static Vite frontend. No managed services required.

## Backend (Docker)

    docker build -f backend/Dockerfile -t noticepilot-gst .
    docker run -p 8000:8000 -v noticepilot-data:/srv/data noticepilot-gst

The container serves the API at `http://localhost:8000` (`/api/health`).
State persists in the `noticepilot-data` volume via `NOTICE_PILOT_STORAGE`.

Without Docker:

    cd backend
    pip install -r requirements.txt
    python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

## Frontend (static)

    npm install
    npm run build   # typecheck + production bundle into dist/
    npx vite preview --port 5173   # or serve dist/ with any static server

Point the frontend at the API with `VITE_API_BASE_URL`
(see `.env.example`; bake it at build time for static hosting).

## Environment

| Variable | Default | Purpose |
|---|---|---|
| `VITE_API_BASE_URL` | `http://localhost:8000/api` | Frontend → API base |
| `VITE_DEMO_MODE` | unset (dev implies on) | Show synthetic-demo controls |
| `LLM_PROVIDER` | `deterministic` | `deterministic` (offline) or `openai-compatible` |
| `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` | empty | Live narrator (never commit keys) |
| `LLM_TIMEOUT_S` | `30` | Provider HTTP timeout |
| `DEMO_ENABLED` | `1` | `0` disables `/api/demo/*` server-side |
| `NOTICE_PILOT_STORAGE` | `backend/storage/` | SQLite + uploads directory |

## Database / storage

- SQLite at `$NOTICE_PILOT_STORAGE/notices.db` (WAL mode). Schema is created
  and migrated automatically on startup (`init_db`); the default demo reviewer
  is seeded.
- Uploads: `$NOTICE_PILOT_STORAGE/documents/`, `$NOTICE_PILOT_STORAGE/returns/`.
- Back up the whole storage directory to snapshot a workspace. Demo reset
  (`POST /api/demo/reset`) only touches synthetic fixture data.

## Production notes (demo-grade)

- No authentication is implemented; demo reviewer identities are explicit stubs.
- Bind behind a reverse proxy with TLS for any shared use; restrict CORS
  (`backend/app/main.py`) to your frontend origin.
- Nothing in the system submits to external portals; outbound calls happen
  only if a live LLM provider is configured.
