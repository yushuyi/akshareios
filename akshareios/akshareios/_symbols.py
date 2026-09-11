"""证券代码市场前缀转换（腾讯 / 新浪通用 sh、sz、bj）。"""


def to_market_symbol(symbol: str, *, is_index: bool = False) -> str:
    """
    6 位数字代码 → 带市场前缀，如 600519 → sh600519，399001 → sz399001。
    已带前缀则原样返回。
    股票/指数身份由调用方显式传入 is_index，不做前缀猜测
    （000001 同时是平安银行与上证指数，猜不得）。
    """
    if symbol.startswith(("sh", "sz", "bj")):
        return symbol

    code = symbol.zfill(6)
    if is_index:
        # 399 深指；899050 北证 50 与 920 北交所段归 bj，其余默认上证
        if code.startswith(("399",)):
            return f"sz{code}"
        if code.startswith(("899", "920")):
            return f"bj{code}"
        return f"sh{code}"

    # 与 _datacenter.to_secucode 的市场归属保持一致：
    # 920 北交所新代码段须先于 9（900 沪 B）判断
    if code.startswith(("4", "8", "920")):
        return f"bj{code}"
    if code.startswith(("5", "6", "9")):
        return f"sh{code}"
    return f"sz{code}"
