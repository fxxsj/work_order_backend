"""
导入/导出配置

定义各模型的导出/导入配置，供 ViewSet 使用。
"""

from .import_export import ExportConfig, ExportField, ImportConfig, ImportField


# ============ 客户配置 ============

CUSTOMER_EXPORT_CONFIG = ExportConfig(
    filename='customers',
    sheet_title='客户列表',
    fields=[
        ExportField('名称', lambda x: x.name),
        ExportField('联系人', lambda x: x.contact_person),
        ExportField('电话', lambda x: x.phone),
        ExportField('邮箱', lambda x: x.email),
        ExportField('地址', lambda x: x.address),
        ExportField('业务员', lambda x: x.salesperson.username if x.salesperson else ''),
        ExportField('备注', lambda x: x.notes),
        ExportField('创建时间', lambda x: x.created_at),
    ],
    column_widths=[20, 12, 15, 25, 30, 12, 30, 20],
)


def strip_val(v):
    """字符串转换并去除首尾空格"""
    return str(v).strip() if v else ''


def no_op(v):
    return v


CUSTOMER_IMPORT_CONFIG = ImportConfig(
    model=None,  # 动态设置
    unique_field='name',
    field_mappings=[
        ImportField(['名称', 'name'], 'name', strip_val),
        ImportField(['联系人', 'contact'], 'contact_person', strip_val),
        ImportField(['电话', 'phone'], 'phone', strip_val),
        ImportField(['邮箱', 'email'], 'email', strip_val),
        ImportField(['地址', 'address'], 'address', strip_val),
        ImportField(['备注', 'notes'], 'notes', strip_val),
    ],
    update_fields=['contact_person', 'phone', 'email', 'address', 'notes'],
    create_defaults={'salesperson': lambda user: user if user and user.is_authenticated else None},
    pre_save_hook=None,
    unique_field_case_insensitive=True,
)


# ============ 产品配置 ============

PRODUCT_TYPE_MAP = {
    '单品': 'single',
    '套装主产品': 'group_main',
    '套装子产品': 'group_item',
    'single': 'single',
    'group_main': 'group_main',
    'group_item': 'group_item',
}


def product_pre_save_hook(instance, data):
    """产品保存前钩子"""
    group_name = data.get('product_group_name')
    group = None
    if group_name:
        from .models.products import ProductGroup
        group = ProductGroup.objects.filter(name=group_name).first()
    
    if instance:
        if hasattr(instance, 'product_group'):
            instance.product_group = group
    else:
        data['product_group'] = group
        data.pop('product_group_name', None)


def parse_product_type(val):
    """解析产品类型"""
    if val is None:
        return 'single'
    return PRODUCT_TYPE_MAP.get(str(val).strip(), 'single')


def parse_number(val, default=0):
    """解析数字"""
    if val is None:
        return default
    try:
        return float(val) if default == 0.0 else int(val)
    except (ValueError, TypeError):
        return default


def parse_bool(val):
    """解析布尔值"""
    if val is None:
        return True
    return str(val).strip().lower() in ('是', 'yes', 'true', '1', '启用')


PRODUCT_EXPORT_CONFIG = ExportConfig(
    filename='products',
    sheet_title='产品列表',
    fields=[
        ExportField('编码', lambda x: x.code),
        ExportField('名称', lambda x: x.name),
        ExportField('规格', lambda x: x.specification),
        ExportField('单位', lambda x: x.unit),
        ExportField('单价', lambda x: str(x.unit_price) if x.unit_price else '0'),
        ExportField('库存数量', lambda x: x.stock_quantity or 0),
        ExportField('最小库存', lambda x: x.min_stock_quantity or 0),
        ExportField('产品类型', lambda x: {'single': '单品', 'group_main': '套装主产品', 'group_item': '套装子产品'}.get(x.product_type, x.product_type or '')),
        ExportField('产品组', lambda x: x.product_group.name if x.product_group else ''),
        ExportField('描述', lambda x: x.description),
        ExportField('是否启用', lambda x: '是' if x.is_active else '否'),
        ExportField('创建时间', lambda x: x.created_at),
    ],
    column_widths=[15, 20, 20, 8, 10, 10, 10, 12, 15, 30, 10, 20],
)


