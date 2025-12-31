"""
初始化用户组和权限的管理命令
运行: python manage.py init_groups
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from workorder.models import WorkOrder, Customer, Product, Material, Process, Department, Artwork, Die


class Command(BaseCommand):
    help = '初始化系统用户组和权限（业务员等）'

    def handle(self, *args, **options):
        # 定义角色及其权限
        role_permissions = {
            '业务员': {
                'workorder': ['add', 'view', 'change'],  # 可以创建、查看、修改施工单
                'customer': ['add', 'view', 'change'],  # 可以创建、查看、修改客户（与施工单权限逻辑一致）
                'department': ['add', 'view', 'change'],  # 可以创建、查看、修改部门（与客户管理权限逻辑一致）
                'process': ['add', 'view', 'change'],  # 可以创建、查看、修改工序（与客户管理权限逻辑一致）
                'product': ['add', 'view', 'change'],  # 可以创建、查看、修改产品（与客户管理权限逻辑一致）
                'material': ['add', 'view', 'change'],  # 可以创建、查看、修改物料（与客户管理权限逻辑一致）
                'artwork': ['add', 'view', 'change'],  # 可以创建、查看、修改图稿（与客户管理权限逻辑一致）
                'die': ['add', 'view', 'change'],  # 可以创建、查看、修改刀模（与客户管理权限逻辑一致）
            },
            # 可以在这里添加更多角色
            # '生产管理员': {
            #     'workorder': ['add', 'view', 'change', 'delete'],
            #     'process': ['add', 'view', 'change'],
            #     ...
            # },
        }
        
        # 创建组并分配权限
        for group_name, permissions_config in role_permissions.items():
            group, created = Group.objects.get_or_create(name=group_name)
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'✓ 成功创建用户组: {group_name}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'⚠ 用户组已存在: {group_name}')
                )
            
            # 分配权限
            permissions_added = 0
            for model_name, actions in permissions_config.items():
                # 获取模型类
                model_map = {
                    'workorder': WorkOrder,
                    'customer': Customer,
                    'department': Department,
                    'process': Process,
                    'product': Product,
                    'material': Material,
                    'artwork': Artwork,
                    'die': Die,
                }
                
                if model_name not in model_map:
                    self.stdout.write(
                        self.style.ERROR(f'✗ 未知的模型: {model_name}')
                    )
                    continue
                
                model = model_map[model_name]
                content_type = ContentType.objects.get_for_model(model)
                
                # 为每个操作添加权限
                for action in actions:
                    codename = f'{action}_{model_name}'
                    try:
                        permission = Permission.objects.get(
                            content_type=content_type,
                            codename=codename
                        )
                        if permission not in group.permissions.all():
                            group.permissions.add(permission)
                            permissions_added += 1
                            self.stdout.write(
                                f'  ✓ 添加权限: {permission.name} ({codename})'
                            )
                    except Permission.DoesNotExist:
                        self.stdout.write(
                            self.style.ERROR(f'  ✗ 权限不存在: {codename}')
                        )
            
            if permissions_added > 0:
                self.stdout.write(
                    self.style.SUCCESS(f'  → 为 {group_name} 组添加了 {permissions_added} 个权限')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'  → {group_name} 组权限未变更')
                )
        
        self.stdout.write('')
        self.stdout.write(
            self.style.SUCCESS('=' * 60)
        )
        self.stdout.write(
            self.style.SUCCESS('用户组和权限初始化完成！')
        )
        self.stdout.write('')
        self.stdout.write('下一步操作：')
        self.stdout.write('1. 在 Django Admin 中将用户添加到相应的组中')
        self.stdout.write('2. 或者使用命令: python manage.py assign_permissions <username> <group_name>')
        self.stdout.write('')

