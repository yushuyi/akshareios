"""数值转换与行数限制工具。"""

MAX_KLINE_ROWS = 250


def to_float(value) -> float | None:
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def to_int(value) -> int | None:
    try:
        return int(value)
    except (ValueError, TypeError):
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
