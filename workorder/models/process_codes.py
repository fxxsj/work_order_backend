"""
工序编码常量
定义所有工序的编码和分类
"""


class ProcessCodes:
    """工序编码常量类"""

    # 基础工序
    CTP = 'CTP'      # 制版
    DIE = 'DIE'      # 模切
    CUT = 'CUT'      # 开料
    PRT = 'PRT'      # 印刷

    # 表面处理工序
    FOIL_G = 'FOIL_G'  # 烫金
    FOIL_S = 'FOIL_S'  # 烫银
    EMB = 'EMB'        # 压凸
    BEM = 'BEM'        # 压纹

    # 覆膜工序
    CFM = 'CFM'      # 覆光膜
    CFMM = 'CFMM'    # 覆哑膜

    # UV 工序
    UV = 'UV'        # UV

    # 后道工序
    GLUING = 'GLUING'      # 粘胶
    WINDOW = 'WINDOW'      # 粘窗口
    PASTE = 'PASTE'        # 裱坑
    MOUNT = 'MOUNT'        # 对裱
    PACK = 'PACK'          # 包装
    NAILING = 'NAILING'    # 打钉

    # 其他工序
    OIL = 'OIL'      # 过油
    VAMP = 'VAMP'    # 压线

    @staticmethod
    def is_parallel(process_code):
        """
        判断工序是否可以并行

        可并行的工序包括：
        - 烫金、烫银
        - 压凸、压纹
        - 覆光膜、覆哑膜
        - UV
        - 粘胶、粘窗口、打钉

        Args:
            process_code: 工序编码

        Returns:
            bool: 如果可以并行返回 True，否则返回 False
        """
        parallel_processes = [
            ProcessCodes.FOIL_G,
            ProcessCodes.FOIL_S,
            ProcessCodes.EMB,
            ProcessCodes.BEM,
            ProcessCodes.CFM,
            ProcessCodes.CFMM,
            ProcessCodes.UV,
            ProcessCodes.GLUING,
            ProcessCodes.WINDOW,
            ProcessCodes.NAILING,
        ]
        return process_code in parallel_processes

    @staticmethod
    def requires_material_cut_status(process_code):
        """
        判断工序是否需要物料已开料的状态

        某些工序只能在物料开料后才能进行

        Args:
            process_code: 工序编码

        Returns:
            bool: 如果需要物料已开料返回 True，否则返回 False
        """
        # 印刷相关的工序需要物料已开料
        requires_cut = [
            ProcessCodes.PRT,      # 印刷
            ProcessCodes.OIL,      # 过油
            ProcessCodes.CFM,      # 覆光膜
            ProcessCodes.CFMM,     # 覆哑膜
            ProcessCodes.UV,       # UV
        ]
        return process_code in requires_cut
