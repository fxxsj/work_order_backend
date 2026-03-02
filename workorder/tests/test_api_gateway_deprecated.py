import pytest

from workorder.services import api_gateway


def test_workorder_api_service_deprecated():
    with pytest.raises(RuntimeError):
        api_gateway.WorkOrderAPIService.create_workorder({}, None)


def test_task_api_service_deprecated():
    with pytest.raises(RuntimeError):
        api_gateway.TaskAPIService.get_my_tasks(None)


def test_report_api_service_deprecated():
    with pytest.raises(RuntimeError):
        api_gateway.ReportAPIService.get_workorder_statistics()


def test_system_api_service_deprecated():
    with pytest.raises(RuntimeError):
        api_gateway.SystemAPIService.health_check()
