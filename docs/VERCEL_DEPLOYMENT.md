# Vercel and Neon deployment

The Vercel project root must be the `backend` repository directory. This project does
not need a `vercel.json`: current Vercel Django detection finds `manage.py` and the
`WSGI_APPLICATION` setting, and serves the Django application directly. Keeping the
deployment zero-config avoids replacing Django's URL routing with a second function
router.

## Vercel environment variables

Set these in Vercel Project Settings for Production (and Preview if that environment
uses a separate Neon branch):

```text
DJANGO_DEBUG=0
DJANGO_SECRET_KEY=<a-long-random-secret>
DATABASE_URL=postgresql://<user>:<password>@<neon-host>/<database>?sslmode=require
DJANGO_ALLOWED_HOSTS=<backend-project>.vercel.app
FRONTEND_URL=https://<frontend-project>.vercel.app
CORS_ALLOWED_ORIGINS=https://<frontend-project>.vercel.app
CSRF_TRUSTED_ORIGINS=https://<frontend-project>.vercel.app
```

Use the real Vercel domains, and include custom domains as comma-separated values when
needed. `DJANGO_ALLOWED_HOSTS` contains hostnames only; CORS and CSRF variables contain
full origins including `https://` and no trailing slash.

## Apply Neon migrations explicitly

Run this from the backend directory on a machine with the project's Python dependencies.
Use the Neon connection string from the Neon dashboard; do not commit it or place it in
source control.

```powershell
$env:DATABASE_URL = "postgresql://<user>:<password>@<neon-host>/<database>?sslmode=require"
$env:DJANGO_DEBUG = "0"
$env:DJANGO_SECRET_KEY = "<the-same-random-secret-used-in-vercel>"
$env:DJANGO_ALLOWED_HOSTS = "<backend-project>.vercel.app"

uv run python manage.py check --deploy
uv run python manage.py migrate --noinput
uv run python manage.py showmigrations market
```

`market.0001_initial` creates `market_category` and `market_campaign`; the later
migrations extend the existing schema. No migration runs during a request.

## Frontend environment variable

In the separate frontend Vercel project set:

```text
NUXT_PUBLIC_API_BASE_URL=https://<backend-project>.vercel.app/api
```

The frontend sends credentials for session authentication. The backend must therefore
list the exact frontend origin in both CORS and CSRF settings.
