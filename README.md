# Spotter Guard

Spotter Guard is a weather-aware truck route planner. Drivers enter a journey, departure date/time, load weight and checkpoint interval, then compare truck routes, checkpoint risks and travel time on an interactive map.

Developed and maintained by [John Tasie](https://tasie.vercel.app) (`tasiejohn777@gmail.com`).

## Stack

- `frontend/`: React, TypeScript, Vite, CSS and MapLibre GL.
- `backend/`: Django REST Framework with Photon geocoding, Valhalla truck routing, checkpoint geometry, simulated weather and the risk engine.
- `docs/API_CONTRACT.md`: request/response schema and assessment rules.

The frontend calls `POST /api/routes/plan`. MapLibre displays route GeoJSON, checkpoints, endpoint markers and a geographic weather overlay with a `0–48h` forecast slider.

## Local setup

Backend:

```sh
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py test
python manage.py runserver
```

Frontend, in a second terminal:

```sh
cd frontend
npm install
cp .env.example .env
npm run dev
```

Set `VITE_API_BASE_URL` in `frontend/.env` when Django is not running at `http://127.0.0.1:8000`.

`frontend/.env.example` contains the local API URL. This is the only frontend environment variable.

## Configuration

Backend variables belong in `backend/.env` and must not be committed. The checked-in example is safe for offline development; Valhalla-backed routing uses:

- `DJANGO_DEBUG`, `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`
- `SPOTTER_CORS_ALLOWED_ORIGINS`
- `SPOTTER_ROUTE_MODE=live`
- `SPOTTER_ROUTING_PROVIDER=valhalla`
- `VALHALLA_BASE_URL` and `VALHALLA_CLIENT_ID`
- `PHOTON_BASE_URL`
- `DJANGO_SECURE_SSL_REDIRECT` and optional HSTS settings for HTTPS hosting

Photon geocoding and Valhalla routing run server-side. API credentials are not exposed to the frontend. Keep `HERE_LIVE_ENABLED=false`; the application does not use HERE for normal route requests.

## Routing and analysis

Valhalla requests use truck routing and return the valid alternatives available from the routing service; the application never fabricates routes. Checkpoints are generated along each route at `10`, `25` or `50` mile intervals. Arrival times are estimated from route geometry and duration, and simulated weather values are evaluated at those checkpoints.

Weather is simulated, deterministic and clearly marked in the interface. It varies by route geography, checkpoint and forecast time; it is not a live weather forecast.

Risk uses the assessment wind, rain, snow and load rules documented in `docs/API_CONTRACT.md`. Route recommendations use this order:

1. Fewest Severe miles.
2. Fewest High miles.
3. Lowest average risk.
4. Shortest duration.

No-travel mileage is reported separately and does not silently change that ranking.

## Testing and build

```sh
cd frontend
npm run test -- --run
npm run lint
npx tsc --noEmit
npm run build

cd ../backend
python manage.py test
```

Tests use mocked provider responses and do not call paid routing services.

## Deployment

Build the frontend as static files:

```sh
cd frontend
npm ci
npm run build
```

Set `VITE_API_BASE_URL` to the deployed Django API before the build. Run Django with Gunicorn:

```sh
cd backend
gunicorn config.wsgi:application
```

For production, set `DJANGO_DEBUG=0`, a secure `DJANGO_SECRET_KEY`, explicit allowed hosts and the exact frontend origin in `SPOTTER_CORS_ALLOWED_ORIGINS`. The health check is `GET /api/health` and returns `{"status":"ok"}`.

SQLite is sufficient for the stateless assessment service, but ephemeral hosting can reset it. Use a managed database only if persistent application data is added later.

## Known limitations

- Valhalla and Photon are external public services and may be rate-limited or unavailable.
- Simulated weather is for assessment demonstration, not operational dispatch decisions.
- MapLibre tiles and hosted frontend/API connectivity require deployment-level verification.

## Links

- Hosted application: to be added
- Loom walkthrough: to be added
