"""
Locust load test file for work order system
Tests API endpoints under concurrent load
"""
import random
import json
from locust import HttpUser, task, between, events
from locust.runners import MasterRunner
from locust_config import TARGET_HOST, TEST_USERS

class CommonBehaviorMixin:
    """Common behaviors shared across user types"""

    def on_start(self):
        """Login when user starts"""
        self._login()

    def _login(self):
        """Authenticate and store token"""
        user_type = random.choice(['supervisor', 'operator', 'maker'])
        credentials = TEST_USERS[user_type]

        response = self.client.post('/api/auth/login/', json={
            'username': credentials['username'],
            'password': credentials['password']
        }, name='[Auth] Login')

        if response.status_code == 200:
            data = response.json()
            if 'token' in data:
                self.token = data['token']
                self.client.headers.update({
                    'Authorization': f'Token {self.token}'
                })
            elif 'access' in data:
                # JWT token format
                self.token = data['access']
                self.client.headers.update({
                    'Authorization': f'Bearer {self.token}'
                })

    def _get_random_task_id(self):
        """Get a random task ID from the list"""
        response = self.client.get('/api/tasks/?page_size=1', name='[Tasks] Get random ID')
        if response.status_code == 200:
            results = response.json().get('results', [])
            if results:
                return results[0]['id']
        return None

    def _get_random_workorder_id(self):
        """Get a random work order ID"""
        response = self.client.get('/api/workorders/?page_size=1', name='[WorkOrders] Get random ID')
        if response.status_code == 200:
            results = response.json().get('results', [])
            if results:
                return results[0]['id']
        return None

class WorkOrderUser(CommonBehaviorMixin, HttpUser):
    """
    Simulates a regular user working with work orders and tasks
    Most common operations with realistic weighting
    """

    wait_time = between(1, 5)  # Wait 1-5 seconds between tasks
    host = TARGET_HOST

    @task(5)
    def view_task_list(self):
        """View task list - most common operation (weight 5)"""
        filters = {}
        if random.random() < 0.3:
            filters['status'] = random.choice(['pending', 'in_progress', 'completed'])
        self.client.get('/api/tasks/', params=filters, name='[Tasks] List')

    @task(3)
    def view_workorder_list(self):
        """View work order list (weight 3)"""
        self.client.get('/api/workorders/', params={
            'page': random.randint(1, 3),
            'page_size': 20
        }, name='[WorkOrders] List')

    @task(2)
    def view_task_detail(self):
        """View task detail"""
        task_id = self._get_random_task_id()
        if task_id:
            self.client.get(f'/api/tasks/{task_id}/', name='[Tasks] Detail')

    @task(1)
    def view_notifications(self):
        """View notifications (weight 1)"""
        self.client.get('/api/notifications/', name='[Notifications] List')

    @task(1)
    def view_statistics(self):
        """View dashboard statistics"""
        self.client.get('/api/statistics/task_summary/', name='[Stats] Task Summary')

class SupervisorUser(CommonBehaviorMixin, HttpUser):
    """
    Simulates supervisor with additional permissions
    Focuses on task assignment and department management
    """

    wait_time = between(2, 6)
    host = TARGET_HOST
    weight = 1  # Fewer supervisors than regular users

    @task(4)
    def view_department_tasks(self):
        """View department tasks"""
        departments = [1, 2, 3, 4, 5]
        dept_id = random.choice(departments)
        self.client.get('/api/tasks/', params={
            'assigned_department': dept_id,
            'status': 'pending'
        }, name='[Supervisor] Department Tasks')

    @task(3)
    def view_department_workload(self):
        """View department workload statistics"""
        self.client.get('/api/statistics/department_workload/', name='[Supervisor] Workload')

    @task(2)
    def assign_task(self):
        """Assign a task to operator (lower weight - write operation)"""
        # Get a pending task
        response = self.client.get('/api/tasks/', params={
            'status': 'pending',
            'page_size': 1
        }, name='[Supervisor] Get Pending Task')

        if response.status_code == 200:
            tasks = response.json().get('results', [])
            if tasks:
                task_id = tasks[0]['id']
                # Assign to random operator
                operator_id = random.randint(1, 50)
                self.client.post(f'/api/tasks/{task_id}/assign/', json={
                    'operator_id': operator_id
                }, name='[Supervisor] Assign Task')

    @task(1)
    def view_dashboard(self):
        """View supervisor dashboard"""
        self.client.get('/api/statistics/collaboration/', name='[Supervisor] Dashboard')

