import pytest

from workorder.models.audit import AuditLog, AuditLogSettings
from workorder.tests.conftest import TestDataFactory


@pytest.mark.django_db
def test_audit_log_records_update_changes():
    settings = AuditLogSettings.get_settings()
    settings.enabled = True
    settings.audited_models = ['workorder.customer']
    settings.excluded_fields = []
    settings.save()

    AuditLog.objects.all().delete()

    customer = TestDataFactory.create_customer(name='客户A')

    # 清理创建日志，只验证更新日志
    AuditLog.objects.all().delete()

    customer.name = '客户B'
    customer.save()

    log = AuditLog.objects.filter(
        action_type=AuditLog.ACTION_UPDATE,
        object_id=str(customer.pk),
    ).latest('created_at')

    assert 'name' in log.changed_fields
    assert log.changes['old']['name'] == '客户A'
    assert log.changes['new']['name'] == '客户B'
