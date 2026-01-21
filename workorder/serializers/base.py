"""
基础序列化器模块

包含基础序列化器类和具体模型的序列化器。
"""

from rest_framework import serializers
from django.contrib.auth.models import User
from django.utils import timezone
from ..models.base import Customer, Department, Process


class BaseModelSerializer(serializers.ModelSerializer):
    """
    基础序列化器

    提供通用的字段和验证逻辑，所有序列化器应继承此类。

    特性:
        - 自动包含 created_at 和 updated_at 字段
        - 自动验证创建时间不能是未来时间

    使用示例:
        class MySerializer(BaseModelSerializer):
            class Meta:
                model = MyModel
                fields = '__all__'
    """

    # 如果模型有这些字段，自动定义为只读
    created_at = serializers.DateTimeField(read_only=True, required=False)
    updated_at = serializers.DateTimeField(read_only=True, required=False)

    class Meta:
        abstract = True

    def validate_created_at(self, value):
        """
        验证创建时间不能是未来时间

        Args:
            value: 创建时间值

        Returns:
            验证通过的时间值

        Raises:
            ValidationError: 如果创建时间是未来时间
        """
        if value and value > timezone.now():
            raise serializers.ValidationError("创建时间不能是未来时间")
        return value


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
    """客户序列化器

    提供完整的字段验证和业务规则检查。

    验证规则：
        - name: 必填，长度2-200
        - phone: 可选，格式验证（数字、连字符、加号、括号、空格）
        - email: 可选，Django EmailField 基础验证
    """
    salesperson_name = serializers.CharField(source='salesperson.username', read_only=True, allow_null=True)

    class Meta:
        model = Customer
        fields = '__all__'

    def validate_name(self, value):
        """验证客户名称"""
        if not value or not value.strip():
            raise serializers.ValidationError("客户名称不能为空")
        if len(value) < 2:
            raise serializers.ValidationError("客户名称至少需要2个字符")
        if len(value) > 200:
            raise serializers.ValidationError("客户名称不能超过200个字符")
        return value.strip()

    def validate_phone(self, value):
        """验证联系电话"""
        import re
        if value and not re.match(r'^[\d\-+() ]+$', value):
            raise serializers.ValidationError("电话号码格式不正确")
        return value

    def validate_email(self, value):
        """验证邮箱格式（Django EmailField 已有基础验证，这里可添加额外规则）"""
        return value


class DepartmentSerializer(serializers.ModelSerializer):
    """部门序列化器

    提供完整的字段验证和业务规则检查。

    验证规则：
        - code: 只能包含小写字母、数字和下划线，长度2-20
        - name: 必填，长度2-50
        - sort_order: 非负整数，最大99999
        - parent: 不能形成循环引用，层级深度不能超过3级
    """
    processes = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Process.objects.all(),
        required=False
    )
    process_names = serializers.SerializerMethodField()
    parent = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(),
        required=False,
        allow_null=True
    )
    parent_name = serializers.SerializerMethodField()
    children_count = serializers.SerializerMethodField()
    level = serializers.SerializerMethodField()

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

    def get_level(self, obj):
        """获取部门层级"""
        return obj.get_level()

    def validate_code(self, value):
        """验证部门编码格式

        确保编码只包含小写字母、数字和下划线。
        """
        import re

        if not value:
            raise serializers.ValidationError("部门编码不能为空")

        if not re.match(r'^[a-z0-9_]+$', value):
            raise serializers.ValidationError(
                "部门编码只能包含小写字母、数字和下划线"
            )

        if len(value) < 2 or len(value) > 20:
            raise serializers.ValidationError("部门编码长度必须在2-20个字符之间")

        # 编辑时不允许修改编码
        if self.instance and value != self.instance.code:
            raise serializers.ValidationError("部门编码不可修改")

        return value

    def validate_name(self, value):
        """验证部门名称"""
        if not value:
            raise serializers.ValidationError("部门名称不能为空")

        if len(value) < 2 or len(value) > 50:
            raise serializers.ValidationError("部门名称长度必须在2-50个字符之间")

        return value

    def validate_sort_order(self, value):
        """验证排序字段"""
        if value < 0:
            raise serializers.ValidationError("排序值不能为负数")
        if value > 99999:
            raise serializers.ValidationError("排序值超出合理范围（最大99999）")
        return value

    def validate(self, attrs):
        """对象级验证

        检查：
            1. 不能将自己设为上级部门（循环引用）
            2. 不能将自己的子孙设为上级部门（循环引用）
            3. 层级深度不能超过3级
        """
        parent = attrs.get('parent')

        if parent:
            # 编辑时检查循环引用
            if self.instance:
                # 不能将自己设为上级
                if parent.id == self.instance.id:
                    raise serializers.ValidationError({
                        'parent': '不能将自己设为上级部门'
                    })

                # 不能将自己的子孙设为上级
                descendants = self.instance.get_descendants()
                descendant_ids = [d.id for d in descendants]
                if parent.id in descendant_ids:
                    raise serializers.ValidationError({
                        'parent': '不能将子部门设为上级部门，这会造成循环引用'
                    })

            # 检查层级深度（最多3级：0, 1, 2）
            parent_level = parent.get_level()
            if parent_level >= 2:
                raise serializers.ValidationError({
                    'parent': '部门层级不能超过3级'
                })

        return attrs


