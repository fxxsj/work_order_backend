"""
基础序列化器模块

包含用户、客户、部门和工序的序列化器。
"""

from rest_framework import serializers
from django.contrib.auth.models import User
from ..models.base import Customer, Department, Process


class UserSerializer(serializers.ModelSerializer):
    """用户序列化器"""
    groups = serializers.SerializerMethodField()
    is_salesperson = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email', 'groups', 'is_salesperson']

    def get_groups(self, obj):
        """获取用户所属的组"""
        return list(obj.groups.values_list('name', flat=True))

    def get_is_salesperson(self, obj):
        """判断用户是否为业务员"""
        return obj.groups.filter(name='业务员').exists()


class CustomerSerializer(serializers.ModelSerializer):
    """客户序列化器"""
    salesperson_name = serializers.CharField(source='salesperson.username', read_only=True, allow_null=True)

    class Meta:
        model = Customer
        fields = '__all__'


class DepartmentSerializer(serializers.ModelSerializer):
    """部门序列化器"""
    processes = serializers.PrimaryKeyRelatedField(many=True, queryset=Process.objects.all(), required=False)
    process_names = serializers.SerializerMethodField()
    parent = serializers.PrimaryKeyRelatedField(queryset=Department.objects.all(), required=False, allow_null=True)
    parent_name = serializers.SerializerMethodField()
    children_count = serializers.SerializerMethodField()

    class Meta:
        model = Department
        fields = '__all__'

    def get_process_names(self, obj):
        """获取工序名称列表"""
        if hasattr(obj, 'processes'):
            return [f"{p.code} - {p.name}" for p in obj.processes.all()]
        return []

    def get_parent_name(self, obj):
        """获取上级部门名称"""
        if obj.parent:
            return obj.parent.name
        return None

    def get_children_count(self, obj):
        """获取子部门数量"""
        if hasattr(obj, 'children'):
            return obj.children.count()
        return 0


class ProcessSerializer(serializers.ModelSerializer):
    """工序序列化器"""
    class Meta:
        model = Process
        fields = '__all__'

    def validate(self, data):
        """验证内置工序的code字段不可修改"""
        if self.instance and self.instance.is_builtin:
            # 如果是内置工序，检查是否尝试修改code字段
            if 'code' in data and data['code'] != self.instance.code:
                raise serializers.ValidationError({
                    'code': '内置工序的编码不可修改'
                })
        return data

    def validate_code(self, value):
        """验证code字段"""
        # 如果是更新操作且是内置工序，code字段应该保持不变
        if self.instance and self.instance.is_builtin:
            if value != self.instance.code:
                raise serializers.ValidationError('内置工序的编码不可修改')
        return value
