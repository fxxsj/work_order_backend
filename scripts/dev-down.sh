#!/usr/bin/env bash
set -euo pipefail

# 终止 backend runserver
if pgrep -f "manage.py runserver" > /dev/null 2>&1; then
    pkill -f "manage.py runserver"
    echo "Backend runserver 已终止"
else
    echo "Backend runserver 未运行"
fi
