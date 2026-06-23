from django.core.management.base import BaseCommand
from django.core.management.base import CommandError
from django.db.utils import OperationalError, ProgrammingError

from workorder.models import Notification


class Command(BaseCommand):
    help = "按系统通知设置清理过期通知和超限通知"

    def add_arguments(self, parser):
        parser.add_argument(
            "--user-id",
            type=int,
            action="append",
            dest="user_ids",
            help="只清理指定用户的通知，可重复传入多个 --user-id",
        )

    def handle(self, *args, **options):
        user_ids = options.get("user_ids") or None
        scope = (
            f"用户 {', '.join(str(user_id) for user_id in user_ids)}"
            if user_ids
            else "全部用户"
        )

        queryset = Notification.objects.all()
        if user_ids:
            queryset = queryset.filter(recipient_id__in=user_ids)

        try:
            before_count = queryset.count()
            Notification.apply_retention_policy(user_ids)
            after_count = queryset.count()
        except (OperationalError, ProgrammingError) as exc:
            raise CommandError(
                "通知相关数据表不存在，请先执行数据库迁移。"
            ) from exc
        removed_count = before_count - after_count

        self.stdout.write(
            self.style.SUCCESS(
                f"通知清理完成: 范围={scope}, 清理数量={removed_count}, 剩余数量={after_count}"
            )
        )
