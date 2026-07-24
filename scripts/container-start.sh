#!/usr/bin/env bash
set -euo pipefail

echo "[container] Applying database migrations..."
python manage.py migrate --noinput

echo "[container] Initializing required system data..."
python manage.py init_system_data

echo "[container] Starting Daphne..."
exec daphne -b 0.0.0.0 -p 8000 config.asgi:application
