"""Giữ Tool 4–5 ở chế độ an toàn khi đăng ký cho LLM host."""

import pytest

from mcp_server.tools import benchmark, explain


@pytest.mark.asyncio
async def test_explain_llm_facade_forces_estimate_and_visible_indexes(monkeypatch):
    calls = []

    async def fake_explain(sql, **kwargs):
        calls.append((sql, kwargs))
        return "ok"

    monkeypatch.setattr(explain, "explain_query", fake_explain)
    assert await explain.explain_for_llm("SELECT 1") == "ok"
    assert calls == [("SELECT 1", {"mode": "estimate", "use_invisible_indexes": False})]


@pytest.mark.asyncio
async def test_benchmark_llm_facade_bounds_work_and_disables_hash(monkeypatch):
    calls = []

    async def fake_benchmark(sql, **kwargs):
        calls.append((sql, kwargs))
        return "ok"

    monkeypatch.setattr(benchmark, "benchmark_query", fake_benchmark)
    assert await benchmark.benchmark_for_llm("SELECT 1") == "ok"
    assert calls == [("SELECT 1", {
        "warmup_runs": 1,
        "measured_runs": 5,
        "timeout_ms": 5000,
        "use_invisible_indexes": False,
        "compute_result_hash": False,
    })]
