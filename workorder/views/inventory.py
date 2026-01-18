"""
库存相关视图集

包含库存管理的所有视图集：
- ProductStockViewSet: 成品库存
- StockInViewSet: 入库单
- StockOutViewSet: 出库单
- DeliveryOrderViewSet: 发货单
- DeliveryItemViewSet: 发货明细
- QualityInspectionViewSet: 质量检验
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Sum, Q, Count, F
from django.db import transaction

from workorder.models import (
    ProductStock, StockIn, StockOut,
    DeliveryOrder, DeliveryItem, QualityInspection
)
from workorder.serializers.inventory import (
    ProductStockSerializer,
    ProductStockUpdateSerializer,
    StockInSerializer,
    StockInCreateSerializer,
    StockOutSerializer,
    DeliveryItemSerializer,
    DeliveryOrderSerializer,
    DeliveryOrderListSerializer,
    DeliveryOrderCreateSerializer,
    DeliveryOrderUpdateSerializer,
    QualityInspectionSerializer,
    QualityInspectionCreateSerializer,
    QualityInspectionUpdateSerializer,
)


class ProductStockViewSet(viewsets.ModelViewSet):
    """成品库存视图集"""
    queryset = ProductStock.objects.select_related(
        'product', 'work_order'
    ).all()
    serializer_class = ProductStockSerializer

    def get_serializer_class(self):
        """根据操作选择序列化器"""
        if self.action in ['update', 'partial_update']:
            return ProductStockUpdateSerializer
        return ProductStockSerializer

    def get_queryset(self):
        """支持过滤和搜索"""
        queryset = super().get_queryset()

        # 按产品过滤
        product_id = self.request.query_params.get('product')
        if product_id:
            queryset = queryset.filter(product_id=product_id)

        # 按状态过滤
        stock_status = self.request.query_params.get('status')
        if stock_status:
            queryset = queryset.filter(status=stock_status)

        # 搜索
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(batch_no__icontains=search) |
                Q(location__icontains=search) |
                Q(product__name__icontains=search) |
                Q(product__code__icontains=search)
            )

        return queryset

    @action(detail=False, methods=['get'])
    def low_stock(self, request):
        """库存预警"""
        # 获取预警阈值
        min_quantity = request.query_params.get('min_quantity', 10)

        # 查询低库存产品
        low_stocks = self.get_queryset().filter(
            quantity__lte=min_quantity,
            status='in_stock'
        ).select_related('product')

        serializer = self.get_serializer(low_stocks, many=True)
        return Response({
            'count': low_stocks.count(),
            'results': serializer.data
        })

    @action(detail=False, methods=['get'])
    def expired(self, request):
        """已过期库存"""
        from django.utils import timezone

        # 查询已过期的库存
        expired_stocks = self.get_queryset().filter(
            expiry_date__lt=timezone.now().date()
        ).select_related('product')

        serializer = self.get_serializer(expired_stocks, many=True)
        return Response({
            'count': expired_stocks.count(),
            'results': serializer.data
        })

    @action(detail=False, methods=['get'])
    def expiring_soon(self, request):
        """即将过期库存"""
        from django.utils import timezone
        from datetime import timedelta

        # 默认30天内过期
        days = int(request.query_params.get('days', 30))
        threshold_date = timezone.now().date() + timedelta(days=days)

        expiring_stocks = self.get_queryset().filter(
            expiry_date__lte=threshold_date,
            expiry_date__gt=timezone.now().date(),
            status='in_stock'
        ).select_related('product')

        serializer = self.get_serializer(expiring_stocks, many=True)
        return Response({
            'count': expiring_stocks.count(),
            'threshold_date': threshold_date,
            'results': serializer.data
        })

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """库存汇总"""
        queryset = self.get_queryset()

        # 统计数据
        summary = queryset.aggregate(
            total_products=Count('product', distinct=True),
            total_quantity=Sum('quantity'),
            reserved_quantity=Sum('quantity', filter=Q(status='reserved')),
            defective_quantity=Sum('quantity', filter=Q(status='defective')),
        )

        # 按状态统计
        status_stats = queryset.values('status').annotate(
            count=Count('id'),
            quantity=Sum('quantity')
        ).order_by('status')

        return Response({
            'summary': summary,
            'by_status': list(status_stats)
        })


class StockInViewSet(viewsets.ModelViewSet):
    """入库单视图集"""
    queryset = StockIn.objects.select_related(
        'work_order', 'operator', 'submitted_by', 'approved_by'
    ).all()
    serializer_class = StockInSerializer

    def get_serializer_class(self):
        """根据操作选择序列化器"""
        if self.action == 'create':
            return StockInCreateSerializer
        return StockInSerializer

    def get_queryset(self):
        """支持过滤"""
        queryset = super().get_queryset()

        # 按状态过滤
        stockin_status = self.request.query_params.get('status')
        if stockin_status:
            queryset = queryset.filter(status=stockin_status)

        # 按日期范围过滤
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date:
            queryset = queryset.filter(stock_in_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(stock_in_date__lte=end_date)

        return queryset

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """提交入库单"""
        stock_in = self.get_object()

        if stock_in.status != 'draft':
            return Response({
                'error': '只有草稿状态的入库单可以提交'
            }, status=status.HTTP_400_BAD_REQUEST)

        stock_in.status = 'submitted'
        stock_in.submitted_by = request.user
        stock_in.submitted_at = timezone.now()
        stock_in.save()

        serializer = self.get_serializer(stock_in)
        return Response({
            'message': '入库单提交成功',
            'data': serializer.data
        })

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """审核入库单"""
        stock_in = self.get_object()

        if stock_in.status != 'submitted':
            return Response({
                'error': '只有已提交状态的入库单可以审核'
            }, status=status.HTTP_400_BAD_REQUEST)

        stock_in.status = 'completed'
        stock_in.approved_by = request.user
        stock_in.approved_at = timezone.now()
        stock_in.save()

        # TODO: 创建ProductStock记录

        serializer = self.get_serializer(stock_in)
        return Response({
            'message': '入库单审核成功',
            'data': serializer.data
        })


class StockOutViewSet(viewsets.ModelViewSet):
    """出库单视图集"""
    queryset = StockOut.objects.select_related(
        'delivery_order', 'operator', 'submitted_by', 'approved_by'
    ).all()
    serializer_class = StockOutSerializer

    def get_queryset(self):
        """支持过滤"""
        queryset = super().get_queryset()

        # 按状态过滤
        stockout_status = self.request.query_params.get('status')
        if stockout_status:
            queryset = queryset.filter(status=stockout_status)

        # 按出库类型过滤
        out_type = self.request.query_params.get('out_type')
        if out_type:
            queryset = queryset.filter(out_type=out_type)

        return queryset

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """审核出库单"""
        stock_out = self.get_object()

        if stock_out.status != 'submitted':
            return Response({
                'error': '只有已提交状态的出库单可以审核'
            }, status=status.HTTP_400_BAD_REQUEST)

        stock_out.status = 'completed'
        stock_out.approved_by = request.user
        stock_out.approved_at = timezone.now()
        stock_out.save()

        # TODO: 扣减库存

        serializer = self.get_serializer(stock_out)
        return Response({
            'message': '出库单审核成功',
            'data': serializer.data
        })


class DeliveryItemViewSet(viewsets.ModelViewSet):
    """发货明细视图集"""
    queryset = DeliveryItem.objects.select_related('product').all()
    serializer_class = DeliveryItemSerializer

    def get_queryset(self):
        """支持过滤"""
        queryset = super().get_queryset()

        # 按发货单过滤
        delivery_order_id = self.request.query_params.get('delivery_order')
        if delivery_order_id:
            queryset = queryset.filter(delivery_order_id=delivery_order_id)

        return queryset


class DeliveryOrderViewSet(viewsets.ModelViewSet):
    """发货单视图集"""
    queryset = DeliveryOrder.objects.select_related(
        'customer', 'sales_order', 'created_by'
    ).prefetch_related('items__product').all()
    serializer_class = DeliveryOrderSerializer

    def get_serializer_class(self):
        """根据操作选择序列化器"""
        if self.action == 'list':
            return DeliveryOrderListSerializer
        elif self.action == 'create':
            return DeliveryOrderCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return DeliveryOrderUpdateSerializer
        return DeliveryOrderSerializer

    def get_queryset(self):
        """支持过滤和搜索"""
        queryset = super().get_queryset()

        # 按状态过滤
        delivery_status = self.request.query_params.get('status')
        if delivery_status:
            queryset = queryset.filter(status=delivery_status)

        # 按客户过滤
        customer_id = self.request.query_params.get('customer')
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)

        # 按日期范围过滤
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date:
            queryset = queryset.filter(delivery_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(delivery_date__lte=end_date)

        # 搜索
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(order_number__icontains=search) |
                Q(customer__name__icontains=search) |
                Q(logistics_company__icontains=search) |
                Q(tracking_number__icontains=search)
            )

        return queryset

    @action(detail=True, methods=['post'])
    def ship(self, request, pk=None):
        """发货"""
        delivery_order = self.get_object()

        if delivery_order.status != 'pending':
            return Response({
                'error': '只有待发货状态的发货单可以发货'
            }, status=status.HTTP_400_BAD_REQUEST)

        # 更新发货信息
        delivery_order.status = 'shipped'
        delivery_order.delivery_date = timezone.now().date()

        # 获取物流信息
        logistics_company = request.data.get('logistics_company')
        tracking_number = request.data.get('tracking_number')
        if logistics_company:
            delivery_order.logistics_company = logistics_company
        if tracking_number:
            delivery_order.tracking_number = tracking_number

        delivery_order.save()

        # TODO: 创建出库单

        serializer = self.get_serializer(delivery_order)
        return Response({
            'message': '发货成功',
            'data': serializer.data
        })

    @action(detail=True, methods=['post'])
    def receive(self, request, pk=None):
        """签收"""
        delivery_order = self.get_object()

        if delivery_order.status not in ['shipped', 'in_transit']:
            return Response({
                'error': '只有已发货或运输中的发货单可以签收'
            }, status=status.HTTP_400_BAD_REQUEST)

        # 更新签收信息
        delivery_order.status = 'received'
        delivery_order.received_date = timezone.now()

        # 获取签收备注
        received_notes = request.data.get('received_notes')
        if received_notes:
            delivery_order.received_notes = received_notes

        # TODO: 上传签收照片
        receiver_signature = request.FILES.get('receiver_signature')
        if receiver_signature:
            delivery_order.receiver_signature = receiver_signature

        delivery_order.save()

        serializer = self.get_serializer(delivery_order)
        return Response({
            'message': '签收成功',
            'data': serializer.data
        })

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """发货汇总"""
        queryset = self.get_queryset()

        # 统计数据
        summary = queryset.aggregate(
            total_count=Count('id'),
            pending_count=Count('id', filter=Q(status='pending')),
            shipped_count=Count('id', filter=Q(status='shipped')),
            in_transit_count=Count('id', filter=Q(status='in_transit')),
            received_count=Count('id', filter=Q(status='received')),
            total_freight=Sum('freight'),
        )

        # 按状态统计
        status_stats = queryset.values('status').annotate(
            count=Count('id')
        ).order_by('status')

        return Response({
            'summary': summary,
            'by_status': list(status_stats)
        })


class QualityInspectionViewSet(viewsets.ModelViewSet):
    """质量检验视图集"""
    queryset = QualityInspection.objects.select_related(
        'work_order', 'product', 'inspector'
    ).all()
    serializer_class = QualityInspectionSerializer

    def get_serializer_class(self):
        """根据操作选择序列化器"""
        if self.action == 'create':
            return QualityInspectionCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return QualityInspectionUpdateSerializer
        return QualityInspectionSerializer

    def get_queryset(self):
        """支持过滤和搜索"""
        queryset = super().get_queryset()

        # 按检验类型过滤
        inspection_type = self.request.query_params.get('type')
        if inspection_type:
            queryset = queryset.filter(inspection_type=inspection_type)

        # 按结果过滤
        result = self.request.query_params.get('result')
        if result:
            queryset = queryset.filter(result=result)

        # 按日期范围过滤
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date:
            queryset = queryset.filter(inspection_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(inspection_date__lte=end_date)

        # 搜索
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(inspection_number__icontains=search) |
                Q(batch_no__icontains=search) |
                Q(product__name__icontains=search)
            )

        return queryset

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """完成检验"""
        inspection = self.get_object()

        if inspection.result != 'pending':
            return Response({
                'error': '该检验已经有结果了'
            }, status=status.HTTP_400_BAD_REQUEST)

        # 获取检验结果
        result = request.data.get('result')
        if not result:
            return Response({
                'error': '必须指定检验结果'
            }, status=status.HTTP_400_BAD_REQUEST)

        inspection.result = result

        # 更新数量
        passed_quantity = request.data.get('passed_quantity', 0)
        failed_quantity = request.data.get('failed_quantity', 0)
        inspection.passed_quantity = passed_quantity
        inspection.failed_quantity = failed_quantity

        # 保存（会自动计算不良率）
        inspection.save()

        serializer = self.get_serializer(inspection)
        return Response({
            'message': '检验完成',
            'data': serializer.data
        })

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """质检汇总"""
        queryset = self.get_queryset()

        # 统计数据
        summary = queryset.aggregate(
            total_count=Count('id'),
            total_quantity=Sum('inspection_quantity'),
            total_passed=Sum('passed_quantity'),
            total_failed=Sum('failed_quantity'),
            avg_defective_rate=Sum('defective_rate') / Count('id'),
        )

        # 按结果统计
        result_stats = queryset.values('result').annotate(
            count=Count('id')
        ).order_by('result')

        # 按类型统计
        type_stats = queryset.values('inspection_type').annotate(
            count=Count('id')
        ).order_by('inspection_type')

        return Response({
            'summary': summary,
            'by_result': list(result_stats),
            'by_type': list(type_stats)
        })
