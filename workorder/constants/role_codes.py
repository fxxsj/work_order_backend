"""
角色代码常量定义

所有业务角色使用统一的英文 code，避免中文比较和硬编码。
"""

from django.utils.translation import gettext_lazy as _


# =============================================================================
# Role Code 定义
# =============================================================================

ROLE_CODES = {
    'sales': {
        'label': '业务员',
        'label_en': 'Sales Person',
        'description': '负责客户管理和销售订单',
        'aliases': ['salesperson', 'salespersons'],
    },
    'supervisor': {
        'label': '主管',
        'label_en': 'Supervisor',
        'description': '负责生产任务管理和部门协调',
        'aliases': ['supervisor'],
    },
    'manager': {
        'label': '经理',
        'label_en': 'Manager',
        'description': '全面管理权限',
        'aliases': ['managers'],
    },
    'operator': {
        'label': '操作员',
        'label_en': 'Operator',
        'description': '执行生产任务',
        'aliases': ['operators'],
    },
    'finance': {
        'label': '财务',
        'label_en': 'Finance',
        'description': '财务和成本管理',
        'aliases': [],
    },
    'inventory': {
        'label': '仓储',
        'label_en': 'Inventory',
        'description': '库存和物流管理',
        'aliases': ['warehouse'],
    },
    'quality': {
        'label': '质检',
        'label_en': 'Quality',
        'description': '质量检验',
        'aliases': [],
    },
    'admin': {
        'label': '系统管理员',
        'label_en': 'Administrator',
        'description': '系统配置管理',
        'aliases': ['administrators'],
    },
}

# 代码列表（用于验证）
ALL_ROLE_CODES = list(ROLE_CODES.keys())

# 代码 -> 显示名
CODE_TO_LABEL = {code: config['label'] for code, config in ROLE_CODES.items()}

# 别名 -> 标准代码的反向映射
_ALIAS_TO_CODE = {}
for code, config in ROLE_CODES.items():
    for alias in config['aliases']:
        _ALIAS_TO_CODE[alias] = code
    # 中文名也作为别名
    _ALIAS_TO_CODE[config['label']] = code


def resolve_role_code(name_or_alias: str) -> str | None:
    """
    将任意名称（别名、中文名、旧英文名）解析为标准 role code。

    Args:
        name_or_alias: 组名、别名或中文显示名

    Returns:
        标准 role code，如果无法解析返回 None
    """
    if not name_or_alias:
        return None

    # 直接匹配
    if name_or_alias in ROLE_CODES:
        return name_or_alias

    # 通过别名映射
    return _ALIAS_TO_CODE.get(name_or_alias)


def resolve_role_codes(names_or_aliases: list[str]) -> list[str]:
    """
    批量解析 role codes。

    Args:
        names_or_aliases: 组名列表

    Returns:
        标准 role code 列表（自动过滤 None）
    """
    return [r for r in (resolve_role_code(n) for n in names_or_aliases) if r]


# =============================================================================
# Role Code 常量 (直接引用)
# =============================================================================

SALES = 'sales'
SUPERVISOR = 'supervisor'
MANAGER = 'manager'
OPERATOR = 'operator'
FINANCE = 'finance'
INVENTORY = 'inventory'
QUALITY = 'quality'
ADMIN = 'admin'

# Role 对应的 Django Group name (迁移后 auth_group.name 使用此值)
ROLE_GROUP_NAMES = {
    SALES: 'sales',
    SUPERVISOR: 'supervisor',
    MANAGER: 'manager',
    OPERATOR: 'operator',
    FINANCE: 'finance',
    INVENTORY: 'inventory',
    QUALITY: 'quality',
    ADMIN: 'admin',
}

# 中文显示名到代码的反向映射 (用于兼容旧代码)
LABEL_TO_CODE = {config['label']: code for code, config in ROLE_CODES.items()}

# Group name 别名映射（旧名称 -> 新代码）
LEGACY_GROUP_ALIASES = {
    '业务员': SALES,
    '主管': SUPERVISOR,
    '经理': MANAGER,
    '操作员': OPERATOR,
    '财务': FINANCE,
    '仓储': INVENTORY,
    '质检': QUALITY,
    '系统管理员': ADMIN,
    # 英文别名
    'salespersons': SALES,
    'operators': OPERATOR,
    'managers': MANAGER,
    'administrators': ADMIN,
    'supervisor': SUPERVISOR,
    'warehouse': INVENTORY,
}