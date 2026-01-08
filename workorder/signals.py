"""
信号处理器：实现自动计算数量功能

当物料状态或版型确认状态变化时，自动更新相关任务的完成数量
"""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from .models import (
    WorkOrderMaterial, WorkOrderTask, Artwork, Die, 
    FoilingPlate, EmbossingPlate
)

# 用于存储保存前的状态，以便检测状态变化
_material_status_cache = {}
_plate_confirmation_cache = {}


@receiver(pre_save, sender=WorkOrderMaterial)
def cache_material_status(sender, instance, **kwargs):
    """保存前缓存物料状态"""
    if instance.pk:
        try:
            old_instance = WorkOrderMaterial.objects.get(pk=instance.pk)
            _material_status_cache[instance.pk] = old_instance.purchase_status
        except WorkOrderMaterial.DoesNotExist:
            pass


@receiver(post_save, sender=WorkOrderMaterial)
def update_cutting_task_on_material_status_change(sender, instance, created, **kwargs):
    """物料状态变化时，自动更新相关开料任务的完成数量"""
    # 只处理状态变化，不处理新建
    if created:
        return
    
    # 检查状态是否真的变化了（从非'cut'变为'cut'）
    old_status = _material_status_cache.get(instance.pk)
    if old_status == instance.purchase_status:
        # 状态未变化，不处理
        if instance.pk in _material_status_cache:
            del _material_status_cache[instance.pk]
        return
    
    # 清理缓存
    if instance.pk in _material_status_cache:
        del _material_status_cache[instance.pk]
    
    # 检查物料状态是否为'cut'（已开料）
    if instance.purchase_status == 'cut':
        # 查找关联的开料任务
        cutting_tasks = WorkOrderTask.objects.filter(
            task_type='cutting',
            material=instance.material,
            work_order_process__work_order=instance.work_order,
            auto_calculate_quantity=True,
            status__in=['pending', 'in_progress']
        )
        
        for task in cutting_tasks:
            # 解析物料用量
            quantity = _parse_material_usage(instance.material_usage)
            if quantity > 0:
                # 更新任务完成数量
                old_quantity = task.quantity_completed
                task.quantity_completed = quantity
                
                # 如果数量达到生产数量，自动完成
                if task.production_quantity and quantity >= task.production_quantity:
                    task.status = 'completed'
                elif task.status == 'pending':
                    task.status = 'in_progress'
                
                task.save()
                
                # 如果任务完成，检查工序是否完成
                if task.status == 'completed':
                    task.work_order_process.check_and_update_status()
                
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
            _plate_confirmation_cache[f'artwork_{instance.pk}'] = old_instance.confirmed
        except Artwork.DoesNotExist:
            pass


@receiver(post_save, sender=Artwork)
def update_plate_making_task_on_artwork_confirmation(sender, instance, created, **kwargs):
    """图稿确认时，自动更新相关制版任务的完成数量"""
    # 只处理确认状态变化
    if created:
        return
    
    # 检查确认状态是否真的变化了（从False变为True）
    cache_key = f'artwork_{instance.pk}'
    old_confirmed = _plate_confirmation_cache.get(cache_key, False)
    if old_confirmed == instance.confirmed:
        # 状态未变化，不处理
        if cache_key in _plate_confirmation_cache:
            del _plate_confirmation_cache[cache_key]
        return
    
    # 清理缓存
    if cache_key in _plate_confirmation_cache:
        del _plate_confirmation_cache[cache_key]
    
    # 检查图稿是否已确认
    if instance.confirmed:
        # 查找关联的制版任务
        plate_making_tasks = WorkOrderTask.objects.filter(
            task_type='plate_making',
            artwork=instance,
            auto_calculate_quantity=True,
            status__in=['pending', 'in_progress']
        )
        
        for task in plate_making_tasks:
            # 制版任务完成数量固定为1
            if task.quantity_completed < 1:
                task.quantity_completed = 1
                task.status = 'completed'
                task.save()
                
                # 检查工序是否完成
                task.work_order_process.check_and_update_status()


@receiver(pre_save, sender=Die)
def cache_die_confirmation(sender, instance, **kwargs):
    """保存前缓存刀模确认状态"""
    if instance.pk:
        try:
            old_instance = Die.objects.get(pk=instance.pk)
            _plate_confirmation_cache[f'die_{instance.pk}'] = old_instance.confirmed
        except Die.DoesNotExist:
            pass


