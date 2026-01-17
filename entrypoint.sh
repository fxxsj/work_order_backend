#!/bin/bash

# Entrypoint script for 印刷施工单跟踪系统
set -e

echo "🚀 Starting 印刷施工单跟踪系统..."

# Wait for database to be ready
if [ -n "$DATABASE_URL" ]; then
    echo "⏳ Waiting for database..."
    while ! nc -z ${DATABASE_HOST:-localhost} ${DATABASE_PORT:-5432}; do
        sleep 1
    done
    echo "✅ Database is ready!"
fi

# Wait for Redis to be ready
if [ -n "$REDIS_URL" ]; then
    echo "⏳ Waiting for Redis..."
    while ! nc -z ${REDIS_HOST:-localhost} ${REDIS_PORT:-6379}; do
        sleep 1
    done
    echo "✅ Redis is ready!"
fi

# Run database migrations
echo "🔄 Running database migrations..."
python manage.py migrate --noinput

# Create superuser if needed
if [ "$CREATE_SUPERUSER" = "True" ]; then
    echo "👤 Creating superuser..."
    python manage.py shell << EOF
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='$SUPERUSER_USERNAME').exists():
    User.objects.create_superuser('$SUPERUSER_USERNAME', '$SUPERUSER_EMAIL', '$SUPERUSER_PASSWORD')
    print('Superuser created successfully')
else:
    print('Superuser already exists')
EOF
fi

# Load initial data if needed
if [ "$LOAD_INITIAL_DATA" = "True" ]; then
    echo "📊 Loading initial data..."
    python manage.py load_initial_users
    python manage.py loaddata workorder/fixtures/initial_products.json
fi

# Collect static files
echo "📁 Collecting static files..."
python manage.py collectstatic --noinput --clear

# Set proper permissions
echo "🔐 Setting permissions..."
chown -R django:django /app/staticfiles /app/media

echo "🎉 Setup complete! Starting application..."

# Execute the command passed to the script
exec "$@"