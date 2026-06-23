"""
工具函数
"""

import logging
from django.db import models, transaction, DatabaseError
from django.utils import timezone


logger = logging.getLogger(__name__)


def generate_order_number(
    model_class: models.Model,
    field_name: str,
    prefix: str,
    date_format: str = "%Y%m%d",
    sequence_length: int = 4,
    max_retries: int = 3,
) -> str:
    """
    通用单号生成器：前缀 + 日期 + N位序号
    使用数据库事务和行锁确保并发安全。

    Args:
        model_class: Django 模型类。
        field_name: 用于存储单号的字段名 (e.g., "order_number")。
        prefix: 单号的静态前缀 (e.g., "SO")。
        date_format: 日期部分的格式 (e.g., "%Y%m%d", "%Y%m")。如果为 None，则不包含日期。
        sequence_length: 序号的位数 (e.g., 4)。
        max_retries: 数据库死锁等错误下的最大重试次数。

    Returns:
        生成的唯一单号。

    Raises:
        Exception: 如果重试后仍然失败。
    """
    retry_count = 0
    while retry_count < max_retries:
        try:
            with transaction.atomic():
                now = timezone.now()
                date_part = now.strftime(date_format) if date_format else ""
                full_prefix = f"{prefix}{date_part}"

                last_instance = (
                    model_class.objects.filter(
                        **{f"{field_name}__startswith": full_prefix}
                    )
                    .order_by(f"-{field_name}")
                    .select_for_update()
                    .first()
                )

                if last_instance:
                    last_number_str = getattr(last_instance, field_name)
                    last_sequence = int(
                        last_number_str.removeprefix(full_prefix)
                    )
                    new_sequence = last_sequence + 1
                else:
                    new_sequence = 1

                return f"{full_prefix}{new_sequence:0{sequence_length}d}"

        except DatabaseError as e:
            retry_count += 1
            if retry_count >= max_retries:
                logger.error(
                    f"生成单号失败(模型={model_class.__name__}, 字段={field_name}), "
                    f"已重试{max_retries}次: {e}"
                )
                raise
            logger.warning(
                f"生成单号时发生数据库错误，正在重试 ({retry_count}/{max_retries}): {e}"
            )
            continue
        except Exception as e:
            logger.error(
                f"生成单号时发生未知错误(模型={model_class.__name__}, 字段={field_name}): {e}"
            )
            raise

    # This should not be reached
    raise Exception(
        f"生成单号失败(模型={model_class.__name__}, 字段={field_name}): 超过最大重试次数"
    )


def get_user_role(user):
    """
    获取用户角色

    Args:
        user: User 实例

    Returns:
        str: 用户角色名称，如果用户属于多个组，返回第一个组的名称
    """
    if not user or not user.is_authenticated:
        return None

    groups = user.groups.all()
    if groups.exists():
        return groups.first().name
    return None


def format_color_display(cmyk_colors, other_colors):
    """格式化 CMYK + 专色为显示文本

    示例输出: "CMK+928C,金色（5色）"

    Args:
        cmyk_colors: CMYK 颜色列表，如 ["C", "M", "K"]
        other_colors: 专色列表，如 ["928C", "金色"]

    Returns:
        str: 格式化后的颜色显示文本，无颜色时返回 None
    """
    parts = []
    total_count = 0

    if cmyk_colors:
        cmyk_order = ["C", "M", "Y", "K"]
        cmyk_sorted = [c for c in cmyk_order if c in cmyk_colors]
        if cmyk_sorted:
            parts.append("".join(cmyk_sorted))
            total_count += len(cmyk_colors)

    if other_colors:
        other_list = [c.strip() for c in other_colors if c and c.strip()]
        if other_list:
            parts.append(",".join(other_list))
            total_count += len(other_list)

    if not parts:
        return None

    result = "+".join(parts)
    if total_count > 0:
        result += f"（{total_count}色）"
    return result
