"""
资产相关视图集的 OpenAPI 文档定义。
"""

from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view

from workorder.schema import standard_error_response, standard_success_response
from workorder.serializers.assets import (
    ArtworkProductSerializer,
    ArtworkSerializer,
    DieProductSerializer,
    DieSerializer,
    EmbossingPlateProductSerializer,
    EmbossingPlateSerializer,
    FoilingPlateProductSerializer,
    FoilingPlateSerializer,
)


artwork_docs = extend_schema_view(
    list=extend_schema(
        tags=["资产"],
        summary="获取图稿列表",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("ArtworkListResponse"),
                description="图稿列表",
            )
        },
    ),
    retrieve=extend_schema(
        tags=["资产"],
        summary="获取图稿详情",
        responses={
            200: OpenApiResponse(
                response=standard_success_response(
                    "ArtworkDetailResponse", ArtworkSerializer
                ),
                description="图稿详情",
            )
        },
    ),
)

die_docs = extend_schema_view(
    list=extend_schema(
        tags=["资产"],
        summary="获取刀模列表",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("DieListResponse"),
                description="刀模列表",
            )
        },
    ),
    retrieve=extend_schema(
        tags=["资产"],
        summary="获取刀模详情",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("DieDetailResponse", DieSerializer),
                description="刀模详情",
            )
        },
    ),
)

foiling_plate_docs = extend_schema_view(
    list=extend_schema(
        tags=["资产"],
        summary="获取烫金版列表",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("FoilingPlateListResponse"),
                description="烫金版列表",
            )
        },
    ),
    retrieve=extend_schema(
        tags=["资产"],
        summary="获取烫金版详情",
        responses={
            200: OpenApiResponse(
                response=standard_success_response(
                    "FoilingPlateDetailResponse", FoilingPlateSerializer
                ),
                description="烫金版详情",
            )
        },
    ),
)

embossing_plate_docs = extend_schema_view(
    list=extend_schema(
        tags=["资产"],
        summary="获取压凸版列表",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("EmbossingPlateListResponse"),
                description="压凸版列表",
            )
        },
    ),
    retrieve=extend_schema(
        tags=["资产"],
        summary="获取压凸版详情",
        responses={
            200: OpenApiResponse(
                response=standard_success_response(
                    "EmbossingPlateDetailResponse", EmbossingPlateSerializer
                ),
                description="压凸版详情",
            )
        },
    ),
)

confirm_docs = extend_schema(
    tags=["资产"],
    summary="确认资产",
    responses={
        200: OpenApiResponse(
            response=standard_success_response("AssetConfirmResponse"),
            description="确认成功",
        ),
        400: OpenApiResponse(
            response=standard_error_response("AssetConfirmBadRequest"),
            description="无法确认",
        ),
    },
)


artwork_product_docs = extend_schema_view(
    list=extend_schema(
        tags=["资产"],
        summary="获取图稿-产品关联列表",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("ArtworkProductListResponse"),
                description="关联列表",
            )
        },
    ),
    retrieve=extend_schema(
        tags=["资产"],
        summary="获取图稿-产品关联详情",
        responses={
            200: OpenApiResponse(
                response=standard_success_response(
                    "ArtworkProductDetailResponse", ArtworkProductSerializer
                ),
                description="关联详情",
            )
        },
    ),
)

die_product_docs = extend_schema_view(
    list=extend_schema(
        tags=["资产"],
        summary="获取刀模-产品关联列表",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("DieProductListResponse"),
                description="关联列表",
            )
        },
    ),
    retrieve=extend_schema(
        tags=["资产"],
        summary="获取刀模-产品关联详情",
        responses={
            200: OpenApiResponse(
                response=standard_success_response(
                    "DieProductDetailResponse", DieProductSerializer
                ),
                description="关联详情",
            )
        },
    ),
)

foiling_product_docs = extend_schema_view(
    list=extend_schema(
        tags=["资产"],
        summary="获取烫金版-产品关联列表",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("FoilingPlateProductListResponse"),
                description="关联列表",
            )
        },
    ),
    retrieve=extend_schema(
        tags=["资产"],
        summary="获取烫金版-产品关联详情",
        responses={
            200: OpenApiResponse(
                response=standard_success_response(
                    "FoilingPlateProductDetailResponse",
                    FoilingPlateProductSerializer,
                ),
                description="关联详情",
            )
        },
    ),
)

embossing_product_docs = extend_schema_view(
    list=extend_schema(
        tags=["资产"],
        summary="获取压凸版-产品关联列表",
        responses={
            200: OpenApiResponse(
                response=standard_success_response("EmbossingPlateProductListResponse"),
                description="关联列表",
            )
        },
    ),
    retrieve=extend_schema(
        tags=["资产"],
        summary="获取压凸版-产品关联详情",
        responses={
            200: OpenApiResponse(
                response=standard_success_response(
                    "EmbossingPlateProductDetailResponse",
                    EmbossingPlateProductSerializer,
                ),
                description="关联详情",
            )
        },
    ),
)
