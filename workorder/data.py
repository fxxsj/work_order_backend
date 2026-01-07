"""
预设数据定义
用于迁移文件和管理命令，确保数据一致性
"""

# 预设的21个标准工序数据
PRESET_PROCESSES = [
    {'code': 'CTP', 'name': '制版', 'description': 'CTP制版', 'standard_duration': 0, 'sort_order': 1, 'is_active': True, 'is_builtin': True, 'task_generation_rule': 'general', 'is_parallel': True},
    {'code': 'CUT', 'name': '开料', 'description': '材料开料', 'standard_duration': 0, 'sort_order': 2, 'is_active': True, 'is_builtin': True, 'task_generation_rule': 'general', 'is_parallel': False},
    {'code': 'PRT', 'name': '印刷', 'description': '印刷', 'standard_duration': 0, 'sort_order': 3, 'is_active': True, 'is_builtin': True, 'task_generation_rule': 'general', 'is_parallel': False, 'requires_artwork': True, 'artwork_required': True},
    {'code': 'VAN', 'name': '过油', 'description': '过油', 'standard_duration': 0, 'sort_order': 4, 'is_active': True, 'is_builtin': True, 'task_generation_rule': 'general', 'is_parallel': False},
    {'code': 'LAM_G', 'name': '覆光膜', 'description': '覆光膜', 'standard_duration': 0, 'sort_order': 5, 'is_active': True, 'is_builtin': True, 'task_generation_rule': 'general', 'is_parallel': False},
    {'code': 'LAM_M', 'name': '覆哑膜', 'description': '覆哑膜', 'standard_duration': 0, 'sort_order': 6, 'is_active': True, 'is_builtin': True, 'task_generation_rule': 'general', 'is_parallel': False},
    {'code': 'UV', 'name': 'UV', 'description': 'UV工艺', 'standard_duration': 0, 'sort_order': 7, 'is_active': True, 'is_builtin': True, 'task_generation_rule': 'general', 'is_parallel': False},
    {'code': 'FOIL_G', 'name': '烫金', 'description': '烫金', 'standard_duration': 0, 'sort_order': 8, 'is_active': True, 'is_builtin': True, 'task_generation_rule': 'general', 'is_parallel': False, 'requires_foiling_plate': True, 'foiling_plate_required': True},
    {'code': 'FOIL_S', 'name': '烫银', 'description': '烫银', 'standard_duration': 0, 'sort_order': 9, 'is_active': True, 'is_builtin': True, 'task_generation_rule': 'general', 'is_parallel': False, 'requires_foiling_plate': True, 'foiling_plate_required': True},
    {'code': 'EMB', 'name': '压凸', 'description': '压凸', 'standard_duration': 0, 'sort_order': 10, 'is_active': True, 'is_builtin': True, 'task_generation_rule': 'general', 'is_parallel': False, 'requires_embossing_plate': True, 'embossing_plate_required': True},
    {'code': 'TEX', 'name': '压纹', 'description': '压纹', 'standard_duration': 0, 'sort_order': 11, 'is_active': True, 'is_builtin': True, 'task_generation_rule': 'general', 'is_parallel': False},
    {'code': 'SCORE', 'name': '压线', 'description': '压线', 'standard_duration': 0, 'sort_order': 12, 'is_active': True, 'is_builtin': True, 'task_generation_rule': 'general', 'is_parallel': False},
    {'code': 'DIE', 'name': '模切', 'description': '模切', 'standard_duration': 0, 'sort_order': 13, 'is_active': True, 'is_builtin': True, 'task_generation_rule': 'general', 'is_parallel': True, 'requires_die': True, 'die_required': True},
    {'code': 'TRIM', 'name': '切成品', 'description': '切成品', 'standard_duration': 0, 'sort_order': 14, 'is_active': True, 'is_builtin': True, 'task_generation_rule': 'general', 'is_parallel': False},
    {'code': 'LAM_B', 'name': '对裱', 'description': '对裱', 'standard_duration': 0, 'sort_order': 15, 'is_active': True, 'is_builtin': True, 'task_generation_rule': 'general', 'is_parallel': False},
    {'code': 'MOUNT', 'name': '裱坑', 'description': '裱坑', 'standard_duration': 0, 'sort_order': 16, 'is_active': True, 'is_builtin': True, 'task_generation_rule': 'general', 'is_parallel': False},
    {'code': 'GLUE', 'name': '粘胶', 'description': '粘胶', 'standard_duration': 0, 'sort_order': 17, 'is_active': True, 'is_builtin': True, 'task_generation_rule': 'general', 'is_parallel': False},
    {'code': 'BOX', 'name': '粘盒', 'description': '粘盒', 'standard_duration': 0, 'sort_order': 18, 'is_active': True, 'is_builtin': True, 'task_generation_rule': 'general', 'is_parallel': False},
    {'code': 'WINDOW', 'name': '粘窗口', 'description': '粘窗口', 'standard_duration': 0, 'sort_order': 19, 'is_active': True, 'is_builtin': True, 'task_generation_rule': 'general', 'is_parallel': False},
    {'code': 'STAPLE', 'name': '打钉', 'description': '打钉', 'standard_duration': 0, 'sort_order': 20, 'is_active': True, 'is_builtin': True, 'task_generation_rule': 'general', 'is_parallel': False},
    {'code': 'PACK', 'name': '包装', 'description': '包装', 'standard_duration': 0, 'sort_order': 21, 'is_active': True, 'is_builtin': True, 'task_generation_rule': 'general', 'is_parallel': False},
]

