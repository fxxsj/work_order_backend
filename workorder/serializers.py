from rest_framework import serializers
from django.contrib.auth.models import User
from .models import (
    Customer, Process, Material, WorkOrder,
    WorkOrderProcess, WorkOrderMaterial, ProcessLog
)


class UserSerializer(serializers.ModelSerializer):
    """用户序列化器"""
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email']


class CustomerSerializer(serializers.ModelSerializer):
    """客户序列化器"""
    class Meta:
        model = Customer
        fields = '__all__'


class ProcessSerializer(serializers.ModelSerializer):
    """工序序列化器"""
    class Meta:
        model = Process
        fields = '__all__'


class MaterialSerializer(serializers.ModelSerializer):
    """物料序列化器"""
    class Meta:
        model = Material
        fields = '__all__'


class ProcessLogSerializer(serializers.ModelSerializer):
    """工序日志序列化器"""
    operator_name = serializers.CharField(source='operator.username', read_only=True)
    log_type_display = serializers.CharField(source='get_log_type_display', read_only=True)
    
    class Meta:
        model = ProcessLog
        fields = '__all__'


class WorkOrderProcessSerializer(serializers.ModelSerializer):
    """施工单工序序列化器"""
    process_name = serializers.CharField(source='process.name', read_only=True)
    process_code = serializers.CharField(source='process.code', read_only=True)
    operator_name = serializers.CharField(source='operator.username', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    logs = ProcessLogSerializer(many=True, read_only=True)
    
    class Meta:
        model = WorkOrderProcess
        fields = '__all__'


class WorkOrderMaterialSerializer(serializers.ModelSerializer):
    """施工单物料序列化器"""
    material_name = serializers.CharField(source='material.name', read_only=True)
    material_code = serializers.CharField(source='material.code', read_only=True)
    material_unit = serializers.CharField(source='material.unit', read_only=True)
    
    class Meta:
        model = WorkOrderMaterial
        fields = '__all__'


class WorkOrderListSerializer(serializers.ModelSerializer):
    """施工单列表序列化器（精简版）"""
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    manager_name = serializers.CharField(source='manager.username', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    progress_percentage = serializers.SerializerMethodField()
    
    class Meta:
        model = WorkOrder
        fields = [
            'id', 'order_number', 'customer', 'customer_name',
            'product_name', 'quantity', 'unit', 'status', 'status_display',
            'priority', 'priority_display', 'order_date', 'delivery_date',
            'total_amount', 'manager', 'manager_name', 'progress_percentage',
            'created_at'
        ]
    
    def get_progress_percentage(self, obj):
        return obj.get_progress_percentage()


class WorkOrderDetailSerializer(serializers.ModelSerializer):
    """施工单详情序列化器（完整版）"""
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    customer_detail = CustomerSerializer(source='customer', read_only=True)
    manager_name = serializers.CharField(source='manager.username', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    
    order_processes = WorkOrderProcessSerializer(many=True, read_only=True)
    materials = WorkOrderMaterialSerializer(many=True, read_only=True)
    
    progress_percentage = serializers.SerializerMethodField()
    
    class Meta:
        model = WorkOrder
        fields = '__all__'
    
    def get_progress_percentage(self, obj):
        return obj.get_progress_percentage()


class WorkOrderCreateUpdateSerializer(serializers.ModelSerializer):
    """施工单创建/更新序列化器"""
    
    class Meta:
        model = WorkOrder
        fields = [
            'id', 'order_number', 'customer', 'product_name',
            'specification', 'quantity', 'unit', 'status', 'priority',
            'order_date', 'delivery_date', 'actual_delivery_date',
            'total_amount', 'design_file', 'manager', 'notes'
        ]
        
    def validate_order_number(self, value):
        """验证施工单号唯一性"""
        instance = self.instance
        if instance is None:  # 创建
            if WorkOrder.objects.filter(order_number=value).exists():
                raise serializers.ValidationError('施工单号已存在')
        else:  # 更新
            if WorkOrder.objects.filter(order_number=value).exclude(id=instance.id).exists():
                raise serializers.ValidationError('施工单号已存在')
        return value


class WorkOrderProcessUpdateSerializer(serializers.ModelSerializer):
    """工序更新序列化器"""
    
    class Meta:
        model = WorkOrderProcess
        fields = [
            'id', 'status', 'operator', 'actual_start_time',
            'actual_end_time', 'quantity_completed', 'quantity_defective', 'notes'
        ]

