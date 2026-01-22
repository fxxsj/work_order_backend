"""
物料相关视图集

包含物料、供应商、物料供应商、采购单、收货记录等视图集。
"""

from rest_framework import viewsets, filters, pagination, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db import transaction
from django.db.models import Count, Sum, Case, When, FloatField, F
from django.utils import timezone
from ..permissions import SuperuserFriendlyModelPermissions

from ..models.materials import (
    Material, Supplier, MaterialSupplier,
    PurchaseOrder, PurchaseOrderItem, PurchaseReceiveRecord
)
from ..serializers.materials import (
    MaterialSerializer,
    SupplierSerializer,
    MaterialSupplierSerializer,
    PurchaseOrderListSerializer,
    PurchaseOrderDetailSerializer,
    PurchaseOrderItemSerializer,
    PurchaseReceiveRecordSerializer,
    PurchaseReceiveRecordCreateSerializer,
    InspectionConfirmSerializer,
    ReturnProcessSerializer
)


class MaterialViewSet(viewsets.ModelViewSet):
    """物料视图集（优化版）"""
    permission_classes = [SuperuserFriendlyModelPermissions]
    queryset = Material.objects.all()
    serializer_class = MaterialSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'code', 'specification']
    ordering_fields = ['code', 'created_at', 'stock_quantity']
    ordering = ['code']

    def get_queryset(self):
        """优化查询性能"""
        queryset = super().get_queryset()
        return queryset.select_related(
            'default_supplier'
        )


class SupplierViewSet(viewsets.ModelViewSet):
    """供应商视图集（优化版）"""
    queryset = Supplier.objects.all()
    permission_classes = [SuperuserFriendlyModelPermissions]
    serializer_class = SupplierSerializer
    pagination_class = pagination.PageNumberPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status']
    search_fields = ['name', 'code', 'contact_person', 'phone', 'email']
    ordering_fields = ['created_at', 'name', 'code']
    ordering = ['-created_at']

    def get_queryset(self):
        """优化查询性能：使用注解避免N+1查询"""
        queryset = super().get_queryset()
        # 使用注解预计算物料数量
        queryset = queryset.annotate(
            _material_count=Count('materialsupplier')
        )
        return queryset


class MaterialSupplierViewSet(viewsets.ModelViewSet):
    """物料供应商关联视图集"""
    queryset = MaterialSupplier.objects.all()
    permission_classes = [SuperuserFriendlyModelPermissions]
    serializer_class = MaterialSupplierSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['material', 'supplier', 'is_preferred']
    ordering_fields = ['created_at']
    ordering = ['-created_at']


