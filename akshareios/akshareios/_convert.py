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
    转整数。

    兼容小数字符串：腾讯日 K 成交量返回形如 '31420.00'，直接 int() 会
    ValueError 导致整列静默丢失（绝味会话 2026-10-10 实录：降级腾讯后
    成交量/成交额全为 None）。含非零小数时四舍五入——成交量字段理论上
    恒为整数，小数部分仅为格式噪声。
    """
    try:
        return int(value)
    except (ValueError, TypeError):
        pass
    try:
        number = float(value)
        if math.isfinite(number):
            return int(round(number))
    except (ValueError, TypeError, OverflowError):
        pass
    return None


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
