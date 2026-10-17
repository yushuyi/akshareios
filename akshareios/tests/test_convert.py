#!/usr/bin/env python3
"""_convert 工具函数单元测试（无需联网）"""

from akshareios._convert import apply_row_limit, deduplicate_rows_by_date, to_int


def test_to_int_plain() -> None:
    assert to_int("31420") == 31420
    assert to_int(12) == 12
    assert to_int(12.0) == 12


def test_to_int_decimal_string() -> None:
    # 腾讯日 K 成交量形如 '31420.00'，旧实现 int('31420.00') 直接 None，
    # 导致降级后的成交量列静默丢失
    assert to_int("31420.00") == 31420
    assert to_int("472632158.00") == 472632158


def test_to_int_invalid() -> None:
    assert to_int("") is None
    assert to_int(None) is None
    assert to_int({}) is None
    assert to_int("abc") is None
    # float('inf') 直接 int() 会抛 OverflowError，应统一拦截为 None
    assert to_int(float("inf")) is None
    assert to_int("-inf") is None
    assert to_int("nan") is None
    assert to_int(float("nan")) is None


def test_to_int_float_rounding_consistent() -> None:
    # float 与字符串入参走同一 round 语义，不再 float 截断/字符串四舍五入不一致
    assert to_int(3.7) == 4
    assert to_int("3.7") == 4
    assert to_int(-3.7) == -4


def test_deduplicate_rows_by_date_keeps_last() -> None:
    rows = [
        {"日期": "2026-04-09", "收盘": 9.0},
        {"日期": "2026-04-09", "收盘": 9.2},
        {"日期": "2026-04-10", "收盘": 8.5},
        {"日期": "2026-04-10", "收盘": 8.6},
    ]
    out = deduplicate_rows_by_date(rows)
    assert len(out) == 2
    assert out[0]["收盘"] == 9.2
    assert out[1]["收盘"] == 8.6


def test_deduplicate_rows_by_date_preserves_order() -> None:
    rows = [
        {"日期": "2026-02-01", "收盘": 5.0},
        {"日期": "2026-02-01", "收盘": 5.1},
        {"日期": "2026-02-02", "收盘": 5.2},
    ]
    out = deduplicate_rows_by_date(rows)
    assert [r["日期"] for r in out] == ["2026-02-01", "2026-02-02"]


def test_apply_row_limit_after_dedup() -> None:
    rows = [{"日期": f"2026-04-{i:02d}", "收盘": float(i)} for i in range(1, 11)]
    rows = rows + rows  # 模拟东财重复
    deduped = deduplicate_rows_by_date(rows)
    limited = apply_row_limit(deduped, 3)
    assert len(limited) == 3
    assert limited[-1]["日期"] == "2026-04-10"


if __name__ == "__main__":
    test_deduplicate_rows_by_date_keeps_last()
    test_deduplicate_rows_by_date_preserves_order()
    test_apply_row_limit_after_dedup()
    test_to_int_plain()
    test_to_int_decimal_string()
    test_to_int_invalid()
    print("test_convert: 全部通过")
