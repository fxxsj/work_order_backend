from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone

from workorder.models.core import ProcessLog
from workorder.services.notification_triggers import DeadlineWarningService
from workorder.tests.factories import (
    WorkOrderFactory,
    WorkOrderProcessFactory,
    WorkOrderTaskFactory,
    UserFactory,
)


@pytest.mark.django_db
def test_process_log_complete_triggers_notification():
    workorder_process = WorkOrderProcessFactory(tasks=0)

    with patch(
        "workorder.services.notification_triggers."
        "notification_service.notify_process_completion"
    ) as mocked:
        ProcessLog.objects.create(
            work_order_process=workorder_process,
            log_type="complete",
            content="done",
            operator=None,
        )

    mocked.assert_called_once_with(
        process=workorder_process.process,
        workorder=workorder_process.work_order,
        completed_by=None,
    )


@pytest.mark.django_db
def test_deadline_warning_uses_delivery_date():
    tomorrow = timezone.now().date() + timedelta(days=1)
    workorder = WorkOrderFactory(
        delivery_date=tomorrow, status="in_progress", processes=0
    )

    with patch(
        "workorder.services.notification_triggers."
        "notification_service.notify_deadline_warning"
    ) as mocked:
        DeadlineWarningService.check_deadline_warnings()

    mocked.assert_any_call(workorder, 1)


@pytest.mark.django_db
def test_overdue_tasks_use_planned_end_time():
    planned_end_time = timezone.now() - timedelta(days=1)
    workorder_process = WorkOrderProcessFactory(
        tasks=0, planned_end_time=planned_end_time
    )
    task = WorkOrderTaskFactory(
        work_order_process=workorder_process,
        status="pending",
        assigned_operator=UserFactory(),
    )

    with patch(
        "workorder.services.notification_triggers."
        "notification_service.send_notification"
    ) as mocked:
        DeadlineWarningService.check_overdue_tasks()

    assert mocked.call_count == 1
    _, kwargs = mocked.call_args
    assert kwargs["data"]["task_id"] == task.id
    assert kwargs["data"]["deadline"] == planned_end_time.isoformat()


@pytest.mark.django_db
def test_task_assignment_notification_only_fires_when_operator_changes():
    workorder_process = WorkOrderProcessFactory(tasks=0)
    first_operator = UserFactory()
    second_operator = UserFactory()

    with patch(
        "workorder.services.notification_triggers."
        "notification_service.notify_task_assigned"
    ) as mocked:
        task = WorkOrderTaskFactory(
            work_order_process=workorder_process,
            assigned_operator=first_operator,
        )
        task.quantity_completed = 10
        task.save(update_fields=["quantity_completed", "updated_at"])
        task.assigned_operator = second_operator
        task.save(update_fields=["assigned_operator", "updated_at"])

    assert mocked.call_count == 2
    assert mocked.call_args.kwargs["assigned_operator"] == second_operator
