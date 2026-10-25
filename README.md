# Spotter Guard

Spotter Guard is a React + Django assessment application for helping commercial truck drivers compare routes using weather, load weight, risk, checkpoints, and travel time.

Developed and maintained by [John Tasie](https://tasie.vercel.app).

## Architecture

- `frontend/` — Vite, React, TypeScript, Tailwind CSS, MapLibre GL, typed adapters, fixtures, and responsive dashboard UI.
- `backend/` — Django REST Framework API, route orchestration, checkpoint geometry, weather providers, risk engine, and recommendation ranking.
- `docs/` — API contract, assessment rules, and implementation assumptions.

The frontend calls `POST /api/routes/plan`. MapLibre renders route GeoJSON, checkpoint markers, and a geographic weather corridor overlay. The forecast control exposes seven demo frames from `+0h` through `+48h`.

## Local setup

### Backend

```sh
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py test
python manage.py runserver
```

### Frontend

In a second terminal:

```sh
cd frontend
npm install
cp .env.example .env
npm run dev
```

Open the Vite URL shown in the terminal. The local frontend normally runs at `http://localhost:5173` and Django at `http://127.0.0.1:8000`.

## Configuration

Frontend variables are exposed to browser code only when prefixed with `VITE_`:

- `VITE_API_BASE_URL` — Django API base URL; default local value is `http://127.0.0.1:8000`.

Backend variables belong in `backend/.env` and must never be committed:

- `DJANGO_DEBUG` — use `1` locally and `0` in production.
- `DJANGO_SECRET_KEY` — required, non-default secret in production.
- `DJANGO_ALLOWED_HOSTS` — comma-separated backend hostnames.
- `SPOTTER_CORS_ALLOWED_ORIGINS` — comma-separated deployed frontend origins.
- `SPOTTER_ROUTE_MODE` — `demo` for the safe offline fixture mode; `live` only when deliberately configured.
- `HERE_LIVE_ENABLED` — remains `false` for this submission.
- `HERE_API_KEY` — backend-only live-routing credential; not required in demo mode and never placed in frontend variables.
- `HERE_REQUEST_BUDGET` — persistent maximum number of live HERE route requests; keep `0` unless live routing is explicitly approved.
- `SPOTTER_ROUTING_PROVIDER` — `demo` for the Denver fixture, or `valhalla` to route Dallas–Los Angeles and Seattle–Portland through the configured Valhalla service.
- `VALHALLA_BASE_URL` — Valhalla service URL; defaults to `https://valhalla1.openstreetmap.de`.
- `VALHALLA_CLIENT_ID` — identifying client value sent to the public Valhalla service.
- `PHOTON_BASE_URL` — submit-time OpenStreetMap-based geocoding endpoint; no requests are made while typing.
- `DJANGO_SECURE_SSL_REDIRECT` — defaults to `1` when `DJANGO_DEBUG=0`; set `0` only for a deliberately non-HTTPS local/proxy setup.
- `DJANGO_SECURE_HSTS_SECONDS` — set a positive value only after HTTPS is confirmed end-to-end; keep `0` during local development.
- `DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS` and `DJANGO_SECURE_HSTS_PRELOAD` — optional HSTS hardening; enable only when every relevant subdomain is HTTPS and preload requirements are understood.

## Demo and live routing

The safe public demo uses three saved alternatives—Northern Nebraska, I-70 Central, and Southern Plains—for **Denver, CO → Kansas City, MO**. It generates checkpoints at 10, 25, or 50-mile intervals, interpolates coordinates and arrival times, and evaluates weather at checkpoint arrival times.

With `SPOTTER_ROUTING_PROVIDER=valhalla`, Dallas, TX → Los Angeles, CA and Seattle, WA → Portland, OR use Valhalla's truck costing and accept the valid alternatives returned by that service. The public service is rate-limited and may return fewer than three alternatives; the application never fabricates routes. HERE remains disabled and is not required for Valhalla mode. Other city/state combinations are rejected clearly.

## Risk and recommendation rules

Wind, rain, and snow use the assessment thresholds documented in `docs/API_CONTRACT.md`. Load adjustments are exact:

- Wind `>=55 mph`: No Travel for every load.
- Wind `45–<55 mph` with load `>30,000 lb`: No Travel.
- Wind `35–<45 mph` with load `>40,000 lb`: Severe.

The highest applicable weather risk is used for combined conditions. Recommendations are ranked lexicographically by:

1. Fewest Severe miles.
2. Fewest High miles.
3. Lowest average risk.
4. Shortest duration.

No-travel mileage is reported separately and is not silently inserted into the required ranking order.

## Testing and production build

```sh
# Frontend
cd frontend
npm test
npm run lint
npm run typecheck
npm run build

# Backend
cd ../backend
.venv/bin/python manage.py test
```

Frontend tests use Vitest, React Testing Library, jsdom, and deterministic mocked API responses. No test invokes HERE or another paid provider.

## Deployment guidance

Build the frontend as static assets and serve `frontend/dist` from a static host or CDN:

```sh
cd frontend
npm ci
npm run build
```

Set `VITE_API_BASE_URL` at build time to the deployed Django URL. The Django service can run with a production WSGI server such as Gunicorn after installing `backend/requirements.txt` plus the chosen server package in the deployment environment:

```sh
cd backend
gunicorn config.wsgi:application
```

The API health check is `GET https://<backend-host>/api/health` and returns `{"status":"ok"}` without contacting any provider. Run `python manage.py collectstatic --noinput` during deployment if the Django service needs to publish its static files; the API itself does not serve the Vite frontend.

Before hosting, set `DJANGO_DEBUG=0`, a real `DJANGO_SECRET_KEY`, explicit `DJANGO_ALLOWED_HOSTS`, `SPOTTER_CORS_ALLOWED_ORIGINS` for the exact frontend origin, and confirm the proxy forwards `X-Forwarded-Proto: https`. Set HSTS only after HTTPS is confirmed end-to-end. Keep HERE disabled unless live routing is intentionally approved and configured.

## Known limitations and readiness gaps

- Demo mode supports only Denver, CO → Kansas City, MO and uses saved route/weather fixtures.
- Live HERE routing is implemented behind configuration but has not been called or externally verified.
- SQLite remains configured because the demo API does not persist application data; ephemeral hosting may reset the database and multi-instance production deployments should use a managed database if persistence is later added.
- Django has no authentication; this is appropriate for the assessment demo but not a complete production service.
- Browser E2E/Playwright coverage is not configured. MapLibre rendering, mobile sheet gestures, deployed CORS, tile availability, and hosted frontend/API connectivity require manual or deployment-level verification.
- The build reports normal Browserslist freshness and bundle-size warnings; these do not block the build.

## Submission links

- Hosted application: **to be added after deployment**
- Loom walkthrough (5–10 minutes): **to be added after recording**

See `docs/API_CONTRACT.md` for the request/response schema and authoritative implementation interpretations.
