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
        if code.startswith("399"):
            return f"sz{code}"
        return f"sh{code}"

    if code.startswith("6"):
        return f"sh{code}"
    if code.startswith(("8", "4")):
        return f"bj{code}"
    return f"sz{code}"
