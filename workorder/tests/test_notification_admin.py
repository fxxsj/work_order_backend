import pytest
from datetime import timedelta
from django.core.management import call_command
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from workorder.models import (
    Notification,
    NotificationTemplate,
    SystemNotificationSettings,
    UserProfile,
)
from workorder.tests.factories import UserFactory


@pytest.mark.django_db
def test_admin_session_requires_staff():
    client = APIClient()
    user = UserFactory(is_staff=False)
    client.force_authenticate(user=user)

    response = client.post("/api/v1/auth/admin-session/")

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_admin_session_allows_staff():
    client = APIClient()
    user = UserFactory(is_staff=True)
    client.force_authenticate(user=user)

    response = client.post("/api/v1/auth/admin-session/")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["data"]["admin_url"] == "/admin/"


@pytest.mark.django_db
def test_user_notification_settings_persist():
    client = APIClient()
    user = UserFactory(is_staff=True)
    client.force_authenticate(user=user)

    update_response = client.post(
        "/api/v1/user-notification-settings/update_settings/",
        {
            "email_notifications": False,
            "websocket_notifications": True,
            "task_assignments": False,
            "process_completions": True,
            "deadline_warnings": False,
            "system_announcements": True,
            "urgency_threshold": "high",
            "quiet_hours_enabled": True,
            "quiet_hours_start": "21:30",
            "quiet_hours_end": "07:30",
        },
        format="json",
    )

    assert update_response.status_code == status.HTTP_200_OK

    profile = UserProfile.objects.get(user=user)
    assert profile.notification_preferences["urgency_threshold"] == "high"
    assert profile.notification_preferences["quiet_hours_start"] == "21:30"

    get_response = client.get("/api/v1/user-notification-settings/get_settings/")
    assert get_response.status_code == status.HTTP_200_OK
    assert get_response.data["data"]["email_notifications"] is False
    assert get_response.data["data"]["quiet_hours_end"] == "07:30"


@pytest.mark.django_db
def test_notification_template_update_and_preview():
    client = APIClient()
    user = UserFactory(is_staff=True)
    client.force_authenticate(user=user)

    update_response = client.post(
        "/api/v1/notification-templates/update_template/",
        {
            "template_name": "task_assigned",
            "title": "任务: {task_name}",
            "message": "施工单 {workorder_number} 由 {assigned_by} 分派",
            "variables": ["task_name", "workorder_number", "assigned_by"],
            "is_active": True,
        },
        format="json",
    )

    assert update_response.status_code == status.HTTP_200_OK
    template = NotificationTemplate.objects.get(key="task_assigned")
    assert template.title == "任务: {task_name}"

    preview_response = client.post(
        "/api/v1/notification-templates/preview_template/",
        {
            "template_name": "task_assigned",
            "variables": {
                "task_name": "打样",
                "workorder_number": "WO-001",
                "assigned_by": "主管A",
            },
        },
        format="json",
    )

    assert preview_response.status_code == status.HTTP_200_OK
    assert preview_response.data["data"]["title"] == "任务: 打样"
    assert "WO-001" in preview_response.data["data"]["message"]


@pytest.mark.django_db
def test_notification_retention_policy_applies_limit():
    user = UserFactory(is_staff=True)
    settings = SystemNotificationSettings.get_solo()
    settings.max_notifications_per_user = 2
    settings.auto_cleanup_enabled = False
    settings.save()

    for index in range(4):
        Notification.objects.create(
            recipient=user,
            notification_type="system",
            title=f"title-{index}",
            content="content",
        )

    Notification.apply_retention_policy([user.id])

    titles = list(
        Notification.objects.filter(recipient=user)
        .order_by("-created_at")
        .values_list("title", flat=True)
    )
    assert len(titles) == 2
    assert titles == ["title-3", "title-2"]


@pytest.mark.django_db
def test_cleanup_notifications_command_applies_retention_policy(capsys):
    user = UserFactory(is_staff=True)
    settings = SystemNotificationSettings.get_solo()
    settings.max_notifications_per_user = 1
    settings.notification_retention_days = 1
    settings.auto_cleanup_enabled = True
    settings.save()

    stale = Notification.objects.create(
        recipient=user,
        notification_type="system",
        title="stale",
        content="content",
    )
    Notification.objects.filter(id=stale.id).update(created_at=timezone.now() - timedelta(days=5))
    Notification.objects.create(
        recipient=user,
        notification_type="system",
        title="keep-newest",
        content="content",
    )
    Notification.objects.create(
        recipient=user,
        notification_type="system",
        title="drop-overflow",
        content="content",
    )

    call_command("cleanup_notifications")
    captured = capsys.readouterr()

    remaining_titles = list(Notification.objects.order_by("-created_at").values_list("title", flat=True))
    assert remaining_titles == ["drop-overflow"]
    assert "通知清理完成" in captured.out


@pytest.mark.django_db
def test_create_notification_renders_template():
    user = UserFactory(is_staff=True)

    notification = Notification.create_notification(
        recipient=user,
        notification_type="task_assigned",
        title="fallback-title",
        content="fallback-content",
        template_key="task_assigned",
        template_variables={
            "task_name": "覆膜",
            "workorder_number": "WO-1001",
            "assigned_by": "主管A",
        },
    )

    assert notification.title == "新任务分配"
    assert notification.content == "您有新的任务: 覆膜"


@pytest.mark.django_db
def test_create_notification_preserves_system_announcement_title():
    user = UserFactory(is_staff=True)

    notification = Notification.create_notification(
        recipient=user,
        notification_type="system",
        title="今晚停机维护",
        content="23:00 开始维护",
        template_key="system_announcement",
        template_variables={
            "title": "今晚停机维护",
            "message": "23:00 开始维护",
        },
    )

    assert notification.title == "今晚停机维护"
    assert notification.content == "23:00 开始维护"


@pytest.mark.django_db
def test_system_notification_admin_publish_list_and_revoke():
    client = APIClient()
    admin = UserFactory(is_staff=True)
    user = UserFactory(is_staff=False)
    client.force_authenticate(user=admin)

    create_response = client.post(
        "/api/v1/system-notifications/create_announcement/",
        {
            "title": "系统维护",
            "content": "今晚 23:00 维护",
            "recipient_ids": [admin.id, user.id],
            "priority": "high",
            "expires_in_days": 1,
        },
        format="json",
    )

    assert create_response.status_code == status.HTTP_201_CREATED
    batch_id = create_response.data["data"]["batch_id"]
    assert Notification.objects.filter(data__batch_id=batch_id).count() == 2

    list_response = client.get("/api/v1/system-notifications/")
    assert list_response.status_code == status.HTTP_200_OK
    rows = list_response.data["data"]["results"]
    assert rows[0]["batch_id"] == batch_id
    assert rows[0]["recipient_count"] == 2
    assert rows[0]["priority"] == "high"

    revoke_response = client.delete(f"/api/v1/system-notifications/{batch_id}/revoke/")
    assert revoke_response.status_code == status.HTTP_200_OK
    assert revoke_response.data["data"]["count"] == 2
    assert Notification.objects.filter(data__batch_id=batch_id).count() == 0


@pytest.mark.django_db
def test_run_notification_maintenance_command(capsys):
    call_command("run_notification_maintenance")
    captured = capsys.readouterr()

    assert "通知维护完成" in captured.out
