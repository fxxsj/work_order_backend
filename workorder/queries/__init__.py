"""Shared query helpers used by both views and services."""

from .sales_order_scope import scope_sales_orders

__all__ = ["scope_sales_orders"]
