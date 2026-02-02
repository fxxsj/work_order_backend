#!/bin/bash
#
# Load test execution script
#

set -e

echo "========================================"
echo "Work Order System - Load Test"
echo "========================================"
echo ""

# Configuration
USERS=${1:-100}
SPAWN_RATE=${2:-10}
RUN_TIME=${3:-5m}
HOST=${4:-http://localhost:8000}

echo "Configuration:"
echo "  Users: $USERS"
echo "  Spawn Rate: $SPAWN_RATE users/sec"
echo "  Run Time: $RUN_TIME"
echo "  Target Host: $HOST"
echo ""

# Safety check
if [[ "$HOST" == *"prod"* ]]; then
    echo "ERROR: Cannot run load test against production!"
    exit 1
fi

# Create results directory
mkdir -p backend/load-test-results
cd backend

# Check if server is running
echo "Checking if server is running..."
if ! curl -sSf "$HOST/api/" > /dev/null 2>&1; then
    echo "ERROR: Server is not responding at $HOST"
    echo "Please start the server first:"
    echo "  python manage.py runserver 8000"
    exit 1
fi
echo "Server is running."
echo ""

# Run load test
echo "Starting load test..."
locust -f locust/locustfile.py \
    --headless \
    --users "$USERS" \
    --spawn-rate "$SPAWN_RATE" \
    --run-time "$RUN_TIME" \
    --host "$HOST" \
    --html load-test-results/report.html \
    --csv load-test-results/results

EXIT_CODE=$?

echo ""
echo "========================================"
echo "Load Test Complete"
echo "========================================"
echo ""
echo "Results saved to:"
echo "  - backend/load-test-results/report.html (HTML report)"
echo "  - backend/load-test-results/results*.csv (Raw data)"
echo ""

if [ $EXIT_CODE -eq 0 ]; then
    echo "SLA Validation: PASSED"
else
    echo "SLA Validation: FAILED"
    echo ""
    echo "Please review the HTML report for details."
fi

exit $EXIT_CODE
