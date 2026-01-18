"""
业务逻辑重构服务

提供统一的业务逻辑入口，分离业务逻辑和视图逻辑
"""

from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from django.db import transaction
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError

from ..models.core import (
    WorkOrder, WorkOrderProcess, WorkOrderTask, WorkOrderProduct,
    WorkOrderMaterial, ProcessLog, TaskLog
)
from ..models.base import Customer, Department, Process
from ..models.products import Product, ProductMaterial
from ..models.materials import Material
from ..models.assets import Artwork, Die, FoilingPlate, EmbossingPlate
from ..models.system import UserProfile, WorkOrderApprovalLog, Notification


class WorkOrderBusinessService:
    """施工单业务逻辑服务"""
    
    @staticmethod
    @transaction.atomic
    def create_workorder(data: Dict[str, Any], created_by: User) -> WorkOrder:
        """
        创建施工单的业务逻辑
        
        Args:
            data: 施工单数据
            created_by: 创建人
            
        Returns:
            WorkOrder: 创建的施工单对象
            
        Raises:
            ValidationError: 验证失败时抛出
        """
        # 数据验证
        WorkOrderBusinessService._validate_workorder_data(data)
        
        # 计算总金额
        total_amount = WorkOrderBusinessService._calculate_total_amount(data)
        
        # 创建施工单
        workorder = WorkOrder.objects.create(
            order_number=data['order_number'],
            customer=data.get('customer'),
            total_amount=total_amount,
            priority=data.get('priority', 'normal'),
            deadline=data.get('deadline'),
            remarks=data.get('remarks', ''),
            created_by=created_by,
            status='pending'
        )
        
        # 创建施工单工序
        if 'processes' in data:
            WorkOrderBusinessService._create_workorder_processes(workorder, data['processes'])
        
        # 创建施工单产品
        if 'products' in data:
            WorkOrderBusinessService._create_workorder_products(workorder, data['products'])
        
        # 创建施工单物料
        if 'materials' in data:
            WorkOrderBusinessService._create_workorder_materials(workorder, data['materials'])
        
        # 自动生成任务
        WorkOrderBusinessService._generate_tasks(workorder, created_by)
        
        # 记录操作日志
        WorkOrderApprovalLog.objects.create(
            work_order=workorder,
            action_type='create',
            action_by=created_by,
            comments='施工单创建'
        )
        
        return workorder
    
    @staticmethod
    @transaction.atomic
    def update_workorder(workorder: WorkOrder, data: Dict[str, Any], updated_by: User) -> WorkOrder:
        """
        更新施工单的业务逻辑
        
        Args:
            workorder: 要更新的施工单
            data: 更新数据
            updated_by: 更新人
            
        Returns:
            WorkOrder: 更新后的施工单对象
            
        Raises:
            ValidationError: 验证失败时抛出
        """
        # 检查编辑权限
        WorkOrderBusinessService._check_edit_permission(workorder, updated_by)
        
        # 数据验证
        WorkOrderBusinessService._validate_workorder_data(data, is_update=True)
        
        # 保存更新前的状态
        old_data = {
            'customer_id': workorder.customer_id,
            'total_amount': workorder.total_amount,
            'priority': workorder.priority,
            'deadline': workorder.deadline,
            'status': workorder.status
        }
        
        # 更新基本字段
        for field, value in data.items():
            if hasattr(workorder, field) and value is not None:
                setattr(workorder, field, value)
        
        # 重新计算总金额
        if 'products' in data or 'materials' in data:
            workorder.total_amount = WorkOrderBusinessService._calculate_total_amount({
                'products': data.get('products', []),
                'materials': data.get('materials', [])
            })
        
        workorder.save()
        
        # 更新关联数据
        if 'processes' in data:
            WorkOrderBusinessService._update_workorder_processes(workorder, data['processes'])
        
        if 'products' in data:
            WorkOrderBusinessService._update_workorder_products(workorder, data['products'])
        
        if 'materials' in data:
            WorkOrderBusinessService._update_workorder_materials(workorder, data['materials'])
        
        # 记录操作日志
        WorkOrderApprovalLog.objects.create(
            work_order=workorder,
            action_type='update',
            action_by=updated_by,
            comments=f'施工单更新: {WorkOrderBusinessService._get_changed_fields(old_data, data)}'
        )
        
        return workorder
    
    @staticmethod
    def approve_workorder(workorder: WorkOrder, approved_by: User, comments: str = '') -> bool:
        """
        审核施工单
        
        Args:
            workorder: 要审核的施工单
            approved_by: 审核人
            comments: 审核意见
            
        Returns:
            bool: 是否成功
        """
        if workorder.approval_status != 'pending':
            raise ValidationError('只有待审核的订单可以审核')
        
        workorder.approval_status = 'approved'
        workorder.approved_by = approved_by
        workorder.approved_at = timezone.now()
        workorder.save()
        
        # 记录审核日志
        WorkOrderApprovalLog.objects.create(
            work_order=workorder,
            action_type='approve',
            action_by=approved_by,
            comments=comments
        )
        
        return True
    
    @staticmethod
    def reject_workorder(workorder: WorkOrder, rejected_by: User, comments: str = '') -> bool:
        """
        拒绝施工单
        
        Args:
            workorder: 要拒绝的施工单
            rejected_by: 拒绝人
            comments: 拒绝理由
            
        Returns:
            bool: 是否成功
        """
        if workorder.approval_status != 'pending':
            raise ValidationError('只有待审核的订单可以拒绝')
        
        workorder.approval_status = 'rejected'
        workorder.approved_by = rejected_by
        workorder.approved_at = timezone.now()
        workorder.save()
        
        # 记录审核日志
        WorkOrderApprovalLog.objects.create(
            work_order=workorder,
            action_type='reject',
            action_by=rejected_by,
            comments=comments
        )
        
        return True
    
    @staticmethod
    def start_workorder(workorder: WorkOrder, started_by: User) -> bool:
        """
        开始施工单
        
        Args:
            workorder: 要开始的施工单
            started_by: 开始人
            
        Returns:
            bool: 是否成功
        """
        if workorder.status != 'pending':
            raise ValidationError('只有待开始的施工单可以开始')
        
        workorder.status = 'in_progress'
        workorder.started_at = timezone.now()
        workorder.save()
        
        # 记录操作日志
        WorkOrderApprovalLog.objects.create(
            work_order=workorder,
            action_type='start',
            action_by=started_by,
            comments='开始施工'
        )
        
        return True
    
    @staticmethod
    def complete_workorder(workorder: WorkOrder, completed_by: User) -> bool:
        """
        完成施工单
        
        Args:
            workorder: 要完成的施工单
            completed_by: 完成人
            
        Returns:
            bool: 是否成功
        """
        if workorder.status != 'in_progress':
            raise ValidationError('只有进行中的施工单可以完成')
        
        # 检查所有工序是否完成
        incomplete_processes = WorkOrderProcess.objects.filter(
            work_order=workorder,
            status__in=['pending', 'in_progress']
        ).exists()
        
        if incomplete_processes:
            raise ValidationError('还有未完成的工序，无法完成施工单')
        
        workorder.status = 'completed'
        workorder.completed_at = timezone.now()
        workorder.save()
        
        # 记录操作日志
        WorkOrderApprovalLog.objects.create(
            work_order=workorder,
            action_type='complete',
            action_by=completed_by,
            comments='完成施工'
        )
        
        return True
    
    @staticmethod
    def _validate_workorder_data(data: Dict[str, Any], is_update: bool = False) -> None:
        """验证施工单数据"""
        if not is_update or 'order_number' in data:
            order_number = data.get('order_number')
            if not order_number:
                raise ValidationError('施工单号不能为空')
            
            if WorkOrder.objects.filter(order_number=order_number).exists():
                raise ValidationError('施工单号已存在')
        
        deadline = data.get('deadline')
        if deadline and deadline <= timezone.now().date():
            raise ValidationError('交货日期必须大于当前日期')
        
        priority = data.get('priority')
        if priority and priority not in ['low', 'normal', 'high', 'urgent']:
            raise ValidationError('优先级无效')
    
    @staticmethod
    def _calculate_total_amount(data: Dict[str, Any]) -> float:
        """计算施工单总金额"""
        total = 0.0
        
        # 产品金额
        for product_data in data.get('products', []):
            product_id = product_data.get('product_id')
            quantity = product_data.get('quantity', 1)
            
            try:
                product = Product.objects.get(id=product_id)
                total += float(product.price or 0) * quantity
            except Product.DoesNotExist:
                continue
        
        # 物料金额
        for material_data in data.get('materials', []):
            material_id = material_data.get('material_id')
            quantity = material_data.get('quantity', 1)
            
            try:
                material = Material.objects.get(id=material_id)
                total += float(material.unit_price or 0) * quantity
            except Material.DoesNotExist:
                continue
        
        return total
    
    @staticmethod
    def _create_workorder_processes(workorder: WorkOrder, processes_data: List[Dict[str, Any]]) -> None:
        """创建施工单工序"""
        for i, process_data in enumerate(processes_data, 1):
            process_id = process_data.get('process_id')
            try:
                process = Process.objects.get(id=process_id)
                WorkOrderProcess.objects.create(
                    work_order=workorder,
                    process=process,
                    order=i,
                    estimated_hours=process_data.get('estimated_hours', process.standard_hours),
                    status='pending'
                )
            except Process.DoesNotExist:
                continue
    
    @staticmethod
    def _create_workorder_products(workorder: WorkOrder, products_data: List[Dict[str, Any]]) -> None:
        """创建施工单产品"""
        for product_data in products_data:
            product_id = product_data.get('product_id')
            quantity = product_data.get('quantity', 1)
            
            try:
                product = Product.objects.get(id=product_id)
                WorkOrderProduct.objects.create(
                    work_order=workorder,
                    product=product,
                    quantity=quantity,
                    unit_price=product.price,
                    total_price=float(product.price or 0) * quantity
                )
            except Product.DoesNotExist:
                continue
    
    @staticmethod
    def _create_workorder_materials(workorder: WorkOrder, materials_data: List[Dict[str, Any]]) -> None:
        """创建施工单物料"""
        for material_data in materials_data:
            material_id = material_data.get('material_id')
            quantity = material_data.get('quantity', 1)
            
            try:
                material = Material.objects.get(id=material_id)
                WorkOrderMaterial.objects.create(
                    work_order=workorder,
                    material=material,
                    quantity=quantity,
                    unit_price=material.unit_price,
                    total_price=float(material.unit_price or 0) * quantity
                )
            except Material.DoesNotExist:
                continue
    
    @staticmethod
    def _update_workorder_processes(workorder: WorkOrder, processes_data: List[Dict[str, Any]]) -> None:
        """更新施工单工序"""
        # 删除现有工序
        WorkOrderProcess.objects.filter(work_order=workorder).delete()
        
        # 重新创建
        WorkOrderBusinessService._create_workorder_processes(workorder, processes_data)
    
    @staticmethod
    def _update_workorder_products(workorder: WorkOrder, products_data: List[Dict[str, Any]]) -> None:
        """更新施工单产品"""
        # 删除现有产品
        WorkOrderProduct.objects.filter(work_order=workorder).delete()
        
        # 重新创建
        WorkOrderBusinessService._create_workorder_products(workorder, products_data)
    
    @staticmethod
    def _update_workorder_materials(workorder: WorkOrder, materials_data: List[Dict[str, Any]]) -> None:
        """更新施工单物料"""
        # 删除现有物料
        WorkOrderMaterial.objects.filter(work_order=workorder).delete()
        
        # 重新创建
        WorkOrderBusinessService._create_workorder_materials(workorder, materials_data)
    
    @staticmethod
    def _generate_tasks(workorder: WorkOrder, created_by: User) -> None:
        """自动生成任务"""
        processes = WorkOrderProcess.objects.filter(work_order=workorder)
        
        for workorder_process in processes:
            # 根据工序类型生成不同任务
            task_name = f"{workorder_process.process.name}任务"
            
            WorkOrderTask.objects.create(
                workorder=workorder,
                process=workorder_process.process,
                task_name=task_name,
                task_type=workorder_process.process.process_type,
                estimated_duration=workorder_process.estimated_hours,
                deadline=workorder.deadline,
                status='ready',
                created_by=created_by
            )
    
    @staticmethod
    def _check_edit_permission(workorder: WorkOrder, user: User) -> None:
        """检查编辑权限"""
        # 如果是已审核的订单，需要特殊权限
        if workorder.approval_status == 'approved':
            if not user.has_perm('workorder.change_approved_workorder'):
                raise ValidationError('没有权限编辑已审核的施工单')
    
    @staticmethod
    def _get_changed_fields(old_data: Dict[str, Any], new_data: Dict[str, Any]) -> str:
        """获取变更字段"""
        changed_fields = []
        
        for field, new_value in new_data.items():
            if field in old_data:
                old_value = old_data[field]
                if old_value != new_value:
                    changed_fields.append(f"{field}: {old_value} -> {new_value}")
        
        return '; '.join(changed_fields) if changed_fields else '无字段变更'


