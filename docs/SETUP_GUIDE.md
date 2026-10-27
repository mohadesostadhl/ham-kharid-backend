# Local setup

Requires Git, uv, Python 3.13 (uv can install it), and Node 24.21 or compatible newer
Node 24. SQLite is included with Python. No PostgreSQL or Docker is needed.

The parent directory contains two independent Git projects. Always run Git commands
inside backend or frontend. No remote is configured. On Windows use `npm.cmd`
when PowerShell execution policy prevents running npm.ps1.

## Terminal 1 — backend

```powershell
cd D:\Projects\uni\te\backend
uv sync --locked
uv run python manage.py migrate
uv run python manage.py seed_demo
uv run python manage.py runserver 127.0.0.1:8000
```

`db.sqlite3` is generated and ignored. Seeding is idempotent: repeating it does not
duplicate campaigns or reset reservations/passwords. Existing deadlines are retained;
for a fresh presentation, use a new SQLITE_PATH before migrate/seed. Do not overwrite
an existing database containing work you want to keep.

## Terminal 2 — frontend

```powershell
cd D:\Projects\uni\te\frontend
npm.cmd ci
npm.cmd run dev
```

Open http://127.0.0.1:3000. Keep the hostname consistent (do not mix localhost and
127.0.0.1 during a session). The API forwards to port 8000. Optional `.env.example`
files document configuration; backend variables are read from the shell, not dotenv.

## Terminal 3 — deadline worker

```powershell
cd D:\Projects\uni\te\backend
uv run python manage.py process_deadlines --watch
```

This polls every 30 seconds; `--interval 5` speeds up a local demonstration.
Without `--watch`, it processes due campaigns once and exits. Stop with Ctrl+C.
The web server rejects expired reservations even while the worker is stopped.

## Development-only fictional accounts

| Username | Role |
|---|---|
| seller_demo | Seller, Sabzineh |
| seller_second | Seller, Avand |
| buyer_demo | Buyer, no initial reservations |
| buyer_demo_2 through buyer_demo_8 | Buyers with sample reservations |

Default local password: `Demo-Only-2026!`. Set DEMO_PASSWORD before the first seed
to override it. These credentials are development-only; seed_demo refuses to run
when DJANGO_DEBUG=0. Never seed a production environment or reuse this password.
The frontend bundle does not include demo credentials.

## Build and checks

Backend: `uv run python manage.py test --noinput`, `uv run ruff check .`,
`uv run ruff format --check .`, `uv run python manage.py check`,
`uv run python manage.py makemigrations --check --dry-run`.

Frontend: `npm.cmd run lint`, `npm.cmd run format:check`, `npm.cmd run typecheck`,
`npm.cmd run build`. Run `npm.cmd run preview` for the built Node server.
Set HOST=127.0.0.1 before preview to restrict listening to loopback.
Both backend and frontend must be running for `npm.cmd run test:e2e`.

## Django administration

From the backend directory, apply migrations and create your own administrator:

```powershell
uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run python manage.py runserver 127.0.0.1:8000
```

Open http://127.0.0.1:8000/admin/ and log in using the credentials you chose.
The admin is served by Django on port 8000. Demo buyer/seller accounts do not have
admin access. No default admin password is created. Reset a forgotten password with
`uv run python manage.py changepassword YOUR_USERNAME`.

Manage users (including marketplace role, display name, passwords, staff status,
groups and permissions), categories and products. Create and edit draft campaigns,
then select them in the campaign list and use **Publish selected drafts**.
Published campaigns are read-only; **Settle selected campaigns past their deadline**
uses the same settlement logic as the deadline worker.

Reservations and orders are created through the marketplace workflow and are
read-only in admin. Use the reservation cancellation action to release capacity,
and the order actions to advance confirmed → shipped → completed. Invalid actions
display an error without changing that record. These records and campaigns cannot
be deleted through admin. This preserves stock counters and order price snapshots.

For additional administrators, enable **Staff status** and grant the required model
permissions individually or through groups. View permission allows inspection;
change permission also enables the corresponding workflow actions. Superusers have
all permissions. The admin uses the project's Persian locale and Tehran timezone.

Local `runserver` serves admin CSS/JS automatically. For deployment, run
`uv run python manage.py collectstatic --noinput` and configure your static-file
server to serve `/static/` from `backend/staticfiles/`.

## Public deployment boundary

This delivery is local-only. Production needs DEBUG=0, a unique secret key, HTTPS,
allowed host/CSRF origins, a production WSGI server, a supervised worker, database
backups and restore tests, shared throttling cache, and review of the dependency
advisory in TESTING.md. Keep the SQLite file on local persistent storage with a
single deployment owner; it is not a multi-host database service.
