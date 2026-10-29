"""
新浪财经备用数据源

参考：akshare/stock/stock_zh_a_sina.py、stock_zh_a_minute
"""

import json
import re

import requests

from akshareios._convert import apply_row_limit, to_float, to_int
from akshareios._http import _EM_HEADERS
from akshareios._pagination import make_page_result
from akshareios._symbols import to_market_symbol

_SINA_HEADERS = {
    **_EM_HEADERS,
    "Referer": "https://finance.sina.com.cn/",
}

_HQ_URL = "https://hq.sinajs.cn/list={symbols}"
_MINUTE_URL = "https://quotes.sina.cn/cn/api/jsonp_v2.php/=/CN_MarketDataService.getKLineData"
_SPOT_URL = "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"
_HY_URL = "https://vip.stock.finance.sina.com.cn/q/view/newSinaHy.php"
_FFLOW_URL = (
    "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/MoneyFlow.ssl_qsfx_lscjfb"
)
_COUNT_URL = (
    "http://vip.stock.finance.sina.com.cn/quotes_service/api/"
    "json_v2.php/Market_Center.getHQNodeStockCount?node=hs_a"
)


def _parse_sina_boards(text: str) -> list[dict]:
    """解析新浪行业板块响应（var S_Finance_bankuai_sinaindustry = {...}，GBK 已解码）。"""
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return []
    try:
        raw = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return []
    items = []
    for label, row in raw.items():
        parts = str(row).split(",")
        if len(parts) < 13:
            continue
        # 盘前/停牌时段领涨股可能为空，to_market_symbol("") 会产出伪代码
        leader_code = to_market_symbol(parts[8]).removeprefix("sh").removeprefix("sz").removeprefix("bj") if parts[8] else None
        items.append({
            "板块代码": label,
            "板块名称": parts[1],
            "公司家数": to_int(parts[2]),
            "平均价格": to_float(parts[3]),
            "涨跌额": to_float(parts[4]),
            "涨跌幅": to_float(parts[5]),
            "总成交量": to_int(parts[6]),
            "总成交额": to_float(parts[7]),
            "领涨股代码": leader_code,
            "领涨股票": parts[12] or None,
            # 降级源的板块代码是新浪体系（new_xxx），不能喂给东财成分股接口，明示给调用方
            "数据源": "新浪行业",
        })
    return items


def sina_board_industry_page(page: int, page_size: int, *, timeout: float) -> dict:
    """新浪行业板块分页 —— 东财行业板块不可用时的降级源。"""
    r = requests.get(_HY_URL, timeout=timeout, headers=_SINA_HEADERS)
    r.raise_for_status()
    items = _parse_sina_boards(r.content.decode("gbk", errors="replace"))
    start = (page - 1) * page_size
    return make_page_result(
        items[start : start + page_size], page=page, page_size=page_size, total=len(items)
    )


def sina_individual_quote(symbol: str, *, timeout: float) -> dict:
    """新浪实时报价，字段少于东财个股详情。"""
    sina_sym = to_market_symbol(symbol)
    r = requests.get(
        _HQ_URL.format(symbols=sina_sym),
        timeout=timeout,
        headers=_SINA_HEADERS,
    )
    r.raise_for_status()
    text = r.text
    m = re.search(r'="([^"]*)"', text)
    if not m:
        return {}
    parts = m.group(1).split(",")
    if len(parts) < 10 or not parts[0]:
        return {}

    prev_close = to_float(parts[2])
    latest = to_float(parts[3])
    change = None
    pct = None
    if prev_close and latest is not None:
        change = round(latest - prev_close, 4)
        if prev_close:
            pct = round(change / prev_close * 100, 4)

    plain = sina_sym.removeprefix("sh").removeprefix("sz").removeprefix("bj")
    return {
        "股票代码": plain,
        "股票简称": parts[0],
        "最新价": latest,
        "今开": to_float(parts[1]),
        "昨收": prev_close,
        "最高": to_float(parts[4]),
        "最低": to_float(parts[5]),
        "成交量": to_int(parts[8]) if len(parts) > 8 else None,
        "成交额": to_float(parts[9]) if len(parts) > 9 else None,
        "涨跌额": change,
        "涨跌幅": pct,
    }


