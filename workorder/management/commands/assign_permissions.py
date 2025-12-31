"""
为用户分配权限的管理命令
运行: python manage.py assign_permissions <username> <group_name>
例如: python manage.py assign_permissions 陈大文 业务员
"""
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User, Group


class Command(BaseCommand):
    help = '将用户添加到指定的组（从而获得该组的权限）'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='用户名')
        parser.add_argument('group_name', type=str, help='组名（如：业务员）')

    def handle(self, *args, **options):
        username = options['username']
        group_name = options['group_name']
        
        # 获取用户
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise CommandError(f'用户 "{username}" 不存在')
        
        # 获取组
        try:
            group = Group.objects.get(name=group_name)
        except Group.DoesNotExist:
            raise CommandError(f'组 "{group_name}" 不存在。请先运行: python manage.py init_groups')
        
        # 将用户添加到组
        if user.groups.filter(name=group_name).exists():
            self.stdout.write(
                self.style.WARNING(f'用户 "{username}" 已经在组 "{group_name}" 中')
            )
        else:
            user.groups.add(group)
            self.stdout.write(
                self.style.SUCCESS(f'✓ 成功将用户 "{username}" 添加到组 "{group_name}"')
            )
        
        # 显示用户当前的权限
        self.stdout.write('')
        self.stdout.write(f'用户 "{username}" 的权限信息:')
        self.stdout.write(f'  组: {", ".join(user.groups.values_list("name", flat=True))}')
        self.stdout.write(f'  权限数量: {user.user_permissions.count() + sum(g.permissions.count() for g in user.groups.all())}')
        
        # 显示组的所有权限
        if group.permissions.exists():
            self.stdout.write('')
            self.stdout.write(f'组 "{group_name}" 的权限:')
            for perm in group.permissions.all():
                self.stdout.write(f'  - {perm.name} ({perm.codename})')
        else:
            self.stdout.write('')
            self.stdout.write(
                self.style.WARNING(f'组 "{group_name}" 没有任何权限')
            )
            self.stdout.write('请运行: python manage.py init_groups 来初始化权限')

