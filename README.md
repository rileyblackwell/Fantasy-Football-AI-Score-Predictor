# Fantasy Football Score Predictor

A web app that projects weekly fantasy points (PPR, half-PPR and standard) for every NFL QB, RB, WR and TE.

- **Backend:** Django + Django REST Framework, Postgres in production (SQLite locally)
- **Frontend:** Vue 3 + Vite + TypeScript, built and served by Django (WhiteNoise)
- **Model:** LightGBM gradient boosting, trained on CPU in a few seconds
- **Data:** [nflverse](https://github.com/nflverse) via `nflreadpy` (weekly stats, schedules with Vegas lines, rosters, injury reports)
- **Hosting:** Railway (web service, Postgres, and a daily cron service)

The original scraper and PyTorch notebook live in [`legacy/`](legacy/) for reference.

## How predictions are made

1. `ingest` downloads regular-season box scores since 2016 plus the current season's schedule, rosters and injury reports.
2. `features.py` builds one row per player-week using only information from *before* that week: recent scoring
   (last 1/3/5/10 games, season average, last season), usage (targets, carries, pass attempts, target share), Vegas
   implied team total and spread, and how many points the opponent has allowed to that position.
3. `modeling.py` trains two LightGBM models (PPR and standard; half-PPR is their average) with Huber loss.
4. `pipeline.py`
   - scores a model trained on earlier seasons against the last full season (shown on the "How it works" page),
   - backtests the current season's played weeks with a model that never saw this season,
   - trains the final model on everything and projects the next unplayed week for active rostered players.
5. Trained models are stored in Postgres (`ModelRun.boosters`), so nothing depends on the container's disk.

## Local development

```bash
# Backend
python -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
cd backend
export DJANGO_DEBUG=1
python manage.py migrate
python manage.py refresh        # first run loads 2016-today (about 30s), then trains
python manage.py runserver      # http://localhost:8000

# Frontend (in another terminal) with hot reload, proxying /api to Django
cd frontend
npm install
npm run dev                     # http://localhost:5173
```

Useful commands:

| Command | What it does |
| --- | --- |
| `python manage.py refresh` | Daily job: pull current-season data, retrain, write predictions |
| `python manage.py refresh --if-empty` | Same, but only if no model exists yet (used on deploy) |
| `python manage.py ingest --full` | Reload every season from 2016 |
| `python manage.py train` | Retrain and re-predict without downloading |

## Tests

```bash
cd backend && python manage.py test predictor
cd frontend && npm test
```

## Deploying on Railway

The root `Dockerfile` builds the Vue app and the Django image. One project holds three services:

| Service | Start command | Notes |
| --- | --- | --- |
| `web` | Dockerfile default (gunicorn) | Pre-deploy: `python manage.py deploy_setup` (migrate, then load data and train if the DB is empty). Healthcheck `/api/health`. Serverless sleep on. |
| `refresh` | `python manage.py refresh` | Same image, cron `0 11 * * *` (daily, 11:00 UTC). Runs ~20s at ~0.5 GB, then exits. |
| `Postgres` | Railway template | `DATABASE_URL` is referenced by both app services. |

Environment variables for `web` and `refresh`: `DATABASE_URL=${{Postgres.DATABASE_URL}}`, `DJANGO_SECRET_KEY`.
