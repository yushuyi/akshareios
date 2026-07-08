#!/usr/bin/env python3
"""_convert 工具函数单元测试（无需联网）"""

from akshareios._convert import apply_row_limit, deduplicate_rows_by_date


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
    print("test_convert: 全部通过")
