#!/usr/bin/env bash
set -euo pipefail

export FLASK_APP="${FLASK_APP:-app:create_app}"
export SECRET_KEY="${SECRET_KEY:-dev}"
export AUTO_CREATE_DB="${AUTO_CREATE_DB:-false}"
export DATABASE_URL="${DATABASE_URL:-postgresql+psycopg2://people_app:people_dev_password@localhost:5432/people_dev}"

.venv/bin/flask db upgrade
.venv/bin/python demo_data.py
.venv/bin/flask run --host 0.0.0.0 --port "${PORT:-5000}" --no-debugger --no-reload
