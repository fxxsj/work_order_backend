"""
实时通知服务

提供WebSocket实时通知、事件驱动的通知发送、通知管理等功能
"""

import json
from typing import Dict, List, Any
from urllib.parse import parse_qs
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync, sync_to_async
from django.contrib.auth.models import User
from django.utils import timezone
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class NotificationEvent:
    """通知事件定义"""

    # 工序相关事件
    PROCESS_STARTED = "process_started"
    PROCESS_COMPLETED = "process_completed"
    PROCESS_PAUSED = "process_paused"
    PROCESS_ERROR = "process_error"

    # 任务相关事件
    TASK_ASSIGNED = "task_assigned"
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_OVERDUE = "task_overdue"

    # 施工单相关事件
    WORKORDER_CREATED = "workorder_created"
    WORKORDER_UPDATED = "workorder_updated"
    WORKORDER_APPROVED = "workorder_approved"
    WORKORDER_REJECTED = "workorder_rejected"
    WORKORDER_COMPLETED = "workorder_completed"

    # 审核相关事件
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_PASSED = "approval_passed"
    APPROVAL_REJECTED = "approval_rejected"
    APPROVAL_STEP_STARTED = "approval_step_started"
    APPROVAL_STEP_COMPLETED = "approval_step_completed"
    APPROVAL_ESCALATED = "approval_escalated"

    # 系统相关事件
    SYSTEM_ANNOUNCEMENT = "system_announcement"
    DEADLINE_WARNING = "deadline_warning"
    URGENT_ORDER = "urgent_order"


class NotificationPriority:
    """通知优先级"""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class NotificationChannel:
    """通知渠道"""

    WEBSOCKET = "websocket"
    EMAIL = "email"
    SMS = "sms"
    IN_APP = "in_app"


