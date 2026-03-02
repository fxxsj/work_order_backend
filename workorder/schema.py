"""
OpenAPI schema helpers for standard API responses.
"""

from __future__ import annotations

from typing import Optional

from drf_spectacular.utils import inline_serializer
from drf_spectacular.openapi import AutoSchema
from rest_framework import serializers


def _data_field(data_serializer=None, many: bool = False):
    if data_serializer is None:
        return serializers.JSONField(required=False, allow_null=True)

    if isinstance(data_serializer, serializers.BaseSerializer):
        return data_serializer

    if isinstance(data_serializer, type) and issubclass(
        data_serializer, serializers.BaseSerializer
    ):
        return data_serializer(many=many)

    return serializers.JSONField(required=False, allow_null=True)


def standard_success_response(name: str, data_serializer=None, many: bool = False):
    return inline_serializer(
        name=name,
        fields={
            "success": serializers.BooleanField(),
            "code": serializers.IntegerField(),
            "message": serializers.CharField(),
            "data": _data_field(data_serializer, many=many),
            "timestamp": serializers.CharField(),
        },
    )


def standard_error_response(name: str, data_serializer=None):
    return inline_serializer(
        name=name,
        fields={
            "success": serializers.BooleanField(),
            "code": serializers.IntegerField(),
            "message": serializers.CharField(),
            "errors": serializers.JSONField(required=False),
            "data": _data_field(data_serializer),
            "timestamp": serializers.CharField(),
        },
    )


class TaggedAutoSchema(AutoSchema):
    """根据视图模块/名称为未显式声明的接口提供默认标签。"""

    CLASS_TAG_MAP = {
        "CustomerViewSet": "客户",
        "DepartmentViewSet": "部门",
        "ProcessViewSet": "工序",
    }

    MODULE_TAG_MAP = {
        "workorder.auth_views": "用户",
        "workorder.views.assets": "资产",
        "workorder.views.finance": "财务",
        "workorder.views.inventory": "库存",
        "workorder.views.materials": "物料",
        "workorder.views.products": "产品",
        "workorder.views.sales": "销售",
        "workorder.views.system": "系统",
        "workorder.views.notification": "通知",
        "workorder.views.monitoring": "统计",
        "workorder.views.multi_level_approval": "审核",
        "workorder.views.work_orders": "施工单",
        "workorder.views.work_order_processes": "工序",
        "workorder.views.work_order_tasks": "任务",
        "workorder.views.work_order_materials": "施工单",
        "workorder.views.work_order_products": "施工单",
        "workorder.views.process_logs": "工序",
    }

    def get_tags(self):
        view_class = self.view.__class__
        class_tag = self.CLASS_TAG_MAP.get(view_class.__name__)
        if class_tag:
            return [class_tag]

        module_name = view_class.__module__
        for module_prefix, tag in self.MODULE_TAG_MAP.items():
            if module_name.startswith(module_prefix):
                return [tag]

        return super().get_tags()