class ProcessSerializer(serializers.ModelSerializer):
    """工序序列化器

    提供完整的字段验证和业务规则检查。
    """
    class Meta:
        model = Process
        fields = '__all__'

    def validate_code(self, value):
        """验证工序编码格式

        确保编码只包含合法字符（字母、数字、连字符、下划线）。
        """
        import re

        if not value:
            raise serializers.ValidationError("工序编码不能为空")

        if not re.match(r'^[A-Za-z0-9_-]+$', value):
            raise serializers.ValidationError(
                "工序编码只能包含字母、数字、连字符和下划线"
            )

        if len(value) < 2 or len(value) > 50:
            raise serializers.ValidationError("工序编码长度必须在2-50个字符之间")

        # 保护内置工序的 code
        if self.instance and self.instance.is_builtin:
            if value != self.instance.code:
                raise serializers.ValidationError('内置工序的编码不可修改')

        return value

    def validate_standard_duration(self, value):
        """验证标准工时"""
        if value < 0:
            raise serializers.ValidationError("标准工时不能为负数")
        if value > 9999:
            raise serializers.ValidationError("标准工时超出合理范围（最大9999小时）")
        return value

    def validate_sort_order(self, value):
        """验证排序字段"""
        if value < 0:
            raise serializers.ValidationError("排序值不能为负数")
        if value > 99999:
            raise serializers.ValidationError("排序值超出合理范围")
        return value

    def validate(self, attrs):
        """对象级业务规则验证

        检查字段之间的业务关系。
        """
        # 验证版要求与版必选的一致性
        if attrs.get('requires_artwork') and not attrs.get('artwork_required'):
            raise serializers.ValidationError({
                'artwork_required': '工序需要图稿时，图稿必选必须开启'
            })

        if attrs.get('requires_die') and not attrs.get('die_required'):
            raise serializers.ValidationError({
                'die_required': '工序需要刀模时，刀模必选必须开启'
            })

        if attrs.get('requires_foiling_plate') and not attrs.get('foiling_plate_required'):
            raise serializers.ValidationError({
                'foiling_plate_required': '工序需要烫金版时，烫金版必选必须开启'
            })

        if attrs.get('requires_embossing_plate') and not attrs.get('embossing_plate_required'):
            raise serializers.ValidationError({
                'embossing_plate_required': '工序需要压凸版时，压凸版必选必须开启'
            })

        # 验证任务生成规则与版要求的一致性
        task_rule = attrs.get('task_generation_rule')
        if task_rule == 'artwork' and not attrs.get('requires_artwork'):
            raise serializers.ValidationError({
                'task_generation_rule': '按图稿生成任务时，必须启用需要图稿'
            })

        if task_rule == 'die' and not attrs.get('requires_die'):
            raise serializers.ValidationError({
                'task_generation_rule': '按刀模生成任务时，必须启用需要刀模'
            })

        return attrs