class RealtimeNotificationService:
    """实时通知服务"""

    def __init__(self):
        self.channel_layer = get_channel_layer()

    def send_notification(
        self,
        event_type: str,
        recipients: List[User],
        data: Dict[str, Any],
        priority: str = NotificationPriority.NORMAL,
        channels: List[str] = None,
    ):
        """
        发送通知

        Args:
            event_type: 事件类型
            recipients: 接收者列表
            data: 通知数据
            priority: 优先级
            channels: 通知渠道列表
        """
        if channels is None:
            channels = [
                NotificationChannel.WEBSOCKET,
                NotificationChannel.IN_APP,
            ]

        recipients = list(
            {
                recipient.id: recipient
                for recipient in recipients
                if recipient
            }.values()
        )
        channel_plan = self._build_channel_plan(
            event_type, recipients, channels, priority
        )
        filtered_recipients = channel_plan["all"]
        if not filtered_recipients:
            return

        payload = self._render_notification_payload(event_type, data)
        notification_data = {
            "event_type": event_type,
            "priority": priority,
            "data": payload,
            "timestamp": timezone.now().isoformat(),
            "channels": channels,
        }

        # 保存到数据库
        self._save_notification_to_db(filtered_recipients, notification_data)

        # 发送WebSocket通知
        if channel_plan[NotificationChannel.WEBSOCKET]:
            self._send_websocket_notification(
                channel_plan[NotificationChannel.WEBSOCKET], notification_data
            )

        # 发送邮件通知（如果是高优先级或紧急）
        if channel_plan[NotificationChannel.EMAIL]:
            self._send_email_notification(
                channel_plan[NotificationChannel.EMAIL], notification_data
            )

    def _build_channel_plan(
        self,
        event_type: str,
        recipients: List[User],
        channels: List[str],
        priority: str,
    ):
        from ..models.system import (
            SystemNotificationSettings,
            UserProfile,
            default_user_notification_preferences,
        )

        settings = SystemNotificationSettings.get_solo()
        preference_key = self._event_preference_key(event_type)
        now_local = timezone.localtime()
        plan = {
            "all": [],
            NotificationChannel.WEBSOCKET: [],
            NotificationChannel.EMAIL: [],
            NotificationChannel.SMS: [],
            NotificationChannel.IN_APP: [],
        }

        for recipient in recipients:
            prefs = default_user_notification_preferences()
            try:
                profile = UserProfile.objects.filter(user=recipient).first()
                if profile and profile.notification_preferences:
                    prefs.update(profile.notification_preferences)
            except Exception:
                pass

            if preference_key and prefs.get(preference_key) is False:
                continue

            plan["all"].append(recipient)
            quiet_hours_active = self._is_quiet_hours(now_local, prefs)
            for channel in channels:
                if not self._is_channel_enabled_globally(channel, settings):
                    continue
                if not self._is_channel_enabled_for_user(
                    channel, prefs, priority
                ):
                    continue
                if quiet_hours_active and channel in {
                    NotificationChannel.WEBSOCKET,
                    NotificationChannel.EMAIL,
                    NotificationChannel.SMS,
                }:
                    continue
                plan[channel].append(recipient)

        return plan

    def _render_notification_payload(
        self, event_type: str, data: Dict[str, Any]
    ):
        from ..models.system import NotificationTemplate

        payload = dict(data or {})
        variables = {
            key: value
            for key, value in payload.items()
            if value is not None
            and not isinstance(value, (dict, list, tuple, set))
        }
        if "task_name" not in variables and payload.get("work_content"):
            variables["task_name"] = payload["work_content"]
        rendered = (
            NotificationTemplate.render(event_type, variables)
            if event_type
            else None
        )
        if rendered:
            payload["title"] = rendered["title"]
            payload["message"] = rendered["message"]
        return payload

    def _event_preference_key(self, event_type: str):
        mapping = {
            NotificationEvent.TASK_ASSIGNED: "task_assignments",
            NotificationEvent.PROCESS_COMPLETED: "process_completions",
            NotificationEvent.DEADLINE_WARNING: "deadline_warnings",
            NotificationEvent.SYSTEM_ANNOUNCEMENT: "system_announcements",
            NotificationEvent.WORKORDER_APPROVED: "system_announcements",
            NotificationEvent.WORKORDER_REJECTED: "system_announcements",
        }
        return mapping.get(event_type)

    def _is_channel_enabled_globally(self, channel: str, settings):
        mapping = {
            NotificationChannel.WEBSOCKET: settings.websocket_enabled,
            NotificationChannel.EMAIL: settings.email_enabled,
            NotificationChannel.SMS: settings.sms_enabled,
            NotificationChannel.IN_APP: True,
        }
        return mapping.get(channel, True)

    def _is_channel_enabled_for_user(
        self, channel: str, prefs: Dict[str, Any], priority: str
    ):
        if channel == NotificationChannel.WEBSOCKET:
            return prefs.get("websocket_notifications", True)
        if channel == NotificationChannel.EMAIL:
            if not prefs.get("email_notifications", True):
                return False
            threshold = prefs.get("urgency_threshold", "normal")
            rank = {
                NotificationPriority.LOW: 0,
                NotificationPriority.NORMAL: 1,
                NotificationPriority.HIGH: 2,
                NotificationPriority.URGENT: 3,
            }
            return rank.get(priority, 1) >= rank.get(str(threshold), 1)
        return True

    def _is_quiet_hours(self, current_time, prefs: Dict[str, Any]):
        if not prefs.get("quiet_hours_enabled", False):
            return False

        start = prefs.get("quiet_hours_start", "22:00")
        end = prefs.get("quiet_hours_end", "08:00")
        try:
            start_hour, start_minute = [int(part) for part in start.split(":")]
            end_hour, end_minute = [int(part) for part in end.split(":")]
        except Exception:
            return False

        current_minutes = current_time.hour * 60 + current_time.minute
        start_minutes = start_hour * 60 + start_minute
        end_minutes = end_hour * 60 + end_minute

        if start_minutes == end_minutes:
            return False
        if start_minutes < end_minutes:
            return start_minutes <= current_minutes < end_minutes
        return (
            current_minutes >= start_minutes or current_minutes < end_minutes
        )

    def _save_notification_to_db(
        self, recipients: List[User], data: Dict[str, Any]
    ):
        """保存通知到数据库"""
        try:
            from ..models.system import Notification

            valid_types = {
                choice[0] for choice in Notification.NOTIFICATION_TYPE_CHOICES
            }
            event_type = data.get("event_type")
            if event_type in valid_types:
                notification_type = event_type
            else:
                mapping = {
                    NotificationEvent.WORKORDER_APPROVED: "approval_passed",
                    NotificationEvent.WORKORDER_REJECTED: "approval_rejected",
                    NotificationEvent.TASK_ASSIGNED: "task_assigned",
                    NotificationEvent.PROCESS_COMPLETED: "process_completed",
                    NotificationEvent.DEADLINE_WARNING: "task_due_soon",
                }
                notification_type = mapping.get(event_type, "system")

            notifications = []
            for recipient in recipients:
                payload = data.get("data", {})
                notifications.append(
                    Notification(
                        recipient=recipient,
                        notification_type=notification_type,
                        priority=data.get(
                            "priority", NotificationPriority.NORMAL
                        ),
                        title=payload.get("title", ""),
                        content=payload.get("message", ""),
                        data=data,
                        is_read=False,
                    )
                )

            Notification.objects.bulk_create(notifications)
            Notification.apply_retention_policy(
                [recipient.id for recipient in recipients]
            )

        except Exception as e:
            logger.error(f"保存通知到数据库失败: {e}")

    def _send_websocket_notification(
        self, recipients: List[User], data: Dict[str, Any]
    ):
        """发送WebSocket通知"""
        try:
            for recipient in recipients:
                group_name = f"user_{recipient.id}_notifications"

                async_to_sync(self.channel_layer.group_send)(
                    group_name,
                    {"type": "notification_message", "notification": data},
                )
        except Exception as e:
            logger.error(f"发送WebSocket通知失败: {e}")

    def _send_email_notification(
        self, recipients: List[User], data: Dict[str, Any]
    ):
        """发送邮件通知"""
        try:
            from django.core.mail import send_mail
            from django.template.loader import render_to_string

            for recipient in recipients:
                subject = data["data"].get("title", "系统通知")
                message = data["data"].get("message", "")

                html_message = render_to_string(
                    "notifications/email_template.html",
                    {
                        "user": recipient,
                        "notification": data,
                        "data": data["data"],
                    },
                )

                send_mail(
                    subject=subject,
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[recipient.email],
                    html_message=html_message,
                    fail_silently=True,
                )
        except Exception as e:
            logger.error(f"发送邮件通知失败: {e}")

    def notify_task_assigned(self, task, assigned_operator, assigned_by=None):
        """通知任务分配 - 发送给操作员和部门成员"""
        recipients = [assigned_operator]

        # 通知分配者所在部门的其他成员（根据上下文：部门成员可见）
        if task.assigned_department:
            dept_members = self._get_department_members(
                task.assigned_department
            )
            recipients.extend(dept_members)

        # 去重
        recipients = list(set(recipients))

        process = (
            task.work_order_process.process
            if task.work_order_process
            else None
        )
        process_code = process.code if process else None
        process_name = process.name if process else None

        self.send_notification(
            event_type=NotificationEvent.TASK_ASSIGNED,
            recipients=recipients,
            data={
                "task_id": task.id,
                "task_name": task.work_content,
                "workorder_id": (
                    task.work_order_process.work_order.id
                    if task.work_order_process
                    else None
                ),
                "workorder_number": (
                    task.work_order_process.work_order.order_number
                    if task.work_order_process
                    else ""
                ),
                "process_code": process_code,
                "process_name": process_name,
                "assigned_by": assigned_by.username if assigned_by else "系统",
                "quantity": task.production_quantity,
                "priority": (
                    task.work_order_process.work_order.priority
                    if task.work_order_process
                    else "normal"
                ),
                "deadline": (
                    task.work_order_process.planned_end_time.isoformat()
                    if task.work_order_process
                    and task.work_order_process.planned_end_time
                    else None
                ),
            },
            priority=self._map_priority(
                task.work_order_process.work_order.priority
                if task.work_order_process
                else "normal"
            ),
            channels=[
                NotificationChannel.WEBSOCKET,
                NotificationChannel.IN_APP,
            ],
        )

    def notify_task_completed(self, task, completed_by):
        """通知任务完成 - 发送给主管和施工单创建者"""
        recipients = []

        # 通知主管
        supervisors = self._get_supervisors()
        recipients.extend(supervisors)

        # 通知施工单创建者
        work_order = (
            task.work_order_process.work_order
            if task.work_order_process
            else None
        )
        if work_order and work_order.created_by:
            recipients.append(work_order.created_by)

        recipients = list(set(recipients))

        process = (
            task.work_order_process.process
            if task.work_order_process
            else None
        )
        process_code = process.code if process else None
        process_name = process.name if process else None

        self.send_notification(
            event_type=NotificationEvent.TASK_COMPLETED,
            recipients=recipients,
            data={
                "task_id": task.id,
                "task_name": task.work_content,
                "workorder_id": work_order.id if work_order else None,
                "workorder_number": (
                    work_order.order_number if work_order else ""
                ),
                "completed_by": (
                    completed_by.username if completed_by else "系统"
                ),
                "completed_at": timezone.now().isoformat(),
                "process_code": process_code,
                "process_name": process_name,
            },
            priority=NotificationPriority.NORMAL,
            channels=[
                NotificationChannel.WEBSOCKET,
                NotificationChannel.IN_APP,
            ],
        )

    def _get_department_members(self, department):
        """获取部门成员"""
        try:
            return User.objects.filter(
                profile__departments=department, is_active=True
            ).distinct()
        except Exception:
            return []

    def _map_priority(self, workorder_priority):
        """映射施工单优先级到通知优先级"""
        priority_map = {
            "urgent": NotificationPriority.URGENT,
            "high": NotificationPriority.HIGH,
            "normal": NotificationPriority.NORMAL,
            "low": NotificationPriority.LOW,
        }
        return priority_map.get(
            workorder_priority, NotificationPriority.NORMAL
        )

    def notify_workorder_approval(self, workorder, status, approved_by=None):
        """通知施工单审核结果"""
        recipients = [workorder.created_by]

        if status == "approved":
            event_type = NotificationEvent.WORKORDER_APPROVED
            priority = NotificationPriority.HIGH
        else:
            event_type = NotificationEvent.WORKORDER_REJECTED
            priority = NotificationPriority.URGENT

        self.send_notification(
            event_type=event_type,
            recipients=recipients,
            data={
                "workorder_id": workorder.id,
                "workorder_number": workorder.order_number,
                "approved_by": approved_by.username if approved_by else "系统",
                "status": status,
            },
            priority=priority,
        )

    def notify_process_completion(self, process, workorder, completed_by=None):
        """通知工序完成"""
        # 通知下一个工序的操作员
        next_process = self._get_next_process(workorder, process)
        recipients = []

        if next_process:
            # 获取下一个工序的操作员
            next_operators = self._get_process_operators(next_process)
            recipients.extend(next_operators)

        # 通知施工单创建者
        recipients.append(workorder.created_by)

        # 通知生产主管
        supervisors = self._get_supervisors()
        recipients.extend(supervisors)

        self.send_notification(
            event_type=NotificationEvent.PROCESS_COMPLETED,
            recipients=list(set(recipients)),  # 去重
            data={
                "process_id": process.id,
                "process_name": process.name,
                "workorder_id": workorder.id,
                "workorder_number": workorder.order_number,
                "completed_by": (
                    completed_by.username if completed_by else "系统"
                ),
            },
            priority=NotificationPriority.NORMAL,
        )

    def notify_deadline_warning(self, workorder, days_remaining):
        """通知交货期预警"""
        if not workorder.delivery_date:
            return
        recipients = [workorder.created_by]

        # 添加相关操作员
        operators = self._get_workorder_operators(workorder)
        recipients.extend(operators)

        # 添加主管
        supervisors = self._get_supervisors()
        recipients.extend(supervisors)

        priority = (
            NotificationPriority.URGENT
            if days_remaining <= 1
            else NotificationPriority.HIGH
        )

        self.send_notification(
            event_type=NotificationEvent.DEADLINE_WARNING,
            recipients=list(set(recipients)),
            data={
                "workorder_id": workorder.id,
                "workorder_number": workorder.order_number,
                "deadline": workorder.delivery_date.strftime("%Y-%m-%d"),
                "days_remaining": days_remaining,
            },
            priority=priority,
        )

    def _get_next_process(self, workorder, current_process):
        """获取下一个工序"""
        try:
            from ..models.core import WorkOrderProcess

            current_order = WorkOrderProcess.objects.get(
                workorder=workorder, process=current_process
            ).order

            next_process = WorkOrderProcess.objects.filter(
                workorder=workorder, order=current_order + 1
            ).first()

            return next_process.process if next_process else None

        except Exception:
            return None

    def _get_process_operators(self, process):
        """获取工序操作员"""
        try:
            return User.objects.filter(
                userprofile__department=process.department,
                userprofile__is_active=True,
            ).distinct()
        except Exception:
            return []

    def _get_workorder_operators(self, workorder):
        """获取施工单相关操作员"""
        try:
            from ..models.core import WorkOrderProcess, Process

            processes = WorkOrderProcess.objects.filter(
                workorder=workorder
            ).values_list("process", flat=True)

            departments = Process.objects.filter(id__in=processes).values_list(
                "department", flat=True
            )
            return User.objects.filter(
                userprofile__department__in=departments,
                userprofile__is_active=True,
            ).distinct()
        except Exception:
            return []

    def _get_supervisors(self):
        """获取主管列表"""
        try:
            return User.objects.filter(
                groups__name="supervisor", is_active=True
            ).distinct()
        except Exception:
            return []


