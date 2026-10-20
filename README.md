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

The backend does not fabricate live routing or weather results. It validates `POST /api/routes/plan` and returns a provider configuration error until real providers are added.

```sh
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py test
python manage.py runserver
```

See `docs/API_CONTRACT.md` for the shared request/response contract and exact risk rules.
