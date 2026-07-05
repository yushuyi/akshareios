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
