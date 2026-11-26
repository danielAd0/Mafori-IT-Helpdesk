#!/usr/bin/env bash
# Runs on Render at every deploy (owner: Dan). Stops at the first error.
set -o errexit

pip install -r requirements.txt

# Copy CSS and images into staticfiles/ for WhiteNoise
python manage.py collectstatic --no-input

# Apply any new database migrations
python manage.py migrate --no-input

# Departments and categories: only fills a list that's still empty,
# so edits made in the admin panel survive every deploy
python manage.py seed_reference_data

# First admin account, from the DJANGO_SUPERUSER_* values set in Render.
# Only created once; later deploys skip it.
if [ -n "${DJANGO_SUPERUSER_EMAIL:-}" ]; then
  python manage.py createsuperuser --no-input || echo "Admin account already exists, skipping."
fi

# Print Django's production checklist into the deploy log
python manage.py check --deploy