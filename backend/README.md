# Spotter Guard backend

This is the Django REST Framework foundation for the Spotter Guard route-planning API.

The backend includes an offline demo provider and separately gated HERE/Open-Meteo adapters. In safe demo mode, `POST /api/routes/plan` returns clearly labeled saved route and weather fixtures. Live mode requires explicit provider configuration and never falls back to demo data.

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

The safe defaults are `SPOTTER_ROUTE_MODE=demo` and `HERE_LIVE_ENABLED=false`. Demo mode supports only Denver, CO to Kansas City, MO and rejects unsupported locations rather than returning unrelated geometry. Open-Meteo is only selected in deliberate live mode; HERE remains disabled unless explicitly enabled by an operator. Do not commit `.env` or API keys.

For production, set `DJANGO_DEBUG=0`, `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, and `SPOTTER_CORS_ALLOWED_ORIGINS`. Start the WSGI application with `gunicorn config.wsgi:application`. The unauthenticated health check is `GET /api/health` and returns `{"status":"ok"}`. Set `DJANGO_SECURE_SSL_REDIRECT=1` only when the hosting proxy terminates HTTPS and forwards `X-Forwarded-Proto`.

Threshold assumptions and unresolved source requirements are documented in `spotter/risk.py` and `../docs/API_CONTRACT.md`.
