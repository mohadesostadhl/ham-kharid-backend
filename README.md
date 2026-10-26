# Hamkharid API

Django + Django REST Framework + SQLite. Independent local Git repository.

```powershell
uv sync --locked
uv run python manage.py migrate
uv run python manage.py seed_demo
uv run python manage.py runserver 127.0.0.1:8000
```

In another terminal in this folder, run deadline processing:

```powershell
uv run python manage.py process_deadlines --watch
```

Frontend lives in the independent sibling `../frontend` repository.
Open http://127.0.0.1:3000 after starting it. Use the same hostname consistently.

See [setup and development demo accounts](docs/SETUP_GUIDE.md),
[architecture](docs/ARCHITECTURE.md), [test results](docs/TESTING.md),
and [Persian presentation guide](docs/PRESENTATION_GUIDE.md).
