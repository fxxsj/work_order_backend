"""产品客户历史关系回填命令测试。"""

from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from openpyxl import Workbook

from workorder.models.base import Customer
from workorder.models.products import Product, ProductCustomer


class BackfillProductCustomersCommandTest(TestCase):
    def setUp(self):
        self.customer_a = Customer.objects.create(name="客户 A")
        self.customer_b = Customer.objects.create(name="客户 B")
        self.product_a = Product.objects.create(code="P-A", name="产品 A")
        self.product_b = Product.objects.create(code="P-B", name="产品 B")
        self.temporary_directory = TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)

    def build_file(self, rows, headers=("客户", "产品名称", "单位")):
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "合并查询"
        sheet.append(list(headers))
        for row in rows:
            sheet.append(list(row))
        path = Path(self.temporary_directory.name) / "history.xlsx"
        workbook.save(path)
        workbook.close()
        return path

    def test_default_mode_only_previews_without_writing(self):
        path = self.build_file(
            [
                ("客户 A", "产品 A"),
                ("客户 A", "产品 A"),
                ("客户 B", "产品 B"),
            ]
        )
        stdout = StringIO()

        call_command(
            "backfill_product_customers_from_history",
            str(path),
            stdout=stdout,
        )

        self.assertEqual(ProductCustomer.objects.count(), 0)
        self.assertIn("源文件唯一关系：2", stdout.getvalue())
        self.assertIn("数据库未发生变化", stdout.getvalue())

    def test_apply_is_idempotent_and_normalizes_width_and_whitespace(self):
        path = self.build_file(
            [
                ("  客户   A ", "产品 Ａ"),
                ("客户 B", "产品 B"),
            ]
        )

        call_command(
            "backfill_product_customers_from_history",
            str(path),
            apply=True,
        )
        call_command(
            "backfill_product_customers_from_history",
            str(path),
            apply=True,
        )

        self.assertSetEqual(
            set(ProductCustomer.objects.values_list("product_id", "customer_id")),
            {
                (self.product_a.id, self.customer_a.id),
                (self.product_b.id, self.customer_b.id),
            },
        )

    def test_apply_refuses_unmatched_without_explicit_override(self):
        path = self.build_file(
            [
                ("客户 A", "产品 A"),
                ("不存在客户", "产品 B"),
            ]
        )

        with self.assertRaisesMessage(CommandError, "存在未匹配记录"):
            call_command(
                "backfill_product_customers_from_history",
                str(path),
                apply=True,
            )
        self.assertEqual(ProductCustomer.objects.count(), 0)

        call_command(
            "backfill_product_customers_from_history",
            str(path),
            apply=True,
            allow_unmatched=True,
        )
        self.assertTrue(
            ProductCustomer.objects.filter(
                product=self.product_a,
                customer=self.customer_a,
            ).exists()
        )
        self.assertFalse(Customer.objects.filter(name="不存在客户").exists())

    def test_apply_always_refuses_ambiguous_database_names(self):
        Customer.objects.create(name="客户 A")
        path = self.build_file([("客户 A", "产品 A")])

        with self.assertRaisesMessage(CommandError, "存在重名歧义"):
            call_command(
                "backfill_product_customers_from_history",
                str(path),
                apply=True,
                allow_unmatched=True,
            )

        self.assertEqual(ProductCustomer.objects.count(), 0)

    def test_explicit_override_skips_ambiguous_and_writes_safe_pairs(self):
        Product.objects.create(code="P-A-DUP", name="产品 A")
        path = self.build_file(
            [
                ("客户 A", "产品 A"),
                ("客户 B", "产品 B"),
            ]
        )

        call_command(
            "backfill_product_customers_from_history",
            str(path),
            apply=True,
            allow_ambiguous=True,
        )

        self.assertSetEqual(
            set(ProductCustomer.objects.values_list("product_id", "customer_id")),
            {(self.product_b.id, self.customer_b.id)},
        )

    def test_unit_can_resolve_duplicate_product_names(self):
        self.product_a.unit = "个"
        self.product_a.save(update_fields=["unit"])
        other_product = Product.objects.create(
            code="P-A-OTHER",
            name="产品 A",
            unit="张",
        )
        path = self.build_file([("客户 A", "产品 A", "张")])
        stdout = StringIO()

        call_command(
            "backfill_product_customers_from_history",
            str(path),
            apply=True,
            stdout=stdout,
        )

        self.assertTrue(
            ProductCustomer.objects.filter(
                product=other_product,
                customer=self.customer_a,
            ).exists()
        )
        self.assertFalse(
            ProductCustomer.objects.filter(
                product=self.product_a,
                customer=self.customer_a,
            ).exists()
        )
        self.assertIn("其中按单位消除同名歧义：1", stdout.getvalue())

    def test_missing_required_header_is_rejected(self):
        path = self.build_file(
            [("客户 A", "产品 A")],
            headers=("客户", "错误产品列"),
        )

        with self.assertRaisesMessage(CommandError, "缺少产品列"):
            call_command(
                "backfill_product_customers_from_history",
                str(path),
            )
