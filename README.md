# Mafori IT Helpdesk

A ticketing web app for Mafori Group: staff log IT issues, the IT team works them through a shared queue, and every change is recorded.

**Status:** Milestones 0 to 2 done (docs, project skeleton, staging). Next is Milestone 3, logins.
**Staging:** https://mafori-helpdesk-staging.onrender.com/admin/ (test data only)
**Full documentation:** [docs/PROJECT.md](docs/PROJECT.md)

## Stack

Python 3.13, Django 5.2 LTS, PostgreSQL 16 (psycopg 3), server-rendered templates, Gunicorn + WhiteNoise in production, Ruff for linting and formatting.

## Team

| Person | Area | Owns |
| --- | --- | --- |
| Dan | Database | Models, migrations, query helpers (`tickets/managers.py`), fixtures, `seed_demo`, admin setup |
| Jack | Backend | Views, URLs, forms, workflow rules, login and lockout, middleware |
| Sifiso | Frontend | `templates/`, `static/`, layout and Mafori branding |

Changes to someone else's area go through that person. Models and migrations go through Dan.

## Run it locally (Windows)

One-off: install Python 3.13 and PostgreSQL 16, then create the database in `psql -U postgres`:

```sql
CREATE USER helpdesk_app WITH PASSWORD 'pick-your-own' CREATEDB;
CREATE DATABASE mafori_helpdesk OWNER helpdesk_app ENCODING 'UTF8';
```

Then, in Command Prompt:

```
git clone https://github.com/danielAd0/Mafori-IT-Helpdesk.git C:\helpdesk
cd C:\helpdesk
py -3.13 -m venv .venv
.venv\Scripts\activate.bat
python -m pip install -r requirements.txt
copy .env.example .env
```

Open `.env`, set `DB_PASSWORD` to the password you picked and paste a secret key from:

```
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Build the tables, load data, test and run:

```
python manage.py migrate
python manage.py loaddata initial_data
python manage.py seed_demo
python manage.py test
python manage.py runserver
```

Open http://127.0.0.1:8000/admin/.

Use `python -m pip` and `python -m ruff`, not plain `pip` or `ruff`: Windows can block the `.exe` launchers inside `.venv`. In PowerShell, activate with `.venv\Scripts\Activate.ps1` instead.

After pulling new code, run `python -m pip install -r requirements.txt` and `python manage.py migrate` again.

### Test logins (local only)

`seed_demo` only runs when `DJANGO_DEBUG=True`. It creates:

| Role | Email | Password |
| --- | --- | --- |
| Admin | admin@maforigroup.co.za | Admin@2026 |
| IT agent | it.agent@maforigroup.co.za | Agent@2026 |
| Employee | staff@maforigroup.co.za | Staff@2026 |

These are dummy accounts for your own laptop. Staging has its own admin account; ask Dan for it.

## Before you push

```
python -m ruff format .
python -m ruff check .
python manage.py makemigrations --check
python manage.py test
```

## Git workflow

1. Pull `main`, then branch: `dan/...`, `jack/...`, `sifiso/...`.
2. Push the branch and open a pull request.
3. GitHub Actions runs the same four checks above against PostgreSQL 16. Only merge with a green tick.
4. A teammate reviews, then **Squash and merge** and delete the branch.
5. Every merge to `main` deploys to staging on Render automatically (`render.yaml`, `build.sh`).

## Never commit

- `.env`, passwords, secret keys or real staff details
- `.venv/`, `__pycache__/`, `staticfiles/`, database dumps

If a secret gets committed, tell the group straight away and change it. Deleting the file doesn't remove it from Git history.

Staging holds test data only. No real staff or tickets go anywhere until the production host is agreed with Mafori.
