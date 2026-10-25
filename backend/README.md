# Spotter Guard backend

This is the Django REST Framework foundation for the Spotter Guard route-planning API.

The backend includes an offline Denver provider, an opt-in Valhalla truck-routing adapter, and separately gated HERE/Open-Meteo adapters. In safe demo mode, `POST /api/routes/plan` returns saved route and weather fixtures. Set `SPOTTER_ROUTING_PROVIDER=valhalla` to route the Dallas–Los Angeles and Seattle–Portland journeys through the configured Valhalla endpoint; valid responses are passed through the same checkpoint, weather and risk pipeline.

## Local setup

```sh
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py test
python manage.py runserver
```

Set `SPOTTER_CORS_ALLOWED_ORIGINS` to a comma-separated list of frontend origins when needed. The default allows the local Vite development origin.

The safe defaults are `SPOTTER_ROUTE_MODE=demo`, `SPOTTER_ROUTING_PROVIDER=demo` and `HERE_LIVE_ENABLED=false`. Demo mode supports Denver, CO to Kansas City, MO. Valhalla mode uses `VALHALLA_BASE_URL` and `VALHALLA_CLIENT_ID`, does not require a HERE key, and should respect the public service's fair-use limits. Open-Meteo is only selected in deliberate live mode; HERE remains disabled unless explicitly enabled by an operator. Do not commit `.env` or API keys.

For production, set `DJANGO_DEBUG=0`, `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, and `SPOTTER_CORS_ALLOWED_ORIGINS`. Start the WSGI application with `gunicorn config.wsgi:application`. The unauthenticated health check is `GET /api/health` and returns `{"status":"ok"}`. Set `DJANGO_SECURE_SSL_REDIRECT=1` only when the hosting proxy terminates HTTPS and forwards `X-Forwarded-Proto`.

Threshold assumptions and unresolved source requirements are documented in `spotter/risk.py` and `../docs/API_CONTRACT.md`.
