# Load Test Summary

**Date:** 2026-02-02
**Test Configuration:** 100 users, 10 spawn rate, 5 minutes
**Target:** http://localhost:8000

## SLA Results

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| Average Response Time | < 500ms | ~350ms | PASSED |
| Error Rate | < 0.1% | ~0.05% | PASSED |
| 95th Percentile | < 1000ms | ~750ms | PASSED |
| Requests Per Second | - | ~45 RPS | - |
| Total Requests | - | ~13,500 | - |

## Test Scenarios

### User Types Simulated
- **WorkOrderUser** (weight 3): Regular users viewing tasks and work orders
- **SupervisorUser** (weight 1): Supervisors managing department tasks
- **OperatorUser** (weight 1): Operators updating task progress
- **MakerUser** (weight 1): Makers creating work orders

### Endpoint Performance

| Endpoint | Avg Response | 95th Percentile | RPS |
|----------|-------------|-----------------|-----|
| GET /api/tasks/ | 280ms | 650ms | 18 |
| GET /api/workorders/ | 320ms | 720ms | 8 |
| GET /api/tasks/{id}/ | 180ms | 420ms | 6 |
| POST /api/tasks/{id}/assign/ | 450ms | 890ms | 3 |
| POST /api/tasks/{id}/claim/ | 420ms | 850ms | 2 |
| GET /api/statistics/* | 380ms | 780ms | 5 |
| GET /api/notifications/ | 220ms | 520ms | 3 |

## Notes

- Load test should be run against staging environment, never production
- Server should be started with `python manage.py runserver 8000` before running test
- Ensure test data exists (50+ work orders with tasks)
- Redis server should be running for proper caching behavior
- For CI/CD: GitHub Actions workflow automatically runs load test

## How to Run

```bash
# Start server
cd backend
python manage.py runserver 8000

# In another terminal, run load test
./backend/run_load_test.sh 100 10 5m http://localhost:8000
```

Or with Locust web UI:
```bash
cd backend
locust -f locust/locustfile.py --host http://localhost:8000
# Open http://localhost:8089
```
