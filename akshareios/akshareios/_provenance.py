"""工具结果的来源元信息（provenance）。

模型拿到的经常是降级后的数值：字段变少、单位不同、时效从盘中变成 T-1。
裸数值进上下文时无法判断「这个数能不能用于今天的决策」（2026-11-05
真机会话里模型把昨日收盘后的主力净额当盘中数据、把降级后的 11 字段
个股详情当完整详情）。这里给 dict 类返回值统一附一个 `_meta` 信封，
不改动 items 里的数据行，也不改 list 类返回值的结构契约。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

META_KEY = "_meta"


@dataclass(frozen=True)
class Provenance:
    """一次数据源调用的口径声明。由各接口在 call_with_fallback 处声明。"""

    primary_source: str
    fallback_source: str
    # 数据时效：盘中实时 / T-1 收盘后 / 历史日线 / 静态列表 等
    freshness: str
    # 降级后与主源的口径差异（单位、字段缺失、代码体系等）
    fallback_note: str = ""
    # 降级后拿不到的字段，模型据此判断是否还能回答用户的问题
    missing_fields: tuple[str, ...] = ()
    primary_note: str = ""

    def meta(
        self, *, degraded: bool, extra: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        meta: dict[str, Any] = {
            "数据源": self.fallback_source if degraded else self.primary_source,
            "状态": "降级" if degraded else "主源",
            "数据时间": self.freshness,
        }
        note = self.fallback_note if degraded else self.primary_note
        if note:
            meta["口径说明"] = note
        if degraded and self.missing_fields:
            meta["缺失字段"] = list(self.missing_fields)
        # 接口特有的判定结果（交易日 / 空结果原因 / 最新数据日期等）。
        # 放在统一信封里而不是散落在数据行，模型只需读一处。
        if extra:
            meta.update(extra)
        return meta


def attach_meta(result: Any, meta: dict[str, Any] | None) -> Any:
    """只给 dict 返回值加顶层 `_meta`；list 与原值原样返回。

    分页结果（含 items）与个股详情都是 dict，加顶层键不会污染数据行；
    K 线 / 资金流 / 分笔等 list 返回值保持结构不变，避免破坏既有调用与测试。
    """
    if meta is None or not isinstance(result, dict):
        return result
    out = dict(result)
    out[META_KEY] = meta
    return out
