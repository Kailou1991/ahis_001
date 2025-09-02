#!/usr/bin/env bash
set -euo pipefail
if [ -f ".env" ]; then export $(grep -v '^#' .env | xargs); fi
python manage.py kobo_sync_all --since none --advisory-lock
python manage.py send_camvac_weekly_kobo
python manage.py backfill_campaigns_kobo
python manage.py sync_admin_areas
# python manage.py seed_initial_data_user
# python manage.py seed_actes
