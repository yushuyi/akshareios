"""
HTTP 请求工具 —— 统一 Session + 自动重试 + 随机 CDN 节点
"""

import random

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148"
)

_EM_HEADERS = {
    "User-Agent": _UA,
    "Referer": "https://quote.eastmoney.com/",
}

_CDN_NODES = [80, 82, 83, 84, 85, 86, 87, 88, 89, 90]
_CLIST_MAX_FALLBACKS = 2
_PUSH2_MAX_FALLBACKS = 3


def _create_session() -> requests.Session:
    session = requests.Session()
    # 重试预算从紧：单次 get 最坏 2 attempt × timeout + backoff ≈ 32s，
    # 配合 call_with_fallback 的 primary_retries=1 与降级源仍在终端 120s 预算内；
    # 原 total=3 时最坏 66s/次，主源重试一遍即 132s 超限（2026-10 实录超时根因）
    retry_strategy = Retry(
        total=1,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(_EM_HEADERS)
    return session


_session = _create_session()

# clist 轮换用：不挂重试（轮换节点本身就是重试），仅复用连接池拿 keep-alive
_plain_session = requests.Session()


def get(url: str, params: dict = None, timeout: float = 15, **kwargs) -> requests.Response:
    """发起 GET 请求，自带重试策略"""
    return _session.get(url, params=params, timeout=timeout, **kwargs)


def get_push2_clist(params: dict, timeout: float = 15) -> dict:
    """
    获取东方财富 push2 clist 数据，自动轮换 CDN 节点。
    主域名失败后最多再试 3 个节点；单次请求不重试，避免 iOS 上长时间挂起。
    """
    per_try = min(timeout, 5)
    urls = ["https://push2.eastmoney.com/api/qt/clist/get"]
    for node in random.sample(_CDN_NODES, _CLIST_MAX_FALLBACKS):
        urls.append(f"https://{node}.push2.eastmoney.com/api/qt/clist/get")

    last_err: Exception | None = None
    for url in urls:
        try:
            resp = _plain_session.get(
                url, params=params, timeout=per_try, headers=_EM_HEADERS
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("data"):
                return data
        except (requests.ConnectionError, requests.Timeout) as exc:
            last_err = exc
            continue
        except Exception as exc:
            last_err = exc
            continue

    if last_err:
        raise requests.ConnectionError(f"push2 clist 不可用: {last_err}") from last_err
    raise requests.ConnectionError("所有 push2 CDN 节点不可用，请稍后重试")


def get_push2_json(path: str, params: dict, timeout: float = 15) -> dict:
    """
    获取东方财富 push2 接口的 JSON（clist 之外的接口，如 details/get）。

    主域名失败后最多再试 3 个 CDN 节点；单次请求不重试，避免 iOS 上长时间挂起。
    :param path: 接口路径，如 "/api/qt/stock/details/get"
    """
    per_try = min(timeout, 6)
    urls = [f"https://push2.eastmoney.com{path}"]
    for node in random.sample(_CDN_NODES, _PUSH2_MAX_FALLBACKS):
        urls.append(f"https://{node}.push2.eastmoney.com{path}")

    last_err: Exception | None = None
    for url in urls:
        try:
            resp = _plain_session.get(url, params=params, timeout=per_try, headers=_EM_HEADERS)
            resp.raise_for_status()
            data = resp.json()
            if data.get("data"):
                return data
        except (requests.ConnectionError, requests.Timeout) as exc:
            last_err = exc
            continue
        except Exception as exc:
            last_err = exc
            continue

    if last_err:
        raise requests.ConnectionError(f"push2 {path} 不可用: {last_err}") from last_err
    raise requests.ConnectionError(f"所有 push2 CDN 节点不可用: {path}")


def get_push2his_json(path: str, params: dict, timeout: float = 15) -> dict:
    """
    获取东方财富 push2his 接口的 JSON（kline/trends/fflow 等历史数据）。

    主域名失败后最多再试 3 个 CDN 节点；单次请求不重试、单节点超时上限 6s，
    避免主域瞬时变慢时干等耗尽终端 120s 预算（2026-10 分钟 K 超时根因）。
    :param path: 接口路径，如 "/api/qt/stock/kline/get"
    :return: 首个成功节点返回的完整 JSON（含 data 为空的合法响应，交由调用方解析）
    """
    per_try = min(timeout, 6)
    urls = [f"https://push2his.eastmoney.com{path}"]
    for node in random.sample(_CDN_NODES, _PUSH2_MAX_FALLBACKS):
        urls.append(f"https://{node}.push2his.eastmoney.com{path}")

    last_err: Exception | None = None
    for url in urls:
        try:
            resp = _plain_session.get(url, params=params, timeout=per_try, headers=_EM_HEADERS)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            last_err = exc
            continue

    if last_err:
        raise requests.ConnectionError(f"push2his {path} 不可用: {last_err}") from last_err
    raise requests.ConnectionError(f"所有 push2his CDN 节点不可用: {path}")
