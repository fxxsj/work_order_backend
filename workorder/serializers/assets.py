"""
资产序列化器模块

包含图稿、刀模、烫金版、压凸版等资产的序列化器。
"""

from rest_framework import serializers
from ..models.assets import (
    Artwork, ArtworkProduct,
    Die, DieProduct,
    FoilingPlate, FoilingPlateProduct,
    EmbossingPlate, EmbossingPlateProduct
)


class ArtworkProductSerializer(serializers.ModelSerializer):
    """图稿产品序列化器"""
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_code = serializers.CharField(source='product.code', read_only=True)

    class Meta:
        model = ArtworkProduct
        fields = '__all__'


class ArtworkSerializer(serializers.ModelSerializer):
    """图稿序列化器

    提供完整的字段验证和业务规则检查。
    """
    products = ArtworkProductSerializer(many=True, read_only=True)
    products_data = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False,
        help_text='产品列表数据，格式：[{"product": 1, "imposition_quantity": 2}]'
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
    confirmed_by_name = serializers.CharField(source='confirmed_by.username', read_only=True, allow_null=True)

    class Meta:
        model = Artwork
        fields = '__all__'
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
        valid_colors = {'C', 'M', 'Y', 'K'}
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

    def get_color_display(self, obj):
        """生成色数显示文本，格式：CMK+928C,金色（5色）"""
        parts = []
        total_count = 0

        # CMYK颜色：按照固定顺序C、M、Y、K排列
        if obj.cmyk_colors:
            cmyk_order = ['C', 'M', 'Y', 'K']  # 固定顺序：1C2M3Y4K
            cmyk_sorted = [c for c in cmyk_order if c in obj.cmyk_colors]
            if cmyk_sorted:
                cmyk_str = ''.join(cmyk_sorted)  # 按固定顺序连接，如：CMK
                parts.append(cmyk_str)
                total_count += len(obj.cmyk_colors)

        # 其他颜色：用逗号分隔
        if obj.other_colors:
            other_colors_list = [c.strip() for c in obj.other_colors if c and c.strip()]
            if other_colors_list:
                other_colors_str = ','.join(other_colors_list)  # 用逗号分隔
                parts.append(other_colors_str)
                total_count += len(other_colors_list)

        # 组合显示：如果有CMYK和其他颜色，用+号连接
        if len(parts) > 1:
            result = '+'.join(parts)
        elif len(parts) == 1:
            result = parts[0]
        else:
            return '-'

        # 添加色数统计
        if total_count > 0:
            result += f'（{total_count}色）'

        return result

    def get_die_names(self, obj):
        """获取所有刀模名称"""
        return [die.name for die in obj.dies.all()]

    def get_die_codes(self, obj):
        """获取所有刀模编码"""
        return [die.code for die in obj.dies.all()]

    def get_foiling_plate_names(self, obj):
        """获取所有烫金版名称"""
        return [plate.name for plate in obj.foiling_plates.all()]

    def get_foiling_plate_codes(self, obj):
        """获取所有烫金版编码"""
        return [plate.code for plate in obj.foiling_plates.all()]

    def get_embossing_plate_names(self, obj):
        """获取所有压凸版名称"""
        return [plate.name for plate in obj.embossing_plates.all()]

    def get_embossing_plate_codes(self, obj):
        """获取所有压凸版编码"""
        return [plate.code for plate in obj.embossing_plates.all()]

    def get_code(self, obj):
        """获取完整编码（包含版本号），用于向后兼容"""
        return obj.get_full_code()

    def create(self, validated_data):
        """创建图稿，如果主编码为空则自动生成，并创建关联产品"""
        products_data = validated_data.pop('products_data', [])

        # 如果主编码为空，自动生成
        if not validated_data.get('base_code'):
            validated_data['base_code'] = Artwork.generate_base_code()

        # 如果指定了 base_code 但没有指定 version，自动获取下一个版本号
        if validated_data.get('base_code') and 'version' not in validated_data:
            validated_data['version'] = Artwork.get_next_version(validated_data['base_code'])

        artwork = super().create(validated_data)

        # 创建关联产品
        for idx, product_data in enumerate(products_data):
            ArtworkProduct.objects.create(
                artwork=artwork,
                product_id=product_data.get('product'),
                imposition_quantity=product_data.get('imposition_quantity', 1),
                sort_order=idx
            )

        return artwork

    def update(self, instance, validated_data):
        """更新图稿，处理产品列表"""
        products_data = validated_data.pop('products_data', None)

        artwork = super().update(instance, validated_data)

        # 如果提供了产品数据，更新产品列表
        if products_data is not None:
            # 删除现有产品关联
            ArtworkProduct.objects.filter(artwork=artwork).delete()

            # 创建新的产品关联
            for idx, product_data in enumerate(products_data):
                ArtworkProduct.objects.create(
                    artwork=artwork,
                    product_id=product_data.get('product'),
                    imposition_quantity=product_data.get('imposition_quantity', 1),
                    sort_order=idx
                )

        return artwork


