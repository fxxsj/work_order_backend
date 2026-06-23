"""
资产序列化器模块

包含图稿、刀模、烫金版、压凸版等资产的序列化器。
"""

from typing import List

from rest_framework import serializers

from ..models.assets import (
    Artwork,
    ArtworkImage,
    ArtworkProduct,
    Die,
    DieImage,
    DieProduct,
    EmbossingPlate,
    EmbossingPlateImage,
    EmbossingPlateProduct,
    FoilingPlate,
    FoilingPlateImage,
    FoilingPlateProduct,
)
from .base import (
    PlateAssetSerializer,
    create_image_serializer,
    create_product_serializer,
)
from ..utils import format_color_display


class ArtworkProductSerializer(serializers.ModelSerializer):
    """图稿产品序列化器"""

    product_name = serializers.CharField(source="product.name", read_only=True)
    product_code = serializers.CharField(source="product.code", read_only=True)

    class Meta:
        model = ArtworkProduct
        fields = "__all__"


# 资产图片序列化器（工厂生成，字段配置统一）
ArtworkImageSerializer = create_image_serializer(
    ArtworkImage, "ArtworkImageSerializer"
)
DieImageSerializer = create_image_serializer(DieImage, "DieImageSerializer")


class ArtworkSerializer(serializers.ModelSerializer):
    """图稿序列化器

    提供完整的字段验证和业务规则检查。
    """

    products = ArtworkProductSerializer(many=True, read_only=True)
    # 新增 - 图稿图片列表
    images = ArtworkImageSerializer(many=True, read_only=True)
    products_data = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False,
        help_text='产品列表数据，格式：[{"product": 1, "imposition_quantity": 2}]',
    )
    # 色数显示（计算字段）
    color_display = serializers.SerializerMethodField()
    # 刀模信息
    die_names = serializers.SerializerMethodField()
    die_codes = serializers.SerializerMethodField()
    # 烫金版信息
    foiling_plate_names = serializers.SerializerMethodField()
    foiling_plate_codes = serializers.SerializerMethodField()
    # 压凸版信息
    embossing_plate_names = serializers.SerializerMethodField()
    embossing_plate_codes = serializers.SerializerMethodField()
    # 完整编码（包含版本号），用于向后兼容
    code = serializers.SerializerMethodField()
    # 确认信息
    confirmed_by_name = serializers.CharField(
        source="confirmed_by.username", read_only=True, allow_null=True
    )

    class Meta:
        model = Artwork
        fields = "__all__"
        # base_code 字段不在 read_only_fields 中，允许自定义输入

    def validate_name(self, value):
        """验证图稿名称"""
        if not value or not value.strip():
            raise serializers.ValidationError("图稿名称不能为空")
        if len(value) > 200:
            raise serializers.ValidationError("图稿名称不能超过200个字符")
        return value.strip()

    def validate_cmyk_colors(self, value):
        """验证CMYK颜色"""
        valid_colors = {"C", "M", "Y", "K"}
        if value:
            for color in value:
                if color not in valid_colors:
                    raise serializers.ValidationError(
                        f"无效的CMYK颜色: {color}，允许的值: C, M, Y, K"
                    )
        return value

    def validate_other_colors(self, value):
        """验证其他颜色列表"""
        if value:
            # 过滤空值并去除空白
            return [c.strip() for c in value if c and c.strip()]
        return value

    def get_color_display(self, obj) -> str:
        """生成色数显示文本，格式：CMK+928C,金色（5色）"""
        return format_color_display(obj.cmyk_colors, obj.other_colors) or "-"

    def get_die_names(self, obj) -> List[str]:
        """获取所有刀模名称"""
        return [die.name for die in obj.dies.all()]

    def get_die_codes(self, obj) -> List[str]:
        """获取所有刀模编码"""
        return [die.code for die in obj.dies.all()]

    def get_foiling_plate_names(self, obj) -> List[str]:
        """获取所有烫金版名称"""
        return [plate.name for plate in obj.foiling_plates.all()]

    def get_foiling_plate_codes(self, obj) -> List[str]:
        """获取所有烫金版编码"""
        return [plate.code for plate in obj.foiling_plates.all()]

    def get_embossing_plate_names(self, obj) -> List[str]:
        """获取所有压凸版名称"""
        return [plate.name for plate in obj.embossing_plates.all()]

    def get_embossing_plate_codes(self, obj) -> List[str]:
        """获取所有压凸版编码"""
        return [plate.code for plate in obj.embossing_plates.all()]

    def get_code(self, obj) -> str:
        """获取完整编码（包含版本号），用于向后兼容"""
        return obj.get_full_code()

    def create(self, validated_data):
        """创建图稿，如果主编码为空则自动生成，并创建关联产品"""
        products_data = validated_data.pop("products_data", [])

        # 如果主编码为空，自动生成
        if not validated_data.get("base_code"):
            validated_data["base_code"] = Artwork.generate_base_code()

        # 如果指定了 base_code 但没有指定 version，自动获取下一个版本号
        if validated_data.get("base_code") and "version" not in validated_data:
            validated_data["version"] = Artwork.get_next_version(
                validated_data["base_code"]
            )

        artwork = super().create(validated_data)

        # 创建关联产品
        for idx, product_data in enumerate(products_data):
            ArtworkProduct.objects.create(
                artwork=artwork,
                product_id=product_data.get("product"),
                imposition_quantity=product_data.get("imposition_quantity", 1),
                sort_order=idx,
            )

        return artwork

    def update(self, instance, validated_data):
        """更新图稿，处理产品列表"""
        products_data = validated_data.pop("products_data", None)

        artwork = super().update(instance, validated_data)

        # 如果提供了产品数据，更新产品列表
        if products_data is not None:
            # 删除现有产品关联
            ArtworkProduct.objects.filter(artwork=artwork).delete()

            # 创建新的产品关联
            for idx, product_data in enumerate(products_data):
                ArtworkProduct.objects.create(
                    artwork=artwork,
                    product_id=product_data.get("product"),
                    imposition_quantity=product_data.get(
                        "imposition_quantity", 1
                    ),
                    sort_order=idx,
                )

        return artwork


