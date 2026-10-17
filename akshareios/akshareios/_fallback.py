"""东财主源失败时的自动降级。"""

from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")

# 主源异常时的立即重试次数。东财 push2his 偶发 RemoteDisconnected，
# urllib3 Retry 依赖连接池的重试机制，在 Pyodide 的 requests shim 下不
# 生效；设备 2026-09-30 实录组合调用因此 120s 超时。瞬态断连通常立即
# 重连即可恢复，故不 sleep 直接重试（Pyodide 主线程也不允许 sleep）。
_PRIMARY_RETRIES = 1


def call_with_fallback(
    primary: Callable[[], T],
    fallback: Callable[[], T],
    *,
    retry_on_empty: bool = False,
    primary_retries: int = _PRIMARY_RETRIES,
) -> T:
    """
    先调东财；异常时立即重试 primary_retries 次，仍失败或（可选）空结果
    时走备用源。
    """
    for _ in range(max(0, primary_retries) + 1):
        try:
            result = primary()
            if retry_on_empty and _is_empty(result):
                break
            return result
        except Exception:
            continue
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
