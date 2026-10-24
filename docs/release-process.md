# Release process

How a change gets from a commit to the live site, and how to undo it.

Live URL: **https://bloom-beauty-bar.onrender.com**

```
push to main ──► GitHub Actions CI ──► all checks green? ──yes──► Render builds + deploys ──► health check ──► live
                 (.github/workflows/      │                       (render.yaml,                (/api/health)
                  ci.yml)                 no                       autoDeployTrigger:
                                          ▼                        checksPass)
                                   Render skips the deploy;
                                   the site stays on the last good version
```

## 1. Push → CI

`.github/workflows/ci.yml` runs on **every push (any branch) and every pull
request**. Two jobs run in parallel:

| Job              | What it does                                                                 |
|------------------|------------------------------------------------------------------------------|
| **Lint and tests** | `ruff check`, `ruff format --check`, `node --check` on the frontend JS, unit tests, integration tests on **SQLite**, then integration tests again on **Postgres 17** (a service container, via `TEST_DATABASE_URL`) |
| **Docker image** | Builds `backend/Dockerfile` exactly as Render does, starts it with `PORT=10000`, and checks `/api/health`, the six seeded services, and the home page |

Any failing step fails its job, and a failed job is a failed check on the
commit. Same checks locally, minus the Postgres pass:
`py scripts/run_checks.py`.

To run the integration tests against Postgres locally:

```
docker run -d --rm --name bloom-test-pg -p 55432:5432 \
  -e POSTGRES_USER=bloom -e POSTGRES_PASSWORD=bloom -e POSTGRES_DB=bloom_test postgres:17
# from backend/ (bash shown; in PowerShell: $env:TEST_DATABASE_URL = "...")
TEST_DATABASE_URL=postgresql://bloom:bloom@localhost:55432/bloom_test pytest -m integration
```

`TEST_DATABASE_URL` is wiped before and after every test. Never point it at a
database with real data.

## 2. CI passes → deploy

Render is set to deploy **only after CI passes**. In `render.yaml`:

```yaml
autoDeployTrigger: checksPass
```

When a commit lands on `main`, Render waits for that commit's GitHub checks.
If they all pass, Render deploys it. If any fail, Render skips the deploy and
the site stays on the previous version.

**Why this approach:** Render already watches the repo, so it can wait for
GitHub's checks itself. The alternative was to turn Render's auto-deploy off
and call a Render deploy hook from a final workflow step. That needs a secret
URL stored in GitHub, and a manual dashboard deploy can still skip CI. With
`checksPass` there's no secret, no extra workflow code, and the deploy is
always the exact commit that passed.

**Check it's on:** in the Render dashboard, open the `bloom-beauty-bar`
service, go to **Settings → Build & Deploy → Auto-Deploy**, and confirm it
says **After CI Checks Pass**. Render normally applies the `render.yaml`
change on its next Blueprint sync. If the setting still shows **On Commit**,
sync the Blueprint (**Blueprints → bloom-beauty-bar → Manual Sync**) or
change the setting by hand.

Pull requests and other branches run CI but never deploy. Only `main` is
linked to the service.

## 3. Deploy → live

Render builds the Docker image from the commit and starts it. It switches
traffic only once `GET /api/health` returns 200, so a version that doesn't
start never goes live. On startup the app creates any missing tables and
seeds missing services, so no separate migration step is needed. The
database is untouched by deploys.

Follow progress in the service's **Events** and **Logs** tabs, or on the
commit in GitHub.

## 4. Verify the live site

After the deploy shows **Live**:

```
curl https://bloom-beauty-bar.onrender.com/api/health     # {"status":"ok"}
curl https://bloom-beauty-bar.onrender.com/api/services   # six services
```

Then open the site, make a test booking, check it shows on `/manage.html`,
and cancel it. On the free plan the first request after an idle spell can
take up to a minute while the service wakes up.

## Rollback

**Fast: roll back in Render (about a minute, no rebuild).**
1. Open the `bloom-beauty-bar` service, then **Events**.
2. Find the last deploy that worked and click **Rollback**.

Render redeploys that earlier image. It may switch auto-deploy off so the
next push doesn't undo the rollback. Once the fix is on `main`, set
**Auto-Deploy** back to **After CI Checks Pass**.

**Permanent: revert the change on `main`.**
```
git revert <bad-commit-sha>
git push origin main
```
This goes through CI and deploys like any other change, and it keeps `main`
matching what's live. Do this after a dashboard rollback, or instead of one
when nothing is urgent.

**Database caveat:** rollbacks only change the code. The schema is created
with `create_all`, which only adds tables and never alters them. Rolling back
is safe as long as the bad release didn't change existing tables. If one ever
does, add migrations (Alembic) before relying on rollback.

## Emergency deploy without CI

If CI itself is broken (for example, GitHub Actions is down) and a fix must
ship, use **Manual Deploy → Deploy latest commit** on the service. This skips
the checks, so run `py scripts/run_checks.py` locally first.

## Recommended GitHub setting

Protect `main` (**Settings → Branches**) and require the **Lint and tests**
and **Docker image** checks to pass before pull requests can merge. Then a
red build can't reach `main` at all.
