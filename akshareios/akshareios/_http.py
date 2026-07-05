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


def _create_session() -> requests.Session:
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
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
            resp = requests.get(
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
