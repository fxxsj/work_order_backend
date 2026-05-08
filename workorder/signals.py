"""
信号处理器：实现自动计算数量功能

当物料状态或版型确认状态变化时，自动更新相关任务的完成数量
"""
from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from .models import (
    WorkOrder,
    WorkOrderMaterial,
    WorkOrderTask,
    Artwork,
    Die,
    FoilingPlate,
    EmbossingPlate,
    SalesOrder,
)
from .services.sales_order_status_service import SalesOrderStatusService

# 使用实例属性缓存保存前的状态，避免全局缓存带来的并发问题


@receiver(pre_save, sender=WorkOrder)
def cache_work_order_status(sender, instance, **kwargs):
    """保存前缓存施工单状态，供 post_save 比较使用。"""
    if not instance.pk:
        instance._previous_status = None
        instance._previous_approval_status = None
        instance._previous_sales_order_id = None
        return

    try:
        previous = WorkOrder.objects.only(
            "status",
            "approval_status",
            "sales_order_id",
        ).get(pk=instance.pk)
        instance._previous_status = previous.status
        instance._previous_approval_status = previous.approval_status
        instance._previous_sales_order_id = previous.sales_order_id
    except WorkOrder.DoesNotExist:
        instance._previous_status = None
        instance._previous_approval_status = None
        instance._previous_sales_order_id = None


@receiver(post_save, sender=WorkOrder)
def sync_sales_order_status_on_work_order_change(sender, instance, created, **kwargs):
    """施工单状态或审核状态变化后，自动同步关联销售订单状态。"""
    previous_status = getattr(instance, "_previous_status", None)
    previous_approval_status = getattr(instance, "_previous_approval_status", None)
    previous_sales_order_id = getattr(instance, "_previous_sales_order_id", None)
    status_changed = instance.status != previous_status
    approval_status_changed = instance.approval_status != previous_approval_status
    sales_order_changed = instance.sales_order_id != previous_sales_order_id

    if created:
        if instance.sales_order_id:
            SalesOrderStatusService.sync_status_for_work_order(instance)
        return

    if not status_changed and not approval_status_changed and not sales_order_changed:
        return

    if sales_order_changed and previous_sales_order_id:
        old_sales_order = SalesOrder.objects.filter(pk=previous_sales_order_id).first()
        if old_sales_order is not None:
            SalesOrderStatusService.sync_status_for_sales_orders([old_sales_order])

    SalesOrderStatusService.sync_status_for_work_order(instance)

@receiver(pre_save, sender=WorkOrderMaterial)
def cache_material_status(sender, instance, **kwargs):
    """保存前缓存物料状态"""
    if instance.pk:
        try:
            old_instance = WorkOrderMaterial.objects.get(pk=instance.pk)
            instance._previous_purchase_status = old_instance.purchase_status
        except WorkOrderMaterial.DoesNotExist:
            pass


@receiver(post_save, sender=WorkOrderMaterial)
def update_cutting_task_on_material_status_change(sender, instance, created, **kwargs):
    """物料状态变化时，自动更新相关开料任务的完成数量"""
    # 只处理状态变化，不处理新建
    if created:
        return
    
    # 检查状态是否真的变化了（从非'cut'变为'cut'）
    old_status = getattr(instance, "_previous_purchase_status", None)
    if old_status == instance.purchase_status:
        # 状态未变化，不处理
        return
    
    # 检查物料状态是否为'cut'（已开料）
    if instance.purchase_status == "cut":
        transaction.on_commit(lambda: _update_cutting_tasks(instance))


