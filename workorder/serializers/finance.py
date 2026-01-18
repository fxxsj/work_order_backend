"""
财务相关序列化器

包含财务管理的所有序列化器：
- CostCenter: 成本中心
- CostItem: 成本项目
- ProductionCost: 生产成本
- Invoice: 发票
- Payment: 收款记录
- PaymentPlan: 收款计划
- Statement: 对账单
"""

from rest_framework import serializers
from django.contrib.auth.models import User
from workorder.models import (
    CostCenter, CostItem, ProductionCost,
    Invoice, Payment, PaymentPlan, Statement
)


# ==================== 成本核算序列化器 ====================

class CostCenterSerializer(serializers.ModelSerializer):
    """成本中心序列化器"""
    parent_name = serializers.CharField(source='parent.name', read_only=True, allow_null=True)
    manager_name = serializers.CharField(source='manager.username', read_only=True, allow_null=True)
    children_count = serializers.SerializerMethodField()
    type_display = serializers.CharField(source='get_type_display', read_only=True)

    class Meta:
        model = CostCenter
        fields = '__all__'

    def get_children_count(self, obj):
        """获取子成本中心数量"""
        return obj.children.count() if hasattr(obj, 'children') else 0


class CostItemSerializer(serializers.ModelSerializer):
    """成本项目序列化器"""
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    allocation_method_display = serializers.CharField(
        source='get_allocation_method_display', read_only=True
    )

    class Meta:
        model = CostItem
        fields = '__all__'


class ProductionCostSerializer(serializers.ModelSerializer):
    """生产成本序列化器"""
    work_order_number = serializers.CharField(
        source='work_order.order_number', read_only=True
    )
    customer_name = serializers.SerializerMethodField()
    calculated_by_name = serializers.CharField(
        source='calculated_by.username', read_only=True, allow_null=True
    )
    variance_rate_formatted = serializers.SerializerMethodField()

    class Meta:
        model = ProductionCost
        fields = '__all__'
        read_only_fields = ['work_order']

    def get_customer_name(self, obj):
        """获取客户名称"""
        if obj.work_order and obj.work_order.customer:
            return obj.work_order.customer.name
        return None

    def get_variance_rate_formatted(self, obj):
        """格式化差异率显示"""
        return f"{obj.variance_rate:.2f}%"


class ProductionCostUpdateSerializer(serializers.ModelSerializer):
    """生产成本更新序列化器"""

    class Meta:
        model = ProductionCost
        fields = [
            'material_cost', 'labor_cost', 'equipment_cost', 'overhead_cost',
            'standard_cost', 'notes'
        ]


# ==================== 发票管理序列化器 ====================

