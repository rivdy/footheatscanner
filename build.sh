#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input

# Gunakan DATABASE_PUBLIC_URL saat build (internal URL belum tersedia di build phase)
if [ -n "$DATABASE_PUBLIC_URL" ]; then
  DATABASE_URL=$DATABASE_PUBLIC_URL python manage.py migrate
else
  python manage.py migrate
fi