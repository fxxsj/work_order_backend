"""Admin site presentation helpers."""

from types import MethodType


WORKORDER_ADMIN_GROUPS = [
    (
        "基础资料",
        {
            "Customer",
            "Department",
            "Process",
            "UserProfile",
        },
    ),
    (
        "产品与资产",
        {
            "Product",
            "ProductGroup",
            "ProductGroupItem",
            "ProductStockLog",
            "Artwork",
            "Die",
            "FoilingPlate",
            "EmbossingPlate",
        },
    ),
    (
        "销售与生产",
        {
            "SalesOrder",
            "SalesOrderItem",
            "WorkOrder",
            "WorkOrderProduct",
            "WorkOrderProcess",
            "WorkOrderMaterial",
            "WorkOrderTask",
            "ProcessLog",
            "TaskLog",
            "WorkOrderApprovalLog",
            "TaskAssignmentRule",
        },
    ),
    (
        "采购与库存",
        {
            "Material",
            "Supplier",
            "MaterialSupplier",
            "PurchaseOrder",
            "PurchaseOrderItem",
            "PurchaseReceiveRecord",
            "MaterialStockLog",
            "ProductStock",
            "StockIn",
            "StockOut",
            "DeliveryOrder",
            "DeliveryItem",
            "QualityInspection",
        },
    ),
    (
        "财务管理",
        {
            "CostCenter",
            "CostItem",
            "ProductionCost",
            "Invoice",
            "Payment",
            "PaymentPlan",
            "Statement",
        },
    ),
    (
        "系统与审计",
        {
            "Notification",
            "NotificationTemplate",
            "SystemNotificationSettings",
            "AuditLog",
            "AuditLogExport",
            "AuditLogSettings",
        },
    ),
]


def configure_admin_site(site):
    """Group workorder models on the admin index by business domain."""

    if getattr(site, "_workorder_grouping_enabled", False):
        return

    original_get_app_list = site.get_app_list

    def get_grouped_app_list(self, request, app_label=None):
        app_list = original_get_app_list(request, app_label)
        grouped_app_list = []

        for app in app_list:
            if app["app_label"] != "workorder":
                grouped_app_list.append(app)
                continue

            models_by_name = {
                model["object_name"]: model for model in app.get("models", [])
            }
            grouped_names = set()

            for group_name, model_names in WORKORDER_ADMIN_GROUPS:
                models = [
                    models_by_name[name]
                    for name in model_names
                    if name in models_by_name
                ]
                if not models:
                    continue

                grouped_names.update(model["object_name"] for model in models)
                grouped_app_list.append(
                    {
                        **app,
                        "name": group_name,
                        "app_label": f"workorder_{len(grouped_app_list)}",
                        "models": sorted(
                            models, key=lambda model: model["name"]
                        ),
                    }
                )

            remaining_models = [
                model
                for model in app.get("models", [])
                if model["object_name"] not in grouped_names
            ]
            if remaining_models:
                grouped_app_list.append(
                    {
                        **app,
                        "name": "其他",
                        "app_label": "workorder_other",
                        "models": sorted(
                            remaining_models, key=lambda model: model["name"]
                        ),
                    }
                )

        return grouped_app_list

    site.get_app_list = MethodType(get_grouped_app_list, site)
    site._workorder_grouping_enabled = True