class InvoiceSerializer(serializers.ModelSerializer):
    """发票序列化器"""
    invoice_type_display = serializers.CharField(source='get_invoice_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    # 关联信息
    sales_order_number = serializers.CharField(
        source='sales_order.order_number', read_only=True, allow_null=True
    )
    work_order_number = serializers.CharField(
        source='work_order.order_number', read_only=True, allow_null=True
    )
    customer_name = serializers.CharField(source='customer.name', read_only=True)

    # 操作人信息
    created_by_name = serializers.CharField(
        source='created_by.username', read_only=True, allow_null=True
    )
    submitted_by_name = serializers.CharField(
        source='submitted_by.username', read_only=True, allow_null=True
    )
    approved_by_name = serializers.CharField(
        source='approved_by.username', read_only=True, allow_null=True
    )

    class Meta:
        model = Invoice
        fields = '__all__'
        read_only_fields = ['invoice_number']

    def validate(self, data):
        """验证发票数据"""
        invoice_type = data.get('invoice_type')
        amount = data.get('amount')
        tax_rate = data.get('tax_rate')

        # 金额必须大于0
        if amount is not None and amount <= 0:
            raise serializers.ValidationError({'amount': '金额必须大于0'})

        # 税率必须在合理范围内
        if tax_rate is not None and (tax_rate < 0 or tax_rate > 100):
            raise serializers.ValidationError({'tax_rate': '税率必须在0-100之间'})

        return data


class InvoiceCreateSerializer(serializers.ModelSerializer):
    """发票创建序列化器"""

    class Meta:
        model = Invoice
        fields = [
            'invoice_type', 'sales_order', 'work_order', 'customer',
            'amount', 'tax_rate', 'issue_date',
            'customer_tax_number', 'customer_address', 'customer_phone',
            'customer_bank', 'customer_account', 'notes'
        ]

    def validate(self, data):
        """验证创建数据"""
        # 必须选择客户
        if not data.get('customer'):
            raise serializers.ValidationError({'customer': '必须选择客户'})

        # 如果选择了销售订单，自动填充客户开票信息
        sales_order = data.get('sales_order')
        if sales_order and sales_order.customer:
            customer = sales_order.customer
            # 如果未提供客户开票信息，尝试从客户信息获取
            if not data.get('customer_tax_number'):
                data['customer_tax_number'] = getattr(customer, 'tax_number', '')
            if not data.get('customer_address'):
                data['customer_address'] = customer.address
            if not data.get('customer_phone'):
                data['customer_phone'] = customer.phone

        return data


class InvoiceUpdateSerializer(serializers.ModelSerializer):
    """发票更新序列化器"""

    class Meta:
        model = Invoice
        fields = [
            'invoice_code', 'invoice_type', 'amount', 'tax_rate',
            'issue_date', 'status',
            'customer_tax_number', 'customer_address', 'customer_phone',
            'customer_bank', 'customer_account', 'notes', 'attachment'
        ]


# ==================== 收款管理序列化器 ====================

class PaymentSerializer(serializers.ModelSerializer):
    """收款记录序列化器"""
    payment_method_display = serializers.CharField(
        source='get_payment_method_display', read_only=True
    )

    # 关联信息
    sales_order_number = serializers.CharField(
        source='sales_order.order_number', read_only=True, allow_null=True
    )
    invoice_number = serializers.CharField(
        source='invoice.invoice_number', read_only=True, allow_null=True
    )
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    recorded_by_name = serializers.CharField(
        source='recorded_by.username', read_only=True, allow_null=True
    )

    class Meta:
        model = Payment
        fields = '__all__'
        read_only_fields = ['payment_number', 'remaining_amount']


class PaymentCreateSerializer(serializers.ModelSerializer):
    """收款创建序列化器"""

    class Meta:
        model = Payment
        fields = [
            'sales_order', 'invoice', 'customer', 'amount',
            'payment_method', 'payment_date',
            'bank_account', 'transaction_number', 'notes'
        ]

    def validate(self, data):
        """验证创建数据"""
        # 必须选择客户
        if not data.get('customer'):
            raise serializers.ValidationError({'customer': '必须选择客户'})

        # 收款金额必须大于0
        amount = data.get('amount')
        if amount and amount <= 0:
            raise serializers.ValidationError({'amount': '收款金额必须大于0'})

        # 付款日期不能晚于今天
        payment_date = data.get('payment_date')
        if payment_date and payment_date > timezone.now().date():
            raise serializers.ValidationError({'payment_date': '付款日期不能晚于今天'})

        return data


class PaymentUpdateSerializer(serializers.ModelSerializer):
    """收款更新序列化器"""

    class Meta:
        model = Payment
        fields = [
            'amount', 'payment_method', 'payment_date',
            'bank_account', 'transaction_number',
            'applied_amount', 'notes'
        ]


class PaymentPlanSerializer(serializers.ModelSerializer):
    """收款计划序列化器"""
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    sales_order_number = serializers.CharField(
        source='sales_order.order_number', read_only=True
    )

    class Meta:
        model = PaymentPlan
        fields = '__all__'

    def get_progress_percentage(self, obj):
        """获取收款进度"""
        if obj.plan_amount > 0:
            return int((obj.paid_amount / obj.plan_amount) * 100)
        return 0


# ==================== 对账管理序列化器 ====================

class StatementSerializer(serializers.ModelSerializer):
    """对账单序列化器"""
    statement_type_display = serializers.CharField(
        source='get_statement_type_display', read_only=True
    )
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    # 关联信息
    customer_name = serializers.CharField(
        source='customer.name', read_only=True, allow_null=True
    )
    supplier_name = serializers.CharField(
        source='supplier.name', read_only=True, allow_null=True
    )
    created_by_name = serializers.CharField(
        source='created_by.username', read_only=True, allow_null=True
    )
    confirmed_by_name = serializers.CharField(
        source='confirmed_by.username', read_only=True, allow_null=True
    )

    class Meta:
        model = Statement
        fields = '__all__'
        read_only_fields = ['statement_number', 'closing_balance']


class StatementCreateSerializer(serializers.ModelSerializer):
    """对账单创建序列化器"""

    class Meta:
        model = Statement
        fields = [
            'statement_type', 'customer', 'supplier',
            'period', 'start_date', 'end_date',
            'opening_balance', 'notes'
        ]

    def validate(self, data):
        """验证创建数据"""
        statement_type = data.get('statement_type')

        # 客户对账单必须选择客户
        if statement_type == 'customer' and not data.get('customer'):
            raise serializers.ValidationError({'customer': '客户对账单必须选择客户'})

        # 供应商对账单必须选择供应商
        if statement_type == 'supplier' and not data.get('supplier'):
            raise serializers.ValidationError({'supplier': '供应商对账单必须选择供应商'})

        # 结束日期必须晚于开始日期
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError({
                'end_date': '结束日期必须晚于或等于开始日期'
            })

        return data


# ==================== 成本分析序列化器 ====================

class CostAnalysisSerializer(serializers.Serializer):
    """成本分析序列化器（用于统计报表）"""
    period = serializers.CharField()
    total_orders = serializers.IntegerField()
    total_cost = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_profit = serializers.DecimalField(max_digits=12, decimal_places=2)
    profit_rate = serializers.DecimalField(max_digits=5, decimal_places=2)

    # 成本明细
    material_cost = serializers.DecimalField(max_digits=12, decimal_places=2)
    labor_cost = serializers.DecimalField(max_digits=12, decimal_places=2)
    equipment_cost = serializers.DecimalField(max_digits=12, decimal_places=2)
    overhead_cost = serializers.DecimalField(max_digits=12, decimal_places=2)

    # 对比分析
    standard_cost = serializers.DecimalField(max_digits=12, decimal_places=2)
    actual_cost = serializers.DecimalField(max_digits=12, decimal_places=2)
    variance = serializers.DecimalField(max_digits=12, decimal_places=2)


# ==================== 导出所有序列化器 ====================

__all__ = [
    # 成本核算
    'CostCenterSerializer',
    'CostItemSerializer',
    'ProductionCostSerializer',
    'ProductionCostUpdateSerializer',

    # 发票管理
    'InvoiceSerializer',
    'InvoiceCreateSerializer',
    'InvoiceUpdateSerializer',

    # 收款管理
    'PaymentSerializer',
    'PaymentCreateSerializer',
    'PaymentUpdateSerializer',
    'PaymentPlanSerializer',

    # 对账管理
    'StatementSerializer',
    'StatementCreateSerializer',

    # 成本分析
    'CostAnalysisSerializer',
]
