"""
OpenAPI schema helpers for standard API responses.
"""

from __future__ import annotations

from typing import Optional

from drf_spectacular.utils import inline_serializer
from rest_framework import serializers


def _data_field(data_serializer=None, many: bool = False):
    if data_serializer is None:
        return serializers.JSONField(required=False, allow_null=True)

    if isinstance(data_serializer, serializers.BaseSerializer):
        return data_serializer

    if isinstance(data_serializer, type) and issubclass(
        data_serializer, serializers.BaseSerializer
    ):
        return data_serializer(many=many)

    return serializers.JSONField(required=False, allow_null=True)


def standard_success_response(name: str, data_serializer=None, many: bool = False):
    return inline_serializer(
        name=name,
        fields={
            "success": serializers.BooleanField(),
            "code": serializers.IntegerField(),
            "message": serializers.CharField(),
            "data": _data_field(data_serializer, many=many),
            "timestamp": serializers.CharField(),
        },
    )


def standard_error_response(name: str, data_serializer=None):
    return inline_serializer(
        name=name,
        fields={
            "success": serializers.BooleanField(),
            "code": serializers.IntegerField(),
            "message": serializers.CharField(),
            "errors": serializers.JSONField(required=False),
            "data": _data_field(data_serializer),
            "timestamp": serializers.CharField(),
        },
    )