# 预设工序编码列表（用于回滚和验证）
PRESET_PROCESS_CODES = [p['code'] for p in PRESET_PROCESSES]

# 预设部门数据（共11个部门）
# 管理部门（顶层，5个）
PRESET_MANAGEMENT_DEPARTMENTS = [
    {'name': '业务部', 'code': 'business', 'sort_order': 1, 'parent': None},
    {'name': '财务部', 'code': 'finance', 'sort_order': 2, 'parent': None},
    {'name': '设计部', 'code': 'design', 'sort_order': 3, 'parent': None},
    {'name': '采购部', 'code': 'purchase', 'sort_order': 4, 'parent': None},
    {'name': '运输部', 'code': 'logistics', 'sort_order': 11, 'parent': None},
]

# 生产部（父部门，1个）
PRESET_PRODUCTION_DEPARTMENT = {
    'name': '生产部',
    'code': 'production',
    'sort_order': 5,
    'parent': None
}

# 生产车间（子部门，5个）
PRESET_WORKSHOP_DEPARTMENTS = [
    {'name': '裁切车间', 'code': 'cutting', 'sort_order': 6},
    {'name': '印刷车间', 'code': 'printing', 'sort_order': 7},
    {'name': '外协车间', 'code': 'outsourcing', 'sort_order': 8},
    {'name': '模切车间', 'code': 'die_cutting', 'sort_order': 9},
    {'name': '包装车间', 'code': 'packaging', 'sort_order': 10},
]

# 所有预设部门编码列表（用于回滚）
PRESET_DEPARTMENT_CODES = (
    [d['code'] for d in PRESET_MANAGEMENT_DEPARTMENTS] +
    [PRESET_PRODUCTION_DEPARTMENT['code']] +
    [d['code'] for d in PRESET_WORKSHOP_DEPARTMENTS]
)

# 部门与工序关联关系配置
DEPARTMENT_PROCESS_MAPPING = {
    'design': ['CTP'],  # 设计部负责制版
    'production': ['CUT', 'PRT', 'VAN', 'LAM_G', 'LAM_M', 'UV', 'FOIL_G', 'FOIL_S', 'EMB', 'TEX', 'SCORE', 'DIE', 'TRIM', 'LAM_B', 'MOUNT', 'GLUE', 'BOX', 'WINDOW', 'STAPLE', 'PACK'],  # 生产部：所有子部门的工序（按sort_order排序）
    'cutting': ['CUT', 'SCORE', 'TRIM'],  # 裁切车间：开料、压线、切成品
    'printing': ['PRT', 'VAN'],  # 印刷车间：印刷、过油
    'outsourcing': ['CUT', 'PRT', 'VAN', 'LAM_G', 'LAM_M', 'UV', 'FOIL_G', 'FOIL_S', 'EMB', 'TEX', 'DIE', 'LAM_B', 'MOUNT', 'BOX', 'STAPLE'],  # 外协车间：多个工序
    'die_cutting': ['FOIL_G', 'FOIL_S', 'EMB', 'SCORE', 'DIE'],  # 模切车间：烫金、烫银、压凸、压线、模切
    'packaging': ['CUT', 'TEX', 'LAM_B', 'MOUNT', 'GLUE', 'BOX', 'WINDOW', 'STAPLE', 'PACK'],  # 包装车间：多个工序
}

