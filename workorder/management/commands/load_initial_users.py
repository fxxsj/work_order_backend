"""
加载初始用户数据的管理命令
运行: python manage.py load_initial_users
功能：
1. 从 fixtures 文件加载用户数据
2. 自动为用户创建 UserProfile 并关联部门
"""

from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.contrib.auth.models import Group
from django.contrib.auth.models import User
from workorder.models import UserProfile, Department


class Command(BaseCommand):
    help = "加载初始用户数据（从 fixtures 文件加载用户，并自动关联部门）"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="强制执行，即使用户已存在也会覆盖",
        )

    def handle(self, *args, **options):
        force = options.get("force", False)

        # 用户与部门、角色组的映射关系
        user_mapping = {
            "business_user": {"department": "business", "role": "sales"},
            "finance_user": {"department": "finance", "role": "finance"},
            "design_user": {"department": "design", "role": "design"},
            "purchase_user": {"department": "purchase", "role": "procurement"},
            "quality_user": {"department": "quality", "role": "quality"},
            "warehouse_user": {"department": "warehouse", "role": "inventory"},
            "production_user": {
                "department": "production",
                "role": "supervisor",
            },
            "cutting_user": {"department": "cutting", "role": "operator"},
            "printing_user": {"department": "printing", "role": "operator"},
            "outsourcing_user": {
                "department": "outsourcing",
                "role": "operator",
            },
            "die_cutting_user": {
                "department": "die_cutting",
                "role": "operator",
            },
            "packaging_user": {"department": "packaging", "role": "operator"},
        }
        # 检查是否已有用户（排除超级用户）
        existing_users = User.objects.filter(username__in=user_mapping.keys())
        if existing_users.exists() and not force:
            self.stdout.write(
                self.style.WARNING(
                    f"⚠ 发现 {existing_users.count()} 个用户已存在："
                )
            )
            for user in existing_users:
                self.stdout.write(f"  - {user.username}")
            self.stdout.write(
                self.style.WARNING(
                    "使用 --force 参数强制执行（将删除并重新创建这些用户）"
                )
            )
            return

        try:
            # 如果 force=True，先删除现有用户
            if force and existing_users.exists():
                self.stdout.write("正在删除现有用户...")
                UserProfile.objects.filter(user__in=existing_users).delete()
                deleted_count = existing_users.count()
                existing_users.delete()
                self.stdout.write(
                    self.style.SUCCESS(f"✓ 已删除 {deleted_count} 个现有用户")
                )

            # 1. 从 fixtures 加载用户数据
            self.stdout.write("正在从 fixtures 加载用户数据...")
            call_command("loaddata", "initial_users", verbosity=0)
            self.stdout.write(self.style.SUCCESS("✓ 用户数据加载完成"))

            # 2. 为每个用户创建 UserProfile，关联部门和角色组
            self.stdout.write("正在创建用户扩展信息并关联部门/角色组...")
            created_count = 0
            updated_count = 0
            role_updated_count = 0

            for username, config in user_mapping.items():
                try:
                    user = User.objects.get(username=username)
                    dept_code = config["department"]
                    role_code = config["role"]

                    # 获取或创建 UserProfile
                    profile, created = UserProfile.objects.get_or_create(
                        user=user
                    )

                    # 获取部门并关联
                    try:
                        department = Department.objects.get(code=dept_code)
                        profile.departments.clear()
                        profile.departments.add(department)

                        group = Group.objects.get(name=role_code)
                        user.groups.clear()
                        user.groups.add(group)
                        role_updated_count += 1

                        if created:
                            created_count += 1
                            self.stdout.write(
                                f"  ✓ 创建用户扩展信息: {username} → "
                                f"{department.name} / {role_code}"
                            )
                        else:
                            updated_count += 1
                            self.stdout.write(
                                f"  ✓ 更新用户扩展信息: {username} → "
                                f"{department.name} / {role_code}"
                            )
                    except Department.DoesNotExist:
                        self.stdout.write(
                            self.style.WARNING(
                                f"  ⚠ 部门 {dept_code} 不存在，跳过用户 {username}"
                            )
                        )
                    except Group.DoesNotExist:
                        self.stdout.write(
                            self.style.WARNING(
                                f"  ⚠ 角色组 {role_code} 不存在，"
                                f"请先执行迁移或 init_groups，跳过用户 {username}"
                            )
                        )

                except User.DoesNotExist:
                    self.stdout.write(
                        self.style.WARNING(f"  ⚠ 用户 {username} 不存在，跳过")
                    )

            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS("=" * 60))
            self.stdout.write(self.style.SUCCESS("用户数据加载完成！"))
            self.stdout.write("")
            self.stdout.write(f"创建用户扩展信息: {created_count} 个")
            if updated_count > 0:
                self.stdout.write(f"更新用户扩展信息: {updated_count} 个")
            self.stdout.write(f"同步用户角色组: {role_updated_count} 个")
            self.stdout.write("")
            self.stdout.write("所有用户的默认密码为: 123456")
            self.stdout.write("")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ 加载失败: {e}"))
            raise
