"""角色代码常量定义。"""

ROLE_CODES = {
    "sales": {
        "label": "业务员",
        "label_en": "Sales Person",
        "description": "负责客户管理和销售订单",
    },
    "supervisor": {
        "label": "主管",
        "label_en": "Supervisor",
        "description": "负责生产任务管理和部门协调",
    },
    "manager": {
        "label": "经理",
        "label_en": "Manager",
        "description": "全面管理权限",
    },
    "operator": {
        "label": "操作员",
        "label_en": "Operator",
        "description": "执行生产任务",
    },
    "finance": {
        "label": "财务",
        "label_en": "Finance",
        "description": "财务和成本管理",
    },
    "procurement": {
        "label": "采购",
        "label_en": "Procurement",
        "description": "供应商和采购订单管理",
    },
    "design": {
        "label": "设计/制版",
        "label_en": "Design / Prepress",
        "description": "图稿、版类资料和制版任务",
    },
    "inventory": {
        "label": "仓储",
        "label_en": "Inventory",
        "description": "库存和物流管理",
    },
    "quality": {
        "label": "质检",
        "label_en": "Quality",
        "description": "质量检验",
    },
    "admin": {
        "label": "系统管理员",
        "label_en": "Administrator",
        "description": "系统配置管理",
    },
}

ALL_ROLE_CODES = list(ROLE_CODES.keys())
CODE_TO_LABEL = {code: config["label"] for code, config in ROLE_CODES.items()}


def resolve_role_code(role_code: str) -> str | None:
    """校验并返回标准 role code。"""
    return role_code if role_code in ROLE_CODES else None


def resolve_role_codes(role_codes: list[str]) -> list[str]:
    """批量校验 role code，自动过滤非预设角色。"""
    return [code for code in role_codes if code in ROLE_CODES]


SALES = "sales"
SUPERVISOR = "supervisor"
MANAGER = "manager"
OPERATOR = "operator"
FINANCE = "finance"
PROCUREMENT = "procurement"
DESIGN = "design"
INVENTORY = "inventory"
QUALITY = "quality"
ADMIN = "admin"
