"""
施工单任务批量操作 Mixin

包含批量操作方法。
"""

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from workorder.models.core import WorkOrderTask, TaskLog
from workorder.models.system import Notification


class TaskBulkMixin:
    """
    批量操作 Mixin

    提供批量操作方法，包括批量更新数量、批量完成、批量取消、批量分派。
    """

    @action(detail=False, methods=['post'])
    def batch_update_quantity(self, request):
        """批量更新任务数量"""
        """批量更新任务完成数量
        
        请求参数：
        - task_ids: 任务ID列表（必填）
        - quantity_increment: 每个任务的增量数量（可以是列表，对应每个任务；也可以是单个值，应用到所有任务）
        - quantity_defective: 不良品数量（可选，同上）
        - notes: 备注（可选）
        """
        from workorder.models.core import TaskLog
        
        task_ids = request.data.get('task_ids', [])
        quantity_increment = request.data.get('quantity_increment')
        quantity_defective = request.data.get('quantity_defective', 0)
        notes = request.data.get('notes', '')
        
        if not task_ids:
            return Response(
                {'error': '请提供任务ID列表'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if quantity_increment is None:
            return Response(
                {'error': '请提供完成数量增量'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 获取任务
        tasks = WorkOrderTask.objects.filter(id__in=task_ids)
        if tasks.count() != len(task_ids):
            return Response(
                {'error': '部分任务不存在'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 检查权限：操作员只能更新自己分派的任务
        user = request.user
        unauthorized_tasks = []
        for task in tasks:
            # 检查权限：生产主管、任务分派的操作员、施工单创建人可以更新
            can_update = False
            if user.has_perm('workorder.change_workorder'):
                can_update = True
            elif task.assigned_operator == user:
                can_update = True
            elif task.work_order_process.work_order.created_by == user:
                can_update = True
            
            if not can_update:
                unauthorized_tasks.append(task.id)
        
        if unauthorized_tasks:
            return Response(
                {'error': f'您没有权限更新以下任务：{unauthorized_tasks}'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # 处理数量增量（支持列表或单个值）
        if isinstance(quantity_increment, list):
            if len(quantity_increment) != len(task_ids):
                return Response(
                    {'error': '数量增量列表长度必须与任务ID列表长度相同'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            increments = quantity_increment
        else:
            increments = [quantity_increment] * len(task_ids)
        
        # 处理不良品数量
        if isinstance(quantity_defective, list):
            if len(quantity_defective) != len(task_ids):
                return Response(
                    {'error': '不良品数量列表长度必须与任务ID列表长度相同'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            defectives = quantity_defective
        else:
            defectives = [quantity_defective] * len(task_ids)
        
        # 批量更新任务
        updated_tasks = []
        failed_tasks = []
        
        for task, increment, defective in zip(tasks, increments, defectives):
            try:
                # 并发控制：检查版本号
                expected_version = request.data.get('versions', {}).get(str(task.id))
                if expected_version is not None and task.version != expected_version:
                    failed_tasks.append({
                        'task_id': task.id,
                        'error': '任务已被其他操作员更新，请刷新后重试'
                    })
                    continue
                
                # 计算新的完成数量
                quantity_before = task.quantity_completed
                new_quantity_completed = quantity_before + increment
                
                # 验证数量
                if new_quantity_completed < 0:
                    failed_tasks.append({
                        'task_id': task.id,
                        'error': '更新后完成数量不能小于0'
                    })
                    continue
                
                if task.production_quantity and new_quantity_completed > task.production_quantity:
                    failed_tasks.append({
                        'task_id': task.id,
                        'error': f'更新后完成数量（{new_quantity_completed}）不能超过生产数量（{task.production_quantity}）'
                    })
                    continue
                
                # 更新任务
                task.quantity_completed = new_quantity_completed
                if defective:
                    task.quantity_defective = (task.quantity_defective or 0) + defective
                
                if notes:
                    task.production_requirements = notes
                
                # 根据数量自动判断状态
                if task.production_quantity and new_quantity_completed >= task.production_quantity:
                    task.status = 'completed'
                elif task.status == 'pending':
                    task.status = 'in_progress'
                elif task.status == 'completed' and new_quantity_completed < task.production_quantity:
                    task.status = 'in_progress'
                
                # 更新版本号
                task.version += 1
                task.save()
                
                # 记录操作日志
                TaskLog.objects.create(
                    task=task,
                    log_type='update_quantity',
                    content=f'批量更新完成数量：{quantity_before} → {new_quantity_completed}，本次完成：{increment}，不良品：{defective}' + (f'，备注：{notes}' if notes else ''),
                    quantity_before=quantity_before,
                    quantity_after=new_quantity_completed,
                    quantity_increment=increment,
                    quantity_defective_increment=defective,
                    operator=user
                )
                
                # 如果任务完成，检查工序是否完成
                if task.status == 'completed':
                    task.work_order_process.check_and_update_status()
                
                updated_tasks.append(task.id)
                
            except Exception as e:
                failed_tasks.append({
                    'task_id': task.id,
                    'error': str(e)
                })
        
        return Response({
            'message': f'成功更新 {len(updated_tasks)} 个任务，失败 {len(failed_tasks)} 个',
            'updated_count': len(updated_tasks),
            'failed_count': len(failed_tasks),
            'updated_task_ids': updated_tasks,
            'failed_tasks': failed_tasks
        })
    
    def batch_complete(self, request):
        """批量完成任务
        
        请求参数：
        - task_ids: 任务ID列表（必填）
        - completion_reason: 完成理由（可选）
        - notes: 备注（可选）
        """
        from workorder.models.core import TaskLog
        
        task_ids = request.data.get('task_ids', [])
        completion_reason = request.data.get('completion_reason', '')
        notes = request.data.get('notes', '')
        
        if not task_ids:
            return Response(
                {'error': '请提供任务ID列表'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 获取任务
        tasks = WorkOrderTask.objects.filter(id__in=task_ids)
        if tasks.count() != len(task_ids):
            return Response(
                {'error': '部分任务不存在'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 检查权限
        user = request.user
        unauthorized_tasks = []
        for task in tasks:
            can_complete = False
            if user.has_perm('workorder.change_workorder'):
                can_complete = True
            elif task.assigned_operator == user:
                can_complete = True
            elif task.work_order_process.work_order.created_by == user:
                can_complete = True
            
            if not can_complete:
                unauthorized_tasks.append(task.id)
        
        if unauthorized_tasks:
            return Response(
                {'error': f'您没有权限完成以下任务：{unauthorized_tasks}'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # 批量完成任务
        completed_tasks = []
        failed_tasks = []
        
        for task in tasks:
            try:
                # 检查任务状态
                if task.status == 'completed':
                    failed_tasks.append({
                        'task_id': task.id,
                        'error': '任务已经完成'
                    })
                    continue
                
                if task.status == 'cancelled':
                    failed_tasks.append({
                        'task_id': task.id,
                        'error': '已取消的任务无法完成'
                    })
                    continue
                
                # 记录更新前的状态和数量
                status_before = task.status
                quantity_before = task.quantity_completed
                
                # 强制设置为已完成
                task.status = 'completed'
                if notes:
                    task.production_requirements = notes
                
                # 如果完成数量为0，设置为生产数量
                if not task.quantity_completed and task.production_quantity:
                    task.quantity_completed = task.production_quantity
                
                # 更新版本号
                task.version += 1
                task.save()
                
                # 记录操作日志
                log_content = f'批量强制完成任务，完成数量：{quantity_before} → {task.quantity_completed}，状态：{status_before} → completed'
                if completion_reason:
                    log_content += f'，完成理由：{completion_reason}'
                if notes:
                    log_content += f'，备注：{notes}'
                
                TaskLog.objects.create(
                    task=task,
                    log_type='complete',
                    content=log_content,
                    quantity_before=quantity_before,
                    quantity_after=task.quantity_completed,
                    status_before=status_before,
                    status_after='completed',
                    completion_reason=completion_reason,
                    operator=user
                )
                
                # 检查工序是否完成
                task.work_order_process.check_and_update_status()
                
                completed_tasks.append(task.id)
                
            except Exception as e:
                failed_tasks.append({
                    'task_id': task.id,
                    'error': str(e)
                })
        
        return Response({
            'message': f'成功完成 {len(completed_tasks)} 个任务，失败 {len(failed_tasks)} 个',
            'completed_count': len(completed_tasks),
            'failed_count': len(failed_tasks),
            'completed_task_ids': completed_tasks,
            'failed_tasks': failed_tasks
        })
    
    def batch_cancel(self, request):
        """批量取消任务
        
        请求参数：
        - task_ids: 任务ID列表（必填）
        - cancellation_reason: 取消原因（必填）
        - notes: 备注（可选）
        """
        from workorder.models.core import TaskLog
        
        task_ids = request.data.get('task_ids', [])
        cancellation_reason = request.data.get('cancellation_reason', '').strip()
        notes = request.data.get('notes', '')
        
        if not task_ids:
            return Response(
                {'error': '请提供任务ID列表'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not cancellation_reason:
            return Response(
                {'error': '请填写取消原因'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 获取任务
        tasks = WorkOrderTask.objects.filter(id__in=task_ids)
        if tasks.count() != len(task_ids):
            return Response(
                {'error': '部分任务不存在'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 检查权限
        user = request.user
        unauthorized_tasks = []
        for task in tasks:
            can_cancel = False
            if user.has_perm('workorder.change_workorder'):
                can_cancel = True
            elif task.assigned_operator == user:
                can_cancel = True
            elif task.work_order_process.work_order.created_by == user:
                can_cancel = True
            
            if not can_cancel:
                unauthorized_tasks.append(task.id)
        
        if unauthorized_tasks:
            return Response(
                {'error': f'您没有权限取消以下任务：{unauthorized_tasks}'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # 批量取消任务
        cancelled_tasks = []
        failed_tasks = []
        
        for task in tasks:
            try:
                # 检查任务状态
                if task.status == 'cancelled':
                    failed_tasks.append({
                        'task_id': task.id,
                        'error': '任务已经取消'
                    })
                    continue
                
                if task.status == 'completed':
                    failed_tasks.append({
                        'task_id': task.id,
                        'error': '已完成的任务无法取消'
                    })
                    continue
                
                # 记录取消前的状态
                status_before = task.status
                quantity_before = task.quantity_completed
                
                # 取消任务
                task.status = 'cancelled'
                task.version += 1
                task.save()
                
                # 记录操作日志
                log_content = f'批量取消任务，原因：{cancellation_reason}'
                if notes:
                    log_content += f'，备注：{notes}'
                
                TaskLog.objects.create(
                    task=task,
                    log_type='status_change',
                    content=log_content,
                    status_before=status_before,
                    status_after='cancelled',
                    operator=user
                )
                
                # 创建取消通知
                if task.assigned_operator:
                    Notification.create_notification(
                        recipient=task.assigned_operator,
                        notification_type='task_cancelled',
                        title=f'任务已取消：{task.work_content}',
                        content=f'任务"{task.work_content}"已被取消。取消原因：{cancellation_reason}',
                        priority='normal',
                        work_order=task.work_order_process.work_order,
                        work_order_process=task.work_order_process,
                        task=task
                    )
                
                cancelled_tasks.append(task.id)
                
            except Exception as e:
                failed_tasks.append({
                    'task_id': task.id,
                    'error': str(e)
                })
        
        return Response({
            'message': f'成功取消 {len(cancelled_tasks)} 个任务，失败 {len(failed_tasks)} 个',
            'cancelled_count': len(cancelled_tasks),
            'failed_count': len(failed_tasks),
            'cancelled_task_ids': cancelled_tasks,
            'failed_tasks': failed_tasks
        })
    
    def batch_assign(self, request):
        """批量分派任务到部门和操作员
        
        请求参数：
        - task_ids: 任务ID列表（必填）
        - assigned_department: 分派部门ID（可选）
        - assigned_operator: 分派操作员ID（可选）
        - reason: 调整原因（可选）
        - notes: 备注（可选）
        """
        from workorder.models.core import TaskLog, Department
        from django.contrib.auth.models import User
        
        task_ids = request.data.get('task_ids', [])
        department_id = request.data.get('assigned_department')
        operator_id = request.data.get('assigned_operator')
        reason = request.data.get('reason', '')
        notes = request.data.get('notes', '')
        
        if not task_ids:
            return Response(
                {'error': '请提供任务ID列表'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 获取任务
        tasks = WorkOrderTask.objects.filter(id__in=task_ids)
        if tasks.count() != len(task_ids):
            return Response(
                {'error': '部分任务不存在'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 验证部门和操作员
        department = None
        if department_id:
            try:
                department = Department.objects.get(id=department_id)
            except Department.DoesNotExist:
                return Response(
                    {'error': '部门不存在'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        operator = None
        if operator_id:
            try:
                operator = User.objects.get(id=operator_id)
            except User.DoesNotExist:
                return Response(
                    {'error': '操作员不存在'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        # 批量分派任务
        assigned_tasks = []
        failed_tasks = []
        
        for task in tasks:
            try:
                # 记录调整前的状态
                old_department = task.assigned_department
                old_operator = task.assigned_operator
                changes = []
                
                # 更新分派部门
                if department_id is not None:
                    if department:
                        if task.assigned_department != department:
                            changes.append(f'部门：{old_department.name if old_department else "未分配"} → {department.name}')
                            task.assigned_department = department
                    else:
                        if task.assigned_department:
                            changes.append(f'部门：{old_department.name if old_department else "未分配"} → 未分配')
                            task.assigned_department = None
                
                # 更新分派操作员
                if operator_id is not None:
                    if operator:
                        old_operator_name = f"{old_operator.first_name}{old_operator.last_name}" if old_operator else "未分配"
                        new_operator_name = f"{operator.first_name}{operator.last_name}"
                        if task.assigned_operator != operator:
                            changes.append(f'操作员：{old_operator_name} → {new_operator_name}')
                            task.assigned_operator = operator
                    else:
                        if task.assigned_operator:
                            old_operator_name = f"{old_operator.first_name}{old_operator.last_name}" if old_operator else "未分配"
                            changes.append(f'操作员：{old_operator_name} → 未分配')
                            task.assigned_operator = None
                
                # 如果有变更，保存并记录日志
                if changes:
                    task.save()
                    
                    # 记录调整日志
                    log_content = f'批量调整任务分派：{", ".join(changes)}'
                    if reason:
                        log_content += f'，原因：{reason}'
                    if notes:
                        log_content += f'，备注：{notes}'
                    
                    TaskLog.objects.create(
                        task=task,
                        log_type='status_change',
                        content=log_content,
                        operator=request.user
                    )
                    
                    # 如果分派了新的操作员，创建通知
                    if operator and task.assigned_operator == operator:
                        Notification.create_notification(
                            recipient=operator,
                            notification_type='task_assigned',
                            title=f'新任务分派：{task.work_content}',
                            content=f'您有一个新任务：{task.work_content}（施工单：{task.work_order_process.work_order.order_number}）',
                            priority='normal',
                            work_order=task.work_order_process.work_order,
                            work_order_process=task.work_order_process,
                            task=task
                        )
                
                assigned_tasks.append(task.id)
                
            except Exception as e:
                failed_tasks.append({
                    'task_id': task.id,
                    'error': str(e)
                })
        
        return Response({
            'message': f'成功分派 {len(assigned_tasks)} 个任务，失败 {len(failed_tasks)} 个',
            'assigned_count': len(assigned_tasks),
            'failed_count': len(failed_tasks),
            'assigned_task_ids': assigned_tasks,
            'failed_tasks': failed_tasks
        })

    @action(detail=False, methods=['post'], url_path='batch-delete')
    def batch_delete(self, request):
        """批量删除任务（仅草稿状态）

        请求参数：
        - task_ids: 任务ID列表（必填）
        - reason: 删除原因（可选）

        权限：
        - 施工单创建人可以删除草稿任务
        - 超级管理员可以删除草稿任务
        """
        from workorder.models.core import TaskLog

        task_ids = request.data.get('task_ids', [])
        reason = request.data.get('reason', '批量删除')

        if not task_ids:
            return Response(
                {'error': '请提供任务ID列表'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 获取任务
        tasks = WorkOrderTask.objects.filter(id__in=task_ids)
        if tasks.count() != len(task_ids):
            return Response(
                {'error': '部分任务不存在'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = request.user
        deleted_tasks = []
        failed_tasks = []

        for task in tasks:
            try:
                # 只允许删除草稿状态的任务
                if task.status != 'draft':
                    failed_tasks.append({
                        'task_id': task.id,
                        'error': '只能删除草稿状态的任务'
                    })
                    continue

                # 权限检查：施工单创建人或超级管理员
                can_delete = False
                if user.is_superuser:
                    can_delete = True
                elif task.work_order_process.work_order.created_by == user:
                    can_delete = True

                if not can_delete:
                    failed_tasks.append({
                        'task_id': task.id,
                        'error': '您没有权限删除此任务'
                    })
                    continue

                # 记录删除前的信息
                task_id = task.id
                work_content = task.work_content

                # 删除任务
                task.delete()

                # 记录删除日志（使用 TaskLog 如果有外键关联问题则跳过）
                # 由于任务已删除，无法创建关联日志，改为在响应中记录

                deleted_tasks.append({
                    'task_id': task_id,
                    'work_content': work_content
                })

            except Exception as e:
                failed_tasks.append({
                    'task_id': task.id,
                    'error': str(e)
                })

        return Response({
            'message': f'成功删除 {len(deleted_tasks)} 个任务，失败 {len(failed_tasks)} 个',
            'deleted_count': len(deleted_tasks),
            'failed_count': len(failed_tasks),
            'deleted_tasks': deleted_tasks,
            'failed_tasks': failed_tasks
        })

