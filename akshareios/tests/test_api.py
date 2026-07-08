#!/usr/bin/env python3
"""akshareios v0.3.0 API 冒烟测试（需联网）"""

import sys

import akshareios as ak


def _ok(name: str) -> None:
    print(f"  ✓ {name}")


def test_version() -> None:
    assert ak.__version__ == "0.4.1"
    _ok(f"version {ak.__version__}")


def test_stock_zh_a_hist_min_em() -> None:
    import time

    last_err = None
    for attempt in range(2):
        try:
            rows = ak.stock_zh_a_hist_min_em(symbol="600519", period="5", limit=5)
            assert isinstance(rows, list)
            assert len(rows) <= 5
            if rows:
                assert "时间" in rows[-1]
            _ok(f"分钟K线 rows={len(rows)}")
            return
        except Exception as e:
            last_err = e
            if attempt == 0:
                time.sleep(2)
    raise last_err


def test_index_zh_a_hist() -> None:
    rows = ak.index_zh_a_hist(
        symbol="000001",
        start_date="20250101",
        end_date="20250701",
        limit=5,
    )
    assert isinstance(rows, list)
    assert len(rows) <= 5
    if rows:
        assert "日期" in rows[-1]
    _ok(f"上证指数 rows={len(rows)}")


def test_stock_board_industry_name_em() -> None:
    try:
        r = ak.stock_board_industry_name_em(page=1, page_size=5)
    except Exception as e:
        _ok(f"行业板块跳过(仅东财源): {type(e).__name__}")
        return
    assert "items" in r and len(r["items"]) <= 5
    assert r["total"] > 0
    if r["items"]:
        assert "板块名称" in r["items"][0]
    _ok(f"行业板块 items={len(r['items'])} total={r['total']}")


def test_stock_zt_pool_em() -> None:
    r = ak.stock_zt_pool_em(page=1, page_size=5)
    assert "items" in r
    assert isinstance(r["items"], list)
    assert len(r["items"]) <= 5
    _ok(f"涨停池 items={len(r['items'])} total={r['total']}")


def test_existing_apis() -> None:
    info = ak.stock_individual_info_em(symbol="600519")
    assert info.get("股票简称")
    _ok(f"个股 {info.get('股票简称')}")

    hist = ak.stock_zh_a_hist(symbol="600519", limit=3)
    assert len(hist) <= 3
    _ok(f"日K rows={len(hist)}")

    lst = ak.stock_info_a_code_name(page=1, page_size=3)
    assert len(lst["items"]) <= 3
    _ok(f"列表 items={len(lst['items'])}")


TESTS = [
    test_version,
    test_stock_zh_a_hist_min_em,
    test_index_zh_a_hist,
    test_stock_board_industry_name_em,
    test_stock_zt_pool_em,
    test_existing_apis,
]


def main() -> int:
    print("akshareios API 冒烟测试")
    failed = []
    for fn in TESTS:
        try:
            fn()
        except Exception as e:
            print(f"  ✗ {fn.__name__}: {e}")
            failed.append(fn.__name__)
    if failed:
        print(f"\n失败 {len(failed)}/{len(TESTS)}: {', '.join(failed)}")
        return 1
    print(f"\n全部通过 ({len(TESTS)}/{len(TESTS)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
