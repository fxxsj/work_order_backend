"""
资产相关视图集

包含图稿、刀模、烫金版、压凸版等资产的视图集。
"""

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.permissions import DjangoModelPermissions
from django.db.models import Sum

from ..models.assets import (
    Artwork, ArtworkProduct,
    Die, DieProduct,
    FoilingPlate, FoilingPlateProduct,
    EmbossingPlate, EmbossingPlateProduct
)
from ..serializers.assets import (
    ArtworkSerializer, ArtworkProductSerializer,
    DieSerializer, DieProductSerializer,
    FoilingPlateSerializer, FoilingPlateProductSerializer,
    EmbossingPlateSerializer, EmbossingPlateProductSerializer
)
from ..models.core import WorkOrder


class ArtworkViewSet(viewsets.ModelViewSet):
    """图稿视图集"""
    permission_classes = [DjangoModelPermissions]  # 使用Django模型权限，与客户管理权限逻辑一致
    queryset = Artwork.objects.all()
    serializer_class = ArtworkSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['base_code', 'version']
    search_fields = ['base_code', 'name', 'imposition_size']
    ordering_fields = ['created_at', 'base_code', 'version', 'name']
    ordering = ['-base_code', '-version']
    
    @action(detail=True, methods=['post'])
    def create_version(self, request, pk=None):
        """基于现有图稿创建新版本"""
        original_artwork = self.get_object()
        
        # 获取下一个版本号
        next_version = Artwork.get_next_version(original_artwork.base_code)
        
        # 创建新版本，复制原图稿的所有信息
        new_artwork = Artwork.objects.create(
            base_code=original_artwork.base_code,
            version=next_version,
            name=original_artwork.name,
            cmyk_colors=original_artwork.cmyk_colors.copy() if original_artwork.cmyk_colors else [],
            other_colors=original_artwork.other_colors.copy() if original_artwork.other_colors else [],
            imposition_size=original_artwork.imposition_size,
            notes=original_artwork.notes
        )
        
        # 复制关联的刀模
        new_artwork.dies.set(original_artwork.dies.all())
        
        # 复制关联的产品
        for ap in original_artwork.products.all():
            ArtworkProduct.objects.create(
                artwork=new_artwork,
                product=ap.product,
                imposition_quantity=ap.imposition_quantity,
                sort_order=ap.sort_order
            )
        
        serializer = self.get_serializer(new_artwork)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """设计部确认图稿"""
        artwork = self.get_object()
        
        if artwork.confirmed:
            return Response(
                {'error': '该图稿已经确认过了'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        artwork.confirmed = True
        artwork.confirmed_by = request.user
        artwork.confirmed_at = timezone.now()
        artwork.save()
        
        # 检查相关的制版工序任务是否全部完成
        # 找到所有包含该图稿的任务（制版任务类型为plate_making）
        tasks = WorkOrderTask.objects.filter(
            artwork=artwork,
            task_type='plate_making',
            work_order_process__status='in_progress'
        )
        
        for task in tasks:
            # 如果图稿已确认，可以标记任务为完成
            if task.artwork.confirmed:
                task.status = 'completed'
                task.quantity_completed = 1
                task.save()
                
                # 检查工序是否完成
                task.work_order_process.check_and_update_status()
        
        serializer = self.get_serializer(artwork)
        return Response(serializer.data)
    
    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.prefetch_related('products__product')



class DieViewSet(viewsets.ModelViewSet):
    """刀模视图集"""
    permission_classes = [DjangoModelPermissions]  # 使用Django模型权限，与客户管理权限逻辑一致
    queryset = Die.objects.all()
    serializer_class = DieSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = []
    search_fields = ['code', 'name', 'size', 'material']
    ordering_fields = ['created_at', 'code', 'name']
    ordering = ['-created_at']
    
    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """设计部确认刀模"""
        die = self.get_object()
        
        if die.confirmed:
            return Response(
                {'error': '该刀模已经确认过了'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        die.confirmed = True
        die.confirmed_by = request.user
        die.confirmed_at = timezone.now()
        die.save()
        
        # 检查相关的制版工序任务是否全部完成
        # 找到所有包含该刀模的制版任务（task_type='plate_making'）
        tasks = WorkOrderTask.objects.filter(
            die=die,
            task_type='plate_making',
            work_order_process__status='in_progress'
        )
        
        for task in tasks:
            # 如果刀模已确认，可以标记任务为完成
            if task.die and task.die.confirmed:
                task.status = 'completed'
                task.quantity_completed = 1
                task.save()
                
                # 检查工序是否完成
                task.work_order_process.check_and_update_status()
        
        serializer = self.get_serializer(die)
        return Response(serializer.data)
    
    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.prefetch_related('products__product')



class FoilingPlateViewSet(viewsets.ModelViewSet):
    """烫金版视图集"""
    permission_classes = [DjangoModelPermissions]  # 使用Django模型权限，与客户管理权限逻辑一致
    queryset = FoilingPlate.objects.all()
    serializer_class = FoilingPlateSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = []
    search_fields = ['code', 'name', 'size', 'material']
    ordering_fields = ['created_at', 'code', 'name']
    ordering = ['-created_at']
    
    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """设计部确认烫金版"""
        foiling_plate = self.get_object()
        
        if foiling_plate.confirmed:
            return Response(
                {'error': '该烫金版已经确认过了'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        foiling_plate.confirmed = True
        foiling_plate.confirmed_by = request.user
        foiling_plate.confirmed_at = timezone.now()
        foiling_plate.save()
        
        # 检查相关的制版工序任务是否全部完成
        # 找到所有包含该烫金版的制版任务（task_type='plate_making'）
        tasks = WorkOrderTask.objects.filter(
            foiling_plate=foiling_plate,
            task_type='plate_making',
            work_order_process__status='in_progress'
        )
        
        for task in tasks:
            # 如果烫金版已确认，可以标记任务为完成
            if task.foiling_plate and task.foiling_plate.confirmed:
                task.status = 'completed'
                task.quantity_completed = 1
                task.save()
                
                # 检查工序是否完成
                task.work_order_process.check_and_update_status()
        
        serializer = self.get_serializer(foiling_plate)
        return Response(serializer.data)
    
    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.prefetch_related('products__product')



class EmbossingPlateViewSet(viewsets.ModelViewSet):
    """压凸版视图集"""
    permission_classes = [DjangoModelPermissions]  # 使用Django模型权限，与客户管理权限逻辑一致
    queryset = EmbossingPlate.objects.all()
    serializer_class = EmbossingPlateSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = []
    search_fields = ['code', 'name', 'size', 'material']
    ordering_fields = ['created_at', 'code', 'name']
    ordering = ['-created_at']
    
    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """设计部确认压凸版"""
        embossing_plate = self.get_object()
        
        if embossing_plate.confirmed:
            return Response(
                {'error': '该压凸版已经确认过了'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        embossing_plate.confirmed = True
        embossing_plate.confirmed_by = request.user
        embossing_plate.confirmed_at = timezone.now()
        embossing_plate.save()
        
        # 检查相关的制版工序任务是否全部完成
        # 找到所有包含该压凸版的制版任务（task_type='plate_making'）
        tasks = WorkOrderTask.objects.filter(
            embossing_plate=embossing_plate,
            task_type='plate_making',
            work_order_process__status='in_progress'
        )
        
        for task in tasks:
            # 如果压凸版已确认，可以标记任务为完成
            if task.embossing_plate and task.embossing_plate.confirmed:
                task.status = 'completed'
                task.quantity_completed = 1
                task.save()
                
                # 检查工序是否完成
                task.work_order_process.check_and_update_status()
        
        serializer = self.get_serializer(embossing_plate)
        return Response(serializer.data)
    
    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.prefetch_related('products__product')



class ArtworkProductViewSet(viewsets.ModelViewSet):
    """图稿产品视图集"""
    queryset = ArtworkProduct.objects.all()
    serializer_class = ArtworkProductSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    ordering_fields = ['sort_order']
    ordering = ['artwork', 'sort_order']
    def get_filterset(self):
        """延迟创建 FilterSet，避免模块加载时的关系解析问题"""
        from django_filters import FilterSet

        class ArtworkProductFilterSet(FilterSet):
            class Meta:
                model = ArtworkProduct
                fields = ['artwork', 'product']

        return ArtworkProductFilterSet



class DieProductViewSet(viewsets.ModelViewSet):
    """刀模产品视图集"""
    queryset = DieProduct.objects.all()
    serializer_class = DieProductSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    ordering_fields = ['sort_order']
    ordering = ['die', 'sort_order']
    def get_filterset(self):
        """延迟创建 FilterSet，避免模块加载时的关系解析问题"""
        from django_filters import FilterSet

        class DieProductFilterSet(FilterSet):
            class Meta:
                model = DieProduct
                fields = ['die', 'product']

        return DieProductFilterSet



class FoilingPlateProductViewSet(viewsets.ModelViewSet):
    """烫金版产品视图集"""
    queryset = FoilingPlateProduct.objects.all()
    serializer_class = FoilingPlateProductSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    ordering_fields = ['sort_order']
    ordering = ['foiling_plate', 'sort_order']
    def get_filterset(self):
        """延迟创建 FilterSet，避免模块加载时的关系解析问题"""
        from django_filters import FilterSet

        class FoilingPlateProductFilterSet(FilterSet):
            class Meta:
                model = FoilingPlateProduct
                fields = ['foiling_plate', 'product']

        return FoilingPlateProductFilterSet



class EmbossingPlateProductViewSet(viewsets.ModelViewSet):
    """压凸版产品视图集"""
    queryset = EmbossingPlateProduct.objects.all()
    serializer_class = EmbossingPlateProductSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    ordering_fields = ['sort_order']
    ordering = ['embossing_plate', 'sort_order']
    def get_filterset(self):
        """延迟创建 FilterSet，避免模块加载时的关系解析问题"""
        from django_filters import FilterSet

        class EmbossingPlateProductFilterSet(FilterSet):
            class Meta:
                model = EmbossingPlateProduct
                fields = ['embossing_plate', 'product']

        return EmbossingPlateProductFilterSet

