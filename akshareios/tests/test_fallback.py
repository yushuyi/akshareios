#!/usr/bin/env python3
"""call_with_fallback 降级与重试单元测试（无需联网）"""

import pytest

from akshareios._fallback import call_with_fallback


def test_primary_succeeds_first_try() -> None:
    calls = []

    def primary():
        calls.append("p")
        return "ok"

    def fallback():
        calls.append("f")
        return "fallback"

    assert call_with_fallback(primary, fallback) == "ok"
    assert calls == ["p"]


def test_primary_fails_then_succeeds_on_retry() -> None:
    """主源首次异常，重试一次成功，返回第二次结果，不走降级。"""
    calls = []

    def primary():
        calls.append("p")
        if len(calls) == 1:
            raise ConnectionError("RemoteDisconnected")
        return "ok"

    def fallback():
        calls.append("f")
        return "fallback"

    assert call_with_fallback(primary, fallback) == "ok"
    assert calls == ["p", "p"]


def test_primary_always_fails_uses_fallback() -> None:
    """主源两次均异常，落备用源。"""
    calls = []

    def primary():
        calls.append("p")
        raise ConnectionError("RemoteDisconnected")

    def fallback():
        calls.append("f")
        return "fallback"

    assert call_with_fallback(primary, fallback) == "fallback"
    assert calls == ["p", "p", "f"]


def test_primary_retries_zero_calls_once() -> None:
    """primary_retries=0 时主源只尝试一次。"""
    calls = []

    def primary():
        calls.append("p")
        raise ConnectionError("boom")

    def fallback():
        calls.append("f")
        return "fallback"

    assert call_with_fallback(primary, fallback, primary_retries=0) == "fallback"
    assert calls == ["p", "f"]


def test_negative_retries_treated_as_zero() -> None:
    calls = []

    def primary():
        calls.append("p")
        raise ConnectionError("boom")

    def fallback():
        calls.append("f")
        return "fallback"

    assert call_with_fallback(primary, fallback, primary_retries=-3) == "fallback"
    assert calls == ["p", "f"]


def test_empty_result_breaks_to_fallback() -> None:
    """retry_on_empty=True 时空结果不重试，直接降级。"""
    calls = []

    def primary():
        calls.append("p")
        return []

    def fallback():
        calls.append("f")
        return ["fb"]

    assert call_with_fallback(primary, fallback, retry_on_empty=True) == ["fb"]
    assert calls == ["p", "f"]


def test_fallback_failure_chains_primary_cause() -> None:
    """备用源也失败时，主源根因通过 raise from 保留。"""
    def primary():
        raise ConnectionError("主源根因")

    def fallback():
        raise ValueError("备用源失败")

    with pytest.raises(ValueError) as excinfo:
        call_with_fallback(primary, fallback)
    assert isinstance(excinfo.value.__cause__, ConnectionError)


def test_provenance_marks_dict_but_not_list() -> None:
    """传 provenance 时 dict 带 _meta；list 必须保持原结构，避免破坏调用契约。"""
    from akshareios._provenance import Provenance

    p = Provenance(
        primary_source="东财", fallback_source="新浪",
        freshness="盘中实时", fallback_note="字段较少",
        missing_fields=("市盈率",),
    )

    def boom():
        raise ConnectionError("主源不可用")

    r = call_with_fallback(lambda: {"items": [{"a": 1}]}, boom, provenance=p)
    assert r["_meta"]["状态"] == "主源"
    assert r["_meta"]["数据源"] == "东财"
    assert r["_meta"]["数据时间"] == "盘中实时"
    assert r["items"] == [{"a": 1}]

    r = call_with_fallback(boom, lambda: {"b": 2}, provenance=p)
    assert r["_meta"]["状态"] == "降级"
    assert r["_meta"]["数据源"] == "新浪"
    assert r["_meta"]["口径说明"] == "字段较少"
    assert r["_meta"]["缺失字段"] == ["市盈率"]

    assert call_with_fallback(boom, lambda: [{"x": 1}], provenance=p) == [{"x": 1}]


def test_no_provenance_keeps_legacy_behavior() -> None:
    """不传 provenance 时返回值与旧版逐字节一致。"""
    def boom():
        raise ConnectionError("主源不可用")

    r = call_with_fallback(boom, lambda: {"b": 2})
    assert r == {"b": 2}


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-q"]))
