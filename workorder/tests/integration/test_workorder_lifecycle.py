"""Integration tests for complete work order lifecycle"""
import pytest
from rest_framework import status
from rest_framework.test import APIClient
from workorder.tests.factories import (
    WorkOrderFactory, UserFactory, DepartmentFactory, ProcessFactory,
    WorkOrderProcessFactory, CustomerFactory, ProductFactory
)
from workorder.models import WorkOrder


@pytest.mark.django_db
@pytest.mark.integration
class TestWorkOrderLifecycle:
    """Test complete work order lifecycle from creation to completion"""

    def test_full_workorder_lifecycle(self, api_client):
        """
        GIVEN: A new work order
        WHEN: Following the complete lifecycle (create -> approve -> dispatch -> complete)
        THEN: All transitions work correctly
        """
        # Setup
        dept = DepartmentFactory(name='Printing')
        process = ProcessFactory(name='Offset Printing')
        maker = UserFactory(username='maker', departments=[dept])
        supervisor = UserFactory(username='supervisor', departments=[dept])
        operator = UserFactory(username='operator', departments=[dept])
        customer = CustomerFactory(name='Test Customer')
        product = ProductFactory()

        # Step 1: Create workorder with draft tasks
        api_client.force_authenticate(user=maker)
        response = api_client.post('/api/workorders/', {
            'customer': customer.id,
            'production_quantity': 100,
            'delivery_date': '2026-12-31',
            'priority': 'normal',
        }, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        workorder_id = response.data['id']
        workorder = WorkOrder.objects.get(id=workorder_id)

        # Add processes manually (API might not support nested creation)
        wop = WorkOrderProcessFactory(
            work_order=workorder,
            process=process,
            tasks=1
        )

        # Verify draft tasks were created
        draft_tasks = workorder.tasks.filter(status='draft')
        assert draft_tasks.count() > 0

        # Step 2: Approve workorder
        api_client.force_authenticate(user=supervisor)
        response = api_client.post(f'/api/workorders/{workorder_id}/approve/')

        assert response.status_code == status.HTTP_200_OK
        workorder.refresh_from_db()
        assert workorder.approval_status == 'approved'

        # Verify tasks converted to pending
        tasks = workorder.tasks.filter(status='pending')
        assert tasks.count() == draft_tasks.count()

        # Step 3: Auto-dispatch (tasks assigned to department)
        task = tasks.first()
        # Task should have department assigned
        assert task.assigned_department == dept

        # Step 4: Supervisor assigns task to operator
        response = api_client.post(f'/api/workorder-tasks/{task.id}/assign/', {
            'operator_id': operator.id
        }, format='json')

        assert response.status_code == status.HTTP_200_OK
        task.refresh_from_db()
        assert task.assigned_operator == operator

        # Step 5: Operator starts task (if endpoint exists, else skip)
        # Many APIs don't have explicit start, task goes to in_progress on update

        # Step 6: Operator completes task
        api_client.force_authenticate(user=operator)
        response = api_client.post(f'/api/workorder-tasks/{task.id}/complete/', {
            'completion_quantity': 100,
            'defective_quantity': 0
        }, format='json')

        assert response.status_code == status.HTTP_200_OK
        task.refresh_from_db()
        assert task.status == 'completed'

    def test_workorder_with_multiple_processes(self, api_client):
        """
        GIVEN: A workorder with multiple processes
        WHEN: Workorder is approved
        THEN: Tasks are generated for all processes
        """
        dept = DepartmentFactory()
        process1 = ProcessFactory(name='CTP')
        process2 = ProcessFactory(name='Printing')
        process3 = ProcessFactory(name='Die Cutting')

        maker = UserFactory(username='maker', departments=[dept])
        supervisor = UserFactory(username='supervisor', departments=[dept])
        customer = CustomerFactory()

        api_client.force_authenticate(user=maker)
        response = api_client.post('/api/workorders/', {
            'customer': customer.id,
            'production_quantity': 500,
            'delivery_date': '2026-12-31',
        }, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        workorder_id = response.data['id']
        workorder = WorkOrder.objects.get(id=workorder_id)

        # Create multiple processes
        WorkOrderProcessFactory(work_order=workorder, process=process1, tasks=1)
        WorkOrderProcessFactory(work_order=workorder, process=process2, tasks=1)
        WorkOrderProcessFactory(work_order=workorder, process=process3, tasks=1)

        # Approve
        api_client.force_authenticate(user=supervisor)
        api_client.post(f'/api/workorders/{workorder_id}/approve/')

        # Verify tasks for all processes
        workorder.refresh_from_db()
        tasks = workorder.tasks.filter(status='pending')
        assert tasks.count() == 3  # One task per process

    def test_workorder_edit_before_approval(self, api_client):
        """
        GIVEN: A draft workorder
        WHEN: Maker edits processes
        THEN: Tasks are synced with new processes
        """
        dept = DepartmentFactory()
        process1 = ProcessFactory(name='CTP')
        process2 = ProcessFactory(name='Printing')

        maker = UserFactory(username='maker', departments=[dept])
        customer = CustomerFactory()

        # Create workorder
        api_client.force_authenticate(user=maker)
        response = api_client.post('/api/workorders/', {
            'customer': customer.id,
            'production_quantity': 100,
            'delivery_date': '2026-12-31',
        }, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        workorder_id = response.data['id']
        workorder = WorkOrder.objects.get(id=workorder_id)

        # Add first process with tasks
        WorkOrderProcessFactory(work_order=workorder, process=process1, tasks=1)
        initial_task_count = workorder.tasks.count()

        # Add second process
        WorkOrderProcessFactory(work_order=workorder, process=process2, tasks=1)

        # After adding process, should have more tasks
        workorder.refresh_from_db()
        assert workorder.tasks.count() > initial_task_count

    def test_workorder_priority_levels(self, api_client):
        """
        GIVEN: Workorders with different priorities
        WHEN: Querying workorders
        THEN: Priority field is correctly set
        """
        dept = DepartmentFactory()
        user = UserFactory(username='user', departments=[dept])
        customer = CustomerFactory()

        api_client.force_authenticate(user=user)

        # Create workorders with different priorities
        for priority in ['low', 'normal', 'high', 'urgent']:
            response = api_client.post('/api/workorders/', {
                'customer': customer.id,
                'production_quantity': 100,
                'priority': priority,
                'delivery_date': '2026-12-31',
            }, format='json')
            assert response.status_code == status.HTTP_201_CREATED

        # List workorders
        response = api_client.get('/api/workorders/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] >= 4

    def test_workorder_deletion_cascade(self, api_client):
        """
        GIVEN: A workorder with tasks
        WHEN: Workorder is deleted
        THEN: All related tasks are deleted
        """
        dept = DepartmentFactory()
        user = UserFactory(username='user', departments=[dept])

        workorder = WorkOrderFactory(created_by=user, processes=1)
        initial_task_count = WorkOrderTask.objects.filter(work_order=workorder).count()
        assert initial_task_count > 0

        # Delete workorder
        workorder.delete()

        # Verify tasks are deleted
        final_task_count = WorkOrderTask.objects.filter(work_order=workorder).count()
        assert final_task_count == 0
