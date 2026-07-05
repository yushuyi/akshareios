"""证券代码市场前缀转换（腾讯 / 新浪通用 sh、sz、bj）。"""

# 上证系列指数（6 位代码）
_SH_INDEX_PREFIXES = ("000", "001")


def to_market_symbol(symbol: str, *, is_index: bool = False) -> str:
    """
    6 位数字代码 → 带市场前缀，如 600519 → sh600519，399001 → sz399001。
    已带前缀则原样返回。
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


def is_index_code(symbol: str) -> bool:
    code = symbol.removeprefix("sh").removeprefix("sz").removeprefix("bj")
    if code.startswith("399"):
        return True
    if code.startswith(_SH_INDEX_PREFIXES):
        return True
    return False
