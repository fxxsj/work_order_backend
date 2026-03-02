import pytest
from rest_framework.test import APIRequestFactory, force_authenticate

from workorder.response import APIResponse
from workorder.tests.factories import UserFactory
from workorder.views.work_order_tasks import WorkOrderTaskViewSet


@pytest.mark.django_db
def test_department_operators_requires_param():
    factory = APIRequestFactory()
    request = factory.get("/api/v1/workorder-tasks/department-operators/")
    force_authenticate(request, user=UserFactory())
    view = WorkOrderTaskViewSet.as_view({"get": "department_operators"})
    response = view(request)

    assert response.status_code == 400
    assert "请提供 department_id 参数" in response.data.get("message", "")


def test_apiresponse_error_normalizes_error_data():
    response = APIResponse.error("操作失败", data={"error": "操作失败"})

    assert response.data["success"] is False
    assert response.data["message"] == "操作失败"
    assert response.data["data"] is None
    assert response.data["errors"] == {}


def test_apiresponse_error_extracts_errors_and_keeps_context():
    response = APIResponse.error(
        "操作失败",
        data={"error": "操作失败", "errors": {"field": ["无效"]}, "context": {"id": 1}},
    )

    assert response.data["success"] is False
    assert response.data["message"] == "操作失败"
    assert response.data["errors"] == {"field": ["无效"]}
    assert response.data["data"] == {"context": {"id": 1}}


def test_apiresponse_success_unwraps_message_payload():
    response = APIResponse.success(data={"message": "保存成功", "data": {"id": 1}})

    assert response.data["success"] is True
    assert response.data["message"] == "保存成功"
    assert response.data["data"] == {"id": 1}
