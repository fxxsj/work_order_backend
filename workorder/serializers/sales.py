"""
销售订单序列化器模块

包含销售订单和销售订单明细的序列化器。
"""

from typing import List

from rest_framework import serializers

from ..models.sales import SalesOrder, SalesOrderItem


class SalesOrderItemSerializer(serializers.ModelSerializer):
    """销售订单明细序列化器"""

    product_name = serializers.CharField(source="product.name", read_only=True)
    product_code = serializers.CharField(source="product.code", read_only=True)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = SalesOrderItem
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at", "subtotal", "sales_order"]
        extra_kwargs = {
            "sales_order": {"required": False},
            "delivered_quantity": {"required": False},
        }

    def update(self, instance, validated_data):
        """禁止在更新时修改关联销售订单"""
        validated_data.pop("sales_order", None)
        return super().update(instance, validated_data)


class SalesOrderListSerializer(serializers.ModelSerializer):
    """销售订单列表序列化器"""

    customer_name = serializers.CharField(source="customer.name", read_only=True)
    customer_code = serializers.CharField(source="customer.code", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    payment_status_display = serializers.CharField(
        source="get_payment_status_display", read_only=True
    )
    submitted_by_name = serializers.CharField(
        source="submitted_by.username", read_only=True, allow_null=True
    )
    approved_by_name = serializers.CharField(
        source="approved_by.username", read_only=True, allow_null=True
    )
    items_count = serializers.SerializerMethodField()
    work_order_count = serializers.SerializerMethodField()

    class Meta:
        model = SalesOrder
        fields = "__all__"

    def get_items_count(self, obj) -> int:
        """获取订单明细数量"""
        return obj.items.count()

    def get_work_order_count(self, obj) -> int:
        """获取关联施工单数量"""
        return obj.get_related_work_orders_queryset().count()


class SalesOrderDetailSerializer(serializers.ModelSerializer):
    """销售订单详情序列化器"""

    customer_name = serializers.CharField(source="customer.name", read_only=True)
    customer_contact = serializers.CharField(
        source="customer.contact_person", read_only=True
    )
    customer_phone = serializers.CharField(source="customer.phone", read_only=True)
    customer_address = serializers.CharField(source="customer.address", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    payment_status_display = serializers.CharField(
        source="get_payment_status_display", read_only=True
    )
    submitted_by_name = serializers.CharField(
        source="submitted_by.username", read_only=True, allow_null=True
    )
    approved_by_name = serializers.CharField(
        source="approved_by.username", read_only=True, allow_null=True
    )
    items = SalesOrderItemSerializer(many=True, required=False)
    work_order_numbers = serializers.SerializerMethodField()
    delivery_order_numbers = serializers.SerializerMethodField()
    invoice_numbers = serializers.SerializerMethodField()
    work_order_summaries = serializers.SerializerMethodField()
    delivery_order_summaries = serializers.SerializerMethodField()
    invoice_summaries = serializers.SerializerMethodField()
    payment_count = serializers.SerializerMethodField()
    pending_payment_plan_count = serializers.SerializerMethodField()
    pending_payment_plan_amount = serializers.SerializerMethodField()
    unpaid_amount = serializers.SerializerMethodField()

    class Meta:
        model = SalesOrder
        fields = "__all__"
        # 以下字段在任意模式下均只读（系统自动管理）
        always_read_only_fields = [
            "order_number",
            "status",
            "payment_status",
            "subtotal",
            "tax_amount",
            "total_amount",
            "actual_delivery_date",
            "submitted_by",
            "submitted_at",
            "approved_by",
            "approved_at",
            "approval_comment",
            "rejection_reason",
            "completion_reason",
            "created_by",
            "created_at",
            "updated_at",
        ]

    def get_extra_kwargs(self):
        """动态控制字段只读：创建时放开大部分字段，编辑时全部锁定"""
        extra_kwargs = super().get_extra_kwargs()
        # 始终只读的字段
        always_read_only = getattr(self.Meta, "always_read_only_fields", [])
        if always_read_only:
            extra_kwargs["read_only_fields"] = list(always_read_only)
        return extra_kwargs

    def get_work_order_numbers(self, obj) -> List[str]:
        """获取关联的施工单号列表"""
        return [
            work_order.order_number
            for work_order in obj.get_related_work_orders()
            if work_order.order_number
        ]

    def get_delivery_order_numbers(self, obj) -> List[str]:
        """获取关联的发货单号列表"""
        return [
            delivery.order_number
            for delivery in obj.delivery_orders.all()
            if delivery.order_number
        ]

    def get_invoice_numbers(self, obj) -> List[str]:
        """获取关联的发票号列表"""
        return [
            invoice.invoice_number
            for invoice in obj.invoices.all()
            if invoice.invoice_number
        ]

    def get_work_order_summaries(self, obj) -> List[dict]:
        """获取关联施工单摘要"""
        return [
            {
                "id": work_order.id,
                "number": work_order.order_number,
                "status_display": work_order.get_status_display(),
                "source_label": "生产执行",
                "batch_no": None,
            }
            for work_order in obj.get_related_work_orders()
            if work_order.order_number
        ]

    def get_delivery_order_summaries(self, obj) -> List[dict]:
        """获取关联发货单摘要"""
        return [
            {
                "id": delivery.id,
                "number": delivery.order_number,
                "status_display": delivery.get_status_display(),
                "source_label": "发货交付",
                "batch_no": None,
            }
            for delivery in obj.delivery_orders.all()
            if delivery.order_number
        ]

    def get_invoice_summaries(self, obj) -> List[dict]:
        """获取关联发票摘要"""
        return [
            {
                "id": invoice.id,
                "number": invoice.invoice_number,
                "status_display": invoice.get_status_display(),
                "source_label": "财务开票",
                "batch_no": None,
            }
            for invoice in obj.invoices.all()
            if invoice.invoice_number
        ]

    def get_payment_count(self, obj) -> int:
        """获取收款记录数量"""
        return obj.payments.count()

    def get_pending_payment_plan_count(self, obj) -> int:
        """获取待收款计划数量"""
        return obj.payment_plans.exclude(status="completed").count()

    def get_pending_payment_plan_amount(self, obj) -> float:
        """获取待收款计划金额"""
        pending_amount = 0
        for plan in obj.payment_plans.exclude(status="completed").all():
            pending_amount += max(float(plan.plan_amount - plan.paid_amount), 0)
        return pending_amount

    def get_unpaid_amount(self, obj) -> float:
        """获取未回款金额"""
        return max(float(obj.total_amount - obj.paid_amount), 0)

    def validate_delivery_date(self, value):
        """验证交货日期

        新建订单时：交货日期不能早于今天
        编辑订单时：允许保留历史交货日期
        """
        from django.utils import timezone

        # 编辑模式时，如果日期未改变，允许保留原值
        if self.instance and self.instance.delivery_date == value:
            return value
        # 新建或修改日期时，验证不能早于今天
        if value and value < timezone.now().date() and not self.instance:
            raise serializers.ValidationError("交货日期不能早于今天")
        return value

    def validate_tax_rate(self, value):
        """验证税率"""
        if value < 0 or value > 100:
            raise serializers.ValidationError("税率必须在0-100之间")
        return value

    def to_internal_value(self, data):
        """移除客户端传入的 order_number（系统自动生成）"""
        if isinstance(data, dict):
            data = data.copy()
            data.pop("order_number", None)
        return super().to_internal_value(data)

    def validate_discount_amount(self, value):
        """验证折扣金额"""
        if value < 0:
            raise serializers.ValidationError("折扣金额不能为负数")
        return value

    def validate(self, attrs):
        """对象级验证"""
        order_date = attrs.get("order_date")
        delivery_date = attrs.get("delivery_date")

        if self.instance:
            order_date = order_date or self.instance.order_date
            delivery_date = delivery_date or self.instance.delivery_date

        if order_date and delivery_date and delivery_date < order_date:
            raise serializers.ValidationError(
                {"delivery_date": "交货日期不能早于订单日期"}
            )

        return attrs

    def create(self, validated_data):
        """创建销售订单及其明细"""
        items_data = validated_data.pop("items", [])

        try:
            sales_order = SalesOrder.objects.create(**validated_data)
        except Exception as e:
            raise serializers.ValidationError(f"创建销售订单失败: {str(e)}")

        # 创建订单明细
        for i, item_data in enumerate(items_data):
            try:
                SalesOrderItem.objects.create(sales_order=sales_order, **item_data)
            except Exception as e:
                raise serializers.ValidationError(
                    f"创建订单明细失败 (第{i+1}项): {str(e)}"
                )

        # 更新订单总金额
        try:
            sales_order.update_totals()
        except Exception as e:
            # 不阻止流程，记录错误即可
            pass

        return sales_order

    def update(self, instance, validated_data):
        """更新销售订单及其明细"""
        items_data = validated_data.pop("items", None)

        # 更新销售订单基本信息
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # 如果提供了明细数据，更新明细
        if items_data is not None:
            # 删除原有明细
            instance.items.all().delete()

            # 创建新明细
            for item_data in items_data:
                SalesOrderItem.objects.create(sales_order=instance, **item_data)

            # 更新订单总金额
            instance.update_totals()

        return instance
