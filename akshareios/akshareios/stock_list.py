"""
沪深京 A 股代码名称列表

数据源：东方财富 push2 API
原版参考：akshare/stock_feature/stock_hist_em.py → stock_zh_a_spot_em() 的股票列表部分
"""

from akshareios._http import get_push2_clist


def stock_info_a_code_name(timeout: float = 15) -> list[dict]:
    """
    获取沪深京全部 A 股的代码和名称列表。

    :param timeout: 请求超时时间（秒）
    :return: [{"code": "000001", "name": "平安银行"}, ...]
    """
    all_stocks = []
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
            "fid": "f3",
            "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048",
            "fields": "f12,f14",
        }
        data = get_push2_clist(params, timeout=timeout)
        data_body = data.get("data", {})
        diff = data_body.get("diff", [])
        if not diff:
            break

        for item in diff:
            if "f12" in item:
                all_stocks.append({"code": item["f12"], "name": item["f14"]})

        total = data_body.get("total", 0)
        if len(all_stocks) >= total:
            break
        page += 1

    return all_stocks
