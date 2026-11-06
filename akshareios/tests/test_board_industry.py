#!/usr/bin/env python3
"""板块成分股接口与板块代码解析单元测试（无需联网，monkeypatch 网络层）"""

import pytest

import akshareios.board_industry as bi


@pytest.fixture()
def mock_board_list():
    """正常东财板块列表（非降级）"""

    def _factory(items, has_more=False):
        bi.stock_board_industry_name_em = lambda page, page_size, timeout: {
            "items": items,
            "page": page,
            "page_size": page_size,
            "total": len(items),
            "total_pages": 1,
            "has_more": has_more,
        }

    return _factory


@pytest.fixture()
def mock_clist():
    """正常 push2 clist 响应"""

    def _factory(total=134, diff=None):
        bi.get_push2_clist = lambda params, timeout: {
            "data": {"total": total, "diff": diff if diff is not None else [
                {"f12": "603990", "f14": "麦迪科技", "f2": 18.87, "f3": 2.55, "f5": "-"},
            ]}
        }

    return _factory


def test_bk_code_case_insensitive(mock_board_list, mock_clist):
    """小写 bk 代码也应直接走代码路径（不翻板块列表）"""
    mock_clist(total=7)
    r = bi.stock_board_industry_cons_em("bk0737")
    assert r["total"] == 7


def test_name_resolves_to_bk_code(mock_board_list, mock_clist):
    mock_board_list([{"板块代码": "BK0735", "板块名称": "计算机设备"},
                     {"板块代码": "BK0737", "板块名称": "软件开发"}])
    mock_clist()
    r = bi.stock_board_industry_cons_em("软件开发")
    assert r["total"] == 134
    assert r["items"][0]["名称"] == "麦迪科技"


def test_dash_field_becomes_none(mock_board_list, mock_clist):
    mock_clist()
    r = bi.stock_board_industry_cons_em("BK0737")
    assert r["items"][0]["成交量"] is None


def test_degraded_board_list_falls_back_to_sina_cons(mock_board_list, monkeypatch):
    """板块列表降级新浪时按名称查成分股，应走新浪降级源而不是抛「稍后重试」"""
    mock_board_list([{"板块代码": "new_blhy", "板块名称": "玻璃行业", "数据源": "新浪行业"}])
    called = {}

    def fake_cons(node, *, page, page_size, timeout):
        called["node"] = node
        return {"items": [], "page": page, "page_size": page_size,
                "total": 19, "total_pages": 1, "has_more": False}

    monkeypatch.setattr(bi, "sina_board_industry_cons_page", fake_cons)
    r = bi.stock_board_industry_cons_em("玻璃行业")
    assert called["node"] == "new_blhy"
    assert r["total"] == 19
    assert r["_meta"]["状态"] == "降级"
    assert r["_meta"]["数据源"] == "新浪行业成分股"


def test_sina_node_code_skips_board_list(monkeypatch):
    """直接传 new_xxx 时不应翻板块列表，直接走新浪成分股"""
    def boom(*args, **kwargs):
        raise AssertionError("传 new_xxx 时不应翻板块列表")

    monkeypatch.setattr(bi, "stock_board_industry_name_em", boom)
    monkeypatch.setattr(
        bi, "sina_board_industry_cons_page",
        lambda node, *, page, page_size, timeout: {
            "items": [], "page": page, "page_size": page_size,
            "total": 0, "total_pages": 0, "has_more": False,
        },
    )
    r = bi.stock_board_industry_cons_em("new_blhy")
    assert r["_meta"]["状态"] == "降级"


def test_main_source_has_provenance_meta(mock_board_list, mock_clist):
    """主源返回也要带 _meta，否则模型无法区分「主源」与「忘了打标」"""
    mock_clist(total=7)
    r = bi.stock_board_industry_cons_em("BK0737")
    assert r["_meta"]["状态"] == "主源"
    assert r["_meta"]["数据源"] == "东方财富 push2 clist"


def test_both_sources_empty_raises_actionable_error(mock_board_list):
    """双源均空时不得落到「未找到板块」，要报双源不可用"""
    mock_board_list([])
    with pytest.raises(ValueError, match="均暂不可用"):
        bi.stock_board_industry_cons_em("软件开发")


def test_push2_down_error_mentions_bk_hint(mock_board_list, mock_clist):
    """网络 outage 与 BK 代码传错不可区分，报错需同时给出两条出路"""
    mock_board_list([{"板块代码": "BK0737", "板块名称": "软件开发"}])

    def boom(params, timeout):
        raise bi.requests.ConnectionError("所有 push2 CDN 节点不可用")

    bi.get_push2_clist = boom
    with pytest.raises(ValueError, match="BK 代码无效"):
        bi.stock_board_industry_cons_em("软件开发")


def test_name_scan_pages_until_match():
    """名称在后续页：翻页直到命中，has_more 终止"""
    def fake_name_em(page, page_size, timeout):
        return {
            "items": [{"板块代码": f"BK{1000 + page}", "板块名称": f"板块{page}"}],
            "has_more": page < 3,
        }

    bi.stock_board_industry_name_em = fake_name_em
    bi.get_push2_clist = lambda params, timeout: {"data": {"total": 1, "diff": [
        {"f12": "600000", "f14": "浦发银行"}]}}
    r = bi.stock_board_industry_cons_em("板块2")
    assert r["total"] == 1


def test_sina_cons_unit_conversion(monkeypatch):
    """新浪成分股：股→手、万元→元，量比留 None，总数取 count 接口。"""
    import akshareios._fallback_sina as sfs

    row = {
        "code": "600176", "name": "中国巨石", "trade": "27.45",
        "changepercent": -5.443, "pricechange": -1.58,
        "volume": 149088592, "amount": 4060205103,
        "turnoverratio": 3.75388, "per": 33.423,
        "high": 28.08, "low": 26.5, "open": 27.06, "settlement": 29.03,
        "mktcap": 10988610.31836, "nmc": 10902006.39186,
    }

    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return [row]

    monkeypatch.setattr(sfs, "_sina_node_count", lambda node, *, timeout: 19)
    monkeypatch.setattr(
        sfs.requests, "get",
        lambda url, params=None, timeout=None, headers=None: _Resp(),
    )
    r = sfs.sina_board_industry_cons_page("new_blhy", page=1, page_size=3, timeout=10)
    it = r["items"][0]
    assert r["total"] == 19
    assert it["代码"] == "600176"
    assert it["成交量"] == 1490885            # 股 → 手
    assert it["总市值"] == 109886103183.6     # 万元 → 元
    assert it["量比"] is None