class PurchaseOrderViewSet(viewsets.ModelViewSet):
    """采购单视图集（优化版）"""
    queryset = PurchaseOrder.objects.all()
    permission_classes = [SuperuserFriendlyModelPermissions]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['order_number', 'supplier__name']
    ordering_fields = ['created_at', 'order_number', 'total_amount']
    ordering = ['-created_at']

    def get_filterset(self):
        """延迟创建 FilterSet，避免模块加载时的关系解析问题"""
        from django_filters import FilterSet

        class PurchaseOrderFilterSet(FilterSet):
            class Meta:
                model = PurchaseOrder
                fields = ['supplier', 'status', 'work_order']

        return PurchaseOrderFilterSet

    def get_serializer_class(self):
        """根据 action 返回不同的序列化器"""
        if self.action == 'list':
            return PurchaseOrderListSerializer
        return PurchaseOrderDetailSerializer

    def get_queryset(self):
        """优化查询性能：使用注解避免N+1查询"""
        queryset = super().get_queryset()

        # 优化：预加载关联数据
        queryset = queryset.select_related(
            'supplier', 'submitted_by', 'approved_by', 'work_order'
        ).prefetch_related(
            'items__material'
        )

        # 优化：使用注解计算items_count和received_progress
        queryset = queryset.annotate(
            items_count=Count('items'),
            total_quantity=Sum('items__quantity'),
            total_received=Sum('items__received_quantity')
        )

        # 计算收货进度百分比
        queryset = queryset.annotate(
            received_progress=Case(
                When(total_quantity__gt=0, then=Sum('items__received_quantity') * 100.0 / Sum('items__quantity')),
                default=0.0,
                output_field=FloatField()
            )
        )

        return queryset

    # ========== 状态操作 Actions ==========

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """提交采购单"""
        order = self.get_object()
        if order.status != 'draft':
            return Response(
                {'error': '只有草稿状态的采购单可以提交'},
                status=status.HTTP_400_BAD_REQUEST
            )

        order.status = 'submitted'
        order.submitted_by = request.user
        order.submitted_at = timezone.now()
        order.save()
        return Response({'message': '提交成功'})

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """批准采购单"""
        order = self.get_object()
        if order.status != 'submitted':
            return Response(
                {'error': '只有已提交状态的采购单可以批准'},
                status=status.HTTP_400_BAD_REQUEST
            )

        order.status = 'approved'
        order.approved_by = request.user
        order.approved_at = timezone.now()
        order.save()
        return Response({'message': '批准成功'})

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """拒绝采购单"""
        order = self.get_object()
        if order.status != 'submitted':
            return Response(
                {'error': '只有已提交状态的采购单可以拒绝'},
                status=status.HTTP_400_BAD_REQUEST
            )

        order.status = 'draft'  # 退回草稿
        order.rejection_reason = request.data.get('rejection_reason', '')
        order.save()
        return Response({'message': '已拒绝，采购单已退回草稿状态'})

    @action(detail=True, methods=['post'])
    def place_order(self, request, pk=None):
        """下单"""
        order = self.get_object()
        if order.status != 'approved':
            return Response(
                {'error': '只有已批准状态的采购单可以下单'},
                status=status.HTTP_400_BAD_REQUEST
            )

        order.status = 'ordered'
        ordered_date = request.data.get('ordered_date')
        if ordered_date:
            order.ordered_date = ordered_date
        else:
            order.ordered_date = timezone.now().date()
        order.save()
        return Response({'message': '下单成功'})

    @action(detail=True, methods=['post'])
    def receive(self, request, pk=None):
        """分批收货（改进版）

        支持分批收货，创建收货记录，不直接入库（需要质检后入库）
        """
        order = self.get_object()
        if order.status != 'ordered':
            return Response(
                {'error': '只有已下单状态的采购单可以收货'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = PurchaseReceiveRecordCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        items_data = serializer.validated_data.get('items', [])
        received_date = serializer.validated_data.get('received_date', timezone.now().date())

        created_records = []
        errors = []

        with transaction.atomic():
            for item_data in items_data:
                item_id = item_data.get('item_id')
                received_quantity = item_data.get('received_quantity')
                delivery_note_number = item_data.get('delivery_note_number', '')
                notes = item_data.get('notes', '')

                # 查找采购单明细
                item = order.items.filter(id=item_id).first()
                if not item:
                    errors.append(f'采购单明细 {item_id} 不存在')
                    continue

                # 计算已收货的数量（来自收货记录）
                existing_received = sum(
                    r.received_quantity or 0
                    for r in item.receive_records.all()
                )
                remaining = item.quantity - existing_received

                if received_quantity > remaining:
                    errors.append(
                        f'物料 {item.material.name} 收货数量 {received_quantity} '
                        f'超过剩余数量 {remaining}'
                    )
                    continue

                # 创建收货记录
                record = PurchaseReceiveRecord.objects.create(
                    purchase_order_item=item,
                    received_quantity=received_quantity,
                    received_date=received_date,
                    received_by=request.user,
                    delivery_note_number=delivery_note_number,
                    notes=notes,
                    inspection_status='pending'
                )
                created_records.append(record.id)

        if errors:
            return Response({
                'message': '部分收货成功',
                'created_records': created_records,
                'errors': errors
            }, status=status.HTTP_207_MULTI_STATUS)

        return Response({
            'message': '收货成功，请进行质检',
            'created_records': created_records
        })

    @action(detail=True, methods=['get'])
    def receive_records(self, request, pk=None):
        """获取采购单的所有收货记录"""
        order = self.get_object()
        records = PurchaseReceiveRecord.objects.filter(
            purchase_order_item__purchase_order=order
        ).select_related(
            'purchase_order_item__material',
            'received_by',
            'inspected_by',
            'stocked_by',
            'returned_by'
        ).order_by('-received_date', '-created_at')

        serializer = PurchaseReceiveRecordSerializer(records, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def pending_inspections(self, request, pk=None):
        """获取待质检的收货记录"""
        order = self.get_object()
        records = PurchaseReceiveRecord.objects.filter(
            purchase_order_item__purchase_order=order,
            inspection_status='pending'
        ).select_related(
            'purchase_order_item__material',
            'received_by'
        ).order_by('-received_date')

        serializer = PurchaseReceiveRecordSerializer(records, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """取消采购单"""
        order = self.get_object()
        if order.status in ['received', 'cancelled']:
            return Response(
                {'error': '已收货或已取消的采购单无法取消'},
                status=status.HTTP_400_BAD_REQUEST
            )

        order.status = 'cancelled'
        order.save()
        return Response({'message': '取消成功'})

    @action(detail=False, methods=['get'])
    def low_stock_materials(self, request):
        """获取库存预警物料"""
        # 查询库存低于最小库存的物料
        materials = Material.objects.filter(
            stock_quantity__lt=F('min_stock_quantity')
        ).values(
            'id', 'code', 'name', 'stock_quantity',
            'min_stock_quantity', 'default_supplier__name'
        ).annotate(
            needed_quantity=F('min_stock_quantity') - F('stock_quantity')
        )

        return Response({'materials': list(materials)})


class PurchaseOrderItemViewSet(viewsets.ModelViewSet):
    """采购单明细视图集"""
    queryset = PurchaseOrderItem.objects.all()
    permission_classes = [SuperuserFriendlyModelPermissions]
    serializer_class = PurchaseOrderItemSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    ordering_fields = ['created_at']
    ordering = ['purchase_order', 'id']

    def get_filterset(self):
        """延迟创建 FilterSet，避免模块加载时的关系解析问题"""
        from django_filters import FilterSet

        class PurchaseOrderItemFilterSet(FilterSet):
            class Meta:
                model = PurchaseOrderItem
                fields = ['purchase_order', 'material', 'status']

        return PurchaseOrderItemFilterSet

    def get_queryset(self):
        """优化查询"""
        return super().get_queryset().select_related(
            'purchase_order', 'material', 'work_order_material'
        ).prefetch_related('receive_records')


class PurchaseReceiveRecordViewSet(viewsets.ModelViewSet):
    """采购收货记录视图集

    提供收货记录的CRUD操作和质检、入库、退货等业务操作。
    """
    queryset = PurchaseReceiveRecord.objects.all()
    permission_classes = [SuperuserFriendlyModelPermissions]
    serializer_class = PurchaseReceiveRecordSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['delivery_note_number', 'purchase_order_item__material__name']
    ordering_fields = ['received_date', 'created_at']
    ordering = ['-received_date', '-created_at']

    def get_filterset(self):
        """延迟创建 FilterSet"""
        from django_filters import FilterSet, CharFilter

        class PurchaseReceiveRecordFilterSet(FilterSet):
            purchase_order = CharFilter(
                field_name='purchase_order_item__purchase_order',
                lookup_expr='exact'
            )

            class Meta:
                model = PurchaseReceiveRecord
                fields = ['purchase_order_item', 'inspection_status', 'is_stocked', 'is_returned']

        return PurchaseReceiveRecordFilterSet

    def get_queryset(self):
        """优化查询"""
        return super().get_queryset().select_related(
            'purchase_order_item__purchase_order__supplier',
            'purchase_order_item__material',
            'received_by',
            'inspected_by',
            'stocked_by',
            'returned_by'
        )

    @action(detail=True, methods=['post'])
    def confirm_inspection(self, request, pk=None):
        """确认质检结果

        将收货记录的质检状态从"待质检"更新为具体结果。
        """
        record = self.get_object()

        if record.inspection_status != 'pending':
            return Response(
                {'error': '该记录已完成质检'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = InspectionConfirmSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        qualified_qty = serializer.validated_data['qualified_quantity']
        unqualified_qty = serializer.validated_data.get('unqualified_quantity', 0)
        reason = serializer.validated_data.get('unqualified_reason', '')

        # 验证数量总和
        total = qualified_qty + unqualified_qty
        if total != record.received_quantity:
            return Response(
                {'error': f'合格数量({qualified_qty}) + 不合格数量({unqualified_qty}) '
                         f'必须等于收货数量({record.received_quantity})'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 确认质检
        record.confirm_inspection(
            qualified_qty=qualified_qty,
            unqualified_qty=unqualified_qty,
            reason=reason,
            user=request.user
        )

        return Response({
            'message': '质检确认成功',
            'inspection_status': record.inspection_status,
            'qualified_quantity': str(record.qualified_quantity),
            'unqualified_quantity': str(record.unqualified_quantity)
        })

    @action(detail=True, methods=['post'])
    def stock_in(self, request, pk=None):
        """合格物料入库

        将质检合格的物料入库，更新物料库存。
        """
        record = self.get_object()

        if record.inspection_status == 'pending':
            return Response(
                {'error': '请先完成质检'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if record.is_stocked:
            return Response(
                {'error': '该记录已入库'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not record.qualified_quantity or record.qualified_quantity <= 0:
            return Response(
                {'error': '没有合格物料可入库'},
                status=status.HTTP_400_BAD_REQUEST
            )

        success = record.stock_in(user=request.user)

        if success:
            return Response({
                'message': '入库成功',
                'stocked_quantity': str(record.qualified_quantity),
                'material_name': record.material.name,
                'new_stock': str(record.material.stock_quantity)
            })
        else:
            return Response(
                {'error': '入库失败'},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['post'])
    def process_return(self, request, pk=None):
        """处理退货

        将质检不合格的物料进行退货处理。
        """
        record = self.get_object()

        if record.inspection_status == 'pending':
            return Response(
                {'error': '请先完成质检'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if record.is_returned:
            return Response(
                {'error': '该记录已退货'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not record.unqualified_quantity or record.unqualified_quantity <= 0:
            return Response(
                {'error': '没有不合格物料可退货'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = ReturnProcessSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        return_qty = serializer.validated_data['return_quantity']
        return_note = serializer.validated_data.get('return_note', '')

        if return_qty > record.unqualified_quantity:
            return Response(
                {'error': f'退货数量({return_qty})不能超过不合格数量({record.unqualified_quantity})'},
                status=status.HTTP_400_BAD_REQUEST
            )

        success = record.process_return(
            return_qty=return_qty,
            note=return_note,
            user=request.user
        )

        if success:
            return Response({
                'message': '退货处理成功',
                'returned_quantity': str(return_qty),
                'material_name': record.material.name
            })
        else:
            return Response(
                {'error': '退货处理失败'},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['get'])
    def pending_list(self, request):
        """获取所有待质检的收货记录"""
        records = self.get_queryset().filter(
            inspection_status='pending'
        ).order_by('-received_date')

        page = self.paginate_queryset(records)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(records, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def pending_stock_in(self, request):
        """获取待入库的收货记录（已质检但未入库）"""
        records = self.get_queryset().filter(
            inspection_status__in=['qualified', 'partial_qualified'],
            is_stocked=False,
            qualified_quantity__gt=0
        ).order_by('-inspected_at')

        page = self.paginate_queryset(records)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(records, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def pending_return(self, request):
        """获取待退货的收货记录（有不合格物料但未退货）"""
        records = self.get_queryset().filter(
            inspection_status__in=['unqualified', 'partial_qualified'],
            is_returned=False,
            unqualified_quantity__gt=0
        ).order_by('-inspected_at')

        page = self.paginate_queryset(records)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(records, many=True)
        return Response(serializer.data)