class TaskBusinessService:
    """任务业务逻辑服务"""
    
    @staticmethod
    @transaction.atomic
    def assign_task(task: WorkOrderTask, assigned_to: User, assigned_by: User) -> bool:
        """
        分配任务
        
        Args:
            task: 要分配的任务
            assigned_to: 分配给谁
            assigned_by: 分配人
            
        Returns:
            bool: 是否成功
        """
        if task.status not in ['pending', 'ready']:
            raise ValidationError('只有待分配的任务可以分配')
        
        task.assigned_to = assigned_to
        task.status = 'pending'
        task.assigned_at = timezone.now()
        task.save()
        
        # 记录任务日志
        TaskLog.objects.create(
            task=task,
            action_type='assign',
            action_by=assigned_by,
            comments=f'任务分配给 {assigned_to.username}'
        )
        
        return True
    
    @staticmethod
    @transaction.atomic
    def start_task(task: WorkOrderTask, started_by: User) -> bool:
        """
        开始任务
        
        Args:
            task: 要开始的任务
            started_by: 开始人
            
        Returns:
            bool: 是否成功
        """
        if task.status != 'pending':
            raise ValidationError('只有待处理的任务可以开始')
        
        if task.assigned_to != started_by:
            raise ValidationError('只有任务分配人可以开始任务')
        
        task.status = 'in_progress'
        task.started_at = timezone.now()
        task.save()
        
        # 记录任务日志
        TaskLog.objects.create(
            task=task,
            action_type='start',
            action_by=started_by,
            comments='任务开始执行'
        )
        
        return True
    
    @staticmethod
    @transaction.atomic
    def complete_task(task: WorkOrderTask, completed_by: User, 
                     completed_quantity: int = None, defective_quantity: int = 0,
                     comments: str = '') -> bool:
        """
        完成任务
        
        Args:
            task: 要完成的任务
            completed_by: 完成人
            completed_quantity: 完成数量
            defective_quantity: 不良品数量
            comments: 完成备注
            
        Returns:
            bool: 是否成功
        """
        if task.status != 'in_progress':
            raise ValidationError('只有进行中的任务可以完成')
        
        if task.assigned_to != completed_by:
            raise ValidationError('只有任务分配人可以完成任务')
        
        task.status = 'completed'
        task.completed_at = timezone.now()
        task.completed_quantity = completed_quantity
        task.defective_quantity = defective_quantity
        task.save()
        
        # 记录任务日志
        TaskLog.objects.create(
            task=task,
            action_type='complete',
            action_by=completed_by,
            comments=f'任务完成，完成数量: {completed_quantity}，不良品数量: {defective_quantity}。{comments}'
        )
        
        # 检查是否需要开始下一个工序
        TaskBusinessService._check_and_start_next_process(task)
        
        return True
    
    @staticmethod
    def _check_and_start_next_process(completed_task: WorkOrderTask) -> None:
        """检查并开始下一个工序"""
        workorder = completed_task.workorder
        
        # 查找当前工序的顺序
        current_process = WorkOrderProcess.objects.filter(
            work_order=workorder,
            process=completed_task.process
        ).first()
        
        if not current_process:
            return
        
        # 查找下一个工序
        next_process = WorkOrderProcess.objects.filter(
            work_order=workorder,
            order=current_process.order + 1
        ).first()
        
        if not next_process:
            # 所有工序完成，完成施工单
            if workorder.status == 'in_progress':
                workorder.status = 'completed'
                workorder.completed_at = timezone.now()
                workorder.save()
            return
        
        # 更新下一个工序状态为准备就绪
        next_process.status = 'ready'
        next_process.save()
        
        # 自动分配任务给合适的操作员
        TaskBusinessService._auto_assign_next_tasks(workorder, next_process)
    
    @staticmethod
    def _auto_assign_next_tasks(workorder: WorkOrder, next_process: WorkOrderProcess) -> None:
        """自动分配下一个工序的任务"""
        # 这里可以集成智能分配算法
        # 暂时简单分配给部门的操作员
        try:
            from ..services.smart_assignment import SmartAssignmentService
            
            assignment_service = SmartAssignmentService()
            tasks = WorkOrderTask.objects.filter(
                workorder=workorder,
                process=next_process.process,
                status='ready'
            )
            
            for task in tasks:
                result = assignment_service.smart_assign_single_task(task)
                if result['success']:
                    task.assigned_to_id = result['assigned_to']
                    task.status = 'pending'
                    task.save()
        except Exception:
            # 如果智能分配失败，跳过
            pass


