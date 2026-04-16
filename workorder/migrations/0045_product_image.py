from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("workorder", "0044_salesorder_contract_number"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProductImage",
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
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
                (
                    "image",
                    models.ImageField(
                        help_text="支持 JPG、PNG、WebP 等常见图片格式",
                        upload_to="product_images/",
                        verbose_name="图片文件",
                    ),
                ),
                ("sort_order", models.IntegerField(default=0, help_text="数值越小排越前", verbose_name="排序")),
                (
                    "description",
                    models.CharField(
                        blank=True,
                        help_text="如：正面、背面、结构示意等",
                        max_length=200,
                        verbose_name="描述",
                    ),
                ),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="images",
                        to="workorder.product",
                        verbose_name="产品",
                    ),
                ),
            ],
            options={
                "verbose_name": "产品图片",
                "verbose_name_plural": "产品图片",
                "ordering": ["product", "sort_order"],
            },
        ),
        migrations.AddIndex(
            model_name="productimage",
            index=models.Index(fields=["product"], name="product_image_product_idx"),
        ),
    ]
