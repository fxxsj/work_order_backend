from django.core.management.base import BaseCommand, CommandError
from django.db.utils import OperationalError, ProgrammingError

from workorder.models import Notification
from workorder.services.notification_triggers import DeadlineWarningService


class Command(BaseCommand):
    help = "执行通知系统日常维护，包括交期预警、逾期任务检查和通知清理"

    def handle(self, *args, **options):
        try:
            before_count = Notification.objects.count()

            DeadlineWarningService.check_deadline_warnings()
            DeadlineWarningService.check_overdue_tasks()
            Notification.apply_retention_policy()

            after_count = Notification.objects.count()
        except (OperationalError, ProgrammingError) as exc:
            raise CommandError(
                "通知相关数据表不存在，请先执行数据库迁移。"
            ) from exc

        self.stdout.write(
            self.style.SUCCESS(
                "通知维护完成: "
                f"当前通知数量={after_count}, "
                f"净变化={after_count - before_count}"
            )
        )
