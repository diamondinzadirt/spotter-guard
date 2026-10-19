# Spotter Guard

A frontend-only assessment demo for weather-aware commercial truck routing.

Developed and maintained by [John Tasie](https://tasie.vercel.app).

- Email: [tasiejohn777@gmail.com](mailto:tasiejohn777@gmail.com)
- GitHub: [diamondinzadirt](https://github.com/diamondinzadirt)
- Portfolio: [tasie.vercel.app](https://tasie.vercel.app)

## Run locally

Requires Node.js 18 or newer.

```sh
npm install
npm run dev
```

Open the local URL printed by Vite. Create a production build with `npm run build`, or preview one with `npm run preview`.

## Included

- Responsive desktop control center with route planner, map, route comparison, weather, and checkpoints.
- Mobile Map, Routes, Weather, and Plan views with persistent selected route and forecast state.
- Denver to Kansas City demo routes with selectable paths, checkpoints, risk levels, and a 0–48 hour weather slider.
- Typed mock service contract ready for Django integration.

## Integration

The demo intentionally shows `Assessment Demo — Live Routing Not Connected`. Replace the mock `planRoutes` adapter with a typed HTTP adapter pointed at `VITE_API_BASE_URL`. The canonical request and response shape is documented in `docs/API_CONTRACT.md`.

No authentication, database, routing API, weather API, or authoritative risk calculation is included in this frontend build.

The application runs independently using Vite directly. The current interface uses the local mock service; a future Django integration can use `VITE_API_BASE_URL` as described above.
