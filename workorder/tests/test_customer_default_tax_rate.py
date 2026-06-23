"""Tests for Customer default_tax_rate field."""

from decimal import Decimal

from django.test import TestCase
from django.contrib.auth.models import User
from workorder.models.base import Customer
from workorder.serializers.base import CustomerSerializer


class CustomerDefaultTaxRateTests(TestCase):
    """客户默认税率字段测试"""

    def test_default_tax_rate_defaults_to_13(self):
        """默认税率应为 13%"""
        customer = Customer.objects.create(name="Test Customer")
        self.assertEqual(customer.default_tax_rate, Decimal("13.00"))

    def test_default_tax_rate_can_be_set(self):
        """可以设置自定义默认税率"""
        customer = Customer.objects.create(
            name="Test Customer", default_tax_rate=Decimal("6.00")
        )
        self.assertEqual(customer.default_tax_rate, Decimal("6.00"))

    def test_serializer_returns_default_tax_rate(self):
        """序列化器应返回 default_tax_rate"""
        customer = Customer.objects.create(
            name="Test Customer", default_tax_rate=Decimal("9.00")
        )
        serializer = CustomerSerializer(customer)
        self.assertEqual(
            Decimal(str(serializer.data["default_tax_rate"])), Decimal("9.00")
        )

    def test_serializer_validates_tax_rate_range(self):
        """序列化器应校验税率范围 0-100"""
        data = {
            "name": "Test Customer",
            "default_tax_rate": Decimal("101.00"),
        }
        serializer = CustomerSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("default_tax_rate", serializer.errors)

    def test_serializer_accepts_zero_tax_rate(self):
        """序列化器应接受 0 税率"""
        data = {"name": "Test Customer", "default_tax_rate": Decimal("0.00")}
        serializer = CustomerSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(
            Decimal(str(serializer.validated_data["default_tax_rate"])),
            Decimal("0.00"),
        )

    def test_serializer_accepts_valid_tax_rate(self):
        """序列化器应接受有效税率"""
        data = {"name": "Test Customer", "default_tax_rate": Decimal("13.00")}
        serializer = CustomerSerializer(data=data)
        self.assertTrue(serializer.is_valid())
