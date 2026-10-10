"""
A 股分笔成交明细（成交明细）

数据源按场景分工：

- 最近一个交易日：腾讯 stock.gtimg.cn（主源），东财 details/get（备用源），
  通过 call_with_fallback 自动降级；盘中实时刷新，当日 16:00 后为全天数据。
- 任意历史交易日：网易 cjmx（免费渠道中唯一支持指定历史日期的源）。

以上均为交易所切片数据（约 3 秒一笔），并非 Level-2 逐笔成交；
成交量单位为「手」，成交金额单位为「元」。
"""

import re
from datetime import datetime, timedelta

import requests

from akshareios._convert import ensure_symbol, to_float, to_int
from akshareios._fallback import call_with_fallback
from akshareios._http import get, get_push2_json
from akshareios._symbols import to_market_symbol


# 市场归属：北交所段（4/8/920）、沪市段（5/6/9，须排除 920），其余为深市。
# 东财 secid 与网易页面前缀共用同一判断，避免两处自相矛盾。


def _is_bj(code: str) -> bool:
    return code.startswith(("4", "8", "920"))


def _is_sh(code: str) -> bool:
    return not _is_bj(code) and code.startswith(("5", "6", "9"))


# ---------------------------------------------------------------- 腾讯源

_TX_URL = "https://stock.gtimg.cn/data/index.php"
_TX_HEADERS = {"Referer": "https://gu.qq.com/"}
_TX_PROP = {"B": "买盘", "S": "卖盘", "M": "中性盘"}
_TX_MAX_PAGES = 300


def stock_zh_a_tick_tx(symbol: str, *, timeout: float = 15) -> list[dict]:
    """
    腾讯财经-分笔成交明细（最近一个交易日）。

    盘中调用返回截至当前时刻的明细，当日 16:00 后为全天数据；
    次日开盘前调用仍返回上一交易日数据，开盘后切换为新交易日。
    """
    code = ensure_symbol(symbol)
    tx_sym = to_market_symbol(code)

    rows: list[dict] = []
    seen_idx: set[str] = set()
    page = 0
    while page < _TX_MAX_PAGES:
        r = get(
            _TX_URL,
            params={"appn": "detail", "action": "data", "c": tx_sym, "p": page},
            timeout=timeout,
            headers=_TX_HEADERS,
        )
        text = _extract_js_string(r.text)
        page_count = 0
        for record in text.split("|") if text else []:
            fields = record.split("/")
            if len(fields) < 7:
                continue
            seq = fields[0]
            # 序号全局唯一且跨页连续，用它去重（同一秒可能有多笔，不能按时间去重）
            if seq in seen_idx:
                continue
            seen_idx.add(seq)
            rows.append({
                "成交时间": fields[1],
                "成交价格": to_float(fields[2]),
                "价格变动": to_float(fields[3]),
                "成交量": to_int(fields[4]),
                "成交金额": to_int(fields[5]),
                "性质": _TX_PROP.get(fields[6], fields[6]),
            })
            page_count += 1

        if page_count == 0:
            # 再探一页，防止个别空页造成提前终止
            r2 = get(
                _TX_URL,
                params={"appn": "detail", "action": "data", "c": tx_sym, "p": page + 1},
                timeout=timeout,
                headers=_TX_HEADERS,
            )
            if not _extract_js_string(r2.text):
                break
        page += 1

    return rows


def _extract_js_string(text: str) -> str:
    """
    提取响应中唯一的数据字符串。

    响应形如：v_detail_data_sh603517=[0,"0/09:25:00/...|..."]
    数据内部只含数字、时间、/、| 与 S/B/M，不含双引号，取首尾双引号之间即可。
    """
    if not text:
        return ""
    first, last = text.find('"'), text.rfind('"')
    return text[first + 1:last] if first >= 0 and last > first else ""


# ---------------------------------------------------------------- 东财源

_EM_DETAILS_PATH = "/api/qt/stock/details/get"
# 东财方向标记（对齐上游 AKShare stock_intraday_em）：2 买盘、1 卖盘、4 中性盘
_EM_PROP = {"2": "买盘", "1": "卖盘", "4": "中性盘"}
_EM_UT = "bd1d9ddb04089700cf9c27f6f7426281"
_EM_MAX_PAGES = 30


def stock_zh_a_tick_em(symbol: str, *, timeout: float = 15) -> list[dict]:
    """
    东方财富-当日分笔成交明细（含 09:15 起集合竞价记录）。

    单次请求返回最近约 1000 条，成交活跃的标的自动向前翻页补全。
    东财不提供价格变动，成交金额按 价格 × 成交量 × 100 估算。
    """
    code = ensure_symbol(symbol)
    # 东财 secid：沪市 1、深市与北交所 0
    market = 1 if _is_sh(code) else 0
    secid = f"{market}.{code}"

    rows: list[dict] = []
    seen: set[str] = set()
    for pos in range(_EM_MAX_PAGES):
        envelope = get_push2_json(
            _EM_DETAILS_PATH,
            params={
                "secid": secid,
                "fields1": "f1,f2,f3,f4",
                "fields2": "f51,f52,f53,f54,f55",
                "ut": _EM_UT,
                "fltt": "2",
                "pos": f"-{pos}",
            },
            timeout=timeout,
        )
        # get_push2_json 返回外层 envelope，details 在其 data 层
        details = (envelope.get("data") or {}).get("details") or []
        page_count = 0
        for line in details:
            if line in seen:
                continue
            seen.add(line)
            fields = line.split(",")
            if len(fields) < 5:
                continue
            price = to_float(fields[1])
            volume = to_int(fields[2])
            amount = (
                int(round(price * volume * 100))
                if price is not None and volume is not None
                else None
            )
            rows.append({
                "成交时间": fields[0],
                "成交价格": price,
                "价格变动": None,
                "成交量": volume,
                "成交金额": amount,
                "性质": _EM_PROP.get(fields[4], "中性盘"),
            })
            page_count += 1

        if page_count == 0:
            break
        # 本页最早记录已到盘前集合竞价，全天拉取完毕；取最小时间，不依赖返回顺序
        earliest = min(line.split(",")[0] for line in details)
        if earliest[:5] <= "09:15":
            break

    rows.sort(key=lambda x: x["成交时间"])
    return rows