DieProductSerializer = create_product_serializer(
    DieProduct,
    "DieProductSerializer",
    extra_fields={
        "relation_type_display": serializers.CharField(
            source="get_relation_type_display", read_only=True
        ),
    },
)


class DieSerializer(PlateAssetSerializer):
    """刀模序列化器"""

    plate_model = Die
    plate_name_verbose = "刀模"
    product_model = DieProduct
    product_fk_field = "die"
    use_transaction = True

    products = DieProductSerializer(many=True, read_only=True)
    images = DieImageSerializer(many=True, read_only=True)
    die_type_display = serializers.CharField(
        source="get_die_type_display", read_only=True
    )

    class Meta:
        model = Die
        fields = "__all__"

    def _build_product_kwargs(self, product_data, index):
        return {
            "product_id": product_data.get("product"),
            "quantity": product_data.get("quantity", 1),
            "relation_type": product_data.get("relation_type", "exclusive"),
            "sort_order": index,
        }


FoilingPlateImageSerializer = create_image_serializer(
    FoilingPlateImage, "FoilingPlateImageSerializer"
)
FoilingPlateProductSerializer = create_product_serializer(
    FoilingPlateProduct, "FoilingPlateProductSerializer"
)


class FoilingPlateSerializer(PlateAssetSerializer):
    """烫金版序列化器"""

    plate_model = FoilingPlate
    plate_name_verbose = "烫金版"
    product_model = FoilingPlateProduct
    product_fk_field = "foiling_plate"
    use_transaction = False

    products = FoilingPlateProductSerializer(many=True, read_only=True)
    images = FoilingPlateImageSerializer(many=True, read_only=True)

    class Meta:
        model = FoilingPlate
        fields = "__all__"


EmbossingPlateImageSerializer = create_image_serializer(
    EmbossingPlateImage, "EmbossingPlateImageSerializer"
)
EmbossingPlateProductSerializer = create_product_serializer(
    EmbossingPlateProduct, "EmbossingPlateProductSerializer"
)


class EmbossingPlateSerializer(PlateAssetSerializer):
    """压凸版序列化器"""

    plate_model = EmbossingPlate
    plate_name_verbose = "压凸版"
    product_model = EmbossingPlateProduct
    product_fk_field = "embossing_plate"
    use_transaction = False

    products = EmbossingPlateProductSerializer(many=True, read_only=True)
    images = EmbossingPlateImageSerializer(many=True, read_only=True)

    class Meta:
        model = EmbossingPlate
        fields = "__all__"
