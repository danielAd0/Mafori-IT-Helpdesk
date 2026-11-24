# Mafori IT Helpdesk

Ticketing web app for Mafori Group: staff log IT issues, the IT team works them through to closed.

**Status:** Milestone 0 - documentation. No code yet.

**Stack:** Python 3.13, Django 5.2 LTS, PostgreSQL 16, deployed to a cloud host.

**Team**
- Dan - database (models, migrations, query helpers, backups)
- Jack - backend (views, workflow rules, logins and permissions)
- Sifiso - frontend (templates, CSS, Mafori branding)

**Rules**
- Never commit `.env`, passwords, secret keys or real staff details.
- No pushing straight to `main`: branch, pull request, one approval.

The full project documentation is shared with the team separately and will be added to `docs/` in Milestone 1.