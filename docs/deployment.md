# Deploying to Render

Bloom Beauty Bar deploys to [Render](https://render.com) from the
[`render.yaml`](../render.yaml) Blueprint at the repo root. It creates:

| Resource           | Type                      | Notes                                          |
|--------------------|---------------------------|------------------------------------------------|
| `bloom-beauty-bar` | Web service (Docker)      | Built from `backend/Dockerfile`, repo root as context; serves the API and the frontend |
| `bloom-db`         | Managed Postgres          | Database `bloom`, user `bloom`; private to Render |

Both run in the `frankfurt` region (the closest Render region to South
Africa) on the free plan.

## How it fits together

- **Database:** the web service's `DATABASE_URL` is filled in from the
  database's internal connection string. Render's URL starts with
  `postgresql://`; `normalize_database_url` in `backend/app/sql_store.py`
  rewrites it to `postgresql+psycopg://` so SQLAlchemy uses psycopg (v3),
  which is in `requirements.txt`.
- **Port:** Render sets `PORT`; the Dockerfile's command runs uvicorn on
  `${PORT:-8000}`, so it still listens on 8000 locally.
- **Tables and seed data:** on startup the app runs `create_all` and seeds the
  six services if they're missing, so a fresh database is ready on first boot
  and redeploys don't duplicate anything.
- **Frontend:** baked into the same image and served at `/`; the pages call
  `/api/...` on the same origin.
- **Health check:** Render waits for `GET /api/health` to return 200 before
  switching traffic to a new deploy.

## First deploy

1. Push the repo to GitHub (it's already at
   `github.com/sanam-singh1104/bloom-beauty-bar`).
2. In the Render dashboard, choose **New → Blueprint**, connect the GitHub
   repo, and pick the `main` branch.
3. Render reads `render.yaml` and lists `bloom-beauty-bar` and `bloom-db`.
   Click **Apply**. The database is created first, then the image is built and
   started.
4. When the deploy is live, open the service's `https://<name>.onrender.com`
   URL. Check:
   - `/api/health` returns `{"status": "ok"}`
   - `/api/services` lists the six seeded services
   - the home page loads, a booking can be made, and it shows on
     `/manage.html`

No secrets need to be entered by hand; the database credentials are wired up
by the Blueprint.

## Later deploys

Pushes to `main` deploy automatically, but **only after the GitHub Actions CI
checks pass** (`autoDeployTrigger: checksPass`). Changes to `render.yaml`
itself are applied by Render on the next sync of the Blueprint. The full flow,
verification, and rollback are in [release-process.md](release-process.md).

## Things to know about the free plan

- The web service **sleeps after ~15 minutes without traffic**; the next
  request takes up to a minute while it wakes up.
- A free Postgres database **expires 30 days after creation** (with a grace
  period to upgrade). Move `bloom-db` to a paid plan, by changing `plan:` in
  `render.yaml`, before relying on it for real bookings.
- Only one free Postgres database is allowed per workspace.

## Troubleshooting

- **Build fails copying `frontend/`:** the Docker context must be the repo
  root (`dockerContext: .`), not `backend/`.
- **`No module named 'psycopg2'`:** `DATABASE_URL` isn't going through
  `normalize_database_url`, or the scheme is something unexpected; check the
  value in the service's **Environment** tab.
- **Deploy stuck on the health check:** look at the service **Logs**; the app
  usually failed to reach the database at startup. Confirm `bloom-db` is
  available and in the same region.
- **Run against the Render database locally:** copy the database's *External*
  connection string, add your IP to its access control list in the dashboard,
  and set `DATABASE_URL` to it before starting uvicorn. Don't commit it.
