"""Tách số đo index thử khỏi baseline và cố định chế độ optimizer của mỗi session."""
import argparse
import json
from contextlib import contextmanager

import pytest

from mcp_server.tools import benchmark, explain
from scripts import measure_p95_baseline as measurement


def arguments(path, invisible=True):
    return argparse.Namespace(output=str(path), group=None, ids=["q01"], force=False,
                              use_invisible_indexes=invisible)


@pytest.mark.asyncio
async def test_invisible_measurement_cannot_overwrite_baseline(tmp_path, monkeypatch):
    baseline = tmp_path / "baseline.json"
    monkeypatch.setattr(measurement, "DEFAULT_OUTPUT", baseline)

    async def no_measurement(*args, **kwargs):
        pytest.fail("Must reject output path before measurement")

    monkeypatch.setattr(measurement, "benchmark_query", no_measurement)
    with pytest.raises(ValueError, match="baseline"):
        await measurement.run(arguments(baseline))
    assert not baseline.exists()


@pytest.mark.asyncio
async def test_invisible_measurement_forwards_mode_and_saves_it(tmp_path, monkeypatch):
    calls = []

    async def fake_benchmark(sql, **kwargs):
        calls.append(kwargs)
        return json.dumps({"ok": True, "data": {
            "runs": 20, "timed_out_runs": 0, "result_hash": "sha256:test",
            "p50_ms": 10, "p95_ms": 12, "row_count": 1, "rows_examined": 100,
        }})

    monkeypatch.setattr(measurement, "benchmark_query", fake_benchmark)
    output = tmp_path / "after.json"
    assert await measurement.run(arguments(output)) == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert calls[0]["use_invisible_indexes"] is True
    assert payload["meta"]["use_invisible_indexes"] is True
    assert payload["results"]["q01"]["use_invisible_indexes"] is True


@pytest.mark.asyncio
async def test_existing_result_file_cannot_change_optimizer_mode(tmp_path, monkeypatch):
    output = tmp_path / "before.json"
    original = json.dumps({"meta": {"use_invisible_indexes": False}, "results": {"q01": {}}})
    output.write_text(original, encoding="utf-8")

    async def no_measurement(*args, **kwargs):
        pytest.fail("Must reject mixed modes before measurement")

    monkeypatch.setattr(measurement, "benchmark_query", no_measurement)
    with pytest.raises(ValueError, match="mode"):
        await measurement.run(arguments(output))
    assert output.read_text(encoding="utf-8") == original


@pytest.mark.asyncio
@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("tool", ["benchmark", "explain"])
async def test_each_tool_explicitly_sets_invisible_index_mode(monkeypatch, enabled, tool):
    commands = []

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, sql):
            commands.append(sql)

        def fetchone(self):
            return {"EXPLAIN": '{"query_block":{"cost_info":{"query_cost":"1"}}}'}

    class Connection:
        def cursor(self):
            return Cursor()

    @contextmanager
    def fake_connection():
        yield Connection()

    if tool == "benchmark":
        monkeypatch.setattr(benchmark, "get_conn", fake_connection)
        monkeypatch.setattr(benchmark, "_run_streamed_once", lambda *args: (1, 1, 1))
        result = await benchmark.benchmark_query("SELECT 1", warmup_runs=0, measured_runs=5,
                                                 use_invisible_indexes=enabled,
                                                 compute_result_hash=False)
    else:
        monkeypatch.setattr(explain, "get_conn", fake_connection)
        result = await explain.explain_query("SELECT 1", use_invisible_indexes=enabled)
    assert json.loads(result)["ok"] is True
    switch = "on" if enabled else "off"
    assert f"SET SESSION optimizer_switch = 'use_invisible_indexes={switch}'" in commands


@pytest.mark.asyncio
async def test_partial_timeout_cannot_return_successful_benchmark(monkeypatch):
    attempts = 0

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def execute(self, _sql):
            pass

    class Conn:
        def cursor(self):
            return Cursor()

    @contextmanager
    def fake_connection():
        yield Conn()

    def run_once(*_):
        nonlocal attempts
        attempts += 1
        if attempts == 2:
            raise RuntimeError("maximum statement execution time exceeded")
        return 1.0, 10, 1

    monkeypatch.setattr(benchmark, "get_conn", fake_connection)
    monkeypatch.setattr(benchmark, "_run_streamed_once", run_once)
    result = json.loads(await benchmark.benchmark_query(
        "SELECT 1", warmup_runs=0, measured_runs=5, compute_result_hash=False,
    ))
    assert attempts == 5
    assert result["ok"] is False
    assert result["error"]["code"] == "MEASUREMENT_INVALID"
    assert result["data"] is None


@pytest.mark.asyncio
async def test_missing_required_hash_invalidates_benchmark(monkeypatch):
    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def execute(self, _sql):
            pass

    class Conn:
        def cursor(self):
            return Cursor()

    @contextmanager
    def fake_connection():
        yield Conn()

    monkeypatch.setattr(benchmark, "get_conn", fake_connection)
    monkeypatch.setattr(benchmark, "_run_streamed_once", lambda *_: (1.0, 10, 1))
    monkeypatch.setattr(benchmark, "_hash_streamed_result", lambda *_: (None, 1))
    result = json.loads(await benchmark.benchmark_query(
        "SELECT 1", warmup_runs=0, measured_runs=5,
    ))
    assert result["ok"] is False
    assert result["error"]["code"] == "MEASUREMENT_INVALID"
