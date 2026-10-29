#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全市场涨跌幅分布模块的单元测试（monkeypatch 网络，无需联网）"""

import pytest
import requests as requests_lib

import akshareios.stock_dist as sd


# --------------------------------------------------------------- 分桶边界

def test_bucket_flat_zero() -> None:
    dist = {d["区间"]: d["家数"] for d in sd.bucket_changes([0.0, 0.0, 1.5])}
    assert dist["平盘"] == 2
    assert dist["涨幅1%~2%"] == 1


def test_bucket_half_open_boundaries() -> None:
    # [low, high)：-2.0 落「跌幅2%~3%」，2.0 落「涨幅2%~3%」，10.0 落「涨幅≥10%」
    dist = {d["区间"]: d["家数"] for d in sd.bucket_changes([-2.0, 2.0, 10.0, -10.5])}
    assert dist["跌幅2%~3%"] == 1
    assert dist["涨幅2%~3%"] == 1
    assert dist["涨幅≥10%"] == 1
    assert dist["跌幅≥10%"] == 1


def test_bucket_no_silent_drop() -> None:
    # 分桶计数总和 == 输入条数（任何值都必须落入唯一桶）
    changes = [-11.0, -9.95, -5.0, -2.0, -0.001, 0.0, 0.001, 1.0, 2.5, 6.0, 9.0, 9.99, 20.0]
    dist = sd.bucket_changes(changes)
    assert sum(d["家数"] for d in dist) == len(changes)


# --------------------------------------------------------------- 全市场拉取

def _mk_page(values: list, page: int, total: int, page_size: int = 2) -> dict:
    items = [{"涨跌幅": v} for v in values]
    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": (total + page_size - 1) // page_size,
        "has_more": page * page_size < total,
    }


def test_fetch_all_changes_walks_all_pages() -> None:
    pages = {1: _mk_page([1.0, 2.0], 1, 5), 2: _mk_page([-1.0, None], 2, 5), 3: _mk_page([0.0], 3, 5)}
    changes = sd._fetch_all_changes(lambda p: pages[p])
    assert changes == [1.0, 2.0, -1.0, 0.0]  # None（停牌）被跳过


def test_distribution_falls_back_to_tx(monkeypatch) -> None:
    # 东财整轮失败 → 全量走腾讯，不再逐页试东财
    tx_pages = {1: _mk_page([3.0, -2.0], 1, 3), 2: _mk_page([0.0], 2, 3)}

    def boom(**kw):
        raise requests_lib.exceptions.ConnectionError("push2 不可用")

    monkeypatch.setattr(sd, "_spot_em", boom)
    monkeypatch.setattr(sd, "tx_spot_page", lambda *, page, page_size, timeout: tx_pages[page])
    result = sd.stock_zh_a_change_distribution(timeout=5)
    assert result["总数"] == 3
    assert result["上涨"] == 1
    assert result["下跌"] == 1
    assert result["平盘"] == 1
    assert "全市场 3 只：上涨 1，下跌 1，平盘 1" in result["text"]


def test_distribution_em_midway_fail_falls_back(monkeypatch) -> None:
    # 东财第 1 页成功、第 2 页断连 → 弃掉已拉数据，腾讯从第 1 页整轮重走
    em_pages = {1: _mk_page([1.0, 2.0], 1, 4)}

    def fake_em(**kw):
        if kw["page"] == 1:
            return em_pages[1]
        raise requests_lib.exceptions.ConnectionError("em 中途断")

    tx_calls: list[int] = []
    tx_pages = {1: _mk_page([3.0], 1, 5), 2: _mk_page([-2.0], 2, 5), 3: _mk_page([0.0], 3, 5)}

    def fake_tx(*, page, page_size, timeout):
        tx_calls.append(page)
        return tx_pages[page]

    monkeypatch.setattr(sd, "_spot_em", fake_em)
    monkeypatch.setattr(sd, "tx_spot_page", fake_tx)
    result = sd.stock_zh_a_change_distribution()
    assert tx_calls == [1, 2, 3]
    assert result["总数"] == 3


def test_fetch_total_pages_zero_or_none_single_page() -> None:
    # total_pages 为 0/None 时只走第 1 页，不报错
    assert sd._fetch_all_changes(lambda p: _mk_page([1.0], 1, 0)) == [1.0]
    page = _mk_page([2.0], 1, 5)
    page["total_pages"] = None
    assert sd._fetch_all_changes(lambda p: page) == [2.0]


def test_fetch_empty_middle_page_raises() -> None:
    # 中间页 200 但空列表 → 抛错触发整轮降级，不允许静默缺一块
    pages = {1: _mk_page([1.0], 1, 5), 2: _mk_page([], 2, 5), 3: _mk_page([2.0], 3, 5)}
    with pytest.raises(ValueError):
        sd._fetch_all_changes(lambda p: pages[p])


def test_distribution_em_primary(monkeypatch) -> None:
    em_pages = {1: _mk_page([5.0, -7.0], 1, 2)}
    monkeypatch.setattr(sd, "_spot_em", lambda **kw: em_pages[kw["page"]])
    result = sd.stock_zh_a_change_distribution()
    assert result["总数"] == 2
    dist = {d["区间"]: d["家数"] for d in result["分布"]}
    assert dist["涨幅5%~7%"] == 1
    assert dist["跌幅7%~9%"] == 1
