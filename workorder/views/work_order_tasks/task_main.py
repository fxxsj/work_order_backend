"""
施工单任务主视图集

包含基础的 ViewSet 配置和核心方法。
"""

from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q
import logging

from workorder.models.core import WorkOrderTask
from workorder.serializers.core import WorkOrderTaskSerializer, TaskAssignmentSerializer
from workorder.permissions import WorkOrderTaskPermission
from workorder.services.task_assignment import TaskAssignmentService
from workorder.exceptions import BusinessLogicError, PermissionDeniedError

logger = logging.getLogger(__name__)


class BaseWorkOrderTaskViewSet(viewsets.ModelViewSet):
    """
    施工单任务基础视图集

    提供基础的 CRUD 操作和权限控制。
    """

    permission_classes = [WorkOrderTaskPermission]
    serializer_class = WorkOrderTaskSerializer
    # 优化查询：使用 select_related 和 prefetch_related 避免 N+1 查询
    queryset = WorkOrderTask.objects.select_related(
        'assigned_department',
        'assigned_operator',
        'work_order_process',
        'work_order_process__work_order',
        'work_order_process__work_order__customer',
        'work_order_process__process',
        'work_order_process__department',
        'work_order_process__operator',
        'parent_task',
        'artwork',
        'die',
        'product',
        'material',
        'foiling_plate',
        'embossing_plate',
    ).prefetch_related(
        'logs',
        'subtasks',
    ).all()
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['work_content', 'production_requirements']
    ordering_fields = ['created_at', 'updated_at', 'assigned_department', 'assigned_operator']
    ordering = ['-created_at']

    def get_queryset(self):
        """
        根据用户权限过滤查询集

        权限规则：
        - 管理员可以查看所有任务
        - 操作员只能查看自己分派的任务
        - 生产主管可以查看本部门的所有任务
        """
        queryset = super().get_queryset()
        user = self.request.user

        # 管理员可以查看所有任务
        if user.is_superuser:
            return queryset

        # 操作员只能查看自己分派的任务
        if not user.has_perm('workorder.change_workorder'):
            queryset = queryset.filter(assigned_operator=user)
        # 生产主管可以查看本部门的所有任务
        else:
            user_departments = user.profile.departments.all() if hasattr(user, 'profile') else []
            if user_departments:
                # 可以查看本部门的任务或自己创建的施工单的任务
                queryset = queryset.filter(
                    Q(assigned_department__in=user_departments) |
                    Q(work_order_process__work_order__created_by=user)
                )
            else:
                # 如果没有部门信息，只能查看自己创建的施工单的任务
                queryset = queryset.filter(work_order_process__work_order__created_by=user)

        return queryset

    def perform_update(self, serializer):
        """
        更新任务时，检查工序是否完成

        验证规则：
        - 完成数量不能超过生产数量
        - 任务完成时，检查并更新工序状态
        """
        task = serializer.save()

        # 验证完成数量不能超过生产数量
        if task.quantity_completed is not None and task.production_quantity:
            if task.quantity_completed > task.production_quantity:
                from rest_framework.exceptions import ValidationError
                raise ValidationError(
                    f'完成数量（{task.quantity_completed}）'
                    f'不能超过生产数量（{task.production_quantity}）'
                )

        # 如果任务完成，检查工序是否完成
        if task.status == 'completed':
            task.work_order_process.check_and_update_status()

    @action(detail=True, methods=['post'], url_path='assign')
    def assign(self, request, pk=None):
        """分配任务给指定操作员

        POST /workorder-tasks/{id}/assign/
        Body: {
            "operator_id": 123,
            "notes": "优先处理此任务"  # 可选
        }

        权限：
        - 任务所属部门的主管
        - 施工单创建人
        - 超级管理员
        """
        task = self.get_object()
        serializer = TaskAssignmentSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            result = TaskAssignmentService.assign_to_operator(
                task_id=task.id,
                operator_id=serializer.validated_data['operator_id'],
                assigned_by=request.user,
                notes=serializer.validated_data.get('notes', '')
            )

            # 重新获取更新后的任务数据
            task.refresh_from_db()
            response_serializer = self.get_serializer(task)

            return Response({
                'detail': '任务分配成功',
                'data': result,
                'task': response_serializer.data
            }, status=status.HTTP_200_OK)

        except (PermissionDeniedError, BusinessLogicError) as e:
            return Response({
                'detail': str(e),
                'code': e.default_code
            }, status=status.HTTP_403_FORBIDDEN if isinstance(e, PermissionDeniedError) else status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"任务分配失败: {str(e)}")
            return Response({
                'detail': '任务分配失败，请稍后重试',
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'], url_path='department-operators')
    def department_operators(self, request):
        """获取部门操作员列表

        GET /workorder-tasks/department-operators/?department_id=123

        用于任务分配时选择操作员
        """
        from workorder.models.base import Department

        department_id = request.query_params.get('department_id')
        if not department_id:
            return Response({
                'detail': '请提供 department_id 参数'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            operators = TaskAssignmentService.get_department_operators(department_id)
            return Response({
                'department_id': int(department_id),
                'operators': operators
            })
        except Department.DoesNotExist:
            return Response({
                'detail': f'部门ID {department_id} 不存在'
            }, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['post'], url_path='claim')
    def claim(self, request, pk=None):
        """操作员认领任务

        POST /workorder-tasks/{id}/claim/
        Body: {
            "notes": "我会尽快完成"  # 可选
        }

        权限：
        - 任务所属部门的操作员

        并发控制：
        使用 select_for_update 防止两个操作员同时认领同一任务
        """
        task = self.get_object()

        # 获取可选的备注
        notes = request.data.get('notes', '') if request.data else ''

        try:
            result = TaskAssignmentService.claim_task(
                task_id=task.id,
                operator=request.user,
                notes=notes
            )

            # 重新获取更新后的任务数据
            task.refresh_from_db()
            response_serializer = self.get_serializer(task)

            return Response({
                'detail': result.get('message', '任务认领成功'),
                'data': result,
                'task': response_serializer.data
            }, status=status.HTTP_200_OK)

        except BusinessLogicError as e:
            return Response({
                'detail': str(e),
                'code': e.default_code
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"任务认领失败: {str(e)}")
            return Response({
                'detail': '任务认领失败，请稍后重试',
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'], url_path='claimable')
    def claimable(self, request):
        """获取当前用户可认领的任务列表

        GET /workorder-tasks/claimable/

        返回用户所属部门中未分配操作员的任务
        """
        try:
            claimable_ids = TaskAssignmentService.get_claimable_tasks_for_user(request.user)

            # 获取完整的任务数据
            queryset = self.get_queryset().filter(id__in=claimable_ids)
            page = self.paginate_queryset(queryset)

            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response({
                    'claimable_count': len(claimable_ids),
                    'results': serializer.data
                })

            serializer = self.get_serializer(queryset, many=True)
            return Response({
                'claimable_count': len(claimable_ids),
                'results': serializer.data
            })

        except Exception as e:
            logger.error(f"获取可认领任务列表失败: {str(e)}")
            return Response({
                'detail': '获取可认领任务列表失败',
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
