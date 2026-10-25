# Spotter Guard backend

Django REST Framework API for Photon geocoding, Valhalla truck routing, checkpoint generation, simulated weather and route-risk analysis.

Maintained by [John Tasie](https://tasie.vercel.app) (`tasiejohn777@gmail.com`).

## Local setup

```sh
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py test
python manage.py runserver
```

The current Valhalla configuration uses `SPOTTER_ROUTING_PROVIDER=valhalla` and `SPOTTER_ROUTE_MODE=live`. The checked-in environment example is safe for offline development; set those values when running the Valhalla-backed application. Set `VALHALLA_BASE_URL`, `VALHALLA_CLIENT_ID` and `PHOTON_BASE_URL` as needed. Routing and geocoding are performed only by Django; the frontend never receives provider credentials.

Weather is deterministic simulated data. The service generates checkpoints at 10, 25 or 50 miles, estimates checkpoint arrival times from route geometry and duration, evaluates the assessment risk rules, and ranks routes by Severe miles, High miles, average risk and duration.

Keep `HERE_LIVE_ENABLED=false`. HERE is not used by normal application requests. Do not commit `.env` files or credentials.

## Production

Set `DJANGO_DEBUG=0`, `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS` and `SPOTTER_CORS_ALLOWED_ORIGINS`. Start the WSGI app with:

```sh
gunicorn config.wsgi:application
```

The unauthenticated health endpoint is `GET /api/health` and returns `{"status":"ok"}`. Set `DJANGO_SECURE_SSL_REDIRECT=1` only when the hosting proxy terminates HTTPS and forwards `X-Forwarded-Proto`.

See `../docs/API_CONTRACT.md` for the API schema and authoritative risk interpretations.
