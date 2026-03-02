"""
API网关服务（已弃用）

该模块与当前模型/服务实现不一致，已停止维护。
请通过 DRF ViewSet 访问接口，避免直接调用此模块。
"""

from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from ..models.core import WorkOrder, WorkOrderTask, WorkOrderProcess
from ..services.realtime_notification import notification_service
from ..response import APIResponse


def _deprecated(*_args, **_kwargs):
    raise RuntimeError("api_gateway 已弃用，请改用 DRF ViewSet 接口。")


class WorkOrderAPIService:
    """施工单API服务"""

    create_workorder = staticmethod(_deprecated)
    update_workorder = staticmethod(_deprecated)
    get_workorder_list = staticmethod(_deprecated)
    get_workorder_detail = staticmethod(_deprecated)
    approve_workorder = staticmethod(_deprecated)
    reject_workorder = staticmethod(_deprecated)


class TaskAPIService:
    """任务API服务"""

    assign_task = staticmethod(_deprecated)
    start_task = staticmethod(_deprecated)
    complete_task = staticmethod(_deprecated)
    get_my_tasks = staticmethod(_deprecated)


class ReportAPIService:
    """报表API服务"""

    get_workorder_statistics = staticmethod(_deprecated)
    get_task_statistics = staticmethod(_deprecated)


class SystemAPIService:
    """系统API服务"""

    get_system_info = staticmethod(_deprecated)
    health_check = staticmethod(_deprecated)


# 导入必要的模型
from django.db import models
