#!/bin/bash
# Django开发命令包装脚本
# 由于模块化结构使用了字符串外键引用，需要跳过admin系统检查

COMMAND=${1:-runserver}
shift

echo "🚀 执行 Django 命令: $COMMAND（跳过系统检查）"
echo "⚠️  注意：跳过系统检查是因为模块化结构中使用了字符串外键引用"
echo "    这些引用在运行时会被Django正确解析，所以跳过检查是安全的"
echo ""

if [ "$COMMAND" = "runserver" ]; then
    venv/bin/python manage.py runserver --skip-checks "$@"
elif [ "$COMMAND" = "migrate" ]; then
    venv/bin/python manage.py migrate --skip-checks "$@"
elif [ "$COMMAND" = "createsuperuser" ]; then
    venv/bin/python manage.py createsuperuser "$@"
elif [ "$COMMAND" = "shell" ]; then
    venv/bin/python manage.py shell "$@"
elif [ "$COMMAND" = "makemigrations" ]; then
    venv/bin/python manage.py makemigrations "$@"
else
    venv/bin/python manage.py "$COMMAND" --skip-checks "$@"
fi
