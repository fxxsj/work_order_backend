from django.db import models


class MaterialCalculationMode(models.TextChoices):
    FIXED = "fixed", "固定/直接填写"
    SHEET_IMPOSITION = "sheet_imposition", "拼版后算纸"
    SPECIFICATION_SELECTION = "specification_selection", "待规格确认"


class MaterialPreparationMode(models.TextChoices):
    PENDING = "pending", "待决定"
    DIRECT = "direct", "直接领用/采购"
    INTERNAL_CUTTING = "internal_cutting", "厂内开料"
    SUPPLIER_CUTTING = "supplier_cutting", "供应商按尺寸供货"


def effective_calculation_mode(item):
    if (
        item.planning_required
        and item.calculation_mode == MaterialCalculationMode.FIXED
    ):
        return MaterialCalculationMode.SHEET_IMPOSITION
    return item.calculation_mode


def effective_preparation_mode(item):
    if item.need_cutting:
        return MaterialPreparationMode.INTERNAL_CUTTING
    if (
        item.planning_required
        and item.preparation_mode == MaterialPreparationMode.DIRECT
        and effective_calculation_mode(item)
        == MaterialCalculationMode.SHEET_IMPOSITION
    ):
        return MaterialPreparationMode.SUPPLIER_CUTTING
    return item.preparation_mode


def requires_sheet_planning(item) -> bool:
    """兼容旧 planning_required 字段判断是否需要拼版算纸。"""
    return effective_calculation_mode(item) == (
        MaterialCalculationMode.SHEET_IMPOSITION
    )


def requires_specification_selection(item) -> bool:
    return effective_calculation_mode(item) == (
        MaterialCalculationMode.SPECIFICATION_SELECTION
    )


def requires_material_planning(item) -> bool:
    return requires_sheet_planning(item) or requires_specification_selection(item)


def requires_internal_cutting(item) -> bool:
    """兼容旧 need_cutting 字段判断是否需要生成厂内开料任务。"""
    return effective_preparation_mode(item) == (
        MaterialPreparationMode.INTERNAL_CUTTING
    )


def normalize_material_modes(data, *, instance=None):
    """把新模式与旧布尔字段归一化，供写入入口兼容旧客户端。"""
    uses_legacy_calculation = (
        "calculation_mode" not in data and "planning_required" in data
    )
    uses_legacy_preparation = (
        "preparation_mode" not in data and "need_cutting" in data
    )
    calculation_mode = data.get(
        "calculation_mode",
        (
            effective_calculation_mode(instance)
            if instance is not None
            else MaterialCalculationMode.FIXED
        ),
    )
    preparation_mode = data.get(
        "preparation_mode",
        (
            effective_preparation_mode(instance)
            if instance is not None
            else MaterialPreparationMode.DIRECT
        ),
    )

    if uses_legacy_calculation:
        calculation_mode = (
            MaterialCalculationMode.SHEET_IMPOSITION
            if data["planning_required"]
            else MaterialCalculationMode.FIXED
        )
    if uses_legacy_preparation:
        preparation_mode = (
            MaterialPreparationMode.INTERNAL_CUTTING
            if data["need_cutting"]
            else MaterialPreparationMode.DIRECT
        )
    if (
        uses_legacy_calculation
        and data["planning_required"]
        and preparation_mode == MaterialPreparationMode.DIRECT
    ):
        preparation_mode = MaterialPreparationMode.SUPPLIER_CUTTING

    data["calculation_mode"] = calculation_mode
    data["preparation_mode"] = preparation_mode
    data["planning_required"] = (
        calculation_mode
        in {
            MaterialCalculationMode.SHEET_IMPOSITION,
            MaterialCalculationMode.SPECIFICATION_SELECTION,
        }
    )
    data["need_cutting"] = (
        preparation_mode == MaterialPreparationMode.INTERNAL_CUTTING
    )
    return calculation_mode, preparation_mode


def validate_material_modes(*, material, calculation_mode, preparation_mode):
    """返回字段级错误；空字典表示组合有效。"""
    errors = {}
    if calculation_mode == MaterialCalculationMode.SHEET_IMPOSITION:
        if material.specification_level != "requirement":
            errors["material"] = "拼版后算纸必须选择‘材料要求’层级"
        elif material.material_type != "paper":
            errors["material"] = "只有纸张类物料可以使用拼版后算纸"
        if preparation_mode == MaterialPreparationMode.DIRECT:
            errors["preparation_mode"] = (
                "拼版后算纸必须选择厂内开料或供应商按尺寸供货"
            )
    elif calculation_mode == MaterialCalculationMode.SPECIFICATION_SELECTION:
        if material.specification_level != "requirement":
            errors["material"] = "待规格确认必须选择‘材料要求’层级"
        if preparation_mode not in {
            MaterialPreparationMode.PENDING,
            MaterialPreparationMode.DIRECT,
        }:
            errors["preparation_mode"] = "待规格确认只能保持待决定或直接领用/采购"
    elif material.specification_level == "requirement":
        errors["material"] = "固定用量必须选择具体库存/采购规格"
    elif preparation_mode == MaterialPreparationMode.PENDING:
        errors["preparation_mode"] = "具体库存规格不能保持待决定"
    return errors


def derive_product_material_modes(material):
    """产品录入只选物料，系统按层级和类型推导后续规划方式。"""
    if material.specification_level == "stock":
        return MaterialCalculationMode.FIXED, MaterialPreparationMode.DIRECT
    if material.material_type == "paper":
        return (
            MaterialCalculationMode.SHEET_IMPOSITION,
            MaterialPreparationMode.PENDING,
        )
    return (
        MaterialCalculationMode.SPECIFICATION_SELECTION,
        MaterialPreparationMode.PENDING,
    )
