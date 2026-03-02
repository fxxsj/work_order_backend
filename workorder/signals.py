"""
信号处理器：实现自动计算数量功能

当物料状态或版型确认状态变化时，自动更新相关任务的完成数量
"""
from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from .models import (
    WorkOrderMaterial, WorkOrderTask, Artwork, Die, 
    FoilingPlate, EmbossingPlate
)

# 使用实例属性缓存保存前的状态，避免全局缓存带来的并发问题


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
                
                # 记录操作日志（可选，避免日志过多）
                # from .models import TaskLog
                # TaskLog.objects.create(
                #     task=task,
                #     log_type='update_quantity',
                #     content=f'物料已开料，自动更新完成数量：{old_quantity} → {quantity}',
                #     quantity_before=old_quantity,
                #     quantity_after=quantity,
                #     quantity_increment=quantity - old_quantity
                # )


@receiver(pre_save, sender=Artwork)
def cache_artwork_confirmation(sender, instance, **kwargs):
    """保存前缓存图稿确认状态"""
    if instance.pk:
        try:
            old_instance = Artwork.objects.get(pk=instance.pk)
            instance._previous_confirmed = old_instance.confirmed
        except Artwork.DoesNotExist:
            pass


@receiver(post_save, sender=Artwork)
def update_plate_making_task_on_artwork_confirmation(sender, instance, created, **kwargs):
    """图稿确认时，自动更新相关制版任务的完成数量"""
    # 只处理确认状态变化
    if created:
        return
    
    # 检查确认状态是否真的变化了（从False变为True）
    old_confirmed = getattr(instance, "_previous_confirmed", False)
    if old_confirmed == instance.confirmed:
        # 状态未变化，不处理
        return
    
    # 检查图稿是否已确认
    if instance.confirmed:
        transaction.on_commit(lambda: _complete_plate_tasks(artwork=instance))


@receiver(pre_save, sender=Die)
def cache_die_confirmation(sender, instance, **kwargs):
    """保存前缓存刀模确认状态"""
    if instance.pk:
        try:
            old_instance = Die.objects.get(pk=instance.pk)
            instance._previous_confirmed = old_instance.confirmed
        except Die.DoesNotExist:
            pass


@receiver(post_save, sender=Die)
def update_plate_making_task_on_die_confirmation(sender, instance, created, **kwargs):
    """刀模确认时，自动更新相关制版任务的完成数量"""
    if created:
        return
    
    # 检查确认状态是否真的变化了
    old_confirmed = getattr(instance, "_previous_confirmed", False)
    if old_confirmed == instance.confirmed:
        return
    
    if instance.confirmed:
        transaction.on_commit(lambda: _complete_plate_tasks(die=instance))


@receiver(pre_save, sender=FoilingPlate)
def cache_foiling_plate_confirmation(sender, instance, **kwargs):
    """保存前缓存烫金版确认状态"""
    if instance.pk:
        try:
            old_instance = FoilingPlate.objects.get(pk=instance.pk)
            instance._previous_confirmed = old_instance.confirmed
        except FoilingPlate.DoesNotExist:
            pass


@receiver(post_save, sender=FoilingPlate)
def update_plate_making_task_on_foiling_plate_confirmation(sender, instance, created, **kwargs):
    """烫金版确认时，自动更新相关制版任务的完成数量"""
    if created:
        return
    
    # 检查确认状态是否真的变化了
    old_confirmed = getattr(instance, "_previous_confirmed", False)
    if old_confirmed == instance.confirmed:
        return
    
    if instance.confirmed:
        transaction.on_commit(lambda: _complete_plate_tasks(foiling_plate=instance))


@receiver(pre_save, sender=EmbossingPlate)
def cache_embossing_plate_confirmation(sender, instance, **kwargs):
    """保存前缓存压凸版确认状态"""
    if instance.pk:
        try:
            old_instance = EmbossingPlate.objects.get(pk=instance.pk)
            instance._previous_confirmed = old_instance.confirmed
        except EmbossingPlate.DoesNotExist:
            pass


@receiver(post_save, sender=EmbossingPlate)
def update_plate_making_task_on_embossing_plate_confirmation(sender, instance, created, **kwargs):
    """压凸版确认时，自动更新相关制版任务的完成数量"""
    if created:
        return
    
    # 检查确认状态是否真的变化了
    old_confirmed = getattr(instance, "_previous_confirmed", False)
    if old_confirmed == instance.confirmed:
        return
    
    if instance.confirmed:
        transaction.on_commit(lambda: _complete_plate_tasks(embossing_plate=instance))


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
