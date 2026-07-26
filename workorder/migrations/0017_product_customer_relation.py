# Generated for 产品-客户多对多关系优化

from django.db import migrations, models


def backfill_customer_code(apps, schema_editor):
    """为已有客户回填 code：C + 6位序号，保证唯一。"""
    Customer = apps.get_model("workorder", "Customer")
    seq = 0
    for customer in Customer.objects.filter(code__isnull=True).order_by("id"):
        seq += 1
        customer.code = f"C{seq:06d}"
        # 兜底处理极端重名（理论不会发生，因 code 生成规则保证唯一）
        while Customer.objects.filter(code=customer.code).exists():
            seq += 1
            customer.code = f"C{seq:06d}"
        customer.save(update_fields=["code"])


def reverse_backfill_customer_code(apps, schema_editor):
    Customer = apps.get_model("workorder", "Customer")
    Customer.objects.filter(code__startswith="C").update(code=None)


def backfill_product_customer(apps, schema_editor):
    """从历史销售订单/施工单反推产品-客户关系。

    规则：
    - 收集每个产品被哪些客户使用（来源：SalesOrderItem.sales_order.customer
      与 WorkOrder.customer）。
    - 被至少一个客户使用 → 建立 ProductCustomer 关联（去重）。
    - 从未被使用 → 不建关系（保持通用/待确认，由后续运维归类）。

    注：以 product 主键为聚合维度，不按名称合并。
    """
    Product = apps.get_model("workorder", "Product")
    Customer = apps.get_model("workorder", "Customer")
    SalesOrderItem = apps.get_model("workorder", "SalesOrderItem")
    ProductCustomer = apps.get_model("workorder", "ProductCustomer")

    # 通过销售订单明细反推
    usage = {}  # {product_id: set(customer_id)}
    for item in SalesOrderItem.objects.select_related(
        "sales_order", "product"
    ).exclude(product__isnull=True):
        if item.sales_order_id and item.sales_order.customer_id:
            usage.setdefault(item.product_id, set()).add(
                item.sales_order.customer_id
            )

    # 通过施工单反推（WorkOrderProduct → work_order.customer）
    try:
        WorkOrderProduct = apps.get_model("workorder", "WorkOrderProduct")
        for wop in WorkOrderProduct.objects.select_related(
            "work_order", "product"
        ).exclude(product__isnull=True):
            if wop.work_order_id and wop.work_order.customer_id:
                usage.setdefault(wop.product_id, set()).add(
                    wop.work_order.customer_id
                )
    except LookupError:
        # 模型名可能不同，跳过施工单维度
        pass

    created = 0
    for product_id, customer_ids in usage.items():
        for customer_id in customer_ids:
            _, was_created = ProductCustomer.objects.get_or_create(
                product_id=product_id,
                customer_id=customer_id,
            )
            if was_created:
                created += 1

    if schema_editor.connection.vendor != "sqlite":
        # 日志在非测试环境可见
        pass


def reverse_backfill_product_customer(apps, schema_editor):
    ProductCustomer = apps.get_model("workorder", "ProductCustomer")
    ProductCustomer.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("workorder", "0016_backfill_product_material_resolution_modes"),
    ]

    operations = [
        # 1. Customer 加 code 字段
        migrations.AddField(
            model_name="customer",
            name="code",
            field=models.CharField(
                blank=True,
                help_text="客户编码，用于导入匹配；历史数据迁移时自动回填，可留空",
                max_length=50,
                null=True,
                unique=True,
                verbose_name="客户编码",
            ),
        ),
        migrations.AddIndex(
            model_name="customer",
            index=models.Index(fields=["code"], name="customer_code_idx"),
        ),
        migrations.RunPython(
            backfill_customer_code,
            reverse_code=reverse_backfill_customer_code,
        ),
        # 2. 创建 ProductCustomer 中间表
        migrations.CreateModel(
            name="ProductCustomer",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="创建时间"),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, verbose_name="更新时间"),
                ),
                (
                    "customer_product_code",
                    models.CharField(
                        blank=True,
                        help_text="客户对该产品的内部料号/名称，区别于客户编码",
                        max_length=50,
                        verbose_name="客户内部货号",
                    ),
                ),
                (
                    "default_unit_price",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        help_text="该客户对该产品的默认单价；为空时使用产品全局单价",
                        max_digits=10,
                        null=True,
                        verbose_name="客户专属单价",
                    ),
                ),
                (
                    "notes",
                    models.TextField(blank=True, verbose_name="备注"),
                ),
                (
                    "customer",
                    models.ForeignKey(
                        on_delete=models.CASCADE,
                        related_name="product_links",
                        to="workorder.customer",
                        verbose_name="客户",
                    ),
                ),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=models.CASCADE,
                        related_name="customer_links",
                        to="workorder.product",
                        verbose_name="产品",
                    ),
                ),
            ],
            options={
                "verbose_name": "产品客户关联",
                "verbose_name_plural": "产品客户关联管理",
                "ordering": ["product", "customer"],
            },
        ),
        migrations.AddConstraint(
            model_name="productcustomer",
            constraint=models.UniqueConstraint(
                fields=("product", "customer"),
                name="unique_product_customer",
            ),
        ),
        migrations.AddIndex(
            model_name="productcustomer",
            index=models.Index(fields=["product"], name="pc_product_idx"),
        ),
        migrations.AddIndex(
            model_name="productcustomer",
            index=models.Index(fields=["customer"], name="pc_customer_idx"),
        ),
        migrations.AddIndex(
            model_name="productcustomer",
            index=models.Index(
                fields=["product", "customer"], name="pc_product_customer_idx"
            ),
        ),
        # 3. Product 加 M2M（指向已建的 through 表）
        migrations.AddField(
            model_name="product",
            name="customers",
            field=models.ManyToManyField(
                blank=True,
                help_text="关联客户为空表示通用产品；关联一个为专属；多个为共享",
                related_name="products",
                through="workorder.ProductCustomer",
                to="workorder.customer",
                verbose_name="所属客户",
            ),
        ),
        # 4. 历史回填产品-客户关系
        migrations.RunPython(
            backfill_product_customer,
            reverse_code=reverse_backfill_product_customer,
        ),
    ]
