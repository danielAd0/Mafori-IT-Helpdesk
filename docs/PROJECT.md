# Mafori IT Helpdesk — Project Documentation

Started 24 Nov 2026 · owner: Dan (database)

> This is a copy of the live project doc, kept next to the code. The live doc has the diagrams: https://claude.ai/artifact/PYQZAXH4UP1WHvZuNRKYUM

## Overview

The Mafori IT Helpdesk is a web app where Mafori Group staff log IT issues, and the IT team picks them up, works them and closes them. Every issue becomes a ticket with a reference like MAF-000042, so nothing gets lost in phone calls or messages.

**Who uses it**

- **Employees** log issues and follow the progress of their own tickets.
- **IT agents** work a shared queue: assign, update, add notes and resolve.
- **Admins** manage staff accounts and ticket categories.

**Goals for the first release**

1. Staff can log a ticket and see its status at any time.
2. The IT team has one queue, sorted by urgency, instead of scattered requests.
3. Everyone logs in with their own account, and sees only what their role allows.

**Why the project restarted on Python**

The first version was built on Java EE (GlassFish 4.1.2 on JDK 8, MySQL). It worked locally, but GlassFish 4.1.2 is no longer maintained and is awkward to run on cloud hosts. Django on PostgreSQL deploys to standard cloud platforms and has logins, roles, an admin panel and database migrations built in. The design work carries over: the data model, roles, ticket workflow and security rules from the first version are the starting point for this one.

## Scope

The first release (MVP) covers logging tickets, the IT queue and role-based logins. Everything else waits until that works end to end.

| Area | MVP (release 1) | Later |
| --- | --- | --- |
| Logins | Email + password, roles, lockout after 5 failed attempts, forced password change for new accounts | Single sign-on with Microsoft 365 |
| Tickets | Log a ticket (subject, category, priority, description, asset tag, location); see own tickets and their status | Attachments (screenshots, documents) |
| IT queue | One queue sorted by priority then age; filter by status, priority, agent, unassigned | Saved filters, bulk actions |
| Working a ticket | Assign, change status and priority, public comments, internal IT-only notes, full history | Linked or duplicate tickets |
| Dashboard | Ticket counts per status; employees see their own counts | Reports: per category, per month, average time to resolve |
| Admin | Manage users, roles, departments and categories through the Django admin panel | Custom admin pages |
| Notifications | None | Email when a ticket is assigned, updated or resolved |

**Out of scope:** asset/inventory management, live chat, a mobile app, and any customer-facing (non-staff) access.

## Team and ownership

The team keeps the same three areas as before; only the tools change. Each person owns their files and reviews changes others make to them.

| Person | Area | Owns in Django |
| --- | --- | --- |
| Dan | Database | `models.py` (data model), migrations, PostgreSQL setup, seed data, query helpers that enforce who can see what, management commands, backups |
| Jack | Backend | `views.py`, `urls.py`, `forms.py`, the ticket workflow rules, role and permission checks, login and password flows, middleware |
| Sifiso | Frontend | Templates (`templates/`), base layout and navigation, CSS and Mafori branding (`static/`), form layout, accessibility |

**Shared by everyone:** tests for your own code, the docs in this file, and code review on each other's pull requests.

Where work crosses areas (for example, a new page needs a new field), the person who needs it raises it and the owner makes the change. Nobody edits another person's area without a heads-up first.

## Tech stack and decisions