class ProcessBusinessService:
    """工序业务逻辑服务"""
    
    @staticmethod
    @transaction.atomic
    def start_process(workorder_process: WorkOrderProcess, started_by: User) -> bool:
        """
        开始工序
        
        Args:
            workorder_process: 要开始的工序
            started_by: 开始人
            
        Returns:
            bool: 是否成功
        """
        if workorder_process.status not in ['pending', 'ready']:
            raise ValidationError('只有待处理的工序可以开始')
        
        workorder_process.status = 'in_progress'
        workorder_process.started_at = timezone.now()
        workorder_process.started_by = started_by
        workorder_process.save()
        
        # 记录工序日志
        ProcessLog.objects.create(
            work_order=workorder_process.work_order,
            process=workorder_process.process,
            action_type='start',
            action_by=started_by,
            comments='工序开始执行'
        )
        
        return True
    
    @staticmethod
    @transaction.atomic
    def complete_process(workorder_process: WorkOrderProcess, completed_by: User, 
                        comments: str = '') -> bool:
        """
        完成工序
        
        Args:
            workorder_process: 要完成的工序
            completed_by: 完成人
            comments: 完成备注
            
        Returns:
            bool: 是否成功
        """
        if workorder_process.status != 'in_progress':
            raise ValidationError('只有进行中的工序可以完成')
        
        workorder_process.status = 'completed'
        workorder_process.completed_at = timezone.now()
        workorder_process.completed_by = completed_by
        workorder_process.save()
        
        # 记录工序日志
        ProcessLog.objects.create(
            work_order=workorder_process.work_order,
            process=workorder_process.process,
            action_type='complete',
            action_by=completed_by,
            comments=f'工序完成。{comments}'
        )
        
        # 更新相关任务状态
        ProcessBusinessService._complete_process_tasks(workorder_process, completed_by)
        
        return True
    
    @staticmethod
    def _complete_process_tasks(workorder_process: WorkOrderProcess, completed_by: User) -> None:
        """完成工序相关任务"""
        tasks = WorkOrderTask.objects.filter(
            workorder=workorder_process.work_order,
            process=workorder_process.process,
            status='in_progress'
        )
        
        for task in tasks:
            task.status = 'completed'
            task.completed_at = timezone.now()
            task.save()
            
            # 记录任务日志
            TaskLog.objects.create(
                task=task,
                action_type='complete',
                action_by=completed_by,
                comments='工序完成，任务自动完成'
            )