@receiver(post_save, sender=Die)
def update_plate_making_task_on_die_confirmation(sender, instance, created, **kwargs):
    """刀模确认时，自动更新相关制版任务的完成数量"""
    if created:
        return
    
    # 检查确认状态是否真的变化了
    cache_key = f'die_{instance.pk}'
    old_confirmed = _plate_confirmation_cache.get(cache_key, False)
    if old_confirmed == instance.confirmed:
        if cache_key in _plate_confirmation_cache:
            del _plate_confirmation_cache[cache_key]
        return
    
    if cache_key in _plate_confirmation_cache:
        del _plate_confirmation_cache[cache_key]
    
    if instance.confirmed:
        plate_making_tasks = WorkOrderTask.objects.filter(
            task_type='plate_making',
            die=instance,
            auto_calculate_quantity=True,
            status__in=['pending', 'in_progress']
        )
        
        for task in plate_making_tasks:
            if task.quantity_completed < 1:
                task.quantity_completed = 1
                task.status = 'completed'
                task.save()
                
                # 检查工序是否完成
                task.work_order_process.check_and_update_status()


@receiver(pre_save, sender=FoilingPlate)
def cache_foiling_plate_confirmation(sender, instance, **kwargs):
    """保存前缓存烫金版确认状态"""
    if instance.pk:
        try:
            old_instance = FoilingPlate.objects.get(pk=instance.pk)
            _plate_confirmation_cache[f'foiling_{instance.pk}'] = old_instance.confirmed
        except FoilingPlate.DoesNotExist:
            pass


@receiver(post_save, sender=FoilingPlate)
def update_plate_making_task_on_foiling_plate_confirmation(sender, instance, created, **kwargs):
    """烫金版确认时，自动更新相关制版任务的完成数量"""
    if created:
        return
    
    # 检查确认状态是否真的变化了
    cache_key = f'foiling_{instance.pk}'
    old_confirmed = _plate_confirmation_cache.get(cache_key, False)
    if old_confirmed == instance.confirmed:
        if cache_key in _plate_confirmation_cache:
            del _plate_confirmation_cache[cache_key]
        return
    
    if cache_key in _plate_confirmation_cache:
        del _plate_confirmation_cache[cache_key]
    
    if instance.confirmed:
        plate_making_tasks = WorkOrderTask.objects.filter(
            task_type='plate_making',
            foiling_plate=instance,
            auto_calculate_quantity=True,
            status__in=['pending', 'in_progress']
        )
        
        for task in plate_making_tasks:
            if task.quantity_completed < 1:
                task.quantity_completed = 1
                task.status = 'completed'
                task.save()
                
                # 检查工序是否完成
                task.work_order_process.check_and_update_status()


@receiver(pre_save, sender=EmbossingPlate)
def cache_embossing_plate_confirmation(sender, instance, **kwargs):
    """保存前缓存压凸版确认状态"""
    if instance.pk:
        try:
            old_instance = EmbossingPlate.objects.get(pk=instance.pk)
            _plate_confirmation_cache[f'embossing_{instance.pk}'] = old_instance.confirmed
        except EmbossingPlate.DoesNotExist:
            pass


@receiver(post_save, sender=EmbossingPlate)
def update_plate_making_task_on_embossing_plate_confirmation(sender, instance, created, **kwargs):
    """压凸版确认时，自动更新相关制版任务的完成数量"""
    if created:
        return
    
    # 检查确认状态是否真的变化了
    cache_key = f'embossing_{instance.pk}'
    old_confirmed = _plate_confirmation_cache.get(cache_key, False)
    if old_confirmed == instance.confirmed:
        if cache_key in _plate_confirmation_cache:
            del _plate_confirmation_cache[cache_key]
        return
    
    if cache_key in _plate_confirmation_cache:
        del _plate_confirmation_cache[cache_key]
    
    if instance.confirmed:
        plate_making_tasks = WorkOrderTask.objects.filter(
            task_type='plate_making',
            embossing_plate=instance,
            auto_calculate_quantity=True,
            status__in=['pending', 'in_progress']
        )
        
        for task in plate_making_tasks:
            if task.quantity_completed < 1:
                task.quantity_completed = 1
                task.status = 'completed'
                task.save()
                
                # 检查工序是否完成
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

