# LeftoverEat

Pickup-only surplus food app. A hotel posts leftovers once and picks one of three streams:

| Stream | Claimed by | Price |
|---|---|---|
| Rescue Deal | Customers | Hotel-set, paid at pickup |
| Community Give | Verified NGOs | Free |
| Shelter Feed | Verified animal shelters | Free |

NGO and shelter accounts start as `pending`; an admin must mark them `verified` before free listings are visible or claimable. Claiming reserves portions with an atomic stock decrement. There are no payments and no delivery.

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env   # optional; export the vars or use your own loader
uvicorn app.main:app --reload
pytest -q
```

Open http://localhost:8000. With `SEED_DEMO=1` (default) these accounts exist, all with password `demo12345`:
`hotel@demo.test`, `customer@demo.test`, `ngo@demo.test` (verified), `shelter@demo.test` (verified), `pending-ngo@demo.test`.
The admin is `ADMIN_EMAIL` / `ADMIN_PASSWORD` (defaults `admin@leftovereat.local` / `admin12345`; change them for anything public).

## Configuration

| Variable | Purpose |
|---|---|
| `SECRET_KEY` | Signs session cookies. Required in production. |
| `DATABASE_URL` | SQLite by default; Postgres URL on Railway. |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | Seeds the admin on startup. |
| `SEED_DEMO` | `1` creates demo accounts and listings. Set `0` in production. |
| `COOKIE_SECURE` | `1` in production (HTTPS only cookies). |
| `TZ_OFFSET_MINUTES` | Venue-local time offset for pickup windows. Default `330` (IST). |

## Deploy on Railway

1. Push this repo to GitHub.
2. In Railway: New Project, Deploy from GitHub repo. `railway.toml` selects the Dockerfile and the `/health` check.
3. Add the Postgres plugin; Railway sets `DATABASE_URL`.
4. Set `SECRET_KEY` (long random string), `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `SEED_DEMO=0`, `COOKIE_SECURE=1`.
5. Generate a public domain in Settings, Networking.

Railway redeploys on every push to `main` once the repo is connected. Optionally, GitHub Actions can drive the deploy instead: add repository secrets `RAILWAY_TOKEN` (project token) and `RAILWAY_SERVICE` (service name), and the `deploy` job in `.github/workflows/ci.yml` runs `railway up` after tests pass. If you use both, disable one to avoid double deploys.

Vercel isn't a fit for this FastAPI + database monolith; use it later for a static marketing page if wanted.

## Known MVP limits

- Auth is cookie-session only: no password reset, email verification, or CSRF tokens (cookies are `SameSite=Lax`, HttpOnly).
- Tables are created on startup with `create_all`; there are no migrations yet (add Alembic before changing the schema in production).
- Admin "verification" is a manual judgement. The app does not check FSSAI or any registry.
- Safety text on free listings is a reminder, not legal advice or compliance.
