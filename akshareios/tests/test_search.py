#!/usr/bin/env python3
"""名称→代码解析单测（无需联网）"""

import pytest

import akshareios.stock_search as ss

_MOUTAI = [
    {"Code": "600519", "Name": "贵州茅台", "SecurityTypeName": "沪A",
     "Classify": "AStock", "MktNum": "1"},
]
_SOFTWARE = [
    {"Code": "932094", "Name": "软件开发", "SecurityTypeName": "指数",
     "Classify": "UniversalIndex", "MktNum": "2"},
    {"Code": "BK0737", "Name": "软件开发", "SecurityTypeName": "板块",
     "Classify": "BK", "MktNum": "90"},
    {"Code": "159036", "Name": "软件开发ETF华宝", "SecurityTypeName": "基金",
     "Classify": "Fund", "MktNum": "0"},
]


def test_exact_name_returns_stock_code(monkeypatch):
    monkeypatch.setattr(ss, "_search_suggest", lambda *a, **k: [
        {"Code": "600519", "Name": "贵州茅台", "SecurityTypeName": "沪A",
         "Classify": "AStock", "MktNum": "1"},
    ])
    r = ss.stock_name_to_code("贵州茅台")
    assert r["精确匹配"] == "600519"
    assert r["推荐代码"] == "600519"
    assert r["items"][0]["代码体系"] == "A股"


def test_short_name_gets_single_candidate_recommended(monkeypatch):
    """用户说「茅台」时正式名是「贵州茅台」，唯一 A 股候选应给推荐代码但标明需核对"""
    monkeypatch.setattr(ss, "_search_suggest", lambda *a, **k: _MOUTAI)
    r = ss.stock_name_to_code("茅台")
    assert r["精确匹配"] is None
    assert r["推荐代码"] == "600519"
    assert "核对简称" in r["_meta"]["推荐说明"]


def test_same_name_mixed_types_not_mistaken_for_stock(monkeypatch):
    """「软件开发」同名有指数 / 板块 / 基金，第一个候选绝不能当股票代码"""
    monkeypatch.setattr(ss, "_search_suggest", lambda *a, **k: _SOFTWARE)
    r = ss.stock_name_to_code("软件开发")
    assert r["精确匹配"] is None
    assert r["推荐代码"] is None
    kinds = [i["代码体系"] for i in r["items"]]
    assert kinds == ["指数", "东财板块BK", "基金"]
    assert "别直接把第一个代码" in r["_meta"]["精确匹配说明"]


def test_security_type_filter(monkeypatch):
    monkeypatch.setattr(ss, "_search_suggest", lambda *a, **k: _SOFTWARE)
    r = ss.stock_name_to_code("软件开发", security_type="东财板块BK")
    assert len(r["items"]) == 1
    assert r["items"][0]["代码"] == "BK0737"


def test_resolve_board_code_by_name(monkeypatch):
    monkeypatch.setattr(ss, "_search_suggest", lambda *a, **k: _SOFTWARE)
    assert ss.resolve_board_code_by_name("软件开发") == "BK0737"
    assert ss.resolve_board_code_by_name("不存在的板块") is None


def test_resolve_board_code_swallows_network_error(monkeypatch):
    def boom(*a, **k):
        raise ConnectionError("searchapi 不可用")

    monkeypatch.setattr(ss, "_search_suggest", boom)
    assert ss.resolve_board_code_by_name("软件开发") is None


def test_empty_name_raises():
    with pytest.raises(ValueError, match="不能为空"):
        ss.stock_name_to_code("  ")


def test_meta_declares_code_system_rule(monkeypatch):
    monkeypatch.setattr(ss, "_search_suggest", lambda *a, **k: _SOFTWARE)
    meta = ss.stock_name_to_code("软件开发")["_meta"]
    assert meta["状态"] == "主源"
    assert "代码体系" in meta["口径说明"]
    assert meta["候选数"] == 3