class DieProductSerializer(serializers.ModelSerializer):
    """刀模产品序列化器"""
    product_name = serializers.SerializerMethodField()
    product_code = serializers.SerializerMethodField()

    class Meta:
        model = DieProduct
        fields = '__all__'

    def get_product_name(self, obj):
        return obj.product.name if obj.product else None

    def get_product_code(self, obj):
        return obj.product.code if obj.product else None


class DieSerializer(serializers.ModelSerializer):
    """刀模序列化器

    提供完整的字段验证和业务规则检查。
    """
    products = DieProductSerializer(many=True, read_only=True)
    products_data = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False,
        help_text='产品列表数据，格式：[{"product": 1, "quantity": 2}]'
    )
    # 确认人名称（只读）
    confirmed_by_name = serializers.CharField(
        source='confirmed_by.username', read_only=True, allow_null=True
    )

    class Meta:
        model = Die
        fields = '__all__'
        # code 字段不在 read_only_fields 中，允许自定义输入

    def validate_name(self, value):
        """验证刀模名称"""
        if not value or not value.strip():
            raise serializers.ValidationError("刀模名称不能为空")
        if len(value) > 200:
            raise serializers.ValidationError("刀模名称不能超过200个字符")
        return value.strip()

    def validate_code(self, value):
        """验证刀模编码"""
        if value:
            value = value.strip()
            if len(value) > 50:
                raise serializers.ValidationError("刀模编码不能超过50个字符")
            # 检查编码唯一性（排除当前实例）
            queryset = Die.objects.filter(code=value)
            if self.instance:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise serializers.ValidationError("该刀模编码已存在")
        return value

    def validate_size(self, value):
        """验证尺寸字段长度"""
        if value and len(value) > 100:
            raise serializers.ValidationError("尺寸不能超过100个字符")
        return value.strip() if value else value

    def validate_material(self, value):
        """验证材质字段长度"""
        if value and len(value) > 100:
            raise serializers.ValidationError("材质不能超过100个字符")
        return value.strip() if value else value

    def validate_thickness(self, value):
        """验证厚度字段长度"""
        if value and len(value) > 50:
            raise serializers.ValidationError("厚度不能超过50个字符")
        return value.strip() if value else value

    def validate(self, attrs):
        """对象级验证：已确认刀模不允许修改关键字段"""
        if self.instance and self.instance.confirmed:
            # 已确认的刀模，检查是否修改了关键字段
            protected_fields = ['code', 'name', 'size', 'material', 'thickness']
            for field in protected_fields:
                if field in attrs:
                    old_value = getattr(self.instance, field, None) or ''
                    new_value = attrs.get(field, '') or ''
                    if old_value != new_value:
                        raise serializers.ValidationError({
                            field: f"已确认的刀模不允许修改{Die._meta.get_field(field).verbose_name}"
                        })
        return attrs

    def create(self, validated_data):
        """创建刀模，如果编码为空则自动生成，并创建关联产品"""
        from django.db import transaction

        products_data = validated_data.pop('products_data', [])

        # 如果编码为空，自动生成
        if not validated_data.get('code'):
            validated_data['code'] = Die.generate_code()

        with transaction.atomic():
            die = super().create(validated_data)

            # 创建关联产品
            for idx, product_data in enumerate(products_data):
                DieProduct.objects.create(
                    die=die,
                    product_id=product_data.get('product'),
                    quantity=product_data.get('quantity', 1),
                    sort_order=idx
                )

        return die

    def update(self, instance, validated_data):
        """更新刀模，处理产品列表"""
        from django.db import transaction

        products_data = validated_data.pop('products_data', None)

        with transaction.atomic():
            die = super().update(instance, validated_data)

            # 如果提供了产品数据，更新产品列表
            if products_data is not None:
                # 删除现有产品关联
                DieProduct.objects.filter(die=die).delete()

                # 创建新的产品关联
                for idx, product_data in enumerate(products_data):
                    DieProduct.objects.create(
                        die=die,
                        product_id=product_data.get('product'),
                        quantity=product_data.get('quantity', 1),
                        sort_order=idx
                    )

        return die


