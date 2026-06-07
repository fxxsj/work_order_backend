#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

# 优先使用已有的 run_tests.sh（功能更全）
if [ -f "run_tests.sh" ]; then
    bash run_tests.sh "$@"
    exit $?
fi

# Fallback: 基础测试
source venv/bin/activate
python manage.py test workorder.tests --verbosity=2