PRODUCT_IMPORT_CONFIG = ImportConfig(
    model=None,  # 动态设置
    unique_field='code',
    field_mappings=[
        ImportField(['编码', 'code'], 'code', strip_val),
        ImportField(['名称', 'name'], 'name', strip_val),
        ImportField(['规格', 'specification', 'spec'], 'specification', strip_val),
        ImportField(['单位', 'unit'], 'unit', strip_val),
        ImportField(['单价', 'price', 'unit_price'], 'unit_price', lambda v: parse_number(v, 0.0)),
        ImportField(['库存数量', 'stock', 'stock_quantity'], 'stock_quantity', lambda v: parse_number(v, 0)),
        ImportField(['最小库存', 'min_stock', 'min_stock_quantity'], 'min_stock_quantity', lambda v: parse_number(v, 0)),
        ImportField(['产品类型', 'type', 'product_type'], 'product_type', parse_product_type),
        ImportField(['产品组', 'group', 'product_group'], 'product_group_name', strip_val),
        ImportField(['描述', 'description', 'desc'], 'description', strip_val),
        ImportField(['是否启用', 'active', 'enabled', 'is_active'], 'is_active', parse_bool),
    ],
    update_fields=['name', 'specification', 'unit', 'unit_price', 'stock_quantity',
                  'min_stock_quantity', 'product_type', 'description', 'is_active'],
    pre_save_hook=product_pre_save_hook,
    unique_field_case_insensitive=True,
)


def get_customer_import_config(model_class):
    """获取客户导入配置（动态设置model）"""
    config = ImportConfig(
        model=model_class,
        unique_field='name',
        field_mappings=[
            ImportField(['名称', 'name'], 'name', strip_val),
            ImportField(['联系人', 'contact'], 'contact_person', strip_val),
            ImportField(['电话', 'phone'], 'phone', strip_val),
            ImportField(['邮箱', 'email'], 'email', strip_val),
            ImportField(['地址', 'address'], 'address', strip_val),
            ImportField(['备注', 'notes'], 'notes', strip_val),
        ],
        update_fields=['contact_person', 'phone', 'email', 'address', 'notes'],
        create_defaults={'salesperson': lambda user: user if user and user.is_authenticated else None},
        pre_save_hook=None,
        unique_field_case_insensitive=True,
    )
    return config


def get_product_import_config(model_class):
    """获取产品导入配置（动态设置model）"""
    config = ImportConfig(
        model=model_class,
        unique_field='code',
        field_mappings=[
            ImportField(['编码', 'code'], 'code', strip_val),
            ImportField(['名称', 'name'], 'name', strip_val),
            ImportField(['规格', 'specification', 'spec'], 'specification', strip_val),
            ImportField(['单位', 'unit'], 'unit', strip_val),
            ImportField(['单价', 'price', 'unit_price'], 'unit_price', lambda v: parse_number(v, 0.0)),
            ImportField(['库存数量', 'stock', 'stock_quantity'], 'stock_quantity', lambda v: parse_number(v, 0)),
            ImportField(['最小库存', 'min_stock', 'min_stock_quantity'], 'min_stock_quantity', lambda v: parse_number(v, 0)),
            ImportField(['产品类型', 'type', 'product_type'], 'product_type', parse_product_type),
            ImportField(['产品组', 'group', 'product_group'], 'product_group_name', strip_val),
            ImportField(['描述', 'description', 'desc'], 'description', strip_val),
            ImportField(['是否启用', 'active', 'enabled', 'is_active'], 'is_active', parse_bool),
        ],
        update_fields=['name', 'specification', 'unit', 'unit_price', 'stock_quantity',
                      'min_stock_quantity', 'product_type', 'description', 'is_active'],
        pre_save_hook=product_pre_save_hook,
        unique_field_case_insensitive=True,
    )
    return config


# ============ 物料配置 ============

def material_pre_save_hook(instance, data):
    """物料保存前钩子"""
    supplier_name = data.get('default_supplier_name')
    supplier = None
    if supplier_name:
        from .models.materials import Supplier
        supplier = Supplier.objects.filter(name=supplier_name).first()
    
    if instance:
        instance.default_supplier = supplier
    else:
        data['default_supplier'] = supplier
        data.pop('default_supplier_name', None)


