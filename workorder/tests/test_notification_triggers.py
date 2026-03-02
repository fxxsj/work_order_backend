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
        "workorder.services.notification_triggers.notification_service.notify_process_completion"
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
    workorder = WorkOrderFactory(delivery_date=tomorrow, status="in_progress", processes=0)

    with patch(
        "workorder.services.notification_triggers.notification_service.notify_deadline_warning"
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
        "workorder.services.notification_triggers.notification_service.send_notification"
    ) as mocked:
        DeadlineWarningService.check_overdue_tasks()

    assert mocked.call_count == 1
    _, kwargs = mocked.call_args
    assert kwargs["data"]["task_id"] == task.id
    assert kwargs["data"]["deadline"] == planned_end_time.isoformat()
