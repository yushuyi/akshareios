"""数值转换与行数限制工具。"""

import math
import re

MAX_KLINE_ROWS = 250


def ensure_symbol(symbol) -> str:
    """校验 6 位股票代码，非法时抛 ValueError（对齐 stock_hist 对非法 period 的处理）。"""
    symbol = str(symbol or "").strip()
    if not re.fullmatch(r"\d{6}", symbol):
        raise ValueError(f"无效的股票代码: {symbol!r}，需 6 位数字，如 600519")
    return symbol


def to_float(value) -> float | None:
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def to_int(value) -> int | None:
    """
    转整数：int 原样返回；float 走 round 并拦截非有限值；字符串先尝试
    精确整数解析，失败再按小数 round（含小数字符串）。

    字符串必须先走 int()：直接 float('99999999999999999999') 会丢精度。
    兼容小数字符串：腾讯日 K 成交量返回形如 '31420.00'，直接 int() 会
    ValueError 导致整列静默丢失（绝味会话 2026-10-10 实录：降级腾讯后
    成交量/成交额全为 None）。非有限（inf/nan）与不可解析值返回 None。
    round 为半偶舍入（非四舍五入），成交量字段理论上恒为整手 .00，
    小数部分仅为格式噪声，无实际影响。
    """
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(round(value)) if math.isfinite(value) else None

    text = str(value).strip()
    try:
        return int(text)
    except (ValueError, TypeError):
        pass
    try:
        number = float(text)
    except (ValueError, TypeError):
        return None
    if not math.isfinite(number):
        return None
    return int(round(number))


def deduplicate_rows_by_date(rows: list[dict], *, date_key: str = "日期") -> list[dict]:
    """
    按日期字段去重，保留同日期最后一条。

    东财 push2his 对部分标的（如 *ST）会返回重复日期行；
    对齐上游 akshare 的 drop_duplicates(subset=['date'], keep='last')。
    """
    if not rows:
        return rows
    seen: dict[str, dict] = {}
    order: list[str] = []
    for row in rows:
        date = row.get(date_key)
        if date is None:
            continue
        if date not in seen:
            order.append(date)
        seen[date] = row
    return [seen[d] for d in order]


def apply_row_limit(rows: list, limit: int | None, *, max_rows: int = MAX_KLINE_ROWS) -> list:
    """按时间正序保留尾部 limit 条，默认上限 max_rows。"""
    if limit is None:
        if len(rows) > max_rows:
            return rows[-max_rows:]
        return rows
    if limit > 0 and len(rows) > limit:
        cap = min(limit, max_rows)
        return rows[-cap:]
    return rows
