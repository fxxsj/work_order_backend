"""
初始化用户组的管理命令
运行: python manage.py init_groups
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission


class Command(BaseCommand):
    help = '初始化系统用户组（业务员等）'

    def handle(self, *args, **options):
        # 创建业务员组
        salesperson_group, created = Group.objects.get_or_create(name='业务员')
        if created:
            self.stdout.write(
                self.style.SUCCESS(f'成功创建用户组: 业务员')
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'用户组已存在: 业务员')
            )
        
        # 可以在这里添加更多组
        # 例如：生产管理员、财务等
        
        self.stdout.write(
            self.style.SUCCESS('用户组初始化完成！')
        )
        self.stdout.write(
            self.style.SUCCESS('现在可以在 Django Admin 中将用户添加到相应的组中。')
        )

