"""
工序编码常量定义
统一管理所有工序编码，避免硬编码分散在代码中
"""


class ProcessCodes:
    """工序编码常量类"""
    # 预设工序编码（不可编辑）
    CTP = 'CTP'  # 制版
    CUT = 'CUT'  # 开料
    PRT = 'PRT'  # 印刷
    VAN = 'VAN'  # 过油
    LAM_G = 'LAM_G'  # 覆光膜
    LAM_M = 'LAM_M'  # 覆哑膜
    UV = 'UV'  # UV
    FOIL_G = 'FOIL_G'  # 烫金
    FOIL_S = 'FOIL_S'  # 烫银
    EMB = 'EMB'  # 压凸
    TEX = 'TEX'  # 压纹
    SCORE = 'SCORE'  # 压线
    DIE = 'DIE'  # 模切
    TRIM = 'TRIM'  # 切成品
    LAM_B = 'LAM_B'  # 对裱
    MOUNT = 'MOUNT'  # 裱坑
    GLUE = 'GLUE'  # 粘胶
    BOX = 'BOX'  # 粘盒
    WINDOW = 'WINDOW'  # 粘窗口
    STAPLE = 'STAPLE'  # 打钉
    PACK = 'PACK'  # 包装

    @classmethod
    def is_parallel(cls, code):
        """判断是否为可并行执行的工序（制版、模切）"""
        return code in [cls.CTP, cls.DIE]
    
    @classmethod
    def is_cutting_process(cls, code):
        """判断是否为开料相关工序"""
        return code == cls.CUT
    
    @classmethod
    def is_plate_making_process(cls, code):
        """判断是否为制版工序"""
        return code == cls.CTP
    
    @classmethod
    def requires_material_cut_status(cls, code):
        """判断是否需要物料开料状态"""
        return code == cls.CUT
    
    @classmethod
    def get_all_codes(cls):
        """获取所有工序编码列表"""
        return [
            cls.CTP, cls.CUT, cls.PRT, cls.VAN, cls.LAM_G, cls.LAM_M,
            cls.UV, cls.FOIL_G, cls.FOIL_S, cls.EMB, cls.TEX, cls.SCORE,
            cls.DIE, cls.TRIM, cls.LAM_B, cls.MOUNT, cls.GLUE, cls.BOX,
            cls.WINDOW, cls.STAPLE, cls.PACK
        ]