class FoilingPlateProductSerializer(serializers.ModelSerializer):
    """烫金版产品序列化器"""
    product_name = serializers.SerializerMethodField()
    product_code = serializers.SerializerMethodField()

    class Meta:
        model = FoilingPlateProduct
        fields = '__all__'

    def get_product_name(self, obj):
        return obj.product.name if obj.product else None

    def get_product_code(self, obj):
        return obj.product.code if obj.product else None


class FoilingPlateSerializer(serializers.ModelSerializer):
    """烫金版序列化器"""
    products = FoilingPlateProductSerializer(many=True, read_only=True)
    products_data = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False,
        help_text='产品列表数据，格式：[{"product": 1, "quantity": 2}]'
    )

    class Meta:
        model = FoilingPlate
        fields = '__all__'
        # code 字段不在 read_only_fields 中，允许自定义输入

    def create(self, validated_data):
        """创建烫金版，如果编码为空则自动生成，并创建关联产品"""
        products_data = validated_data.pop('products_data', [])

        # 如果编码为空，自动生成
        if not validated_data.get('code'):
            validated_data['code'] = FoilingPlate.generate_code()

        foiling_plate = super().create(validated_data)

        # 创建关联产品
        for idx, product_data in enumerate(products_data):
            FoilingPlateProduct.objects.create(
                foiling_plate=foiling_plate,
                product_id=product_data.get('product'),
                quantity=product_data.get('quantity', 1),
                sort_order=idx
            )

        return foiling_plate

    def update(self, instance, validated_data):
        """更新烫金版，处理产品列表"""
        products_data = validated_data.pop('products_data', None)

        foiling_plate = super().update(instance, validated_data)

        # 如果提供了产品数据，更新产品列表
        if products_data is not None:
            # 删除现有产品关联
            FoilingPlateProduct.objects.filter(foiling_plate=foiling_plate).delete()

            # 创建新的产品关联
            for idx, product_data in enumerate(products_data):
                FoilingPlateProduct.objects.create(
                    foiling_plate=foiling_plate,
                    product_id=product_data.get('product'),
                    quantity=product_data.get('quantity', 1),
                    sort_order=idx
                )

        return foiling_plate


class EmbossingPlateProductSerializer(serializers.ModelSerializer):
    """压凸版产品序列化器"""
    product_name = serializers.SerializerMethodField()
    product_code = serializers.SerializerMethodField()

    class Meta:
        model = EmbossingPlateProduct
        fields = '__all__'

    def get_product_name(self, obj):
        return obj.product.name if obj.product else None

    def get_product_code(self, obj):
        return obj.product.code if obj.product else None


class EmbossingPlateSerializer(serializers.ModelSerializer):
    """压凸版序列化器"""
    products = EmbossingPlateProductSerializer(many=True, read_only=True)
    products_data = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False,
        help_text='产品列表数据，格式：[{"product": 1, "quantity": 2}]'
    )

    class Meta:
        model = EmbossingPlate
        fields = '__all__'
        # code 字段不在 read_only_fields 中，允许自定义输入

    def create(self, validated_data):
        """创建压凸版，如果编码为空则自动生成，并创建关联产品"""
        products_data = validated_data.pop('products_data', [])

        # 如果编码为空，自动生成
        if not validated_data.get('code'):
            validated_data['code'] = EmbossingPlate.generate_code()

        embossing_plate = super().create(validated_data)

        # 创建关联产品
        for idx, product_data in enumerate(products_data):
            EmbossingPlateProduct.objects.create(
                embossing_plate=embossing_plate,
                product_id=product_data.get('product'),
                quantity=product_data.get('quantity', 1),
                sort_order=idx
            )

        return embossing_plate

    def update(self, instance, validated_data):
        """更新压凸版，处理产品列表"""
        products_data = validated_data.pop('products_data', None)

        embossing_plate = super().update(instance, validated_data)

        # 如果提供了产品数据，更新产品列表
        if products_data is not None:
            # 删除现有产品关联
            EmbossingPlateProduct.objects.filter(embossing_plate=embossing_plate).delete()

            # 创建新的产品关联
            for idx, product_data in enumerate(products_data):
                EmbossingPlateProduct.objects.create(
                    embossing_plate=embossing_plate,
                    product_id=product_data.get('product'),
                    quantity=product_data.get('quantity', 1),
                    sort_order=idx
                )

        return embossing_plate