We build on Django 5.2 LTS with Python 3.13 and PostgreSQL, rendered as server-side pages, and deploy to a cloud host. Django 5.2 is the long-term support release, with security fixes until 30 April 2028 ([endoflife.date](https://endoflife.date/django)); the newer 6.1 is supported only until 31 December 2027.

| Layer | Choice | Why |
| --- | --- | --- |
| Language | Python 3.13 | Supported by Django 5.2 (3.10 to 3.14) and by every library we need |
| Framework | Django 5.2 LTS | Logins, sessions, CSRF protection, password hashing, admin panel and migrations built in |
| Database | PostgreSQL 16 | Already installed on Dan's laptop; Django's best-supported database; offered as a managed service by cloud hosts |
| Pages | Django templates + plain CSS | One codebase, no separate frontend build; Sifiso owns the templates |
| Database driver | psycopg 3 | The current PostgreSQL driver for Django |
| Settings and secrets | Environment variables, loaded from a `.env` file locally | No passwords or keys in the code or the repo |
| Web server (live) | Gunicorn, with WhiteNoise serving CSS and images | The standard way to run Django on a cloud host |
| Tests | Django's test runner | Built in, nothing extra to learn |
| Code style | Ruff (linter and formatter) | One tool, fast, same formatting for everyone |

**What we no longer need from the Java version:** GlassFish, JDK 8, JNDI and connection pools, hand-written SHA-256 hashing, and the SQL stored procedures for accounts. Django handles each of these: its default password hashing (PBKDF2 with a per-user salt) is stronger than what we built, and the admin panel replaces the account procedures.

## Architecture and project structure

One Django project with two apps: `accounts` for people and logins, `tickets` for everything about tickets. Pages are built on the server, so there is one codebase and one thing to deploy.

Every request passes the login check before any view runs:

```
Browser --> Middleware -----------> Views -------------------> Models ---------------> PostgreSQL
            (Jack)                  (Jack)                     (Dan)                   (Dan)
            login required,         URLs, forms, role checks,  query helpers,          tables, indexes,
            forced password change  workflow rules             history rows, migrations  backups
                                      |
                                      v
                                    Templates (Sifiso): HTML pages, CSS, Mafori branding
                                      |
Browser <---- finished HTML page -----+
```

The middleware turns away anyone not logged in, or still on a temporary password, before a view runs. Views never query the database directly: they call Dan's query helpers, which already filter by who is asking.

**Folder layout**

```
C:\helpdesk\                 the repo
  helpdesk\                  settings, root URLs, wsgi (shared)
  accounts\                  User, Department, login, password change, middleware
  tickets\
    models.py                Category, Ticket, TicketComment, TicketHistory (Dan)
    managers.py              query helpers such as visible_to(user) (Dan)
    migrations\              generated from models.py (Dan)
    fixtures\initial_data.json   departments and categories (Dan)
    services.py              workflow: assign, change status, reopen (Jack)
    views.py, urls.py, forms.py  pages and forms (Jack)
    tests\                   tests for this app (everyone)
  templates\                 base layout + a folder per app (Sifiso)
  static\                    CSS, images, Mafori logo (Sifiso)
  docs\                      this documentation
  requirements.txt           exact package versions
  .env.example               settings template, no real secrets
  manage.py
```

## Data model

Six models carry the whole app, the same six as the Java version, now written as Django models that generate the PostgreSQL tables through migrations. Dan owns them; any new field goes through him.

| Model (app) | Key fields | Rules |
| --- | --- | --- |
| `User` (accounts) | email (login, unique, stored lowercase), first and last name, role, department, phone extension, must change password, failed logins, active | A **custom user model**, set up before the first migration because Django can't switch to one later. Never deleted: leavers are deactivated so their tickets keep a name. |
| `Department` (accounts) | name (unique) | IT, Finance, Human Resources, Operations, Sales, Management to start |
| `Category` (tickets) | name (unique), description, active | Retired categories are deactivated, not deleted, so old tickets keep theirs |
| `Ticket` (tickets) | subject (150 characters), description, category, priority, status, requester, assigned agent, asset tag, location, created, updated, resolved and closed times, resolution note | Reference shown as `MAF-` + the ID padded to 6 digits. Requester and category can't be deleted while tickets use them. |
| `TicketComment` (tickets) | ticket, author, body, internal flag, created time | Internal notes are for IT only and are never shown to employees |
| `TicketHistory` (tickets) | ticket, changed by, field (status, assignee, priority, category), old value, new value, changed time | One row per change, written by the app, never edited or deleted. It is the audit trail. |

**Fixed choices** (stored as text, defined once in code):

- Roles: `EMPLOYEE`, `AGENT`, `ADMIN`
- Priorities: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`
- Statuses: `OPEN`, `ASSIGNED`, `IN_PROGRESS`, `ON_HOLD`, `RESOLVED`, `CLOSED`

**Indexes** for the screens people use most: tickets by status and priority (the queue), by assigned agent and status (my work), and by requester and created time (my tickets).

## Roles and permissions

Every user has exactly one role, and the server checks it on every request. Hiding a button is never the only protection.

| Action | Employee | Agent | Admin |
| --- | --- | --- | --- |
| Log a ticket | Yes | Yes | Yes |
| See own tickets and their public comments | Yes | Yes | Yes |
| Comment on own ticket | Yes | Yes | Yes |
| Reopen own resolved ticket | Yes | No | No |
| See all tickets and the IT queue | No | Yes | Yes |
| Assign, change status, change priority | No | Yes | Yes |
| Write and read internal IT notes | No | Yes | Yes |
| See ticket history | Own tickets | Yes | Yes |
| Use the admin panel (users, departments, categories) | No | No | Yes |

An employee who opens another person's ticket by changing the URL gets a "not found" page, the same as for a ticket that doesn't exist, so they can't learn which tickets exist.

## Ticket workflow

Every ticket starts Open and moves through the statuses below. Any move not drawn here is refused by the server.

A ticket closes only after it is resolved; the requester can reopen it until then.

```
                                                        +---- requester reopens -------+
                                                        v                              |
OPEN --agent assigns--> ASSIGNED --agent starts--> IN_PROGRESS --agent resolves--> RESOLVED --agent closes--> CLOSED
                                                     |      ^
                            waiting on parts or user |      | work resumes
                                                     v      |
                                                      ON_HOLD
```

**Rules (Jack builds, Dan's history table records):**

- Agents and admins make every move, except reopening, which only the ticket's requester can do.
- Assigning an Open ticket moves it to Assigned. Reassigning keeps the current status.
- Resolving needs a resolution note and sets the resolved time. Reopening clears it.
- Closing sets the closed time. A closed ticket can't change again; a new problem gets a new ticket.
- Every change of status, assignee, priority or category writes one history row in the same database transaction, so the audit trail can't miss a change.

## Security requirements

These rules apply to every page, and each one gets a test. Most come free with Django; the ones marked **(we build)** are ours.

**Logging in**

- Passwords are hashed with Django's default (PBKDF2, per-user salt). Minimum 8 characters, plus Django's checks against common passwords and passwords too similar to the user's name or email.
- A wrong email and a wrong password give the same message: "Invalid email or password."
- **(we build)** 5 failed attempts in a row locks the account. A locked account is not checked against its password at all, and only an admin can unlock it.
- **(we build)** New accounts and admin password resets get a temporary password and must change it at first login. Until then, every page except change password and log out redirects there.

**Sessions**

- Django starts a new session on every login, which blocks session fixation.
- The session cookie is HttpOnly, and Secure (HTTPS only) on the live site. Sessions end after 30 minutes without activity.
- Log out is a button (POST), never a link.
- Logged-in pages are sent with no-cache headers, so the Back button after logging out can't show them.

**Pages and data**

- Every form carries Django's CSRF token.
- Templates escape user text automatically. Nobody uses `|safe` or `mark_safe` on anything a user typed.
- **(we build)** Who-can-see-what lives in one place: query helpers on the models (for example `Ticket.objects.visible_to(user)`). Views use these helpers, never raw queries.
- The admin panel is open to the ADMIN role only.

**Secrets**

- The secret key, database password and any API keys live in environment variables: a `.env` file locally (never committed), the host's settings on the live site. The repo holds a `.env.example` with placeholders only.
- The live site runs with `DEBUG = False`.
- The GitHub repo is private.

**POPIA**

The helpdesk stores personal information: staff names, work emails, phone extensions and whatever people type into tickets. Under POPIA, Mafori must keep it secure (section 19) and may only send it outside South Africa under the conditions in section 72. That makes the hosting region a decision to confirm with Mafori before go-live (see Open questions).

## Development setup

Each teammate runs the full app on their own Windows laptop, against their own local PostgreSQL. Steps 1 to 4 are once-off; steps 5 to 9 work once Milestone 1 (the project skeleton) is in the repo.

1. **Python 3.13.** Download the Windows installer from python.org. If you already have another Python (say 3.14), untick **Add python.exe to PATH** so it doesn't take over; the `py -3.13` launcher finds 3.13 anyway. Check in Command Prompt: `py -3.13 --version`.
2. **PostgreSQL 16.** Download the Windows installer from postgresql.org, keep port 5432, set a password for the `postgres` superuser and write it down. Skip Stack Builder at the end.
3. **Create the database.** In Command Prompt run `psql -U postgres` (enter the superuser password), then:

   ```sql
   CREATE USER helpdesk_app WITH PASSWORD 'pick-your-own' CREATEDB;
   CREATE DATABASE mafori_helpdesk OWNER helpdesk_app ENCODING 'UTF8';
   ```

   `CREATEDB` lets Django create a throwaway database when tests run. Type `\q` to leave.
4. **Editor.** VS Code with Microsoft's Python extension.
5. **Get the code:** `git clone https://github.com/danielAd0/Mafori-IT-Helpdesk.git C:\helpdesk`, then `cd C:\helpdesk`.
6. **Virtual environment** (keeps this project's packages separate):

   ```
   py -3.13 -m venv .venv
   .venv\Scripts\activate.bat
   python -m pip install -r requirements.txt
   ```

   Your prompt now starts with `(.venv)`. Run the `activate.bat` line every time you open a new terminal for this project (in PowerShell: `.venv\Scripts\Activate.ps1`). Always use `python -m pip` and `python -m ruff`, not `pip` or `ruff` on their own: Windows can block the small `.exe` launchers inside `.venv`. In VS Code, press Ctrl + Shift + P, choose **Python: Select Interpreter**, and pick the one inside `.venv`.
7. **Settings:** `copy .env.example .env`, then open `.env` and fill in your database password from step 3 and a secret key. Generate a key with `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`. Use only letters, digits and dashes in the password: a `#` in `.env` starts a comment.
8. **Build the tables and load data:**

   ```
   python manage.py migrate
   python manage.py loaddata initial_data
   python manage.py seed_demo
   python manage.py test
   ```

   `seed_demo` adds three test logins (admin, IT agent, staff) and sample tickets; it only runs with `DJANGO_DEBUG=True`. The tests should end with OK.
9. **Run it:** `python manage.py runserver`, then open http://127.0.0.1:8000/admin/ and log in as `admin@maforigroup.co.za` / `Admin@2026`. Stop it with Ctrl + C.

Port 8000 doesn't clash with Spring Boot projects on 8080. After pulling new code, run `python -m pip install -r requirements.txt` and `python manage.py migrate` again, in case someone added a package or changed the models.

## Conventions and Git workflow

Nobody pushes straight to `main`. Every change goes through a branch and a pull request that one other teammate approves.

**Branches and pull requests**

1. Pull the latest `main`, then make a branch named for the work: `dan/ticket-model`, `jack/login-view`, `sifiso/base-layout`.
2. Commit in small steps with clear messages: `Add Ticket model and migration`, not `changes`.
3. Push the branch and open a pull request on GitHub. Say what it does and how you tested it.
4. One teammate reviews and approves. The owner of the area (see Team and ownership) reviews changes to their files.
5. Merge with **Squash and merge**, then delete the branch.

This is a team agreement; `main` has no branch protection switched on, so stick to it.

**Code**

- Run `python -m ruff check .` and `python -m ruff format .` before every commit. GitHub Actions also runs ruff, a migrations check and all tests on every push; only merge a pull request with a green tick.
- Models, migrations and query helpers go through Dan. Never edit a migration that's already on `main`; make a new one.
- One migration per model change, committed together with the model change.
- New pages: a view (Jack), a URL, and a template (Sifiso). A view always checks the role before doing anything.
- Names: Python `snake_case`, classes `PascalCase`, templates `tickets/ticket_detail.html`, URLs `/tickets/42/`.
- Every bug fix comes with a test that would have caught it.

**Never commit**

- `.env`, passwords, secret keys or real staff details
- `.venv/`, `__pycache__/`, `staticfiles/`, database dumps

The `.gitignore` from Milestone 1 covers these. If a secret does get committed, tell the group straight away and change that secret: deleting the file doesn't remove it from Git history.

## Deployment and operations

The plan is to deploy a test copy to Render early (Milestone 2) so deploying is never left to the end, then choose the production host with Mafori once cost and data location are agreed.

**Environments**

| Environment | Where | Database | Who uses it |
| --- | --- | --- | --- |
| Local | Each teammate's laptop | Their own PostgreSQL 16 | The developer |
| Staging | Render, auto-deployed from `main` | Render PostgreSQL | The team, and Mafori for demos |
| Production | To decide with Mafori | Managed PostgreSQL with backups | Mafori staff |

**Staging is live** (since 25 Nov 2026): [mafori-helpdesk-staging.onrender.com](https://mafori-helpdesk-staging.onrender.com/admin/), region Frankfurt, deployed from `main` by `render.yaml`. Free database expires 30 days after creation, around 25 Dec 2026.

**Why Render for staging:** it deploys straight from a GitHub branch on every push, gives an HTTPS address, and runs Django with PostgreSQL without a Dockerfile ([Render](https://render.com/hosting/django)). Its free tier is a trial, not a home: free PostgreSQL databases expire 30 days after creation and have no backups ([Render docs](https://render.com/docs/free)). Production needs a paid database.

**Every deploy runs:**

1. `python -m pip install -r requirements.txt`
2. `python manage.py collectstatic --no-input`
3. `python manage.py migrate --no-input`
4. `python manage.py loaddata initial_data` (departments and categories)
5. `python manage.py createsuperuser --no-input` (first deploy only, from the `DJANGO_SUPERUSER_*` values set in Render)
6. Start with Gunicorn: `python -m gunicorn helpdesk.wsgi:application`

Steps 1 to 5 live in `build.sh`; the whole setup lives in `render.yaml`.

**Production checklist** (before real staff log in)

- [ ] Host and region agreed with Mafori, including where the data is stored (POPIA)
- [ ] `DEBUG = False`, a new secret key, `ALLOWED_HOSTS` set to the real address
- [ ] HTTPS on, secure cookies on
- [ ] Daily database backups on, and one restore tested
- [ ] Test accounts and sample tickets removed
- [ ] Real staff accounts created, temporary passwords handed over in person
- [ ] Admin access limited to named IT staff

**Backups:** the managed database's own daily backups, plus a weekly `pg_dump` copy kept somewhere else, so one provider failing can't lose every ticket. Restore-test once a month.

## Roadmap and milestones

We build in thin, working slices: each milestone ends with something running, not a pile of half-done parts. Deploying comes second, so it's never a surprise at the end.

| # | Milestone | Who | Done when | Status |
| --- | --- | --- | --- | --- |
| 0 | Documentation and clean repo | Dan | The team has read and agreed this doc, and the repo is wiped and private | Done |
| 1 | Project skeleton | Dan: project, models, migrations, starting data. Jack: settings, middleware. Sifiso: base layout | Every teammate runs it locally and logs into the admin panel | Dan's part done |
| 2 | Staging on Render | Dan and Jack | Every push to main deploys automatically to a live HTTPS address | Done (25 Nov 2026) |
| 3 | Logins | Jack: login, logout, lockout, password change. Sifiso: login pages. Dan: User model and admin | Every login security test passes on staging | Next |
| 4 | Log and track tickets | Jack: new ticket and my tickets views. Sifiso: ticket pages. Dan: visible_to query helpers | An employee logs a ticket and follows it, and can't see anyone else's | |
| 5 | IT queue and working tickets | Jack: queue, assign, status, comments. Sifiso: queue and detail pages. Dan: history and indexes | An agent takes a ticket from Open to Closed, with every step in its history | |
| 6 | Dashboard and go-live | Everyone | The production checklist is ticked and Mafori staff are using it | |

Each milestone starts once the one above meets its done-when.

Dates are still to be set as a team, once everyone has read this doc. Within a milestone, Dan's models land first, because the views and pages build on them.

## Open questions and decisions

**Open questions**

- [ ] Production host, region and monthly budget: who at Mafori signs off? (Dan to ask)
- [ ] Must ticket data stay in South Africa, or is a host abroad acceptable under POPIA? (Dan to ask)
- [ ] Web address: a subdomain such as helpdesk.maforigroup.co.za? (Dan to ask)
- [x] Account lockout: decided 25 Nov 2026 — our own small check, not django-axes (Jack's proposal). Dan added failed\_logins to User and an admin "Unlock" action.
- [ ] How long are closed tickets kept before they're archived or deleted? (Mafori)
- [ ] Who at Mafori gets the ADMIN role, and who supplies the first staff list? (Mafori)

**Decisions log**

| Date | Decision |
| --- | --- |
| 24 Nov 2026 | Restart on Django 5.2 LTS, Python 3.13 and PostgreSQL 16, server-rendered pages |
| 24 Nov 2026 | Host in the cloud; deploy a staging copy to Render early |
| 24 Nov 2026 | Wipe the GitHub repo's history and start clean; the Java version is archived outside the repo |
| 24 Nov 2026 | Keep the data model, roles, ticket workflow and security rules from the Java design |
| 24 Nov 2026 | Same ownership: Dan database, Jack backend, Sifiso frontend |
