"""
沪深京 A 股实时行情快照

数据源：东方财富 push2 API
原版参考：akshare/stock_feature/stock_hist_em.py → stock_zh_a_spot_em()
"""

from akshareios._http import get_push2_clist

_FIELD_MAP = {
    "f2": "最新价",
    "f3": "涨跌幅",
    "f4": "涨跌额",
    "f5": "成交量",
    "f6": "成交额",
    "f7": "振幅",
    "f8": "换手率",
    "f9": "市盈率-动态",
    "f10": "量比",
    "f12": "代码",
    "f14": "名称",
    "f15": "最高",
    "f16": "最低",
    "f17": "今开",
    "f18": "昨收",
    "f20": "总市值",
    "f21": "流通市值",
    "f23": "市净率",
}


def stock_zh_a_spot_em(timeout: float = 20) -> list[dict]:
    """
    东方财富网-沪深京 A 股-实时行情（全市场快照）

    :param timeout: 请求超时时间（秒）
    :return: [{"代码": "000001", "名称": "平安银行", "最新价": 12.5, ...}, ...]
    """
    all_data = []
    page = 1

    while True:
        params = {
            "pn": str(page),
            "pz": "5000",
            "po": "1",
            "np": "1",
            "ut": "bd1d9ddb04089700cf9c27f6f7426281",
            "fltt": "2",
            "invt": "2",
            "fid": "f12",
            "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048",
            "fields": ",".join(_FIELD_MAP.keys()),
        }
        data_json = get_push2_clist(params, timeout=timeout)
        data_body = data_json.get("data", {})
        diff = data_body.get("diff", [])
        if not diff:
            break

        for item in diff:
            record = {}
            for field_key, field_name in _FIELD_MAP.items():
                val = item.get(field_key)
                if val == "-":
                    val = None
                record[field_name] = val
            all_data.append(record)

        total = data_body.get("total", 0)
        if len(all_data) >= total:
            break
        page += 1

    return all_data
