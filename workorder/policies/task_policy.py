"""
任务权限与业务规则校验
"""

from __future__ import annotations

from typing import Iterable, Optional, Tuple

from workorder.services.service_errors import ServiceError


def ensure_user_can_modify_task(user, task, action_label: str) -> None:
    if user.is_superuser:
        return

    if task.assigned_operator == user:
        return

    work_order = task.work_order_process.work_order

    if task.assigned_department:
        user_departments = (
            user.profile.departments.all() if hasattr(user, "profile") else []
        )
        if (
            task.assigned_department in user_departments
            and user.has_perm("workorder.change_workorder")
        ):
            return

    if work_order.created_by == user:
        return

    raise ServiceError(
        message=f"您没有权限{action_label}此任务。只能{action_label}自己分派的任务或本部门的任务。",
        code=403,
    )


def ensure_task_version(task, expected_version: Optional[int]) -> None:
    if expected_version is None:
        return

    if task.version != expected_version:
        raise ServiceError(
            message="任务已被其他操作员更新，请刷新后重试",
            code=409,
            data={"current_version": task.version},
        )


def ensure_assets_confirmed(task, action_label: str) -> None:
    if task.task_type != "plate_making":
        return

    if task.artwork and not task.artwork.confirmed:
        raise ServiceError(message=f"图稿未确认，无法{action_label}任务", code=400)
    if task.die and not task.die.confirmed:
        raise ServiceError(message=f"刀模未确认，无法{action_label}任务", code=400)
    if task.foiling_plate and not task.foiling_plate.confirmed:
        raise ServiceError(message=f"烫金版未确认，无法{action_label}任务", code=400)
    if task.embossing_plate and not task.embossing_plate.confirmed:
        raise ServiceError(message=f"压凸版未确认，无法{action_label}任务", code=400)


def ensure_material_cut_ready(
    task,
    process_code: str,
    work_order,
    action_label: str,
) -> None:
    if task.task_type != "cutting" or not task.material:
        return

    work_order_material = work_order.materials.filter(material=task.material).first()
    if not work_order_material:
        return

    from workorder.process_codes import ProcessCodes

    if ProcessCodes.requires_material_cut_status(process_code):
        if work_order_material.purchase_status != "cut":
            raise ServiceError(message=f"物料未开料，无法{action_label}开料任务", code=400)


def resolve_design_assets(
    *,
    task,
    artwork_ids: Iterable[int],
    die_ids: Iterable[int],
    work_order,
) -> Tuple[Optional[object], Optional[object]]:
    artwork = None
    die = None

    is_design_task = "设计图稿" in task.work_content or "更新图稿" in task.work_content
    is_die_design_task = "设计刀模" in task.work_content or "更新刀模" in task.work_content

    if is_design_task:
        if not artwork_ids:
            raise ServiceError(message="请至少选择一个图稿", code=400)
        from workorder.models.assets import Artwork

        artworks = Artwork.objects.filter(id__in=artwork_ids)
        if artworks.count() != len(artwork_ids):
            raise ServiceError(message="部分图稿不存在", code=400)
        work_order.artworks.add(*artworks)
        artwork = artworks.first()

    if is_die_design_task:
        if not die_ids:
            raise ServiceError(message="请至少选择一个刀模", code=400)
        from workorder.models.assets import Die

        dies = Die.objects.filter(id__in=die_ids)
        if dies.count() != len(die_ids):
            raise ServiceError(message="部分刀模不存在", code=400)
        work_order.dies.add(*dies)
        die = dies.first()

    return artwork, die
