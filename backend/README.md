# Spotter Guard backend

This is the Django REST Framework foundation for the Spotter Guard route-planning API.

The backend deliberately does not contain a routing or weather provider yet. `POST /api/routes/plan` validates the frontend contract and returns `503 provider_not_configured` until a real provider is registered. This prevents fabricated weather or route results from being presented as live data.

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

Threshold assumptions and unresolved source requirements are documented in `spotter/risk.py` and `../docs/API_CONTRACT.md`.
