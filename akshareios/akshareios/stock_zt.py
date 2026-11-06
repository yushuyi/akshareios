"""
涨停板行情 - 涨停股池

数据源：东方财富 push2ex API
原版参考：akshare/stock_feature/stock_ztb_em.py → stock_zt_pool_em()

0.6.15 起补 `_meta`：非交易日请求（如周日）时东财返回 tc=0 / pool=[]，
与「交易日但当日真没涨停」长得完全一样，模型会把前者读成「今天 0 只涨停」。
响应体里的 qdate 是服务端当前最新池日期，与请求日不一致即可判定「没有
该日数据」，无需额外请求交易日历。
"""

from datetime import datetime

from akshareios._convert import to_float, to_int
from akshareios._http import get
from akshareios._pagination import (
    DEFAULT_PAGE_SIZE,
    clamp_page,
    clamp_page_size,
    make_page_result,
)
from akshareios._provenance import Provenance, attach_meta

_ZT_PROVENANCE = Provenance(
    primary_source="东方财富 push2ex 涨停池",
    fallback_source="无（涨停池无可用降级源，失败即抛错）",
    freshness="当日盘中截至当前时刻的封板数据，收盘后为全天完整池",
    primary_note="涨跌幅 / 换手率单位 %；价格、成交额、封板资金、市值单位元。"
                 "空列表有多种含义，一律先读 `_meta.空结果原因`，"
                 "不要直接当作「当日 0 只涨停」。",
)


def _norm_trade_date(value) -> str:
    """YYYYMMDD / YYYY-MM-DD → YYYYMMDD（东财 date 参数格式）。"""
    if value is None:
        return datetime.now().strftime("%Y%m%d")
    text = str(value).strip().replace("-", "").replace("/", "")
    if len(text) != 8 or not text.isdigit():
        raise ValueError(f"date 格式应为 YYYYMMDD 或 YYYY-MM-DD: {value!r}")
    return text


def _classify_empty(trade_date: str, qdate: str, total: int) -> tuple[str, str]:
    """把「空 items」拆成可判定的几种原因，避免模型误读成当日 0 只涨停。"""
    if total > 0:
        return (
            "有池数据但本页为空",
            "total > 0 但本页无记录：页码越界，请减小 page",
        )
    if qdate and qdate == trade_date:
        return (
            "交易日且已有当日池数据",
            "当日确无涨停股（服务端池日期与请求日一致且 tc=0）",
        )
    if qdate:
        return (
            "未返回该日池数据",
            f"服务端最新池日期为 {qdate}，与请求日 {trade_date} 不一致："
            "多为非交易日 / 盘前未生成 / 历史日期不支持，"
            "空列表不等于「当日 0 只涨停」，不可据此判断市场情绪",
        )
    return (
        "未知",
        "接口未给出池日期，无法判定空结果原因；不可解读为当日 0 只涨停",
    )


def stock_zt_pool_em(
    date: str | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    timeout: float = 15,
) -> dict:
    """
    东方财富-涨停股池（分页）

    :param date: 交易日 YYYYMMDD / YYYY-MM-DD，默认当天
    :param page: 页码，从 1 开始
    :param page_size: 每页条数，默认 20，最大 100
    :return: 分页 dict，带 `_meta`（请求日期 / 服务端最新池日期 / 交易日判定 /
             空结果原因）。非交易日与「当日无涨停」在 items 上都为空，靠 `_meta` 区分。
    """
    page = clamp_page(page)
    page_size = clamp_page_size(page_size)
    trade_date = _norm_trade_date(date)

    url = "https://push2ex.eastmoney.com/getTopicZTPool"
    params = {
        "ut": "7eea3edcaed734bea9cbfc24409ed989",
        "dpt": "wz.ztzt",
        "Pageindex": str(page - 1),
        "pagesize": str(page_size),
        "sort": "fbt:asc",
        "date": trade_date,
    }
    r = get(url, params=params, timeout=timeout)
    r.raise_for_status()
    payload = r.json()
    data = payload.get("data")

    if not isinstance(data, dict):
        result = make_page_result([], page=page, page_size=page_size, total=0)
        return attach_meta(
            result,
            _ZT_PROVENANCE.meta(
                degraded=False,
                extra={
                    "请求日期": trade_date,
                    "服务端最新池日期": None,
                    "交易日判定": "未知",
                    "空结果原因": "接口未返回数据体（非交易日 / 盘前 / 服务异常），"
                                  "不可解读为当日 0 只涨停",
                },
            ),
        )

    qdate = str(data.get("qdate") or "")
    pool = data.get("pool") or []
    total = int(data.get("tc") or len(pool))

    items = []
    base_rank = (page - 1) * page_size
    for idx, row in enumerate(pool):
        items.append(_parse_zt_row(row, rank=base_rank + idx + 1))

    extra: dict = {
        "请求日期": trade_date,
        "服务端最新池日期": qdate or None,
    }
    if not items:
        judgement, reason = _classify_empty(trade_date, qdate, total)
        extra["交易日判定"] = judgement
        extra["空结果原因"] = reason
    else:
        extra["交易日判定"] = (
            "请求日与服务端池日期一致"
            if qdate == trade_date
            else f"服务端最新池日期 {qdate}（请求 {trade_date}）"
        )

    result = make_page_result(items, page=page, page_size=page_size, total=total)
    return attach_meta(result, _ZT_PROVENANCE.meta(degraded=False, extra=extra))


def _parse_zt_row(row: dict, *, rank: int) -> dict:
    zttj = row.get("zttj") or {}
    if isinstance(zttj, dict):
        zttj_str = f"{zttj.get('days', '')}/{zttj.get('ct', '')}"
    else:
        zttj_str = str(zttj)

    price = row.get("p")
    latest = to_float(price) / 1000 if price is not None else None

    fbt = str(row.get("fbt") or "").zfill(6)
    lbt = str(row.get("lbt") or "").zfill(6)

    return {
        "序号": rank,
        "代码": row.get("c"),
        "名称": row.get("n"),
        "最新价": latest,
        "涨跌幅": to_float(row.get("zdp")),
        "成交额": to_float(row.get("amount")),
        "流通市值": to_float(row.get("ltsz")),
        "总市值": to_float(row.get("tshare")),
        "换手率": to_float(row.get("hs")),
        "连板数": to_int(row.get("lbc")),
        "首次封板时间": fbt,
        "最后封板时间": lbt,
        "封板资金": to_float(row.get("fund")),
        "炸板次数": to_int(row.get("zbc")),
        "所属行业": row.get("hybk"),
        "涨停统计": zttj_str,
    }
