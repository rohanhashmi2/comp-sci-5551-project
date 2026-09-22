# InspectIQ

CS 5551 team project — food & beverage inspection management. Server-rendered
Django app.

The design proposal is in [`docs/design-notes.md`](docs/design-notes.md).
Read it and argue with it before writing feature code.

---

## Setup — clean clone to running server

The team uses **your own Supabase project for `runserver`** and **local
Postgres for `pytest`**. Two connection strings, one `.env`. See
`docs/design-notes.md` §12 for why.

### A. Create your Supabase project (once, per developer)

Each developer runs their own free Supabase project. Do not share credentials.

1. Sign up at [supabase.com](https://supabase.com) with your school or personal email.
2. Create a new project. Pick a region close to you.
3. **Record the database password shown in the setup dialog.** It is not displayed again.
4. Wait ~2 minutes for provisioning.
5. In the dashboard: **Project Settings → Database → Connection string → Session pooler → URI**. Copy this string. It contains your password. Do not paste it into PRs, Slack, or shared docs.
6. Check the Postgres major version so you can match it locally. Open the SQL editor and run:
   ```sql
   SHOW server_version;
   ```
   Note the major (e.g. `15` or `17`).

### B. Install local Postgres (for tests only)

Match the Postgres major version to your Supabase project (from step A.6). In the commands below, substitute `<major>` with that number (e.g. `17`).

**macOS — option 1: Postgres.app** (installer with multiple bundled majors)
- Download from [postgresapp.com](https://postgresapp.com).
- Open the app, select the major matching your Supabase project, click *Initialize*.
- Add the CLI to your PATH per the app's on-screen instructions (or `sudo mkdir -p /etc/paths.d && echo /Applications/Postgres.app/Contents/Versions/latest/bin | sudo tee /etc/paths.d/postgresapp`).
- Postgres.app creates a database role matching your macOS username with superuser rights, so `createdb` and psql "just work" as your login user.

**macOS — option 2: Homebrew**
```bash
brew install postgresql@<major>
brew services start postgresql@<major>
```
Homebrew also creates a role matching your macOS username.

**Linux — Debian/Ubuntu**
```bash
sudo apt update
sudo apt install postgresql-<major> postgresql-client-<major>
sudo systemctl enable --now postgresql
sudo -u postgres createuser --superuser "$USER"     # role matching your OS user
```
The `createuser` step is required — a fresh apt install only lets the `postgres` OS user connect. After it, `createdb` and `psql` work as your login user.

**Linux — Fedora/RHEL**
```bash
sudo dnf install postgresql-server postgresql-contrib
sudo postgresql-setup --initdb
sudo systemctl enable --now postgresql
sudo -u postgres createuser --superuser "$USER"
```

**Windows — option 1: EDB installer**
- Download the installer for your chosen major from [postgresql.org/download/windows](https://www.postgresql.org/download/windows/).
- During install, set a password for the built-in `postgres` superuser and remember it.
- Add `C:\Program Files\PostgreSQL\<major>\bin` to your `Path`.
- Windows does not auto-create a role matching your OS user — you connect as `postgres` with the password you set at install.

**Windows — option 2: WSL2**
- Install Ubuntu under WSL2, then follow the Linux — Debian/Ubuntu steps inside the WSL shell. Run all subsequent setup (including the Python venv and pytest) inside WSL.

Verify:
```bash
psql --version                       # should print the major you installed
pg_isready                           # should print "accepting connections"
```

Create the local database that pytest will use:
```bash
createdb inspectiq_dev               # macOS / Linux
# Windows (EDB installer):
#   psql -U postgres -c "CREATE DATABASE inspectiq_dev;"
```

`pytest` will then create/drop `test_inspectiq_dev` around each test run.

### C. Clone and set up the Python environment

```bash
git clone <repo-url> && cd comp-sci-5551-project

python3.12 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate

pip install --upgrade pip
pip install -r requirements/dev.txt
```

### D. Configure `.env`

```bash
cp .env.example .env
```

Edit `.env`:
- `DJANGO_SECRET_KEY` — a long random string. Generate one with:
  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(50))"
  ```
- `DATABASE_URL` — paste your Supabase session-pooler URI from step A.5. Keep the `?sslmode=require` at the end.
- `TEST_DATABASE_URL` — your local Postgres URL.
  - macOS / Linux, after step B: `postgres://<your-os-username>@localhost:5432/inspectiq_dev` (macOS/Linux users can typically expand `$USER` in a shell, but write the literal username into `.env` — `.env` is not shell-expanded).
  - Windows (EDB installer): `postgres://postgres:<the-password-you-set-at-install>@localhost:5432/inspectiq_dev`.

### E. Migrate and run

```bash
python manage.py migrate             # applies schema to your Supabase project
python manage.py createsuperuser     # optional; for /admin

pytest                               # runs against local Postgres
python manage.py runserver           # http://127.0.0.1:8000/
```

If `pytest` fails on first run because `inspectiq_dev` does not exist, run `createdb inspectiq_dev` and re-run.

If `runserver` fails to reach Supabase:
- Free-tier projects **pause after ~1 week of inactivity**. Open the Supabase dashboard and unpause.
- Confirm the URI is the *session pooler* (port 5432, host contains `pooler.supabase.com`), not the direct connection or the transaction pooler (port 6543).
- Confirm `?sslmode=require` is at the end.

---

## Layout

- `config/` — Django project package (settings, urls, wsgi, asgi).
- `apps/accounts/` — custom `User` model with role. Other domain apps live here as they are built (see `docs/design-notes.md`).
- `apps/common/` — shared mixins and helpers.
- `docs/` — design and acceptance documents.
- `requirements/base.txt` — runtime pins. `requirements/dev.txt` — test/lint pins.
- `pyproject.toml` — Black, Ruff, pytest config.

---

## Common commands

```bash
pytest                               # tests (against local Postgres)
pytest --cov=apps                    # tests with coverage
python manage.py migrate             # apply migrations to Supabase
python manage.py makemigrations      # after model changes
python manage.py runserver           # dev server
black .                              # format
ruff check .                         # lint
```
