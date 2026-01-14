"""
销售订单视图集

包含销售订单和采购订单的视图集。
"""

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django_filters import FilterSet, NumberFilter
from django.db.models import Q, Count, Sum
from django.utils import timezone

from rest_framework.permissions import DjangoModelPermissions
from ..models.sales import SalesOrder, SalesOrderItem
from ..models.materials import PurchaseOrder, PurchaseOrderItem
from ..models.core import WorkOrder, WorkOrderProduct
from ..models.products import Product
from ..serializers.sales import (
    SalesOrderListSerializer,
    SalesOrderDetailSerializer,
    SalesOrderItemSerializer,
    PurchaseOrderListSerializer,
    PurchaseOrderDetailSerializer,
    PurchaseOrderItemSerializer
)
from ..models.base import Customer


class SalesOrderViewSet(viewsets.ModelViewSet):
    """销售订单视图集"""
    queryset = SalesOrder.objects.all()
    permission_classes = [DjangoModelPermissions]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['customer', 'status', 'payment_status']
    search_fields = ['order_number', 'customer__name']
    ordering_fields = ['created_at', 'order_date', 'delivery_date']
    ordering = ['-created_at']

    def get_queryset(self):
        """优化查询"""
        return SalesOrder.objects.select_related(
            'customer', 'submitted_by', 'approved_by', 'created_by'
        ).prefetch_related(
            'items', 'items__product', 'work_orders'
        )

    def get_serializer_class(self):
        """根据action选择序列化器"""
        if self.action == 'list':
            return SalesOrderListSerializer
        return SalesOrderDetailSerializer

    def perform_create(self, serializer):
        """创建销售订单时自动设置创建人"""
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """提交销售订单"""
        sales_order = self.get_object()
        if sales_order.status != 'draft':
            return Response(
                {'error': '只有草稿状态的订单才能提交'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 验证订单数据完整性
        errors = sales_order.validate_before_approval()
        if errors:
            return Response(
                {'error': '订单数据验证失败', 'errors': errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 更新订单状态
        sales_order.status = 'submitted'
        sales_order.submitted_by = request.user
        sales_order.submitted_at = timezone.now()
        sales_order.save()

        serializer = self.get_serializer(sales_order)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """审核通过销售订单"""
        sales_order = self.get_object()
        if sales_order.status != 'submitted':
            return Response(
                {'error': '只有已提交状态的订单才能审核'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 再次验证订单数据完整性
        errors = sales_order.validate_before_approval()
        if errors:
            return Response(
                {'error': '订单数据验证失败', 'errors': errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 更新订单状态
        sales_order.status = 'approved'
        sales_order.approved_by = request.user
        sales_order.approved_at = timezone.now()
        sales_order.approval_comment = request.data.get('approval_comment', '')
        sales_order.save()

        # 审核通过后，减少产品库存数量
        self._reduce_product_stock(sales_order)

        serializer = self.get_serializer(sales_order)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """拒绝销售订单"""
        sales_order = self.get_object()
        if sales_order.status != 'submitted':
            return Response(
                {'error': '只有已提交状态的订单才能拒绝'},
                status=status.HTTP_400_BAD_REQUEST
            )

        reason = request.data.get('reason')
        if not reason:
            return Response(
                {'error': '请提供拒绝原因'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 更新订单状态
        sales_order.status = 'cancelled'
        sales_order.approved_by = request.user
        sales_order.approved_at = timezone.now()
        sales_order.approval_comment = request.data.get('approval_comment', '')
        sales_order.rejection_reason = reason
        sales_order.save()

        serializer = self.get_serializer(sales_order)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def start_production(self, request, pk=None):
        """开始生产（将订单状态改为生产中）"""
        sales_order = self.get_object()
        if sales_order.status != 'approved':
            return Response(
                {'error': '只有已审核的订单才能开始生产'},
                status=status.HTTP_400_BAD_REQUEST
            )

        sales_order.status = 'in_production'
        sales_order.save()

        serializer = self.get_serializer(sales_order)
        return Response(serializer.data)

    def _reduce_product_stock(self, sales_order):
        """销售订单审核通过后，减少产品库存数量
        
        规则：
        - 遍历订单明细，减少对应产品的库存数量
        - 减少数量 = 订单明细的 quantity
        """
        from ..models.products import Product

        # 获取订单明细
        items = sales_order.items.all()
        
        # 按产品汇总数量
        product_quantities = {}
        for item in items:
            product_id = item.product.id
            if product_id not in product_quantities:
                product_quantities[product_id] = 0
            product_quantities[product_id] += item.quantity

        # 减少产品库存
        for product_id, quantity in product_quantities.items():
            try:
                product = Product.objects.get(id=product_id)
                try:
                    product.reduce_stock(
                        quantity=quantity,
                        user=None,  # 系统自动操作，不记录操作人
                        reason=f'销售订单{sales_order.order_number}审核通过，出库{quantity}{product.unit}'
                    )
                except ValueError as e:
                    # 库存不足，记录错误日志
                    print(f"库存不足警告：{e}")
            except Product.DoesNotExist:
                # 产品已被删除，忽略
                pass

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """完成订单"""
        sales_order = self.get_object()
        if sales_order.status not in ['approved', 'in_production']:
            return Response(
                {'error': '只有已审核或生产中的订单才能完成'},
                status=status.HTTP_400_BAD_REQUEST
            )

        sales_order.status = 'completed'
        sales_order.actual_delivery_date = timezone.now().date()
        sales_order.save()

        serializer = self.get_serializer(sales_order)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """取消订单"""
        sales_order = self.get_object()
        if sales_order.status in ['completed', 'cancelled']:
            return Response(
                {'error': '已完成或已取消的订单不能再次取消'},
                status=status.HTTP_400_BAD_REQUEST
            )

        reason = request.data.get('reason', '')
        sales_order.status = 'cancelled'
        sales_order.rejection_reason = reason
        sales_order.save()

        serializer = self.get_serializer(sales_order)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def update_payment(self, request, pk=None):
        """更新付款信息"""
        sales_order = self.get_object()
        paid_amount = request.data.get('paid_amount')
        payment_date = request.data.get('payment_date')

        if paid_amount is not None:
            sales_order.paid_amount = Decimal(str(paid_amount))
        if payment_date:
            sales_order.payment_date = payment_date

        sales_order.save()  # save方法会自动更新payment_status

        serializer = self.get_serializer(sales_order)
        return Response(serializer.data)



class SalesOrderItemViewSet(viewsets.ModelViewSet):
    """销售订单明细视图集"""
    queryset = SalesOrderItem.objects.all()
    permission_classes = [DjangoModelPermissions]
    serializer_class = SalesOrderItemSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['sales_order', 'product']
    ordering_fields = ['created_at']
    ordering = ['sales_order', 'id']

    def get_queryset(self):
        """优化查询"""
        return super().get_queryset().select_related('sales_order', 'product')

    def perform_create(self, serializer):
        """创建明细后更新销售订单总金额"""
        item = serializer.save()
        item.sales_order.update_totals()

    def perform_update(self, serializer):
        """更新明细后更新销售订单总金额"""
        item = serializer.save()
        item.sales_order.update_totals()

    def perform_destroy(self, instance):
        """删除明细后更新销售订单总金额"""
        sales_order = instance.sales_order
        super().perform_destroy(instance)
        sales_order.update_totals()




class PurchaseOrderViewSet(viewsets.ModelViewSet):
    """采购单视图集"""
    queryset = PurchaseOrder.objects.all()
    permission_classes = [DjangoModelPermissions]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['supplier', 'status', 'work_order']
    search_fields = ['order_number', 'supplier__name']
    ordering_fields = ['created_at', 'order_number', 'total_amount']
    ordering = ['-created_at']

    def get_serializer_class(self):
        """根据 action 返回不同的序列化器"""
        if self.action == 'list':
            return PurchaseOrderListSerializer
        return PurchaseOrderDetailSerializer

    def get_queryset(self):
        """根据用户权限过滤查询集"""
        queryset = super().get_queryset()
        queryset = queryset.select_related(
            'supplier', 'submitted_by', 'approved_by', 'work_order'
        ).prefetch_related('items__material')
        return queryset

    def perform_create(self, serializer):
        """创建采购单时自动设置提交人"""
        serializer.save(submitted_by=self.request.user)

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """提交采购单"""
        purchase_order = self.get_object()
        if purchase_order.status != 'draft':
            return Response(
                {'error': '只有草稿状态的采购单才能提交'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not purchase_order.items.exists():
            return Response(
                {'error': '采购单必须有明细'},
                status=status.HTTP_400_BAD_REQUEST
            )

        purchase_order.status = 'submitted'
        purchase_order.submitted_at = timezone.now()
        purchase_order.save()

        # 创建通知给有审核权限的用户
        Notification.create_notification(
            recipient=None,  # 广播给所有有权限的用户
            notification_type='purchase_order_submitted',
            title=f'采购单待审核',
            message=f'采购单 {purchase_order.order_number} 已提交审核',
            priority='normal',
            purchase_order=purchase_order
        )

        serializer = self.get_serializer(purchase_order)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """审核通过采购单"""
        purchase_order = self.get_object()
        if purchase_order.status not in ['submitted']:
            return Response(
                {'error': '只有已提交状态的采购单才能审核'},
                status=status.HTTP_400_BAD_REQUEST
            )

        purchase_order.status = 'approved'
        purchase_order.approved_by = request.user
        purchase_order.approved_at = timezone.now()
        purchase_order.save()

        # 创建通知
        Notification.create_notification(
            recipient=purchase_order.submitted_by,
            notification_type='purchase_order_approved',
            title=f'采购单已通过',
            message=f'采购单 {purchase_order.order_number} 已通过审核',
            priority='normal',
            purchase_order=purchase_order
        )

        serializer = self.get_serializer(purchase_order)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """拒绝采购单"""
        purchase_order = self.get_object()
        if purchase_order.status not in ['submitted']:
            return Response(
                {'error': '只有已提交状态的采购单才能拒绝'},
                status=status.HTTP_400_BAD_REQUEST
            )

        rejection_reason = request.data.get('rejection_reason', '').strip()
        if not rejection_reason:
            return Response(
                {'error': '拒绝原因不能为空'},
                status=status.HTTP_400_BAD_REQUEST
            )

        purchase_order.status = 'draft'
        purchase_order.rejection_reason = rejection_reason
        purchase_order.save()

        # 创建通知
        Notification.create_notification(
            recipient=purchase_order.submitted_by,
            notification_type='purchase_order_rejected',
            title=f'采购单已拒绝',
            message=f'采购单 {purchase_order.order_number} 已被拒绝，原因：{rejection_reason}',
            priority='high',
            purchase_order=purchase_order
        )

        serializer = self.get_serializer(purchase_order)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def place_order(self, request, pk=None):
        """确认下单"""
        purchase_order = self.get_object()
        if purchase_order.status != 'approved':
            return Response(
                {'error': '只有已批准状态的采购单才能下单'},
                status=status.HTTP_400_BAD_REQUEST
            )

        ordered_date = request.data.get('ordered_date')
        expected_date = request.data.get('expected_date')

        purchase_order.status = 'ordered'
        if ordered_date:
            purchase_order.ordered_date = ordered_date
        if expected_date:
            purchase_order.expected_date = expected_date
        purchase_order.save()

        serializer = self.get_serializer(purchase_order)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def receive(self, request, pk=None):
        """收货"""
        purchase_order = self.get_object()
        if purchase_order.status not in ['ordered']:
            return Response(
                {'error': '只有已下单状态的采购单才能收货'},
                status=status.HTTP_400_BAD_REQUEST
            )

        items_data = request.data.get('items', [])
        if not items_data:
            return Response(
                {'error': '收货数据不能为空'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 更新每个明细的收货数量
        for item_data in items_data:
            item_id = item_data.get('id')
            received_qty = item_data.get('received_quantity', 0)

            try:
                item = purchase_order.items.get(id=item_id)
                item.received_quantity = received_qty

                # 更新收货状态
                if item.received_quantity >= item.quantity:
                    item.status = 'received'
                elif item.received_quantity > 0:
                    item.status = 'partial'
                else:
                    item.status = 'pending'

                item.save()

                # 更新物料库存
                from ..models.materials import Material
                material = item.material
                material.stock_quantity += received_qty
                material.save()

            except PurchaseOrderItem.DoesNotExist:
                continue

        # 检查是否所有明细都已收货
        all_received = all(
            item.status == 'received' for item in purchase_order.items.all()
        )
        if all_received:
            purchase_order.status = 'received'
            purchase_order.actual_received_date = timezone.now().date()

        serializer = self.get_serializer(purchase_order)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """取消采购单"""
        purchase_order = self.get_object()
        if purchase_order.status not in ['draft', 'submitted', 'approved']:
            return Response(
                {'error': '只有草稿、已提交或已批准状态的采购单才能取消'},
                status=status.HTTP_400_BAD_REQUEST
            )

        purchase_order.status = 'cancelled'
        purchase_order.save()

        serializer = self.get_serializer(purchase_order)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def low_stock_materials(self, request):
        """获取库存不足的物料列表"""
        materials = Material.objects.filter(
            stock_quantity__lt=models.F('min_stock_quantity')
        ).select_related('default_supplier')
        data = [{
            'id': m.id,
            'code': m.code,
            'name': m.name,
            'stock_quantity': float(m.stock_quantity),
            'min_stock_quantity': float(m.min_stock_quantity),
            'needed_quantity': float(m.min_stock_quantity - m.stock_quantity),
            'default_supplier': m.default_supplier.name if m.default_supplier else None,
        } for m in materials]
        return Response({'materials': data})



class PurchaseOrderItemViewSet(viewsets.ModelViewSet):
    """采购单明细视图集"""
    queryset = PurchaseOrderItem.objects.all()
    permission_classes = [DjangoModelPermissions]
    serializer_class = PurchaseOrderItemSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['purchase_order', 'material', 'status']
    ordering_fields = ['created_at']
    ordering = ['purchase_order', 'id']

    def get_queryset(self):
        """优化查询"""
        return super().get_queryset().select_related(
            'purchase_order', 'material', 'work_order_material'
        )

    @action(detail=True, methods=['post'])
    def receive(self, request, pk=None):
        """单独收货某个明细"""
        item = self.get_object()
        if item.purchase_order.status != 'ordered':
            return Response(
                {'error': '只有已下单状态的采购单才能收货'},
                status=status.HTTP_400_BAD_REQUEST
            )

        received_qty = request.data.get('received_quantity', item.received_quantity)
        item.received_quantity = received_qty

        # 更新收货状态
        if item.received_quantity >= item.quantity:
            item.status = 'received'
        elif item.received_quantity > 0:
            item.status = 'partial'
        else:
            item.status = 'pending'

        item.save()

        # 更新物料库存
        material = item.material
        material.stock_quantity += received_qty - item.received_quantity
        material.save()

        # 更新采购单状态
        purchase_order = item.purchase_order
        all_received = all(
            i.status == 'received' for i in purchase_order.items.all()
        )
        if all_received:
            purchase_order.status = 'received'
            purchase_order.actual_received_date = timezone.now().date()
            purchase_order.save()

        serializer = self.get_serializer(item)
        return Response(serializer.data)

