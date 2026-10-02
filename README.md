# SAGAN — Search, Ask, Gather, Analyze, Now

[![Live demo](https://img.shields.io/badge/demo-live-5B3FBF)](https://sagan-tess.vercel.app)
![Python](https://img.shields.io/badge/Python-3.13-3776AB)
![Django](https://img.shields.io/badge/Django-5.2-092E20)
![Deploy](https://img.shields.io/badge/deploy-Vercel-000000)

A web platform for exploring **TESS exoplanet light curves** in the browser. SAGAN pulls the live
TESS Objects of Interest (TOI) catalog from NASA's ExoFOP archive, fetches each target's light curves
from MAST, and lets you clean, fold and compare them interactively — no Python notebook required.

**Live demo:** https://sagan-tess.vercel.app

> The interface is in Brazilian Portuguese. The name honors astronomer Carl Sagan.

## Features

- **Live TOI catalog** — thousands of TESS candidates fetched from ExoFOP/IPAC and cached in memory for 1 hour, with full-text search, disposition/source filters, sortable columns and pagination.
- **Observation browser** — for any TIC ID, lists every available TESS observation (sector, year, pipeline) straight from MAST.
- **Interactive light curves** — zoomable, pannable charts of normalized flux over time, with PNG and CSV export.
- **Analysis pipeline** — chain [Lightkurve](https://docs.lightkurve.org/) operations and see the result instantly:
  flatten (Savitzky–Golay), fold by period, bin, sigma-clip outliers, smooth, normalize (ratio / % / ppm) and truncate.
  Any step can be removed, and an original-vs-processed comparison view is available.
- **Automatic period search** — a Box Least Squares (BLS) periodogram finds the most likely transit period and mid-transit time, and folds the curve centered on the transit.
- **Learning pages** — a step-by-step guide and a theory section on the transit method.

## Architecture

```
Browser ──► Django (Vercel Function) ──► app/data.py ─────► ExoFOP TOI CSV   (in-memory cache, 1 h)
   ▲                 │
   │                 └──────────────────► app/lightcurves.py ─► MAST via lightkurve (LRU cache + /tmp)
   │
   └── the analysis pipeline lives in the browser and is POSTed as JSON on every change
```

The app is **stateless by design**, which is what lets it run on serverless infrastructure:

- No database, sessions or user accounts. The catalog is cached per instance; light curves are cached
  with an LRU cache and lightkurve's file cache in `/tmp`.
- The list of applied operations (the *pipeline*) is kept client-side. Each change sends the whole
  pipeline; the server validates it against a whitelist (known operations, typed and range-checked
  parameters, max 20 steps) and replays it on the base curve. Steps can be removed in any order and
  any instance can serve any request.
- Float payloads are trimmed to 9 significant digits to stay well below the function response limit.

## Tech stack

Python 3.13 · Django 5.2 · Lightkurve 2.6 · Astropy · Pandas · Bootstrap 5 · Google Charts · jQuery · Vercel

## Running locally

```bash
git clone https://github.com/joaovitor-rodrigues/sagan.git
cd sagan
python -m venv .venv
# Windows: .venv\Scripts\activate    Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
python manage.py runserver
```

Open http://127.0.0.1:8000. An internet connection is required (data comes from ExoFOP and MAST).
There is no database, so no migrations are needed.

> The first request on a cold instance is slow: importing the scientific stack takes a few seconds
> and ExoFOP can take ~20 s to generate the TOI catalog. Both are cached afterwards.

## Tests

```bash
python manage.py test
```

26 tests; external services are mocked with a synthetic transit light curve, so the suite runs offline.
It covers catalog search/filters/ordering, the observation lookup, every pipeline operation, chained
pipelines, input validation (unknown operations, bad values, size limit, malformed JSON), CSRF
enforcement, BLS period/T0 recovery and locale-safe numeric inputs.

## Deployment (Vercel)

The project uses Vercel's zero-config Django support: Vercel detects `manage.py`, loads
`sagan.wsgi.application`, runs `collectstatic` (served from the CDN) and deploys the app as a single
Python function. Pushes to `main` deploy to production automatically.

| File | Purpose |
| --- | --- |
| `.python-version` | Pins Python 3.13 |
| `vercel.json` | Function max duration |
| `sagan/settings.py` | Detects `VERCEL=1`: disables DEBUG, trusts `*.vercel.app`, honors `X-Forwarded-Proto`, moves astropy/lightkurve/matplotlib caches to `/tmp` |

Environment variables (see [`.env.example`](.env.example)):

| Variable | Required | Notes |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | yes | Any long random string |
| `DJANGO_ALLOWED_HOSTS` | no | Extra hosts; `*.vercel.app` is added automatically |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | no | Needed only for a custom domain |
| `VERCEL_SUPPORT_LARGE_FUNCTIONS` | yes, `1` | The scientific stack (astropy, scipy, lightkurve) exceeds the standard 500 MB Python bundle |

## Project structure

```
app/
  data.py          # ExoFOP catalog download + cache
  lightcurves.py   # MAST download, pipeline validation and operations, BLS period search
  views.py         # pages, catalog and light-curve endpoints
  tests.py
  static/app/      # CSS, logo, Font Awesome
templates/app/     # Django templates
sagan/             # settings, URLs, WSGI
```

## History

Started in 2021–2022 (originally hosted at
[clebersfonseca/sagan](https://github.com/clebersfonseca/sagan)) and modernized in 2026: Django 4 → 5.2,
live catalog instead of a static CSV, the analysis pipeline, BLS period search, a new UI, a stateless
architecture for serverless deployment and an automated test suite.

## Data credits

This project uses data from the [ExoFOP-TESS](https://exofop.ipac.caltech.edu/tess/) archive (NASA/IPAC)
and the [Mikulski Archive for Space Telescopes (MAST)](https://archive.stsci.edu/), accessed through
[Lightkurve](https://docs.lightkurve.org/). Icons by [Font Awesome](https://fontawesome.com/) (Free license).