def sina_minute_klines(
    symbol: str,
    *,
    period: str,
    limit: int | None,
    timeout: float,
) -> list[dict]:
    """新浪分钟 K 线（period 为 1/5/15/30/60）。"""
    sina_sym = to_market_symbol(symbol)
    datalen = min(limit if limit and limit > 0 else 120, 250)
    params = {
        "symbol": sina_sym,
        "scale": period if period != "1" else "1",
        "ma": "no",
        "datalen": str(datalen),
    }
    r = requests.get(_MINUTE_URL, params=params, timeout=timeout, headers=_SINA_HEADERS)
    r.raise_for_status()
    text = r.text
    if "=(" not in text:
        return []
    payload = text.split("=(", 1)[1].rsplit(");", 1)[0]
    data = json.loads(payload)
    if not isinstance(data, list):
        return []

    rows = []
    for item in data:
        day = item.get("day") or ""
        rows.append({
            "时间": day,
            "开盘": to_float(item.get("open")),
            "收盘": to_float(item.get("close")),
            "最高": to_float(item.get("high")),
            "最低": to_float(item.get("low")),
            "成交量": to_int(item.get("volume")),
            "成交额": to_float(item.get("amount")) if item.get("amount") else None,
            "振幅": None,
            "涨跌幅": None,
            "涨跌额": None,
            "换手率": None,
        })
    return apply_row_limit(rows, limit)


def sina_code_name_page(
    *,
    page: int,
    page_size: int,
    timeout: float,
) -> dict:
    """新浪 A 股列表分页（code + name）。"""
    try:
        cr = requests.get(_COUNT_URL, timeout=timeout, headers=_SINA_HEADERS)
        cr.raise_for_status()
        total = int(re.findall(r"\d+", cr.text)[0])
    except Exception:
        total = 5000

    params = {
        "page": str(page),
        "num": str(page_size),
        "sort": "symbol",
        "asc": "1",
        "node": "hs_a",
        "symbol": "",
        "_s_r_a": "page",
    }
    r = requests.get(_SPOT_URL, params=params, timeout=timeout, headers=_SINA_HEADERS)
    r.raise_for_status()
    # 新浪返回 JSON 数组，可能非严格 JSON
    text = r.text.strip()
    data = json.loads(text)
    items = []
    for row in data:
        code = str(row.get("code", "")).zfill(6)
        items.append({"code": code, "name": row.get("name")})

    return make_page_result(items, page=page, page_size=page_size, total=total)


def _net_pct(net: float | None, turnover: float) -> float | None:
    """净额占成交额百分比；无成交额或无净额时返回 None。"""
    if net is None or turnover <= 0:
        return None
    return round(net / turnover * 100, 2)


def sina_fund_flow(symbol: str, *, limit: int | None, timeout: float) -> list[dict]:
    """
    新浪历史成交分布降级（lscjfb 接口）—— 个股资金流东财不可用时备用。

    r0~r3 为特大/大/中/小单买入额（四档合计=成交额），r0_net~r3_net 为各档
    净流入额；「主力」按东财口径取 特大单+大单。新浪的单档划分阈值与东财
    不完全一致，分档金额为近似值；占比由净额/成交额推算。
    返回按时间正序，字段与东财主源一致。
    """
    params = {
        "page": "1",
        "num": str(min(limit or 250, 250)),
        "sort": "opendate",
        "asc": "0",
        "daima": to_market_symbol(symbol),
    }
    resp = requests.get(_FFLOW_URL, params=params, headers=_SINA_HEADERS, timeout=timeout)
    resp.raise_for_status()
    payload = resp.json()
    if not isinstance(payload, list):
        return []

    rows = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        # 四档买入额合计 = 成交额（A 股买卖金额相等）
        turnover = sum(to_float(item.get(k)) or 0.0 for k in ("r0", "r1", "r2", "r3"))
        r0_net = to_float(item.get("r0_net"))
        r1_net = to_float(item.get("r1_net"))
        r2_net = to_float(item.get("r2_net"))
        r3_net = to_float(item.get("r3_net"))
        # 两档均缺失时主力净额应为 None 而非 0，与同行小/中单语义一致
        main_net = None if r0_net is None and r1_net is None else (r0_net or 0.0) + (r1_net or 0.0)
        change = to_float(item.get("changeratio"))
        rows.append({
            "日期": item.get("opendate"),
            "主力净流入额": main_net,
            "小单净流入额": r3_net,
            "中单净流入额": r2_net,
            "大单净流入额": r1_net,
            "超大单净流入额": r0_net,
            "主力净占比": _net_pct(main_net, turnover),
            "小单净占比": _net_pct(r3_net, turnover),
            "中单净占比": _net_pct(r2_net, turnover),
            "大单净占比": _net_pct(r1_net, turnover),
            "超大单净占比": _net_pct(r0_net, turnover),
            "收盘价": to_float(item.get("trade")),
            "涨跌幅": round(change * 100, 2) if change is not None else None,
        })
    rows.reverse()  # 新浪按日期倒序返回，统一为正序
    return rows
