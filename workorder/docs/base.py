"""
基础数据视图集的 OpenAPI 文档定义。
"""

from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
    inline_serializer,
)
from rest_framework import serializers

from workorder.schema import standard_error_response, standard_success_response
from workorder.serializers.base import (
    CustomerSerializer,
    DepartmentSerializer,
    ProcessSerializer,
)


customer_docs = extend_schema_view(
    list=extend_schema(
        tags=["客户"],
        summary="获取客户列表",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("CustomerListResponse"),
                description="客户列表",
                examples=[
                    OpenApiExample(
                        name="示例响应",
                        summary="客户分页列表",
                        value={
                            "success": True,
                            "code": 200,
                            "message": "操作成功",
                            "data": {
                                "count": 1,
                                "next": None,
                                "previous": None,
                                "results": [
                                    {
                                        "id": 3,
                                        "name": "示例客户",
                                        "contact_person": "张三",
                                        "phone": "13800138000",
                                    }
                                ],
                            },
                            "timestamp": "2026-03-02T09:00:00+08:00",
                        },
                        response_only=True,
                    )
                ],
            )
        },
    ),
    retrieve=extend_schema(
        tags=["客户"],
        summary="获取客户详情",
        responses={
            200: OpenApiResponse(
                response=standard_success_response(
                    "CustomerDetailResponse", CustomerSerializer
                ),
                description="客户详情",
            ),
            404: OpenApiResponse(
                response=standard_error_response("CustomerNotFoundResponse"),
                description="客户不存在",
            ),
        },
    ),
    create=extend_schema(
        tags=["客户"],
        summary="创建客户",
        responses={
            201: OpenApiResponse(
                response=standard_success_response(
                    "CustomerCreateResponse", CustomerSerializer
                ),
                description="创建成功",
            ),
            400: OpenApiResponse(
                response=standard_error_response("CustomerCreateBadRequest"),
                description="请求无效",
            ),
        },
    ),
    destroy=extend_schema(
        tags=["客户"],
        summary="删除客户",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("CustomerDeleteResponse"),
                description="删除成功",
            ),
            400: OpenApiResponse(
                response=standard_error_response("CustomerDeleteBadRequest"),
                description="删除失败",
            ),
        },
    ),
)


department_docs = extend_schema_view(
    list=extend_schema(
        tags=["部门"],
        summary="获取部门列表",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("DepartmentListResponse"),
                description="部门列表",
                examples=[
                    OpenApiExample(
                        name="示例响应",
                        summary="部门分页列表",
                        value={
                            "success": True,
                            "code": 200,
                            "message": "操作成功",
                            "data": {
                                "count": 1,
                                "next": None,
                                "previous": None,
                                "results": [
                                    {"id": 2, "name": "印刷车间", "code": "PRINT"}
                                ],
                            },
                            "timestamp": "2026-03-02T09:00:00+08:00",
                        },
                        response_only=True,
                    )
                ],
            )
        },
    ),
    retrieve=extend_schema(
        tags=["部门"],
        summary="获取部门详情",
        responses={
            200: OpenApiResponse(
                response=standard_success_response(
                    "DepartmentDetailResponse", DepartmentSerializer
                ),
                description="部门详情",
            ),
            404: OpenApiResponse(
                response=standard_error_response("DepartmentNotFoundResponse"),
                description="部门不存在",
            ),
        },
    ),
    create=extend_schema(
        tags=["部门"],
        summary="创建部门",
        responses={
            201: OpenApiResponse(
                response=standard_success_response(
                    "DepartmentCreateResponse", DepartmentSerializer
                ),
                description="创建成功",
            ),
            400: OpenApiResponse(
                response=standard_error_response("DepartmentCreateBadRequest"),
                description="请求无效",
            ),
        },
    ),
    destroy=extend_schema(
        tags=["部门"],
        summary="删除部门",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("DepartmentDeleteResponse"),
                description="删除成功",
            ),
            400: OpenApiResponse(
                response=standard_error_response("DepartmentDeleteBadRequest"),
                description="删除失败",
            ),
        },
    ),
)


department_tree_docs = extend_schema(
    tags=["部门"],
    summary="获取部门树结构",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("DepartmentTreeResponse"),
            description="部门树",
        )
    },
)


department_all_docs = extend_schema(
    tags=["部门"],
    summary="获取所有部门（简化版）",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("DepartmentAllResponse"),
            description="部门列表",
        )
    },
)


process_docs = extend_schema_view(
    list=extend_schema(
        tags=["工序"],
        summary="获取工序列表",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("ProcessListResponse"),
                description="工序列表",
                examples=[
                    OpenApiExample(
                        name="示例响应",
                        summary="工序分页列表",
                        value={
                            "success": True,
                            "code": 200,
                            "message": "操作成功",
                            "data": {
                                "count": 1,
                                "next": None,
                                "previous": None,
                                "results": [
                                    {"id": 5, "name": "印刷", "code": "PRINT"}
                                ],
                            },
                            "timestamp": "2026-03-02T09:00:00+08:00",
                        },
                        response_only=True,
                    )
                ],
            )
        },
    ),
    retrieve=extend_schema(
        tags=["工序"],
        summary="获取工序详情",
        responses={
            200: OpenApiResponse(
                response=standard_success_response(
                    "ProcessDetailResponse", ProcessSerializer
                ),
                description="工序详情",
            ),
            404: OpenApiResponse(
                response=standard_error_response("ProcessNotFoundResponse"),
                description="工序不存在",
            ),
        },
    ),
    create=extend_schema(
        tags=["工序"],
        summary="创建工序",
        responses={
            201: OpenApiResponse(
                response=standard_success_response(
                    "ProcessCreateResponse", ProcessSerializer
                ),
                description="创建成功",
            ),
            400: OpenApiResponse(
                response=standard_error_response("ProcessCreateBadRequest"),
                description="请求无效",
            ),
        },
    ),
    destroy=extend_schema(
        tags=["工序"],
        summary="删除工序",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("ProcessDeleteResponse"),
                description="删除成功",
            ),
            400: OpenApiResponse(
                response=standard_error_response("ProcessDeleteBadRequest"),
                description="删除失败",
            ),
        },
    ),
)


process_batch_update_active_docs = extend_schema(
    tags=["工序"],
    summary="批量更新工序启用状态",
    request=inline_serializer(
        name="ProcessBatchUpdateActiveRequest",
        fields={
            "ids": serializers.ListField(child=serializers.IntegerField()),
            "is_active": serializers.BooleanField(required=False),
        },
    ),
    responses={
        200: OpenApiResponse(
            response=standard_success_response("ProcessBatchUpdateActiveResponse"),
            description="更新成功",
        ),
        400: OpenApiResponse(
            response=standard_error_response("ProcessBatchUpdateActiveBadRequest"),
            description="请求无效",
        ),
    },
)


process_all_docs = extend_schema(
    tags=["工序"],
    summary="获取所有工序（简化版）",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("ProcessAllResponse"),
            description="工序列表",
        )
    },
)
