"""
提取后的服务层回归测试

覆盖 inventory_service、asset_service、finance_service 中下沉到服务层的核心逻辑，
重点关注状态校验、异常转换、聚合计算等容易在视图瘦身时出错的点。
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from workorder.models.assets import Artwork, ArtworkProduct
from workorder.models.base import Customer, Process
from workorder.models.products import Product
from workorder.models.core import WorkOrder, WorkOrderProcess, WorkOrderTask
from workorder.models.finance import (
    Invoice,
    PaymentPlan,
    ProductionCost,
    Statement,
)
from workorder.models.sales import SalesOrder
from workorder.models.inventory import (
    ProductStock,
    QualityInspection,
    StockIn,
)
from workorder.models.system import (
    Notification,
    SystemNotificationSettings,
    UserProfile,
)
from workorder.services.asset_service import (
    ArtworkVersionService,
    AssetConfirmationService,
    AssetImageService,
)
from workorder.services.finance_service import (
    InvoiceService,
    PaymentPlanService,
    ProductionCostService,
    StatementService,
)
from workorder.services.inventory_service import (
    ProductStockService,
    QualityInspectionService,
    StockInService,
)
from workorder.services.monitoring import MonitoringStatsService
from workorder.services.notification_service import (
    NotificationService,
    NotificationTemplateService,
    SystemNotificationService,
    UserNotificationSettingsService,
)
from workorder.services.service_errors import ServiceError


@pytest.fixture
def finance_user(db):
    return User.objects.create_user(
        username="finance_user", password="test", is_staff=True
    )


@pytest.fixture
def test_customer(db):
    return Customer.objects.create(
        name="测试客户", contact_person="张", phone="138"
    )


@pytest.fixture
def test_product(db):
    return Product.objects.create(name="测试产品", code="TEST", unit="件")


@pytest.fixture
def test_work_order(db, test_customer, finance_user):
    return WorkOrder.objects.create(
        customer=test_customer,
        production_quantity=100,
        order_date=timezone.now().date(),
        delivery_date=timezone.now().date() + timedelta(days=1),
        created_by=finance_user,
        manager=finance_user,
    )


@pytest.fixture
def test_sales_order(db, test_customer, finance_user):
    return SalesOrder.objects.create(
        order_number="SO202601010001",
        customer=test_customer,
        order_date=timezone.now().date(),
        delivery_date=timezone.now().date() + timedelta(days=7),
        total_amount=Decimal("1000.00"),
        status="pending",
        payment_status="unpaid",
        created_by=finance_user,
    )


class TestProductStockService:
    """成品库存服务测试"""

    @pytest.fixture
    def stock(self, db, test_product, test_work_order):
        return ProductStock.objects.create(
            product=test_product,
            quantity=Decimal("100"),
            min_stock_level=Decimal("10"),
            batch_no="B001",
            work_order=test_work_order,
        )

    def test_adjust_add(self, stock):
        result = ProductStockService.adjust_stock(
            stock, "add", Decimal("10"), "补货"
        )
        assert result["new_quantity"] == float(Decimal("110"))
        assert "补货" in stock.notes

    def test_adjust_set(self, stock):
        result = ProductStockService.adjust_stock(
            stock, "set", Decimal("50"), "盘点"
        )
        assert result["new_quantity"] == float(Decimal("50"))

    def test_adjust_invalid_type(self, stock):
        with pytest.raises(ServiceError) as exc_info:
            ProductStockService.adjust_stock(
                stock, "multiply", Decimal("2"), "错误"
            )
        assert exc_info.value.code == 400


class TestQualityInspectionService:
    """质检服务测试"""

    @pytest.fixture
    def inspection(self, db, test_work_order, test_product):
        return QualityInspection.objects.create(
            inspection_number="ZJ202601010001",
            inspection_type="final",
            work_order=test_work_order,
            product=test_product,
            result="pending",
        )

    def test_complete_updates_result(self, inspection):
        QualityInspectionService.complete(
            inspection, result="passed", passed_quantity=90, failed_quantity=10
        )
        assert inspection.result == "passed"
        assert inspection.passed_quantity == 90
        assert inspection.failed_quantity == 10

    def test_complete_already_resulted_fails(self, inspection):
        inspection.result = "passed"
        inspection.save()
        with pytest.raises(ServiceError) as exc_info:
            QualityInspectionService.complete(inspection, result="failed")
        assert exc_info.value.code == 400


class TestStockInService:
    """入库单服务测试"""

    @pytest.fixture
    def stock_in(self, db, test_work_order, finance_user):
        return StockIn.objects.create(
            order_number="RK202601010001",
            work_order=test_work_order,
            stock_in_date=timezone.now().date(),
            status="draft",
            operator=finance_user,
        )

    def test_submit_changes_status(self, stock_in, finance_user):
        StockInService.submit(stock_in, finance_user)
        assert stock_in.status == "submitted"
        assert stock_in.submitted_by == finance_user

    def test_submit_non_draft_fails(self, stock_in, finance_user):
        stock_in.status = "submitted"
        stock_in.save()
        with pytest.raises(ServiceError) as exc_info:
            StockInService.submit(stock_in, finance_user)
        assert exc_info.value.code == 400


class TestAssetConfirmationService:
    """资产确认服务测试"""

    @pytest.fixture
    def artwork(self, db):
        return Artwork.objects.create(name="测试图稿", base_code="ARTTEST001")

    @pytest.fixture
    def plate_making_task(self, db, artwork, test_work_order):
        process = Process.objects.create(name="制版", code="PLATE")
        wop = WorkOrderProcess.objects.create(
            work_order=test_work_order,
            process=process,
            sequence=10,
            status="in_progress",
        )
        return WorkOrderTask.objects.create(
            work_order_process=wop,
            task_type="plate_making",
            work_content="制版",
            production_quantity=1,
            artwork=artwork,
        )

    def test_confirm_requires_fk_field(self, artwork, finance_user):
        with pytest.raises(ServiceError) as exc_info:
            AssetConfirmationService.confirm(artwork, "", finance_user)
        assert exc_info.value.code == 500

    def test_confirm_already_confirmed_fails(self, artwork, finance_user):
        artwork.confirmed = True
        artwork.save()
        with pytest.raises(ServiceError) as exc_info:
            AssetConfirmationService.confirm(artwork, "artwork", finance_user)
        assert exc_info.value.code == 400

    def test_confirm_completes_plate_making_task(
        self, artwork, plate_making_task, finance_user
    ):
        AssetConfirmationService.confirm(artwork, "artwork", finance_user)
        assert artwork.confirmed
        plate_making_task.refresh_from_db()
        assert plate_making_task.status == "completed"
        assert plate_making_task.quantity_completed == 1


class TestAssetImageService:
    """资产图片服务测试"""

    @pytest.fixture
    def artwork(self, db):
        return Artwork.objects.create(name="测试图稿")

    def test_create_image_invalid_extension(self, artwork):
        bad_file = SimpleUploadedFile(
            "test.txt", b"x", content_type="text/plain"
        )
        with pytest.raises(ServiceError) as exc_info:
            AssetImageService.create_image(
                ArtworkProduct, "artwork", artwork, bad_file
            )
        assert exc_info.value.code == 400

    def test_delete_image_not_found(self, db):
        with pytest.raises(ServiceError) as exc_info:
            AssetImageService.delete_image(ArtworkProduct, "artwork", 1, 9999)
        assert exc_info.value.code == 404


class TestArtworkVersionService:
    """图稿版本服务测试"""

    @pytest.fixture
    def original(self, db, test_product):
        artwork = Artwork.objects.create(
            name="原始图稿", base_code="ARTVER001", version=1
        )
        ArtworkProduct.objects.create(
            artwork=artwork, product=test_product, imposition_quantity=4
        )
        return artwork

    def test_create_version_increments_and_copies_products(
        self, original, test_product
    ):
        new_artwork = ArtworkVersionService.create_version(original)
        assert new_artwork.base_code == original.base_code
        assert new_artwork.version == 2
        assert new_artwork.products.count() == 1
        assert new_artwork.products.first().product == test_product


class TestInvoiceService:
    """发票服务测试"""

    @pytest.fixture
    def invoice(self, db, test_customer, finance_user):
        return Invoice.objects.create(
            invoice_number="FP202601010001",
            customer=test_customer,
            amount=Decimal("100"),
            tax_amount=Decimal("13"),
            total_amount=Decimal("113"),
            approval_status="draft",
            status="draft",
            created_by=finance_user,
        )

    def test_submit_invalid_status(self, invoice, finance_user):
        invoice.approval_status = "approved"
        invoice.save()
        with pytest.raises(ServiceError) as exc_info:
            InvoiceService.submit(invoice, finance_user)
        assert exc_info.value.code == 400

    def test_approve_invalid_status(self, invoice, finance_user):
        invoice.approval_status = "draft"
        invoice.save()
        with pytest.raises(ServiceError) as exc_info:
            InvoiceService.approve(invoice, finance_user)
        assert exc_info.value.code == 400

    @patch("workorder.services.finance_service.ApprovalService")
    def test_submit_calls_approval_service(
        self, mock_service_cls, invoice, finance_user
    ):
        mock_service = MagicMock()
        mock_service.submit_for_approval.return_value = invoice
        mock_service_cls.return_value = mock_service
        InvoiceService.submit(invoice, finance_user)
        mock_service.submit_for_approval.assert_called_once()


class TestProductionCostService:
    """生产成本服务测试"""

    def test_calculate_material_wraps_exception(self, db, test_work_order):
        cost = ProductionCost.objects.create(
            work_order=test_work_order, period="202601"
        )
        with patch.object(
            cost,
            "auto_calculate_material_cost",
            side_effect=ValueError("boom"),
        ):
            with pytest.raises(ServiceError) as exc_info:
                ProductionCostService.calculate_material(cost)
            assert "boom" in str(exc_info.value.message)
            assert exc_info.value.code == 400


class TestStatementService:
    """对账单服务测试"""

    @pytest.fixture
    def statement(self, db, test_customer):
        return Statement.objects.create(
            statement_number="ST202601010001",
            statement_type="customer",
            customer=test_customer,
            status="draft",
            period="2026-01",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
        )

    def test_generate_requires_period(self):
        with pytest.raises(ServiceError) as exc_info:
            StatementService.generate(customer_id=1, period=None)
        assert exc_info.value.code == 400

    def test_generate_requires_customer_or_supplier(self):
        with pytest.raises(ServiceError) as exc_info:
            StatementService.generate(period="2026-01")
        assert exc_info.value.code == 400

    def test_generate_invalid_period_format(self):
        with pytest.raises(ServiceError) as exc_info:
            StatementService.generate(customer_id=1, period="not-valid")
        assert exc_info.value.code == 400

    def test_confirm_invalid_status(self, statement, finance_user):
        statement.status = "confirmed"
        statement.save()
        with pytest.raises(ServiceError) as exc_info:
            StatementService.confirm(statement, finance_user)
        assert exc_info.value.code == 400


class TestPaymentPlanService:
    """收款计划服务测试"""

    def test_summary_structure(self, db, test_sales_order):
        PaymentPlan.objects.create(
            sales_order=test_sales_order,
            plan_amount=Decimal("100"),
            paid_amount=Decimal("0"),
            plan_date=date.today(),
            status="pending",
        )
        data = PaymentPlanService.get_summary(PaymentPlan.objects.all())
        assert "summary" in data
        assert "by_status" in data
        assert data["summary"]["total_count"] == 1


class TestNotificationService:
    """用户通知服务测试"""

    @pytest.fixture
    def notification(self, db, finance_user):
        return Notification.objects.create(
            recipient=finance_user,
            notification_type="workorder_created",
            title="测试通知",
            content="内容",
            priority="normal",
        )

    def test_mark_read_sets_read_at(self, notification):
        NotificationService.mark_read(notification)
        notification.refresh_from_db()
        assert notification.is_read
        assert notification.read_at is not None

    def test_mark_all_read_returns_count(self, db, finance_user, notification):
        Notification.objects.create(
            recipient=finance_user,
            notification_type="task_assigned",
            title="未读",
            content="内容",
            priority="high",
        )
        count = NotificationService.mark_all_read(
            Notification.objects.filter(recipient=finance_user)
        )
        assert count == 2

    def test_delete_all_read(self, db, finance_user, notification):
        notification.is_read = True
        notification.save()
        count = NotificationService.delete_all_read(
            Notification.objects.filter(recipient=finance_user)
        )
        assert count == 1

    def test_unread_count(self, notification):
        assert (
            NotificationService.unread_count(
                Notification.objects.filter(recipient=notification.recipient)
            )
            == 1
        )

    def test_statistics(self, db, finance_user, notification):
        Notification.objects.create(
            recipient=finance_user,
            notification_type="system",
            title="紧急",
            content="内容",
            priority="urgent",
            is_read=True,
        )
        stats = NotificationService.statistics(
            Notification.objects.filter(recipient=finance_user)
        )
        assert stats["total_count"] == 2
        assert stats["unread_count"] == 1
        assert stats["urgent_count"] == 1

    def test_ws_ticket(self, finance_user):
        data = NotificationService.ws_ticket(finance_user.id)
        assert "ticket" in data
        assert data["expires_in"] == 60


class TestSystemNotificationService:
    """系统通知服务测试"""

    def test_create_announcement_valid(self, db, finance_user):
        result = SystemNotificationService.create_announcement(
            title="公告",
            content="内容",
            recipient_ids=[finance_user.id],
            priority="normal",
        )
        assert result["count"] == 1
        assert result["batch_id"]

    def test_create_announcement_missing_title(self):
        with pytest.raises(ServiceError) as exc_info:
            SystemNotificationService.create_announcement(
                title="", content="内容"
            )
        assert exc_info.value.code == 400

    def test_create_announcement_invalid_priority(self):
        with pytest.raises(ServiceError) as exc_info:
            SystemNotificationService.create_announcement(
                title="公告", content="内容", priority="invalid"
            )
        assert exc_info.value.code == 400

    def test_send_urgent_alert(self, db, finance_user):
        result = SystemNotificationService.send_urgent_alert(
            title="警报",
            content="内容",
            recipient_ids=[finance_user.id],
        )
        assert result["count"] == 1
        assert Notification.objects.filter(data__kind="urgent_alert").exists()

    def test_revoke(self, db, finance_user):
        result = SystemNotificationService.create_announcement(
            title="公告",
            content="内容",
            recipient_ids=[finance_user.id],
        )
        deleted = SystemNotificationService.revoke(result["batch_id"])
        assert deleted == 1
        assert (
            Notification.objects.filter(
                data__batch_id=result["batch_id"]
            ).count()
            == 0
        )

    def test_revoke_not_found(self, db):
        with pytest.raises(ServiceError) as exc_info:
            SystemNotificationService.revoke("non-existent-batch")
        assert exc_info.value.code == 404

    def test_update_settings_valid(self, db):
        _ = SystemNotificationSettings.get_solo()
        data = SystemNotificationService.update_settings(
            {
                "email_threshold": "urgent",
                "notification_retention_days": 60,
                "max_notifications_per_user": 2000,
            }
        )
        assert data["email_threshold"] == "urgent"
        assert data["notification_retention_days"] == 60

    def test_update_settings_invalid_threshold(self, db):
        with pytest.raises(ServiceError) as exc_info:
            SystemNotificationService.update_settings(
                {"email_threshold": "invalid"}
            )
        assert exc_info.value.code == 400

    def test_update_settings_non_int(self, db):
        with pytest.raises(ServiceError) as exc_info:
            SystemNotificationService.update_settings(
                {"notification_retention_days": "abc"}
            )
        assert exc_info.value.code == 400

    def test_update_settings_negative(self, db):
        with pytest.raises(ServiceError) as exc_info:
            SystemNotificationService.update_settings(
                {"notification_retention_days": -1}
            )
        assert exc_info.value.code == 400


class TestUserNotificationSettingsService:
    """用户通知偏好设置服务测试"""

    def test_get_settings_creates_profile(self, db, finance_user):
        assert not UserProfile.objects.filter(user=finance_user).exists()
        data = UserNotificationSettingsService.get_settings(finance_user)
        assert data["user_id"] == finance_user.id
        assert UserProfile.objects.filter(user=finance_user).exists()

    def test_update_settings_valid(self, db, finance_user):
        data = UserNotificationSettingsService.update_settings(
            finance_user,
            {"urgency_threshold": "high", "quiet_hours_start": "21:00"},
        )
        assert data["urgency_threshold"] == "high"
        assert data["quiet_hours_start"] == "21:00"

    def test_update_settings_invalid_threshold(self, db, finance_user):
        with pytest.raises(ServiceError) as exc_info:
            UserNotificationSettingsService.update_settings(
                finance_user, {"urgency_threshold": "xxx"}
            )
        assert exc_info.value.code == 400

    def test_update_settings_invalid_time(self, db, finance_user):
        with pytest.raises(ServiceError) as exc_info:
            UserNotificationSettingsService.update_settings(
                finance_user, {"quiet_hours_start": "25:00"}
            )
        assert exc_info.value.code == 400

    def test_get_notification_preferences(self):
        data = UserNotificationSettingsService.get_notification_preferences()
        assert "task_assigned" in data
        assert data["task_assigned"]["enabled"]


class TestNotificationTemplateService:
    """通知模板服务测试"""

    def test_get_templates_seeds_defaults(self, db):
        data = NotificationTemplateService.get_templates()
        assert "workorder_created" in data

    def test_update_template_valid(self, db):
        result = NotificationTemplateService.update_template(
            template_name="workorder_created",
            title="新标题",
            message="新消息 {workorder_number}",
            variables=["workorder_number"],
            is_active=True,
        )
        assert result["title"] == "新标题"

    def test_update_template_missing_name(self):
        with pytest.raises(ServiceError) as exc_info:
            NotificationTemplateService.update_template(template_name="")
        assert exc_info.value.code == 400

    def test_update_template_not_found(self, db):
        with pytest.raises(ServiceError) as exc_info:
            NotificationTemplateService.update_template(
                template_name="not_exists"
            )
        assert exc_info.value.code == 404

    def test_update_template_invalid_variables(self, db):
        with pytest.raises(ServiceError) as exc_info:
            NotificationTemplateService.update_template(
                template_name="workorder_created", variables="not-list"
            )
        assert exc_info.value.code == 400

    def test_preview_template(self, db):
        result = NotificationTemplateService.preview_template(
            "workorder_created", {"workorder_number": "WO001"}
        )
        assert "WO001" in result["message"]

    def test_preview_template_not_found(self, db):
        with pytest.raises(ServiceError) as exc_info:
            NotificationTemplateService.preview_template("not_exists", {})
        assert exc_info.value.code == 404


class TestMonitoringStatsService:
    """监控统计服务测试"""

    def test_execution_time_stats_aggregates_and_sorts(self):
        execution_times = [
            {"name": "api/a", "execution_time": 0.1},
            {"name": "api/a", "execution_time": 0.3},
            {"name": "api/b", "execution_time": 0.5},
        ]
        result = MonitoringStatsService.get_execution_time_stats(
            execution_times
        )
        assert len(result) == 2
        assert result[0]["endpoint"] == "api/b"
        assert result[0]["avg_time"] == 0.5
        assert result[1]["count"] == 2
        assert result[1]["avg_time"] == 0.2

    def test_get_alert_settings_structure(self):
        data = MonitoringStatsService.get_alert_settings()
        assert "performance_alerts" in data
        assert "business_alerts" in data
        assert "notification_channels" in data
        assert "email" in data["notification_channels"]

    def test_get_alerts(self, monkeypatch):
        monkeypatch.setattr(
            "workorder.services.monitoring."
            "monitoring_service.performance_monitor.get_performance_stats",
            lambda: {"error_rate": 10.0},
        )
        monkeypatch.setattr(
            "workorder.services.monitoring.BusinessMetrics.get_system_metrics",
            staticmethod(
                lambda: {
                    "system_resources": {
                        "cpu_percent": 85.0,
                        "memory_percent": 90.0,
                    }
                }
            ),
        )
        monkeypatch.setattr(
            "workorder.services.monitoring."
            "BusinessMetrics.get_workorder_metrics",
            staticmethod(
                lambda _time_range: {"time_metrics": {"orders_overdue": 10}}
            ),
        )

        alerts = MonitoringStatsService.get_alerts()
        types = {alert["type"] for alert in alerts}
        assert "performance" in types
        assert "resource" in types
        assert "business" in types

    def test_get_productivity_trends(self, db):
        trends = MonitoringStatsService.get_productivity_trends(days=7)
        assert len(trends) == 7
        assert "date" in trends[0]

    def test_get_quality_metrics(self, db, test_work_order):
        process = Process.objects.create(name="质检工序", code="QC")
        wop = WorkOrderProcess.objects.create(
            work_order=test_work_order, process=process, sequence=10
        )
        WorkOrderTask.objects.create(
            work_order_process=wop,
            task_type="quality_check",
            work_content="质检",
            production_quantity=100,
            quantity_completed=90,
            quantity_defective=5,
        )
        data = MonitoringStatsService.get_quality_metrics(days=30)
        assert "defect_stats" in data
        assert data["defect_stats"]["total_defects"] == 5
        assert 0 <= data["quality_score"] <= 100

    def test_get_operations_dashboard(self, db):
        data = MonitoringStatsService.get_operations_dashboard()
        assert "unassigned_tasks" in data
        assert "pending_procurement" in data
        assert "finance" in data
        assert "inventory_consistency" in data
        assert "generated_at" in data

    def test_get_resource_usage_structure(self):
        data = MonitoringStatsService.get_resource_usage()
        assert "cpu" in data
        assert "memory" in data
        assert "disk" in data
        assert "timestamp" in data

    def test_get_user_performance(self, db, finance_user, test_work_order):
        process = Process.objects.create(name="绩效工序", code="PERF")
        wop = WorkOrderProcess.objects.create(
            work_order=test_work_order, process=process, sequence=10
        )
        WorkOrderTask.objects.create(
            work_order_process=wop,
            task_type="production",
            work_content="生产",
            production_quantity=10,
            status="completed",
            assigned_operator=finance_user,
        )
        result = MonitoringStatsService.get_user_performance(days=30)
        assert any(
            item.get("assigned_operator__username") == "finance_user"
            for item in result
        )