MATERIAL_EXPORT_CONFIG = ExportConfig(
    filename='materials',
    sheet_title='物料列表',
    fields=[
        ExportField('编码', lambda x: x.code),
        ExportField('名称', lambda x: x.name),
        ExportField('规格', lambda x: x.specification),
        ExportField('单位', lambda x: x.unit),
        ExportField('单价', lambda x: str(x.unit_price) if x.unit_price else '0'),
        ExportField('库存数量', lambda x: str(x.stock_quantity) if x.stock_quantity else '0'),
        ExportField('最小库存', lambda x: str(x.min_stock_quantity) if x.min_stock_quantity else '0'),
        ExportField('默认供应商', lambda x: x.default_supplier.name if x.default_supplier else ''),
        ExportField('采购周期(天)', lambda x: x.lead_time_days),
        ExportField('是否需要开料', lambda x: '是' if x.need_cutting else '否'),
        ExportField('备注', lambda x: x.notes),
        ExportField('创建时间', lambda x: x.created_at),
    ],
    column_widths=[15, 20, 20, 8, 10, 10, 10, 20, 15, 12, 30, 20],
)


MATERIAL_IMPORT_CONFIG = ImportConfig(
    model=None,  # 动态设置
    unique_field='code',
    field_mappings=[
        ImportField(['编码', 'code'], 'code', strip_val),
        ImportField(['名称', 'name'], 'name', strip_val),
        ImportField(['规格', 'specification', 'spec'], 'specification', strip_val),
        ImportField(['单位', 'unit'], 'unit', strip_val),
        ImportField(['单价', 'price', 'unit_price'], 'unit_price', lambda v: parse_number(v, 0.0)),
        ImportField(['库存数量', 'stock', 'stock_quantity'], 'stock_quantity', lambda v: parse_number(v, 0.0)),
        ImportField(['最小库存', 'min_stock', 'min_stock_quantity'], 'min_stock_quantity', lambda v: parse_number(v, 0.0)),
        ImportField(['默认供应商', 'supplier', 'default_supplier'], 'default_supplier_name', strip_val),
        ImportField(['采购周期', 'lead_time', 'lead_time_days'], 'lead_time_days', lambda v: parse_number(v, 7)),
        ImportField(['是否需要开料', '需要开料', 'need_cutting'], 'need_cutting', parse_bool),
        ImportField(['备注', 'notes', 'desc'], 'notes', strip_val),
    ],
    update_fields=['name', 'specification', 'unit', 'unit_price', 'stock_quantity',
                  'min_stock_quantity', 'lead_time_days', 'need_cutting', 'notes'],
    pre_save_hook=material_pre_save_hook,
    unique_field_case_insensitive=True,
)


def get_material_import_config(model_class):
    """获取物料导入配置（动态设置model）"""
    config = ImportConfig(
        model=model_class,
        unique_field='code',
        field_mappings=[
            ImportField(['编码', 'code'], 'code', strip_val),
            ImportField(['名称', 'name'], 'name', strip_val),
            ImportField(['规格', 'specification', 'spec'], 'specification', strip_val),
            ImportField(['单位', 'unit'], 'unit', strip_val),
            ImportField(['单价', 'price', 'unit_price'], 'unit_price', lambda v: parse_number(v, 0.0)),
            ImportField(['库存数量', 'stock', 'stock_quantity'], 'stock_quantity', lambda v: parse_number(v, 0.0)),
            ImportField(['最小库存', 'min_stock', 'min_stock_quantity'], 'min_stock_quantity', lambda v: parse_number(v, 0.0)),
            ImportField(['默认供应商', 'supplier', 'default_supplier'], 'default_supplier_name', strip_val),
            ImportField(['采购周期', 'lead_time', 'lead_time_days'], 'lead_time_days', lambda v: parse_number(v, 7)),
            ImportField(['是否需要开料', '需要开料', 'need_cutting'], 'need_cutting', parse_bool),
            ImportField(['备注', 'notes', 'desc'], 'notes', strip_val),
        ],
        update_fields=['name', 'specification', 'unit', 'unit_price', 'stock_quantity',
                      'min_stock_quantity', 'lead_time_days', 'need_cutting', 'notes'],
        pre_save_hook=material_pre_save_hook,
        unique_field_case_insensitive=True,
    )
    return config
