"""
Performance tests to verify query optimization

Tests ensure ORM queries are optimized to prevent N+1 problems
and use efficient annotated queries instead of loop-based counting.
"""
from django.test import TestCase, override_settings
from django.db import connection, reset_queries
from django.contrib.auth.models import User, Permission
from django.contrib.contenttypes.models import ContentType

from workorder.models.core import WorkOrderTask, WorkOrder, WorkOrderProcess
from workorder.models.base import Department, Process
from workorder.views.work_order_tasks.task_stats import TaskStatsMixin


class PerformanceTestCase(TestCase):
    """Test query performance and N+1 elimination"""

    def setUp(self):
        """Create test data"""
        # Create department
        self.department = Department.objects.create(name='Test Dept')

        # Create user with permissions
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.user.profile.departments.add(self.department)

        # Add change_workorder permission
        ct = ContentType.objects.get_for_model(WorkOrderTask)
        permission = Permission.objects.get(codename='change_workorder', content_type=ct)
        self.user.user_permissions.add(permission)

        # Create customer
        from workorder.models.base import Customer
        self.customer = Customer.objects.create(
            name='Test Customer',
            contact_person='John Doe',
            phone='1234567890'
        )

        # Create work order
        self.work_order = WorkOrder.objects.create(
            order_number='TEST001',
            customer=self.customer,
            created_by=self.user
        )

        # Create process
        self.process = Process.objects.create(
            name='Test Process',
            code='TEST'
        )

        # Create work order process
        self.work_order_process = WorkOrderProcess.objects.create(
            work_order=self.work_order,
            process=self.process,
            department=self.department
        )

        # Create tasks with different statuses
        for i in range(10):
            task = WorkOrderTask.objects.create(
                work_order_process=self.work_order_process,
                assigned_department=self.department,
                assigned_operator=self.user,
                status='pending',
                work_content=f'Test task {i}',
                production_quantity=100,
                quantity_completed=0,
                quantity_defective=0
            )

            # Complete 5 tasks
            if i < 5:
                task.status = 'completed'
                task.quantity_completed = 100
                task.quantity_defective = 5
                task.save()

                # Create completion log
                from workorder.models.core import TaskLog
                TaskLog.objects.create(
                    task=task,
                    log_type='complete',
                    content='Task completed',
                    operator=self.user
                )

    @override_settings(DEBUG=True)
    def test_collaboration_stats_query_count(self):
        """Test that collaboration_stats uses limited queries"""
        mixin = TaskStatsMixin()

        from django.test import RequestFactory
        factory = RequestFactory()
        request = factory.get('/api/workorder-tasks/collaboration_stats/')
        request.user = self.user

        # Reset query count
        reset_queries()

        # Execute
        response = mixin.collaboration_stats(request)

        # Check response
        self.assertEqual(response.status_code, 200)
        results = response.data['results']
        self.assertGreater(len(results), 0)

        # Check query count (should be < 10 for optimized version)
        query_count = len(connection.queries)
        self.assertLess(
            query_count,
            10,
            f"Too many queries: {query_count}. Expected <10 for optimized collaboration_stats. "
            f"Queries: {[q['sql'] for q in connection.queries]}"
        )

        # Verify data integrity
        operator_stats = results[0]
        self.assertIn('total_tasks', operator_stats)
        self.assertIn('completed_tasks', operator_stats)
        self.assertIn('total_completed_quantity', operator_stats)

    @override_settings(DEBUG=True)
    def test_department_workload_query_count(self):
        """Test that department_workload uses limited queries"""
        mixin = TaskStatsMixin()

        from django.test import RequestFactory
        factory = RequestFactory()
        request = factory.get(f'/api/workorder-tasks/department_workload/?department_id={self.department.id}')
        request.user = self.user

        # Reset query count
        reset_queries()

        # Execute
        response = mixin.department_workload(request)

        # Check response
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['department_id'], self.department.id)

        # Check query count (should be < 15 for optimized version)
        query_count = len(connection.queries)
        self.assertLess(
            query_count,
            15,
            f"Too many queries: {query_count}. Expected <15 for optimized department_workload. "
            f"Queries: {[q['sql'] for q in connection.queries]}"
        )

        # Verify data integrity
        summary = response.data['summary']
        self.assertIn('total_tasks', summary)
        self.assertIn('pending_tasks', summary)
        self.assertIn('completed_tasks', summary)
        self.assertIn('completion_rate', summary)

        # Verify priority distribution
        priority_dist = response.data['priority_distribution']
        self.assertIn('urgent', priority_dist)
        self.assertIn('high', priority_dist)
        self.assertIn('normal', priority_dist)
        self.assertIn('low', priority_dist)

    @override_settings(DEBUG=True)
    def test_task_list_queryset_optimization(self):
        """Test that task list queryset uses select_related properly"""
        from workorder.views.work_order_tasks.task_main import BaseWorkOrderTaskViewSet
        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.get('/api/workorder-tasks/')
        request.user = self.user

        viewset = BaseWorkOrderTaskViewSet()
        viewset.request = request
        viewset.format_kwarg = None

        # Get queryset
        queryset = viewset.get_queryset()

        # Check that queryset uses select_related
        # We can't directly inspect select_related, but we can check query count
        reset_queries()

        # Force evaluation
        list(queryset[:5])

        query_count = len(connection.queries)

        # Should be 1 query for the list (not 1+N)
        self.assertEqual(
            query_count,
            1,
            f"Expected 1 query for task list with select_related, got {query_count}. "
            f"Query: {[q['sql'] for q in connection.queries]}"
        )

    @override_settings(DEBUG=True)
    def test_no_nplus1_in_collaboration_stats(self):
        """Verify collaboration_stats doesn't have N+1 problem"""
        mixin = TaskStatsMixin()

        # Create additional users with tasks to increase data volume
        for i in range(5):
            user = User.objects.create_user(username=f'operator{i}', password='pass')
            user.profile.departments.add(self.department)

            # Create tasks for this user
            for j in range(3):
                WorkOrderTask.objects.create(
                    work_order_process=self.work_order_process,
                    assigned_department=self.department,
                    assigned_operator=user,
                    status='completed',
                    work_content=f'Task {j} for operator {i}',
                    production_quantity=50,
                    quantity_completed=50,
                    quantity_defective=2
                )

        from django.test import RequestFactory
        factory = RequestFactory()
        request = factory.get('/api/workorder-tasks/collaboration_stats/')
        request.user = self.user

        reset_queries()

        # Execute
        response = mixin.collaboration_stats(request)

        query_count = len(connection.queries)

        # With 6 operators, N+1 would be 50+ queries
        # Optimized should be <10 regardless of operator count
        self.assertLess(
            query_count,
            10,
            f"Query count scales with operators (N+1 problem): {query_count} queries for 6 operators. "
            f"Expected <10 for optimized version. "
            f"Queries: {[q['sql'] for q in connection.queries]}"
        )

        # Verify we got data for all operators
        self.assertGreaterEqual(len(response.data['results']), 6)
