"""
销售订单视图集

包含销售订单的视图集。
"""

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django_filters import FilterSet, NumberFilter
from django.db.models import Q, Count, Sum
from django.utils import timezone
from decimal import Decimal

from ..permissions import SuperuserFriendlyModelPermissions
from ..models.sales import SalesOrder, SalesOrderItem
from ..models.products import Product
from ..serializers.sales import (
    SalesOrderListSerializer,
    SalesOrderDetailSerializer,
    SalesOrderItemSerializer
)
from ..models.base import Customer


class SalesOrderViewSet(viewsets.ModelViewSet):
    """销售订单视图集"""
    queryset = SalesOrder.objects.all()
    permission_classes = [SuperuserFriendlyModelPermissions]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['order_number', 'customer__name']
    ordering_fields = ['created_at', 'order_date', 'delivery_date']
    ordering = ['-created_at']

    def get_filterset(self):
        """动态创建 FilterSet，避免模块加载时的关系解析问题"""
        from django_filters import FilterSet

        class SalesOrderFilterSet(FilterSet):
            class Meta:
                model = SalesOrder
                fields = ['customer', 'status', 'payment_status']

        return SalesOrderFilterSet

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

        # 更新订单状态为已拒绝
        sales_order.status = 'rejected'
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

    def _check_stock_availability(self, sales_order):
        """检查库存是否充足

        Returns:
            tuple: (is_available, error_messages)
        """
        errors = []
        items = sales_order.items.all()

        for item in items:
            try:
                product = item.product
                if hasattr(product, 'stock') and product.stock < item.quantity:
                    errors.append(f'{product.name}库存不足（需要{item.quantity}，当前{product.stock}）')
            except Exception:
                pass

        return len(errors) == 0, errors

    def _reduce_product_stock(self, sales_order):
        """销售订单审核通过后，减少产品库存数量

        规则：
        - 遍历订单明细，减少对应产品的库存数量
        - 减少数量 = 订单明细的 quantity
        - 使用事务保证原子性
        """
        from django.db import transaction

        items = sales_order.items.all()

        # 按产品汇总数量
        product_quantities = {}
        for item in items:
            product_id = item.product.id
            if product_id not in product_quantities:
                product_quantities[product_id] = 0
            product_quantities[product_id] += item.quantity

        # 在事务中减少产品库存
        with transaction.atomic():
            for product_id, quantity in product_quantities.items():
                try:
                    product = Product.objects.select_for_update().get(id=product_id)
                    if hasattr(product, 'reduce_stock'):
                        product.reduce_stock(
                            quantity=quantity,
                            user=None,
                            reason=f'销售订单{sales_order.order_number}审核通过，出库{quantity}{product.unit}'
                        )
                    elif hasattr(product, 'stock'):
                        product.stock = max(0, product.stock - quantity)
                        product.save(update_fields=['stock'])
                except Product.DoesNotExist:
                    pass
                except ValueError as e:
                    # 记录库存不足警告但不阻止流程
                    import logging
                    logging.warning(f"库存扣减警告：{e}")

    def _restore_product_stock(self, sales_order):
        """取消已审核订单时恢复产品库存

        规则：
        - 仅当订单已经扣减过库存时才恢复
        - 使用事务保证原子性
        """
        from django.db import transaction

        # 只有已审核、生产中状态的订单才需要恢复库存
        if sales_order.status not in ['approved', 'in_production']:
            return

        items = sales_order.items.all()

        # 按产品汇总数量
        product_quantities = {}
        for item in items:
            product_id = item.product.id
            if product_id not in product_quantities:
                product_quantities[product_id] = 0
            product_quantities[product_id] += item.quantity

        # 在事务中恢复产品库存
        with transaction.atomic():
            for product_id, quantity in product_quantities.items():
                try:
                    product = Product.objects.select_for_update().get(id=product_id)
                    if hasattr(product, 'add_stock'):
                        product.add_stock(
                            quantity=quantity,
                            user=None,
                            reason=f'销售订单{sales_order.order_number}取消，库存回滚{quantity}{product.unit}'
                        )
                    elif hasattr(product, 'stock'):
                        product.stock = product.stock + quantity
                        product.save(update_fields=['stock'])
                except Product.DoesNotExist:
                    pass
                except Exception as e:
                    import logging
                    logging.warning(f"库存恢复警告：{e}")

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
        if sales_order.status in ['completed', 'cancelled', 'rejected']:
            return Response(
                {'error': '已完成、已取消或已拒绝的订单不能再次取消'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 如果订单已审核或生产中，需要恢复库存
        self._restore_product_stock(sales_order)

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
    permission_classes = [SuperuserFriendlyModelPermissions]
    serializer_class = SalesOrderItemSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    ordering_fields = ['created_at']
    ordering = ['sales_order', 'id']

    def get_filterset(self):
        """延迟创建 FilterSet，避免模块加载时的关系解析问题"""
        from django_filters import FilterSet

        class SalesOrderItemFilterSet(FilterSet):
            class Meta:
                model = SalesOrderItem
                fields = ['sales_order', 'product']

        return SalesOrderItemFilterSet

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
