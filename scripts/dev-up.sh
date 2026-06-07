#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

# 优先使用已有的 runserver.sh（功能更全）
if [ -f "runserver.sh" ]; then
    bash runserver.sh runserver "$@"
    exit $?
fi

# Fallback
source venv/bin/activate
python manage.py runserver --skip-checks "$@"
