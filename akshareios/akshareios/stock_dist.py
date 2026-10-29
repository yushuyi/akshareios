"""
全市场涨跌幅区间分布

一次调用返回当天全市场按涨跌幅分桶的统计，供 Agent 单请求直接汇报。
主源：东财 push2 clist（按 f3 排序分页）；主源不可用时整轮切腾讯涨幅榜，
不做逐页混合重试（逐页降级会在主源断连时把每页都拖满重试超时——
2026-10-29 绝味会话实录）。

仅支持「当天/最近收盘」：全市场历史截面无现成单请求接口，不支持指定历史日期。
"""

import math
import time
from datetime import datetime

import requests

from akshareios._fallback_tx import tx_spot_page
from akshareios._pagination import MAX_PAGE_SIZE
from akshareios.stock_spot import _spot_em

_PAGE_SIZE = MAX_PAGE_SIZE
# 串行分页整体时间预算：超限抛错宁失败不吊死终端（终端默认 120s，留出汇总余量）
_TIME_BUDGET_S = 90

# 分桶：单位 %；正侧 [low, high)、负侧 (low, high]（边界值归离零更远的桶）；
# 正好 0 计平盘（占位桶由 v==0 特判命中）
_BUCKETS: list[tuple[float, float, str | None]] = [
    (-float("inf"), -10.0, "跌幅≥10%"),
    (-10.0, -9.0, "跌幅9%~10%"),
    (-9.0, -7.0, "跌幅7%~9%"),
    (-7.0, -5.0, "跌幅5%~7%"),
    (-5.0, -3.0, "跌幅3%~5%"),
    (-3.0, -2.0, "跌幅2%~3%"),
    (-2.0, -1.0, "跌幅1%~2%"),
    (-1.0, 0.0, "跌幅0%~1%"),
    (0.0, 0.0, "平盘"),  # 正好 0 的占位桶（由 v==0 特判命中）
    (0.0, 1.0, "涨幅0%~1%"),
    (1.0, 2.0, "涨幅1%~2%"),
    (2.0, 3.0, "涨幅2%~3%"),
    (3.0, 5.0, "涨幅3%~5%"),
    (5.0, 7.0, "涨幅5%~7%"),
    (7.0, 9.0, "涨幅7%~9%"),
    (9.0, 10.0, "涨幅9%~10%"),
    (10.0, float("inf"), "涨幅≥10%"),
]
_FLAT_INDEX = 8  # (0.0, 0.0, "平盘") 占位桶的下标


def bucket_changes(changes: list[float]) -> list[dict]:
    """分桶；正好 0 计平盘。边界值归离零更远的桶（-2.0 → 跌幅2%~3%，2.0 → 涨幅2%~3%）。"""
    counts = [0] * len(_BUCKETS)
    for v in changes:
        if v == 0:
            counts[_FLAT_INDEX] += 1
            continue
        for i, (low, high, _) in enumerate(_BUCKETS):
            hit = low <= v < high if v > 0 else low < v <= high
            if hit:
                counts[i] += 1
                break
    return [
        {"区间": label, "家数": n}
        for (_, _, label), n in zip(_BUCKETS, counts)
    ]


def _append_changes(changes: list[float], items: list) -> None:
    """提取 items 里的涨跌幅；NaN/Inf 与停牌占位（None/'-'）跳过。"""
    for it in items:
        v = it.get("涨跌幅")
        if isinstance(v, (int, float)) and math.isfinite(v):
            changes.append(float(v))


def _fetch_all_changes(fetch_page, deadline: float | None = None) -> list[float]:
    """串行分页拉全市场涨跌幅；fetch_page(page) 返回 make_page_result 形状。"""
    first = fetch_page(1)
    changes: list[float] = []
    _append_changes(changes, first.get("items") or [])
    total_pages = first.get("total_pages") or 1  # 0/None → 只走第 1 页
    for p in range(2, total_pages + 1):
        if deadline is not None and time.monotonic() > deadline:
            raise TimeoutError("全市场分页超出时间预算")
        d = fetch_page(p)
        items = d.get("items") or []
        if not items and p < total_pages:
            # 中间页 200 但空列表：服务端抖动/翻页错位，宁可降级重走也不静默缺一块
            raise ValueError(f"行情第 {p}/{total_pages} 页返回空列表，疑似分页错位")
        _append_changes(changes, items)
    return changes


def stock_zh_a_change_distribution(timeout: float = 15) -> dict:
    """
    当天全市场涨跌幅区间分布（一次调用直接返回可汇报结果）。

    东财主源探测失败时整轮切腾讯涨幅榜降级。仅支持当天，不支持指定历史日期。
    :return: dict，含 总数/上涨/下跌/平盘/分布/text
    """
    deadline = time.monotonic() + _TIME_BUDGET_S

    def em_page(p: int) -> dict:
        return _spot_em(page=p, page_size=_PAGE_SIZE, sort_by="f3", timeout=timeout)

    try:
        changes = _fetch_all_changes(em_page, deadline)
    except (requests.RequestException, ValueError, TimeoutError):
        # 只捕获数据层异常：代码 bug（TypeError 等）应直接暴露而非静默降级
        def tx_page(p: int) -> dict:
            return tx_spot_page(page=p, page_size=_PAGE_SIZE, timeout=timeout)
        changes = _fetch_all_changes(tx_page, deadline)

    dist = bucket_changes(changes)
    total = len(changes)
    up = sum(d["家数"] for d in dist if d["区间"].startswith("涨幅"))
    down = sum(d["家数"] for d in dist if d["区间"].startswith("跌幅"))
    flat = total - up - down
    lines = [f"全市场 {total} 只：上涨 {up}，下跌 {down}，平盘 {flat}"]
    for d in dist:
        lines.append(f"{d['区间']} {d['家数']} 只")
    return {
        "统计日期": datetime.now().strftime("%Y-%m-%d"),
        "总数": total,
        "上涨": up,
        "下跌": down,
        "平盘": flat,
        "分布": dist,
        "text": "\n".join(lines),
    }
