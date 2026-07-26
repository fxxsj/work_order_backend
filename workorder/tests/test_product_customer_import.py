"""产品客户关系导入的一致性测试。"""

from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from openpyxl import Workbook

from workorder.import_export import import_model
from workorder.import_export_configs import get_product_import_config
from workorder.models.base import Customer
from workorder.models.products import Product


def build_product_file(rows):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["编码", "名称", "产品范围", "所属客户"])
    for row in rows:
        sheet.append(row)
    content = BytesIO()
    workbook.save(content)
    return SimpleUploadedFile(
        "products.xlsx",
        content.getvalue(),
        content_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
    )


class ProductCustomerImportTest(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(name="客户A")
        self.config = get_product_import_config(Product)

    def test_customer_code_is_generated(self):
        self.assertRegex(self.customer.code, r"^C\d{6}$")

    def test_unknown_customer_rolls_back_new_product(self):
        result = import_model(
            build_product_file(
                [["P-NEW", "新产品", "客户专属", "NOT-FOUND"]]
            ),
            self.config,
        )

        self.assertEqual(result["success_count"], 0)
        self.assertEqual(result["error_count"], 1)
        self.assertFalse(Product.objects.filter(code="P-NEW").exists())

    def test_unknown_customer_preserves_existing_product(self):
        product = Product.objects.create(code="P-OLD", name="原名称")
        product.customers.add(self.customer)

        result = import_model(
            build_product_file(
                [["P-OLD", "不应保存的新名称", "客户专属", "NOT-FOUND"]]
            ),
            self.config,
        )

        self.assertEqual(result["success_count"], 0)
        self.assertEqual(result["error_count"], 1)
        product.refresh_from_db()
        self.assertEqual(product.name, "原名称")
        self.assertEqual(list(product.customers.all()), [self.customer])

    def test_scope_and_customer_count_must_match(self):
        result = import_model(
            build_product_file(
                [["P-SHARED", "共享产品", "多客户共享", self.customer.code]]
            ),
            self.config,
        )

        self.assertEqual(result["success_count"], 0)
        self.assertIn("至少两个客户", result["errors"][0])
        self.assertFalse(Product.objects.filter(code="P-SHARED").exists())
