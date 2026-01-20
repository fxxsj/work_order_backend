"""
施工单任务操作 Mixin

包含单个任务的操作方法。
"""

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q
from django.utils import timezone

from workorder.models.core import WorkOrder, WorkOrderTask, TaskLog
from workorder.models.assets import Artwork, Die


class TaskActionsMixin:
    """
    任务操作 Mixin

    提供单个任务的操作方法，包括更新数量、完成任务、拆分任务等。
    """

    @action(detail=True, methods=['post'])
    def update_quantity(self, request, pk=None):
        """更新任务数量（包含业务条件验证，根据数量自动判断状态，记录操作人）"""
        from workorder.models.core import TaskLog
        
        task = self.get_object()
        
        # 权限检查：操作员只能更新自己分派的任务
        user = request.user
        if not user.is_superuser:
            if task.assigned_operator != user:
                # 检查是否是生产主管（本部门任务）
                if task.assigned_department:
                    user_departments = user.profile.departments.all() if hasattr(user, 'profile') else []
                    if task.assigned_department not in user_departments or not user.has_perm('workorder.change_workorder'):
                        # 检查是否是施工单创建人
                        if task.work_order_process.work_order.created_by != user:
                            return Response(
                                {'error': '您没有权限更新此任务。只能更新自己分派的任务或本部门的任务。'},
                                status=status.HTTP_403_FORBIDDEN
                            )
                else:
                    # 任务未分派，只有施工单创建人可以更新
                    if task.work_order_process.work_order.created_by != user:
                        return Response(
                            {'error': '您没有权限更新此任务。只能更新自己分派的任务或本部门的任务。'},
                            status=status.HTTP_403_FORBIDDEN
                        )
        
        from workorder.process_codes import ProcessCodes
        
        # 并发控制：检查版本号（乐观锁）
        expected_version = request.data.get('version')
        if expected_version is not None:
            if task.version != expected_version:
                return Response(
                    {'error': '任务已被其他操作员更新，请刷新后重试', 'current_version': task.version},
                    status=status.HTTP_409_CONFLICT
                )
        
        work_order_process = task.work_order_process
        work_order = work_order_process.work_order
        process_code = work_order_process.process.code
        
        # 获取前端传递的数据
        quantity_increment = request.data.get('quantity_increment')
        quantity_defective = request.data.get('quantity_defective', 0)
        notes = request.data.get('notes', '')
        artwork_ids = request.data.get('artwork_ids', [])
        die_ids = request.data.get('die_ids', [])
        
        if quantity_increment is None:
            return Response(
                {'error': '请提供本次完成数量'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 计算新的完成数量（增量更新）
        quantity_before = task.quantity_completed
        new_quantity_completed = quantity_before + quantity_increment
        
        # 业务条件验证：制版任务需图稿/刀模等已确认
        if task.task_type == 'plate_making':
            if task.artwork and not task.artwork.confirmed:
                return Response(
                    {'error': '图稿未确认，无法更新任务'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if task.die and not task.die.confirmed:
                return Response(
                    {'error': '刀模未确认，无法更新任务'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if task.foiling_plate and not task.foiling_plate.confirmed:
                return Response(
                    {'error': '烫金版未确认，无法更新任务'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if task.embossing_plate and not task.embossing_plate.confirmed:
                return Response(
                    {'error': '压凸版未确认，无法更新任务'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # 业务条件验证：开料任务需物料状态满足条件
        if task.task_type == 'cutting' and task.material:
            work_order_material = work_order.materials.filter(material=task.material).first()
            if work_order_material:
                if ProcessCodes.requires_material_cut_status(process_code):
                    if work_order_material.purchase_status != 'cut':
                        return Response(
                            {'error': '物料未开料，无法更新开料任务'},
                            status=status.HTTP_400_BAD_REQUEST
                        )
        
        # 验证增量数量
        if new_quantity_completed < 0:
            return Response(
                {'error': '更新后完成数量不能小于0'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if task.production_quantity and new_quantity_completed > task.production_quantity:
            return Response(
                {'error': f'更新后完成数量（{new_quantity_completed}）不能超过生产数量（{task.production_quantity}）'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 记录更新前的状态和数量
        status_before = task.status
        
        # 处理设计图稿/设计刀模任务
        is_design_task = '设计图稿' in task.work_content or '更新图稿' in task.work_content
        is_die_design_task = '设计刀模' in task.work_content or '更新刀模' in task.work_content
        
        if is_design_task:
            if not artwork_ids or len(artwork_ids) == 0:
                return Response(
                    {'error': '请至少选择一个图稿'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            artworks = Artwork.objects.filter(id__in=artwork_ids)
            if artworks.count() != len(artwork_ids):
                return Response(
                    {'error': '部分图稿不存在'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            work_order.artworks.add(*artworks)
            task.artwork = artworks.first()
        elif is_die_design_task:
            if not die_ids or len(die_ids) == 0:
                return Response(
                    {'error': '请至少选择一个刀模'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            dies = Die.objects.filter(id__in=die_ids)
            if dies.count() != len(die_ids):
                return Response(
                    {'error': '部分刀模不存在'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            work_order.dies.add(*dies)
            task.die = dies.first()
        
        # 更新任务数量（增量更新）
        task.quantity_completed = new_quantity_completed
        
        # 更新不良品数量
        if quantity_defective is not None:
            task.quantity_defective = (task.quantity_defective or 0) + quantity_defective
        
        if notes:
            task.production_requirements = notes
        
        # 根据数量自动判断状态
        if task.production_quantity and new_quantity_completed >= task.production_quantity:
            task.status = 'completed'
        else:
            if task.status == 'pending':
                task.status = 'in_progress'
            elif task.status == 'completed' and new_quantity_completed < task.production_quantity:
                task.status = 'in_progress'
        
        # 保存任务
        task.save()
        
        # 如果是包装任务，调整库存差异
        stock_increment = new_quantity_completed - (task.stock_accounted_quantity or 0)
        if stock_increment != 0 and task.product:
            try:
                if stock_increment > 0:
                    task.product.add_stock(
                        quantity=stock_increment,
                        user=None,
                        reason=f'施工单{work_order.order_number}包装任务数量编辑，入库{stock_increment}{task.product.unit}'
                    )
                else:
                    try:
                        task.product.reduce_stock(
                            quantity=abs(stock_increment),
                            user=None,
                            reason=f'施工单{work_order.order_number}包装任务数量编辑，出库{abs(stock_increment)}{task.product.unit}'
                        )
                    except ValueError as e:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.warning(f"库存不足警告：{e}")
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"调整产品库存失败：{e}")
            
            # 更新已计入库存的数量
            task.stock_accounted_quantity = new_quantity_completed
            task.save(update_fields=['stock_accounted_quantity'])
        
        # 记录操作日志
        defective_increment = quantity_defective if quantity_defective else 0
        TaskLog.objects.create(
            task=task,
            log_type='update_quantity',
            content=f'更新完成数量：{quantity_before} → {new_quantity_completed}，本次完成：{quantity_increment}，不良品：{defective_increment}，状态：{status_before} → {task.status}' + (f'，备注：{notes}' if notes else ''),
            quantity_before=quantity_before,
            quantity_after=new_quantity_completed,
            quantity_increment=quantity_increment,
            quantity_defective_increment=defective_increment,
            status_before=status_before,
            status_after=task.status,
            operator=request.user
        )
        
        # 如果是子任务，更新父任务
        if task.is_subtask() and task.parent_task:
            task.parent_task.update_from_subtasks()
        
        # 检查工序是否完成
        task.work_order_process.check_and_update_status()
        
        serializer = self.get_serializer(task)
        return Response(serializer.data)
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """强制完成任务（用于完成数量小于生产数量但需要强制标志为已完成的情况）"""
        from workorder.models.core import TaskLog
        
        task = self.get_object()
        
        # 权限检查：操作员只能完成自己分派的任务
        user = request.user
        if not user.is_superuser:
            if task.assigned_operator != user:
                # 检查是否是生产主管（本部门任务）
                if task.assigned_department:
                    user_departments = user.profile.departments.all() if hasattr(user, 'profile') else []
                    if task.assigned_department not in user_departments or not user.has_perm('workorder.change_workorder'):
                        # 检查是否是施工单创建人
                        if task.work_order_process.work_order.created_by != user:
                            return Response(
                                {'error': '您没有权限完成此任务。只能完成自己分派的任务或本部门的任务。'},
                                status=status.HTTP_403_FORBIDDEN
                            )
                else:
                    # 任务未分派，只有施工单创建人可以完成
                    if task.work_order_process.work_order.created_by != user:
                        return Response(
                            {'error': '您没有权限完成此任务。只能完成自己分派的任务或本部门的任务。'},
                            status=status.HTTP_403_FORBIDDEN
                        )
        
        from workorder.process_codes import ProcessCodes
        
        # 并发控制：检查版本号（乐观锁）
        expected_version = request.data.get('version')
        if expected_version is not None:
            if task.version != expected_version:
                return Response(
                    {'error': '任务已被其他操作员更新，请刷新后重试', 'current_version': task.version},
                    status=status.HTTP_409_CONFLICT
                )
        
        work_order_process = task.work_order_process
        work_order = work_order_process.work_order
        process_code = work_order_process.process.code
        
        # 获取前端传递的数据
        completion_reason = request.data.get('completion_reason', '')
        quantity_defective = request.data.get('quantity_defective', 0)  # 不良品数量
        notes = request.data.get('notes', '')
        artwork_ids = request.data.get('artwork_ids', [])
        die_ids = request.data.get('die_ids', [])
        
        # 业务条件验证：制版任务需图稿/刀模等已确认
        if task.task_type == 'plate_making' and task.artwork:
            if not task.artwork.confirmed:
                return Response(
                    {'error': '图稿未确认，无法完成任务'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # 业务条件验证：制版任务需图稿/刀模等已确认
        if task.task_type == 'plate_making':
            if task.artwork and not task.artwork.confirmed:
                return Response(
                    {'error': '图稿未确认，无法完成任务'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if task.die and not task.die.confirmed:
                return Response(
                    {'error': '刀模未确认，无法完成任务'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if task.foiling_plate and not task.foiling_plate.confirmed:
                return Response(
                    {'error': '烫金版未确认，无法完成任务'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if task.embossing_plate and not task.embossing_plate.confirmed:
                return Response(
                    {'error': '压凸版未确认，无法完成任务'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # 业务条件验证：开料任务需物料状态满足条件
        if task.task_type == 'cutting' and task.material:
            work_order_material = work_order.materials.filter(material=task.material).first()
            if work_order_material:
                if ProcessCodes.requires_material_cut_status(process_code):
                    if work_order_material.purchase_status != 'cut':
                        return Response(
                            {'error': '物料未开料，无法完成开料任务'},
                            status=status.HTTP_400_BAD_REQUEST
                        )
        
        # 记录更新前的状态和数量
        status_before = task.status
        quantity_before = task.quantity_completed
        
        # 处理设计图稿/设计刀模任务
        # 注意：设计不属于施工单工序，设计任务通过其他系统管理
        # 以下逻辑用于兼容可能已存在的设计任务（手动创建或历史数据）
        is_design_task = '设计图稿' in task.work_content or '更新图稿' in task.work_content
        is_die_design_task = '设计刀模' in task.work_content or '更新刀模' in task.work_content
        
        if is_design_task:
            if not artwork_ids or len(artwork_ids) == 0:
                return Response(
                    {'error': '请至少选择一个图稿'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            from workorder.models.assets import Artwork
            artworks = Artwork.objects.filter(id__in=artwork_ids)
            if artworks.count() != len(artwork_ids):
                return Response(
                    {'error': '部分图稿不存在'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            work_order.artworks.add(*artworks)
            task.artwork = artworks.first()
        elif is_die_design_task:
            if not die_ids or len(die_ids) == 0:
                return Response(
                    {'error': '请至少选择一个刀模'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            from workorder.models.assets import Die
            dies = Die.objects.filter(id__in=die_ids)
            if dies.count() != len(die_ids):
                return Response(
                    {'error': '部分刀模不存在'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            work_order.dies.add(*dies)
            task.die = dies.first()
        
        # 强制设置为已完成（不根据数量判断）
        task.status = 'completed'
        if notes:
            task.production_requirements = notes

        # 制版任务：完成数量固定为1
        if task.task_type == 'plate_making':
            task.quantity_completed = 1
        else:
            # 其他任务：完成数量自动更新为生产数量
            task.quantity_completed = task.production_quantity

        # 更新不良品数量（如果提供了）
        if quantity_defective is not None:
            task.quantity_defective = quantity_defective

        # 保存任务（模型会自动处理版本号）
        task.save()
        
        # 计算数量增量
        quantity_increment = task.quantity_completed - quantity_before
        defective_increment = quantity_defective if quantity_defective else 0
        
        # 记录操作日志（增强协作追踪）
        log_content = f'强制完成任务，完成数量：{quantity_before} → {task.quantity_completed}，不良品：{defective_increment}，状态：{status_before} → completed'
        if quantity_increment != 0:
            log_content += f'，本次完成：{quantity_increment}'
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
            quantity_increment=quantity_increment,
            quantity_defective_increment=defective_increment,
            status_before=status_before,
            status_after='completed',
            completion_reason=completion_reason,
            operator=request.user
        )
        
        # 如果是子任务，更新父任务
        if task.is_subtask() and task.parent_task:
            task.parent_task.update_from_subtasks()
        
        # 检查工序是否完成
        task.work_order_process.check_and_update_status()
        
        serializer = self.get_serializer(task)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def split(self, request, pk=None):
        """拆分任务为多个子任务（支持多人协作）
        
        请求参数：
        - splits: 子任务列表，每个子任务包含：
          - production_quantity: 生产数量
          - assigned_department: 分派部门ID（可选）
          - assigned_operator: 分派操作员ID（可选）
          - work_content: 工作内容（可选，默认使用父任务内容）
        """
        from workorder.models.core import WorkOrderTask, TaskLog
        
        task = self.get_object()
        
        # 检查任务是否已经拆分
        if task.subtasks.exists():
            return Response(
                {'error': '该任务已经拆分，无法再次拆分'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 检查任务是否已完成
        if task.status == 'completed':
            return Response(
                {'error': '已完成的任务无法拆分'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        splits = request.data.get('splits', [])
        if not splits or len(splits) < 2:
            return Response(
                {'error': '至少需要拆分为2个子任务'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 验证拆分数量总和不超过父任务数量
        total_split_quantity = sum(s.get('production_quantity', 0) for s in splits)
        if total_split_quantity > task.production_quantity:
            return Response(
                {'error': f'子任务数量总和（{total_split_quantity}）不能超过父任务数量（{task.production_quantity}）'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 创建子任务
        created_subtasks = []
        for idx, split_data in enumerate(splits):
            production_quantity = split_data.get('production_quantity', 0)
            if production_quantity <= 0:
                return Response(
                    {'error': f'第{idx+1}个子任务的生产数量必须大于0'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # 获取分派信息
            assigned_department_id = split_data.get('assigned_department')
            assigned_operator_id = split_data.get('assigned_operator')
            work_content = split_data.get('work_content', f"{task.work_content}（子任务{idx+1}）")
            
            # 创建子任务
            subtask = WorkOrderTask.objects.create(
                work_order_process=task.work_order_process,
                task_type=task.task_type,
                work_content=work_content,
                production_quantity=production_quantity,
                quantity_completed=0,
                quantity_defective=0,
                parent_task=task,
                assigned_department_id=assigned_department_id,
                assigned_operator_id=assigned_operator_id,
                artwork=task.artwork,
                die=task.die,
                product=task.product,
                material=task.material,
                foiling_plate=task.foiling_plate,
                embossing_plate=task.embossing_plate,
                production_requirements=task.production_requirements,
                status='pending',
                auto_calculate_quantity=task.auto_calculate_quantity
            )
            created_subtasks.append(subtask)
        
        # 将父任务状态设置为进行中（因为已拆分）
        if task.status == 'pending':
            task.status = 'in_progress'
            task.version += 1
            task.save()
        
        # 记录拆分日志
        TaskLog.objects.create(
            task=task,
            log_type='status_change',
            content=f'任务已拆分为{len(created_subtasks)}个子任务，子任务数量总和：{total_split_quantity}',
            operator=request.user
        )
        
        serializer = self.get_serializer(task)
        return Response({
            'message': f'任务已成功拆分为{len(created_subtasks)}个子任务',
            'parent_task': serializer.data,
            'subtasks_count': len(created_subtasks)
        }, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def assign(self, request, pk=None):
        """分派任务到部门和操作员（支持调整分派）
        
        使用场景：
        - 自动分派后需要调整（如从包装车间调整为外协车间）
        - 手动调整任务分派
        - 记录调整原因和备注
        """
        from workorder.models.core import TaskLog
        
        task = self.get_object()
        department_id = request.data.get('assigned_department')
        operator_id = request.data.get('assigned_operator')
        reason = request.data.get('reason', '')  # 调整原因
        notes = request.data.get('notes', '')  # 备注
        
        # 记录调整前的状态
        old_department = task.assigned_department
        old_operator = task.assigned_operator
        changes = []
        
        # 更新分派部门
        if department_id is not None:
            if department_id:
                try:
                    from workorder.models.base import Department
                    department = Department.objects.get(id=department_id)
                    if task.assigned_department != department:
                        changes.append(f'部门：{old_department.name if old_department else "未分配"} → {department.name}')
                        task.assigned_department = department
                except Department.DoesNotExist:
                    return Response(
                        {'error': '部门不存在'},
                        status=status.HTTP_404_NOT_FOUND
                    )
            else:
                if task.assigned_department:
                    changes.append(f'部门：{old_department.name if old_department else "未分配"} → 未分配')
                    task.assigned_department = None
        
        # 更新分派操作员
        if operator_id is not None:
            if operator_id:
                try:
                    from django.contrib.auth.models import User
                    operator = User.objects.get(id=operator_id)
                    old_operator_name = f"{old_operator.first_name}{old_operator.last_name}" if old_operator else "未分配"
                    new_operator_name = f"{operator.first_name}{operator.last_name}"
                    if task.assigned_operator != operator:
                        changes.append(f'操作员：{old_operator_name} → {new_operator_name}')
                        task.assigned_operator = operator
                except User.DoesNotExist:
                    return Response(
                        {'error': '操作员不存在'},
                        status=status.HTTP_404_NOT_FOUND
                    )
            else:
                if task.assigned_operator:
                    old_operator_name = f"{old_operator.first_name}{old_operator.last_name}" if old_operator else "未分配"
                    changes.append(f'操作员：{old_operator_name} → 未分配')
                    task.assigned_operator = None
        
        # 如果有变更，保存并记录日志
        if changes:
            task.save()
            
            # 记录调整日志
            log_content = f'调整任务分派：{", ".join(changes)}'
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
        
        serializer = self.get_serializer(task)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """取消任务
        
        请求参数：
        - cancellation_reason: 取消原因（必填）
        - notes: 备注（可选）
        
        权限控制：
        - 只有生产主管、创建人或任务分派的操作员可以取消任务
        - 已开始的任务需要特殊权限才能取消
        """
        from workorder.models.core import TaskLog
        from django.contrib.auth.models import User
        
        task = self.get_object()
        cancellation_reason = request.data.get('cancellation_reason', '').strip()
        notes = request.data.get('notes', '')
        
        # 验证取消原因
        if not cancellation_reason:
            return Response(
                {'error': '请填写取消原因'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 检查任务状态
        if task.status == 'cancelled':
            return Response(
                {'error': '任务已经取消，无法重复取消'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if task.status == 'completed':
            return Response(
                {'error': '已完成的任务无法取消'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 权限检查：生产主管、创建人或任务分派的操作员可以取消
        # 这里简化处理，实际可以根据用户角色和部门进行更细粒度的控制
        user = request.user
        can_cancel = False
        
        # 检查是否为生产主管（简化：检查用户是否有管理权限）
        if user.has_perm('workorder.change_workorder'):
            can_cancel = True
        # 检查是否为任务分派的操作员
        elif task.assigned_operator == user:
            can_cancel = True
        # 检查是否为施工单创建人
        elif task.work_order_process.work_order.created_by == user:
            can_cancel = True
        
        if not can_cancel:
            return Response(
                {'error': '您没有权限取消此任务'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # 检查是否会影响工序完成状态
        work_order_process = task.work_order_process
        # 如果工序只有一个任务且该任务被取消，工序无法完成
        if work_order_process.tasks.count() == 1:
            # 如果工序状态不是pending，需要特殊处理
            if work_order_process.status != 'pending':
                return Response(
                    {'error': '该任务是工序的唯一任务，取消后工序无法完成。请先处理工序状态'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # 记录取消前的状态
        status_before = task.status
        quantity_before = task.quantity_completed
        
        # 取消任务
        task.status = 'cancelled'
        task.version += 1
        task.save()
        
        # 记录操作日志
        log_content = f'取消任务，原因：{cancellation_reason}'
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
        
        # 创建任务取消通知
        if task.assigned_operator:
            Notification.create_notification(
                recipient=task.assigned_operator,
                notification_type='task_cancelled',
                title=f'任务已取消：{task.work_content}',
                content=f'任务"{task.work_content}"已被取消。取消原因：{cancellation_reason}',
                priority='normal',
                work_order=work_order_process.work_order,
                work_order_process=work_order_process,
                task=task
            )
        
        # 检查工序状态：如果所有任务都取消或完成，需要更新工序状态
        remaining_tasks = work_order_process.tasks.exclude(status='cancelled')
        if not remaining_tasks.exists():
            # 所有任务都已取消或完成，工序状态需要调整
            if work_order_process.status == 'in_progress':
                # 如果工序进行中但没有可用任务，可能需要暂停或取消工序
                # 这里暂时不自动处理，由用户手动处理
                pass
        
        serializer = self.get_serializer(task)
        return Response({
            'message': '任务已成功取消',
            'task': serializer.data
        })
    
