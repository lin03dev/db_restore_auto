# Database Backup & Restore Automation

Production-oriented PostgreSQL backup, restore, and validation with a secured FastAPI backend and React dashboard.

## Architecture

```
backend/
  main.py                         # Single entry point (API or CLI)
  app/
    api/v1/endpoints/             # Versioned REST API
    core/                         # Config, security, middleware, logging
    domain/                       # Backup, restore, validation logic
    infrastructure/               # PostgreSQL CLI tooling
    schemas/                      # Pydantic request/response models
    services/                     # Application services
    cli/                          # CLI commands
  config/databases.yaml           # Database targets (no secrets)
frontend/
  src/
    app/                          # Application shell
    features/                     # Feature modules (dashboard, jobs, …)
    shared/                       # API client, types, UI primitives
```

## Security

- **API key auth** via `X-API-Key` header (required when `ENVIRONMENT=production`)
- **Secrets in environment only** — connection strings never belong in YAML
- **Binds to `127.0.0.1` by default** — use a reverse proxy for remote access
- **Security headers** on all API responses
- **Log sanitization** redacts connection strings and passwords
- **Input validation** on job requests and database targets
- **CORS** restricted to configured origins; credentials disabled

## Setup

```bash
pip install -r backend/requirements.txt
cd frontend && npm install && cd ..

cp backend/.env.example backend/.env
cp backend/config/databases.yaml.example backend/config/databases.yaml
cp frontend/.env.example frontend/.env
```

Set `API_KEY` in `backend/.env` and the same value in `frontend/.env` as `VITE_API_KEY` when auth is enabled.

## Run

### Backend

```bash
cd backend
python main.py              # API → http://127.0.0.1:8002 (see backend/.env)
python main.py cli --status # CLI pipeline
```

Default ports avoid conflicts with other local projects (`rx_pm` uses 8000/5173).

### Frontend

```bash
cd frontend
npm start                   # → http://localhost:5174
```

## Docker

Run from the **workspace root** (`~/workspace/git-projects`):

| | Native dev | Docker |
|--|------------|--------|
| **App URL** | http://localhost:5174 | http://localhost:5174 |
| **API** | http://127.0.0.1:8002 (direct) | `/api/v1/*` via nginx |
| **Health** | http://127.0.0.1:8002/api/v1/health | http://localhost:5174/api/v1/health |
| **Start** | `python main.py` + `npm start` | `make restore` |

Full details: **[../docker/ACCESS.md](../docker/ACCESS.md#db_restore_auto)**

```bash
cd ~/workspace/git-projects
make restore
curl -sf http://127.0.0.1:5174/api/v1/health
```

## API (`/api/v1`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | No | Liveness probe |
| GET | `/status` | Yes* | Backup/restore status |
| GET | `/databases` | Yes* | Configured databases |
| POST | `/jobs` | Yes* | Start a job |
| GET | `/jobs/{id}` | Yes* | Poll job status |
| POST | `/reset-tracking` | Yes* | Reset restore cooldown |

\* Required when `API_KEY` is set or `ENVIRONMENT=production`.

## Tests

```bash
cd backend && python -m unittest discover -s tests -q
```
