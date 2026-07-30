"""
客户订单序列化器模块

包含客户订单和客户订单明细的序列化器。
"""

from typing import List

from rest_framework import serializers

from ..models.products import Product
from ..models.sales import SalesOrder, SalesOrderItem


class SalesOrderItemSerializer(serializers.ModelSerializer):
    """客户订单明细序列化器"""

    product_name = serializers.CharField(source="product.name", read_only=True)
    product_code = serializers.CharField(source="product.code", read_only=True)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = SalesOrderItem
        fields = "__all__"
        read_only_fields = [
            "created_at",
            "updated_at",
            "subtotal",
            "sales_order",
            "tax_rate",
            "discount_amount",
        ]
        extra_kwargs = {
            "sales_order": {"required": False},
            "delivered_quantity": {"required": False},
        }

    def update(self, instance, validated_data):
        """禁止在更新时修改关联客户订单"""
        validated_data.pop("sales_order", None)
        return super().update(instance, validated_data)


class SalesOrderListSerializer(serializers.ModelSerializer):
    """客户订单列表序列化器"""

    customer_name = serializers.CharField(source="customer.name", read_only=True)
    customer_code = serializers.CharField(source="customer.code", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    approval_status_display = serializers.CharField(
        source="get_approval_status_display", read_only=True
    )
    payment_status_display = serializers.CharField(
        source="get_payment_status_display", read_only=True
    )
    submitted_by_name = serializers.CharField(
        source="submitted_by.username", read_only=True, allow_null=True
    )
    approved_by_name = serializers.CharField(
        source="approved_by.username", read_only=True, allow_null=True
    )
    items_count = serializers.IntegerField(read_only=True)
    work_order_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = SalesOrder
        fields = "__all__"


class SalesOrderDetailSerializer(serializers.ModelSerializer):
    """客户订单详情序列化器"""

    customer_name = serializers.CharField(source="customer.name", read_only=True)
    customer_contact = serializers.CharField(
        source="customer.contact_person", read_only=True
    )
    customer_phone = serializers.CharField(source="customer.phone", read_only=True)
    customer_address = serializers.CharField(source="customer.address", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    approval_status_display = serializers.CharField(
        source="get_approval_status_display", read_only=True
    )
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

    # 财务概览字段
    invoice_total_amount = serializers.SerializerMethodField()
    invoice_received_amount = serializers.SerializerMethodField()
    invoice_unreceived_amount = serializers.SerializerMethodField()
    production_cost_total = serializers.SerializerMethodField()
    gross_profit = serializers.SerializerMethodField()
    gross_profit_rate = serializers.SerializerMethodField()
    total_quantity = serializers.SerializerMethodField()
    delivered_quantity = serializers.SerializerMethodField()
    remaining_quantity = serializers.SerializerMethodField()
    delivery_progress = serializers.SerializerMethodField()

    class Meta:
        model = SalesOrder
        fields = "__all__"
        # 以下字段在任意模式下均只读（系统自动管理）
        always_read_only_fields = [
            "order_number",
            "status",
            "approval_status",
            "payment_status",
            "subtotal",
            "tax_rate",
            "tax_amount",
            "discount_amount",
            "total_amount",
            "deposit_amount",
            "paid_amount",
            "payment_date",
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
        read_only_fields = always_read_only_fields

    def get_fields(self):
        """确保系统字段在创建和编辑时都真正只读，且不会触发 required 校验。"""
        fields = super().get_fields()
        for field_name in getattr(self.Meta, "always_read_only_fields", []):
            field = fields.get(field_name)
            if field is None:
                continue
            field.read_only = True
            field.required = False
        return fields

    def get_work_order_numbers(self, obj) -> List[str]:
        """获取关联的施工单号列表"""
        return [
            work_order.order_number
            for work_order in obj.get_related_work_orders()
            if work_order.order_number
        ]

    def get_delivery_order_numbers(self, obj) -> List[str]:
        """获取关联的送货单号列表"""
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
        """获取关联送货单摘要"""
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

    def get_invoice_total_amount(self, obj) -> float:
        """获取关联发票总额（价税合计）"""
        from django.db.models import Sum

        total = obj.invoices.aggregate(total=Sum("total_amount"))["total"]
        return float(total or 0)

    def get_invoice_received_amount(self, obj) -> float:
        """获取发票已收金额（按核销金额汇总）"""
        from django.db.models import Sum

        total = obj.invoices.filter(payments__isnull=False).aggregate(
            total=Sum("payments__applied_amount")
        )["total"]
        return float(total or 0)

    def get_invoice_unreceived_amount(self, obj) -> float:
        """获取发票未收金额"""
        return max(
            self.get_invoice_total_amount(obj) - self.get_invoice_received_amount(obj),
            0,
        )

    def get_production_cost_total(self, obj) -> float:
        """获取关联施工单的生产成本汇总"""
        from django.db.models import Sum

        total = obj.source_work_orders.filter(production_cost__isnull=False).aggregate(
            total=Sum("production_cost__total_cost")
        )["total"]
        return float(total or 0)

    def get_gross_profit(self, obj) -> float:
        """毛利 = 订单金额 - 生产成本"""
        return max(float(obj.total_amount) - self.get_production_cost_total(obj), 0)

    def get_gross_profit_rate(self, obj) -> float:
        """毛利率 = 毛利 / 订单金额"""
        total = float(obj.total_amount) if obj.total_amount else 0
        if total > 0:
            profit = self.get_gross_profit(obj)
            return round(profit / total * 100, 2)
        return 0.0

    def get_total_quantity(self, obj) -> float:
        return float(sum(item.quantity for item in obj.items.all()))

    def get_delivered_quantity(self, obj) -> float:
        return float(sum(item.delivered_quantity for item in obj.items.all()))

    def get_remaining_quantity(self, obj) -> float:
        return max(
            self.get_total_quantity(obj) - self.get_delivered_quantity(obj),
            0,
        )

    def get_delivery_progress(self, obj) -> float:
        total = self.get_total_quantity(obj)
        if total <= 0:
            return 0
        return round(self.get_delivered_quantity(obj) / total * 100, 2)

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

    def get_value(self, data):
        """移除客户端传入的 order_number（系统自动生成），避免 required 验证报错"""
        if isinstance(data, dict):
            data = data.copy()
            data.pop("order_number", None)
        return super().get_value(data)

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

        # 校验订单明细中的产品是否对该客户可用
        # 规则：客户限定产品必须关联该客户；通用产品（无客户关联）所有客户可用
        items = attrs.get("items")
        customer = attrs.get("customer")
        if customer is None and self.instance:
            customer = self.instance.customer

        if items and customer is not None:
            self._validate_items_product_scope(items, customer)

        return attrs

    def _validate_items_product_scope(self, items, customer):
        """校验订单明细中的产品是否对该客户可用。

        - 通用产品（无客户关联）：所有客户可用
        - 客户限定产品：必须关联该客户
        禁止下单该客户不可用的产品，约束后续新增/修改，不影响历史已保存订单。
        """
        customer_id = customer.id if hasattr(customer, "id") else customer
        product_ids = []
        for item in items:
            product = item.get("product") if isinstance(item, dict) else None
            if product is None:
                continue
            product_ids.append(product.id if hasattr(product, "id") else product)

        if not product_ids:
            return

        product_ids = list(set(product_ids))

        # 通用产品集合（无任何客户关联）
        global_product_ids = set(
            Product.objects.filter(
                id__in=product_ids, customers__isnull=True
            ).values_list("id", flat=True)
        )
        # 该客户关联的产品集合
        customer_product_ids = set(
            Product.objects.filter(
                id__in=product_ids, customers=customer_id
            ).values_list("id", flat=True)
        )

        for idx, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                continue
            product = item.get("product")
            if product is None:
                continue
            pid = product.id if hasattr(product, "id") else product
            if pid in global_product_ids or pid in customer_product_ids:
                continue
            raise serializers.ValidationError(
                {
                    "items": (
                        f"第 {idx} 个产品（ID {pid}）不在该客户可用产品范围内，"
                        f"请先在产品管理中关联该客户或设为通用产品"
                    )
                }
            )

    def create(self, validated_data):
        """创建客户订单及其明细"""
        items_data = validated_data.pop("items", [])
        # 客户订单不再经过审核流程；保留旧字段仅用于历史兼容。
        validated_data["approval_status"] = "approved"

        try:
            sales_order = SalesOrder.objects.create(**validated_data)
        except Exception as e:
            raise serializers.ValidationError(f"创建客户订单失败: {str(e)}")

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
        except Exception:
            # 不阻止流程，记录错误即可
            pass

        return sales_order

    def update(self, instance, validated_data):
        """更新客户订单及其明细"""
        items_data = validated_data.pop("items", None)

        if items_data is not None and (
            instance.source_work_orders.exists() or instance.delivery_orders.exists()
        ):
            current_signature = [
                (
                    item.product_id,
                    item.quantity,
                    item.unit,
                    item.unit_price,
                    item.notes,
                )
                for item in instance.items.all()
            ]
            incoming_signature = [
                (
                    item["product"].id,
                    item.get("quantity"),
                    item.get("unit", "件"),
                    item.get("unit_price", 0),
                    item.get("notes", ""),
                )
                for item in items_data
            ]
            if incoming_signature != current_signature:
                raise serializers.ValidationError(
                    {
                        "items": (
                            "订单已生成施工单或送货单，不能再修改产品明细；"
                            "联系人、地址、交期和备注仍可修改"
                        )
                    }
                )
            # 明细未变化时只更新表头，避免删除重建导致关联记录断开。
            items_data = None

        # 更新客户订单基本信息
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
