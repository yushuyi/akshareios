"""东财主源失败时的自动降级。"""

from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def call_with_fallback(
    primary: Callable[[], T],
    fallback: Callable[[], T],
    *,
    retry_on_empty: bool = False,
) -> T:
    """
    先调东财；异常或（可选）空结果时走备用源。
  """
    try:
        result = primary()
        if retry_on_empty and _is_empty(result):
            return fallback()
        return result
    except Exception:
        return fallback()


def _is_empty(value) -> bool:
    if value is None:
        return True
    if isinstance(value, dict):
        # 分页结果（含 items 键）看 items 长度，否则 make_page_result 恒非空导致空页不降级；
        # 无 items 键的记录 dict 维持原 len 语义
        target = value.get("items", value)
        return len(target) == 0
    if isinstance(value, (list, str)):
        return len(value) == 0
    return False
