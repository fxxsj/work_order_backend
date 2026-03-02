"""
产品相关视图集的 OpenAPI 文档定义。
"""

from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view

from workorder.schema import standard_error_response, standard_success_response
from workorder.serializers.products import (
    ProductGroupItemSerializer,
    ProductGroupSerializer,
    ProductMaterialSerializer,
    ProductSerializer,
)


product_docs = extend_schema_view(
    list=extend_schema(
        tags=["产品"],
        summary="获取产品列表",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("ProductListResponse"),
                description="产品列表",
            )
        },
    ),
    retrieve=extend_schema(
        tags=["产品"],
        summary="获取产品详情",
        responses={
            200: OpenApiResponse(
                response=standard_success_response(
                    "ProductDetailResponse", ProductSerializer
                ),
                description="产品详情",
            )
        },
    ),
    create=extend_schema(
        tags=["产品"],
        summary="创建产品",
        responses={
            201: OpenApiResponse(
                response=standard_success_response(
                    "ProductCreateResponse", ProductSerializer
                ),
                description="创建成功",
            ),
            400: OpenApiResponse(
                response=standard_error_response("ProductCreateBadRequest"),
                description="请求无效",
            ),
        },
    ),
    update=extend_schema(
        tags=["产品"],
        summary="更新产品",
        responses={
            200: OpenApiResponse(
                response=standard_success_response(
                    "ProductUpdateResponse", ProductSerializer
                ),
                description="更新成功",
            )
        },
    ),
    destroy=extend_schema(
        tags=["产品"],
        summary="删除产品",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("ProductDeleteResponse"),
                description="删除成功",
            ),
            400: OpenApiResponse(
                response=standard_error_response("ProductDeleteBadRequest"),
                description="删除失败",
            ),
        },
    ),
)


product_material_docs = extend_schema_view(
    list=extend_schema(
        tags=["产品"],
        summary="获取产品物料列表",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("ProductMaterialListResponse"),
                description="产品物料列表",
            )
        },
    ),
    retrieve=extend_schema(
        tags=["产品"],
        summary="获取产品物料详情",
        responses={
            200: OpenApiResponse(
                response=standard_success_response(
                    "ProductMaterialDetailResponse", ProductMaterialSerializer
                ),
                description="产品物料详情",
            )
        },
    ),
    create=extend_schema(
        tags=["产品"],
        summary="创建产品物料",
        responses={
            201: OpenApiResponse(
                response=standard_success_response(
                    "ProductMaterialCreateResponse", ProductMaterialSerializer
                ),
                description="创建成功",
            ),
            400: OpenApiResponse(
                response=standard_error_response(
                    "ProductMaterialCreateBadRequest"
                ),
                description="请求无效",
            ),
        },
    ),
    update=extend_schema(
        tags=["产品"],
        summary="更新产品物料",
        responses={
            200: OpenApiResponse(
                response=standard_success_response(
                    "ProductMaterialUpdateResponse", ProductMaterialSerializer
                ),
                description="更新成功",
            )
        },
    ),
    destroy=extend_schema(
        tags=["产品"],
        summary="删除产品物料",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("ProductMaterialDeleteResponse"),
                description="删除成功",
            ),
            400: OpenApiResponse(
                response=standard_error_response(
                    "ProductMaterialDeleteBadRequest"
                ),
                description="删除失败",
            ),
        },
    ),
)


product_group_docs = extend_schema_view(
    list=extend_schema(
        tags=["产品"],
        summary="获取产品组列表",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("ProductGroupListResponse"),
                description="产品组列表",
            )
        },
    ),
    retrieve=extend_schema(
        tags=["产品"],
        summary="获取产品组详情",
        responses={
            200: OpenApiResponse(
                response=standard_success_response(
                    "ProductGroupDetailResponse", ProductGroupSerializer
                ),
                description="产品组详情",
            )
        },
    ),
    create=extend_schema(
        tags=["产品"],
        summary="创建产品组",
        responses={
            201: OpenApiResponse(
                response=standard_success_response(
                    "ProductGroupCreateResponse", ProductGroupSerializer
                ),
                description="创建成功",
            ),
            400: OpenApiResponse(
                response=standard_error_response("ProductGroupCreateBadRequest"),
                description="请求无效",
            ),
        },
    ),
    update=extend_schema(
        tags=["产品"],
        summary="更新产品组",
        responses={
            200: OpenApiResponse(
                response=standard_success_response(
                    "ProductGroupUpdateResponse", ProductGroupSerializer
                ),
                description="更新成功",
            )
        },
    ),
    destroy=extend_schema(
        tags=["产品"],
        summary="删除产品组",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("ProductGroupDeleteResponse"),
                description="删除成功",
            ),
            400: OpenApiResponse(
                response=standard_error_response("ProductGroupDeleteBadRequest"),
                description="删除失败",
            ),
        },
    ),
)


product_group_item_docs = extend_schema_view(
    list=extend_schema(
        tags=["产品"],
        summary="获取产品组子项列表",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("ProductGroupItemListResponse"),
                description="产品组子项列表",
            )
        },
    ),
    retrieve=extend_schema(
        tags=["产品"],
        summary="获取产品组子项详情",
        responses={
            200: OpenApiResponse(
                response=standard_success_response(
                    "ProductGroupItemDetailResponse", ProductGroupItemSerializer
                ),
                description="产品组子项详情",
            )
        },
    ),
    create=extend_schema(
        tags=["产品"],
        summary="创建产品组子项",
        responses={
            201: OpenApiResponse(
                response=standard_success_response(
                    "ProductGroupItemCreateResponse", ProductGroupItemSerializer
                ),
                description="创建成功",
            ),
            400: OpenApiResponse(
                response=standard_error_response(
                    "ProductGroupItemCreateBadRequest"
                ),
                description="请求无效",
            ),
        },
    ),
    update=extend_schema(
        tags=["产品"],
        summary="更新产品组子项",
        responses={
            200: OpenApiResponse(
                response=standard_success_response(
                    "ProductGroupItemUpdateResponse", ProductGroupItemSerializer
                ),
                description="更新成功",
            )
        },
    ),
    destroy=extend_schema(
        tags=["产品"],
        summary="删除产品组子项",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("ProductGroupItemDeleteResponse"),
                description="删除成功",
            ),
            400: OpenApiResponse(
                response=standard_error_response(
                    "ProductGroupItemDeleteBadRequest"
                ),
                description="删除失败",
            ),
        },
    ),
)
