#!/bin/bash
set -e

echo "Waiting for PostgreSQL at ${DB_HOST}:${DB_PORT}..."
python << 'PYTHON_SCRIPT'
import socket
import time
import os
import sys

host = os.environ.get('DB_HOST', 'postgres')
port = int(os.environ.get('DB_PORT', '5432'))
max_retries = 30

for attempt in range(max_retries):
    try:
        s = socket.create_connection((host, port), timeout=2)
        s.close()
        print(f"PostgreSQL is ready at {host}:{port}")
        sys.exit(0)
    except (socket.error, ConnectionRefusedError, OSError):
        print(f"Attempt {attempt + 1}/{max_retries}: PostgreSQL not ready, retrying in 2s...")
        time.sleep(2)

print("ERROR: Could not connect to PostgreSQL after 30 attempts. Exiting.")
sys.exit(1)
PYTHON_SCRIPT

echo "Running database migrations..."
python manage.py migrate --noinput

echo "Starting Gunicorn server..."
exec gunicorn restaurant.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 2 \
    --timeout 60 \
    --access-logfile - \
    --error-logfile -