class ReportBusinessService:
    """报表业务逻辑服务"""
    
    @staticmethod
    def get_workorder_statistics(start_date: datetime = None, end_date: datetime = None) -> Dict[str, Any]:
        """
        获取施工单统计
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            Dict[str, Any]: 统计数据
        """
        queryset = WorkOrder.objects.all()
        
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        
        # 基础统计
        total_orders = queryset.count()
        pending_orders = queryset.filter(status='pending').count()
        in_progress_orders = queryset.filter(status='in_progress').count()
        completed_orders = queryset.filter(status='completed').count()
        
        # 审核统计
        approved_orders = queryset.filter(approval_status='approved').count()
        rejected_orders = queryset.filter(approval_status='rejected').count()
        
        # 优先级统计
        priority_stats = {}
        for priority, label in [
            ('urgent', '紧急'),
            ('high', '高'),
            ('normal', '普通'),
            ('low', '低')
        ]:
            count = queryset.filter(priority=priority).count()
            priority_stats[priority] = {
                'label': label,
                'count': count,
                'percentage': round(count / total_orders * 100, 2) if total_orders > 0 else 0
            }
        
        # 金额统计
        total_amount = queryset.aggregate(
            total=models.Sum('total_amount')
        )['total'] or 0
        
        # 按月统计
        monthly_stats = queryset.extra({
            'month': models.ExtractMonth('created_at')
        }).values('month').annotate(
            count=models.Count('id'),
            amount=models.Sum('total_amount')
        ).order_by('month')
        
        return {
            'total_orders': total_orders,
            'status_distribution': {
                'pending': pending_orders,
                'in_progress': in_progress_orders,
                'completed': completed_orders
            },
            'approval_distribution': {
                'approved': approved_orders,
                'rejected': rejected_orders,
                'pending': pending_orders
            },
            'priority_stats': priority_stats,
            'total_amount': total_amount,
            'monthly_stats': list(monthly_stats),
            'completion_rate': round(completed_orders / total_orders * 100, 2) if total_orders > 0 else 0
        }
    
    @staticmethod
    def get_task_statistics(start_date: datetime = None, end_date: datetime = None) -> Dict[str, Any]:
        """
        获取任务统计
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            Dict[str, Any]: 统计数据
        """
        queryset = WorkOrderTask.objects.all()
        
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        
        # 基础统计
        total_tasks = queryset.count()
        completed_tasks = queryset.filter(status='completed').count()
        pending_tasks = queryset.filter(status='pending').count()
        in_progress_tasks = queryset.filter(status='in_progress').count()
        
        # 按状态统计
        status_stats = {}
        for status, label in [
            ('pending', '待处理'),
            ('in_progress', '进行中'),
            ('completed', '已完成'),
            ('skipped', '已跳过')
        ]:
            count = queryset.filter(status=status).count()
            status_stats[status] = {
                'label': label,
                'count': count,
                'percentage': round(count / total_tasks * 100, 2) if total_tasks > 0 else 0
            }
        
        # 按用户统计
        user_stats = queryset.values(
            'assigned_to__username'
        ).annotate(
            total_tasks=models.Count('id'),
            completed_tasks=models.Count('id', filter=models.Q(status='completed'))
        ).order_by('-total_tasks')[:10]
        
        return {
            'total_tasks': total_tasks,
            'status_distribution': {
                'pending': pending_tasks,
                'in_progress': in_progress_tasks,
                'completed': completed_tasks
            },
            'status_stats': status_stats,
            'user_stats': list(user_stats),
            'completion_rate': round(completed_tasks / total_tasks * 100, 2) if total_tasks > 0 else 0
        }


# 导入必要的模型
from django.db import models