# ---------------------------------------------------------------- 网易源（历史任意日期）

def stock_zh_a_tick_163(
    symbol: str,
    trade_date: str | None = None,
    *,
    timeout: float = 15,
) -> list[dict]:
    """
    网易财经-历史分笔成交明细，可指定任意已收盘的交易日。

    :param trade_date: 交易日，支持 YYYYMMDD 或 YYYY-MM-DD；
                       缺省取最近一个交易日
    """
    code = ensure_symbol(symbol)
    date_str = _normalize_date(trade_date) if trade_date else latest_trade_date()

    url = _build_163_url(code, date_str)
    r = get(url, timeout=timeout, headers={"Referer": "https://quotes.money.163.com/"})
    if r.status_code != 200:
        raise requests.ConnectionError(
            f"网易历史成交明细暂不可用（HTTP {r.status_code}，该服务偶发维护）；"
            "最近一个交易日的数据可改用 stock_zh_a_tick_tx 获取"
        )
    r.encoding = "gbk"
    rows = _parse_163_table(r.text)
    if not rows:
        raise ValueError(
            f"网易未返回 {date_str} 的成交明细，请确认该日期为交易日且已收盘"
        )
    return rows


def _build_163_url(code: str, date_str: str) -> str:
    # 网易页面市场前缀：沪市 0，深市及北交所 1
    market_prefix = "0" if _is_sh(code) else "1"
    return (
        f"https://quotes.money.163.com/cjmx/{date_str[:4]}/{date_str}/"
        f"{market_prefix}{code}.html"
    )


def _parse_163_table(html_text: str) -> list[dict]:
    """解析网易成交明细静态表格，列序：时间/价格/价格变动/成交量(手)/成交金额(元)/性质。"""
    rows: list[dict] = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html_text, re.S | re.I):
        cells = [
            re.sub(r"<[^>]+>", "", c).strip()
            for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S | re.I)
        ]
        if len(cells) < 6 or not re.fullmatch(r"\d{2}:\d{2}:\d{2}", cells[0]):
            continue
        rows.append({
            "成交时间": cells[0],
            "成交价格": to_float(cells[1]),
            "价格变动": to_float(cells[2]),
            "成交量": to_int(cells[3].replace(",", "")),
            "成交金额": to_int(cells[4].replace(",", "")),
            "性质": cells[5],
        })
    return rows


# ---------------------------------------------------------------- 统一入口

def stock_zh_a_tick(
    symbol: str,
    trade_date: str | None = None,
    *,
    source: str = "auto",
    timeout: float = 15,
) -> list[dict]:
    """
    分笔成交明细统一入口，自动选择数据源。

    - 不传 trade_date（默认）：取最近一个交易日，腾讯主源、东财备用自动降级；
    - 传入 trade_date：走网易历史源（免费渠道仅网易支持历史日期）。
    :param source: auto / tx / em / 163，可强制指定数据源
    """
    code = ensure_symbol(symbol)
    latest = latest_trade_date()
    want_date = _normalize_date(trade_date) if trade_date else latest
    is_latest = want_date == latest

    if source == "tx":
        return stock_zh_a_tick_tx(code, timeout=timeout)
    if source == "em":
        return stock_zh_a_tick_em(code, timeout=timeout)
    if source == "163":
        return stock_zh_a_tick_163(code, want_date, timeout=timeout)

    # 历史日期：免费渠道只能走网易，失败时由其抛出带说明的异常
    if not is_latest:
        return stock_zh_a_tick_163(code, want_date, timeout=timeout)

    # 最近交易日：腾讯主源，异常或空结果时东财兜底
    return call_with_fallback(
        lambda: stock_zh_a_tick_tx(code, timeout=timeout),
        lambda: stock_zh_a_tick_em(code, timeout=timeout),
        retry_on_empty=True,
    )


# ---------------------------------------------------------------- 日期工具

def _normalize_date(date_str: str) -> str:
    digits = str(date_str).replace("-", "").replace("/", "")
    if not re.fullmatch(r"\d{8}", digits):
        raise ValueError(f"无效的交易日期: {date_str!r}，格式应为 YYYYMMDD")
    return digits


def latest_trade_date(reference: datetime | None = None) -> str:
    """
    返回最近一个交易日（仅剔除周末，不含法定节假日判断）。
    周一回退到上周五，周日回退到上周五，其余回退一天。
    """
    now = reference or datetime.now()
    weekday = now.weekday()  # 周一 0 … 周日 6
    if weekday == 0:       # 周一 → 上周五
        delta = 3
    elif weekday == 6:     # 周日 → 上周五
        delta = 2
    else:                  # 周二至周六 → 前一天
        delta = 1
    return (now - timedelta(days=delta)).strftime("%Y%m%d")