def register_asset_confirmation_handlers(model_class, asset_kwarg_name):
    """
    通用函数，为指定的资产模型注册确认信号处理程序。

    此函数在内部定义并连接信号处理器，以确保每个模型都有唯一的处理器函数，
    避免在循环中注册时发生函数覆盖。

    Args:
        model_class: 资产的模型类 (e.g., Artwork).
        asset_kwarg_name (str): 在调用 _complete_plate_tasks 时用作关键字参数的名称
                               (e.g., 'artwork').
    """

    def cache_confirmation_status(sender, instance, **kwargs):
        """(通用) 保存前缓存资产的 'confirmed' 状态。"""
        if instance.pk:
            try:
                # 从数据库获取旧实例以比较状态
                old_instance = sender.objects.get(pk=instance.pk)
                instance._previous_confirmed = old_instance.confirmed
            except sender.DoesNotExist:
                # 如果对象不存在（例如，在一个事务中被删除后又重新创建），则没有旧状态
                instance._previous_confirmed = False
        else:
            # 新建实例没有旧状态
            instance._previous_confirmed = False

    def update_tasks_on_confirmation(sender, instance, created, **kwargs):
        """(通用) 当 'confirmed' 状态从 False 变为 True 时，自动更新相关任务。"""
        if created:
            return

        old_confirmed = getattr(instance, "_previous_confirmed", False)

        # 只有当状态从 '未确认' (False) 变为 '已确认' (True) 时才执行
        if instance.confirmed and not old_confirmed:
            transaction.on_commit(
                lambda: _complete_plate_tasks(**{asset_kwarg_name: instance})
            )

    # 使用唯一的 dispatch_uid 连接信号，以防止重复注册或信号处理函数被覆盖
    pre_save.connect(
        cache_confirmation_status,
        sender=model_class,
        weak=False,
        dispatch_uid=f"cache_confirmation_status_for_{model_class.__name__}",
    )
    post_save.connect(
        update_tasks_on_confirmation,
        sender=model_class,
        weak=False,
        dispatch_uid=f"update_tasks_on_confirmation_for_{model_class.__name__}",
    )


# --- 信号注册 ---

# 定义需要应用此逻辑的资产模型及其在 _complete_plate_tasks 中的关键字参数名
ASSET_MODELS_TO_REGISTER = {
    Artwork: "artwork",
    Die: "die",
    FoilingPlate: "foiling_plate",
    EmbossingPlate: "embossing_plate",
}

# 循环为每个资产模型注册信号处理器
for model, kwarg_name in ASSET_MODELS_TO_REGISTER.items():
    register_asset_confirmation_handlers(model, kwarg_name)



def _update_cutting_tasks(instance):
    """更新开料任务完成数量（提交后执行）"""
    with transaction.atomic():
        cutting_tasks = (
            WorkOrderTask.objects.select_for_update()
            .filter(
                task_type="cutting",
                material=instance.material,
                work_order_process__work_order=instance.work_order,
                auto_calculate_quantity=True,
                status__in=["pending", "in_progress"],
            )
        )
        quantity = _parse_material_usage(instance.material_usage)
        if quantity <= 0:
            return
        for task in cutting_tasks:
            task.quantity_completed = quantity
            if task.production_quantity and quantity >= task.production_quantity:
                task.status = "completed"
            elif task.status == "pending":
                task.status = "in_progress"
            task.save(update_fields=["quantity_completed", "status"])
            if task.status == "completed":
                task.work_order_process.check_and_update_status()


def _complete_plate_tasks(**filters):
    """完成制版任务（提交后执行）"""
    with transaction.atomic():
        plate_tasks = (
            WorkOrderTask.objects.select_for_update()
            .filter(
                task_type="plate_making",
                auto_calculate_quantity=True,
                status__in=["pending", "in_progress"],
                **filters,
            )
        )
        for task in plate_tasks:
            if task.quantity_completed < 1:
                task.quantity_completed = 1
                task.status = "completed"
                task.save(update_fields=["quantity_completed", "status"])
                task.work_order_process.check_and_update_status()


def _parse_material_usage(usage_str):
    """解析物料用量字符串，提取数字部分"""
    if not usage_str:
        return 0
    
    import re
    # 提取数字部分
    numbers = re.findall(r'\d+', usage_str)
    if numbers:
        return int(numbers[0])
    return 0