class NotificationConsumer(AsyncWebsocketConsumer):
    """WebSocket通知消费者 - 处理实时通知推送"""

    async def connect(self):
        """建立WebSocket连接"""
        # 从查询参数获取 token
        query_string = self.scope.get("query_string", b"").decode("utf-8")

        query_params = parse_qs(query_string)

        # parse_qs 返回字符串键，不是字节键
        token = query_params.get("token", [None])[0]

        if not token:
            logger.warning("WebSocket 连接缺少 token")
            await self.close(code=4001, reason="Missing token")
            return

        # 验证 JWT token 并获取用户（使用 sync_to_async 包装同步 ORM 调用）
        from rest_framework_simplejwt.tokens import AccessToken
        from rest_framework_simplejwt.exceptions import TokenError

        try:
            # 解析 JWT access token
            access_token = AccessToken(token)
            user_id = access_token["user_id"]

            # 从数据库获取用户
            user = await sync_to_async(User.objects.get)(
                id=user_id, is_active=True
            )
        except TokenError as e:
            logger.warning(
                f"WebSocket JWT token 无效: {token[:10]}... - {str(e)}"
            )
            await self.close(code=4001, reason="Invalid JWT token")
            return
        except User.DoesNotExist:
            logger.warning(
                "WebSocket JWT token 中的用户不存在: "
                f"user_id={access_token.get('user_id')}"
            )
            await self.close(code=4001, reason="User not found")
            return

        if not user.is_authenticated:
            await self.close(code=4001, reason="User not authenticated")
            return

        # 设置用户信息到 scope（供后续使用）
        self.scope["user"] = user
        self.user_id = user.id
        self.group_name = f"user_{self.user_id}_notifications"

        # 加入用户通知组
        await self.channel_layer.group_add(self.group_name, self.channel_name)

        await self.accept()

        # 发送连接成功确认
        await self.send(
            json.dumps(
                {
                    "type": "connection_established",
                    "user_id": self.user_id,
                    "timestamp": timezone.now().isoformat(),
                }
            )
        )

        logger.info(f"WebSocket连接建立: user_id={self.user_id}")

    async def disconnect(self, close_code):
        """断开WebSocket连接"""
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(
                self.group_name, self.channel_name
            )
            logger.info(
                f"WebSocket连接断开: user_id={self.user_id}, code={close_code}"
            )

    async def notification_message(self, event):
        """处理通知消息 - 从channel layer接收并转发给客户端"""
        await self.send(
            text_data=json.dumps(
                {"type": "notification", "data": event.get("notification", {})}
            )
        )

    async def heartbeat_message(self, event):
        """处理心跳消息"""
        await self.send(
            text_data=json.dumps(
                {"type": "heartbeat", "timestamp": timezone.now().isoformat()}
            )
        )


