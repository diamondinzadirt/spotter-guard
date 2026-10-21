# Spotter Guard

Spotter Guard is a full-stack assessment demo for weather-aware commercial truck routing.

Developed and maintained by [John Tasie](https://tasie.vercel.app).

## Repository structure

- `frontend/` — Vite, React, TypeScript, Tailwind, mock adapters, and UI.
- `backend/` — Django REST Framework foundation and risk engine.
- `docs/` — API contract and assessment documentation.

## Frontend

Requires Node.js 18 or newer.

```sh
cd frontend
npm install
npm run dev
```

Use `npm run lint`, `npm run typecheck`, and `npm run build` from `frontend/` to validate the application.

## Backend

The backend has a safe offline demo provider and a separately gated HERE/Open-Meteo live provider. Demo mode returns clearly labeled saved route and weather fixtures; live mode requires explicit provider configuration.

```sh
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py test
python manage.py runserver
```

See `docs/API_CONTRACT.md` for the shared request/response contract and exact risk rules.

## Connected local demo

Run Django from `backend/` and Vite from `frontend/`. Copy `frontend/.env.example` to `frontend/.env` so the browser calls Django at `http://127.0.0.1:8000`. The backend remains in safe demo mode by default and makes no HERE requests.
