"""
Locust configuration for load testing
"""
import os

# Target host for load testing
# Use environment variable or default to localhost
TARGET_HOST = os.environ.get('LOCUST_TARGET_HOST', 'http://localhost:8000')

# Safety check to prevent accidental production testing
if 'prod' in TARGET_HOST.lower():
    raise ValueError(
        "CANNOT LOAD TEST PRODUCTION! "
        "Use staging environment. "
        f"Current target: {TARGET_HOST}"
    )

# Test credentials (should match test data setup)
TEST_USERS = {
    'supervisor': {'username': 'test_supervisor', 'password': 'testpass123'},
    'operator': {'username': 'test_operator', 'password': 'testpass123'},
    'maker': {'username': 'test_maker', 'password': 'testpass123'},
}

# Load test targets
TARGET_USERS = 100  # Number of concurrent users
SPAWN_RATE = 10     # Users per second
RUN_TIME = '5m'     # Test duration

# SLA thresholds
SLA_RESPONSE_TIME = 500  # ms
SLA_ERROR_RATE = 0.001   # 0.1%
SLA_P95_RESPONSE_TIME = 1000  # ms