class NotificationManager:
    """通知管理器"""

    @staticmethod
    def create_system_announcement(
        title: str, message: str, priority: str = NotificationPriority.NORMAL
    ):
        """创建系统公告"""
        try:
            # 获取所有活跃用户
            active_users = User.objects.filter(
                userprofile__is_active=True, is_active=True
            ).distinct()

            notification_service = RealtimeNotificationService()
            notification_service.send_notification(
                event_type=NotificationEvent.SYSTEM_ANNOUNCEMENT,
                recipients=list(active_users),
                data={
                    "title": title,
                    "message": message,
                    "type": "system_announcement",
                },
                priority=priority,
                channels=[
                    NotificationChannel.WEBSOCKET,
                    NotificationChannel.IN_APP,
                ],
            )

        except Exception as e:
            logger.error(f"创建系统公告失败: {e}")

    @staticmethod
    def send_urgent_order_alert(workorder):
        """发送紧急订单警报"""
        try:
            # 获取所有主管和操作员
            supervisors = User.objects.filter(
                groups__name="supervisor", is_active=True
            )

            # 获取相关操作员
            operators = RealtimeNotificationService()._get_workorder_operators(
                workorder
            )

            recipients = list(set(list(supervisors) + list(operators)))

            notification_service = RealtimeNotificationService()
            notification_service.send_notification(
                event_type=NotificationEvent.URGENT_ORDER,
                recipients=recipients,
                data={
                    "workorder_id": workorder.id,
                    "workorder_number": workorder.order_number,
                    "type": "urgent_order",
                },
                priority=NotificationPriority.URGENT,
                channels=[
                    NotificationChannel.WEBSOCKET,
                    NotificationChannel.EMAIL,
                    NotificationChannel.IN_APP,
                ],
            )

        except Exception as e:
            logger.error(f"发送紧急订单警报失败: {e}")


# 全局通知服务实例
notification_service = RealtimeNotificationService()