class OperatorUser(CommonBehaviorMixin, HttpUser):
    """
    Simulates operator focused on their tasks
    """

    wait_time = between(3, 8)
    host = TARGET_HOST
    weight = 1

    @task(5)
    def view_my_tasks(self):
        """View my assigned tasks"""
        self.client.get('/api/tasks/', params={
            'status': 'in_progress'
        }, name='[Operator] My Tasks')

    @task(3)
    def view_claimable_tasks(self):
        """View tasks I can claim"""
        self.client.get('/api/tasks/', params={
            'status': 'pending'
        }, name='[Operator] Claimable Tasks')

    @task(2)
    def update_task_progress(self):
        """Update task progress (write operation)"""
        task_id = self._get_random_task_id()
        if task_id:
            self.client.post(f'/api/tasks/{task_id}/update_progress/', json={
                'quantity': random.randint(1, 100)
            }, name='[Operator] Update Progress')

    @task(1)
    def claim_task(self):
        """Claim an unassigned task"""
        response = self.client.get('/api/tasks/', params={
            'status': 'pending',
            'page_size': 1
        }, name='[Operator] Get Claimable')

        if response.status_code == 200:
            tasks = response.json().get('results', [])
            if tasks:
                task_id = tasks[0]['id']
                self.client.post(f'/api/tasks/{task_id}/claim/', name='[Operator] Claim Task')

class MakerUser(CommonBehaviorMixin, HttpUser):
    """
    Simulates maker/sales user creating work orders
    """

    wait_time = between(5, 10)
    host = TARGET_HOST
    weight = 1

    @task(4)
    def view_my_workorders(self):
        """View work orders I created"""
        self.client.get('/api/workorders/', params={
            'page': random.randint(1, 5)
        }, name='[Maker] My WorkOrders')

    @task(1)
    def create_workorder(self):
        """Create a new work order (write operation)"""
        # Minimal work order data for testing
        self.client.post('/api/workorders/', json={
            'customer': 1,  # Assuming customer ID 1 exists
            'production_quantity': random.randint(100, 1000),
            'delivery_date': '2026-12-31',
            'priority': random.choice(['low', 'normal', 'high']),
        }, name='[Maker] Create WorkOrder')

    @task(2)
    def view_products(self):
        """View available products"""
        self.client.get('/api/products/', name='[Maker] Products List')

@events.quitting.add_listener
def on_quitting(environment, **kwargs):
    """
    Validate SLA compliance on quit.
    Exit with error code if SLAs are not met.
    """
    if isinstance(environment.runner, MasterRunner):
        return

    stats = environment.stats
    sla_passed = True

    print("\n" + "="*60)
    print("LOAD TEST RESULTS - SLA VALIDATION")
    print("="*60)

    # SLA 1: Average response time < 500ms
    avg_response_time = stats.total.avg_response_time
    print(f"\n1. Average Response Time: {avg_response_time:.0f}ms")
    print(f"   SLA Threshold: {500}ms")
    if avg_response_time > 500:
        print(f"   FAILED - Exceeds threshold by {avg_response_time - 500:.0f}ms")
        sla_passed = False
    else:
        print(f"   PASSED")

    # SLA 2: Error rate < 0.1%
    fail_ratio = stats.total.fail_ratio
    error_rate = fail_ratio * 100
    print(f"\n2. Error Rate: {error_rate:.3f}%")
    print(f"   SLA Threshold: 0.1%")
    if fail_ratio > 0.001:
        print(f"   FAILED - Exceeds threshold by {error_rate - 0.1:.3f}%")
        sla_passed = False
    else:
        print(f"   PASSED")

    # SLA 3: 95th percentile < 1000ms
    p95 = stats.total.get_response_time_percentile(0.95)
    print(f"\n3. 95th Percentile: {p95:.0f}ms")
    print(f"   SLA Threshold: 1000ms")
    if p95 > 1000:
        print(f"   FAILED - Exceeds threshold by {p95 - 1000:.0f}ms")
        sla_passed = False
    else:
        print(f"   PASSED")

    # RPS achieved
    rps = stats.total.total_rps
    print(f"\n4. Requests Per Second: {rps:.2f}")

    # Total requests
    total_requests = stats.total.num_requests
    print(f"5. Total Requests: {total_requests}")

    print("\n" + "="*60)
    if sla_passed:
        print("SLA VALIDATION: PASSED")
    else:
        print("SLA VALIDATION: FAILED")
        environment.process_exit_code = 1
    print("="*60 + "\n")
