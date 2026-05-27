"""
HTTP 请求工具 —— 统一 Session + 自动重试 + 随机 CDN 节点
"""

import time
import random

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148"
)

_CDN_NODES = [80, 82, 83, 84, 85, 86, 87, 88, 89, 90]


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
    session.headers.update({"User-Agent": _UA})
    return session


_session = _create_session()


def get(url: str, params: dict = None, timeout: float = 15, **kwargs) -> requests.Response:
    """发起 GET 请求，自带重试策略"""
    return _session.get(url, params=params, timeout=timeout, **kwargs)


def get_push2_clist(params: dict, timeout: float = 15) -> dict:
    """
    获取东方财富 push2 clist 数据，自动轮换 CDN 节点。
    如果当前节点被限流则尝试下一个。
    """
    nodes = random.sample(_CDN_NODES, len(_CDN_NODES))

    for node in nodes:
        url = f"https://{node}.push2.eastmoney.com/api/qt/clist/get"
        try:
            resp = _session.get(url, params=params, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
            if data.get("data"):
                return data
        except (requests.ConnectionError, requests.Timeout):
            time.sleep(0.5)
            continue
        except Exception:
            continue

    raise requests.ConnectionError("所有 push2 CDN 节点不可用，请稍后重试")
