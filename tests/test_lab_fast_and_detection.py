"""
tests/test_lab_fast_and_detection.py
------------------------------------

CHỨC NĂNG : Kiểm thử đơn vị cho chế độ thử siêu nhanh (fast 1 lượt) trong
            scripts/lab_demo_runner.py và bộ lọc db=shopdb trong dashboard/detection.py.
PHỤ TRÁCH  : Tình · Vũ    |    REVIEW: Hải
"""

import json
from contextlib import contextmanager
from pathlib import Path

from dashboard.detection import group_tool1_rows, read_slow_log_table
from dashboard.lab_jobs import MODES
from scripts.lab_demo_runner import _default_fast_measure, run_measure


def test_group_tool1_rows_merges_duplicate_fingerprints():
    rows = [
        {"sql_text": "SELECT * FROM orders WHERE id = 1", "exec_count": 1, "avg_latency_ms": 100.0},
        {"sql_text": "SELECT * FROM orders WHERE id = 2", "exec_count": 1, "avg_latency_ms": 300.0},
        {"sql_text": "SELECT * FROM products WHERE id = 5", "exec_count": 1, "avg_latency_ms": 250.0},
    ]
    grouped = group_tool1_rows(rows, top_n=10)
    assert len(grouped) == 2
    assert grouped[0]["exec_count"] == 2
    assert grouped[0]["avg_latency_ms"] == 200.0
    assert grouped[1]["exec_count"] == 1


def test_lab_jobs_includes_fast_mode():
    assert "fast" in MODES
    assert "quick" in MODES
    assert "full" in MODES


def test_read_slow_log_table_filters_current_db_and_select(monkeypatch):
    captured = {}

    class _FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, sql, params):
            captured["sql"] = sql
            captured["params"] = params

        def fetchall(self):
            return [{"sql_text": "SELECT 1"}]

    @contextmanager
    def _fake_conn():
        class _Conn:
            def cursor(self):
                return _FakeCursor()
        yield _Conn()

    monkeypatch.setattr("mcp_server.utils.db.get_conn", _fake_conn)
    monkeypatch.setattr("mcp_server.utils.config.Config.DB_NAME", "shopdb")

    rows = read_slow_log_table(limit=25)
    assert rows == [{"sql_text": "SELECT 1"}]
    assert "WHERE db = %s" in captured["sql"]
    assert "LIKE 'SELECT%%'" in captured["sql"]
    assert captured["params"] == ("shopdb", 25)


def test_default_fast_measure_runs_once_each_side_and_cleans_up():
    events = []

    class _FakeTrial:
        def __init__(self, proposal):
            self.name = proposal["index_name"]

        def create(self, fk_snapshot=None):
            events.append(("create", self.name))

        def drop(self):
            events.append(("drop", self.name))

    async def _fake_explain(sql, mode="estimate", use_invisible_indexes=False):
        return json.dumps({
            "ok": True,
            "data": {"query_cost": 100.0 if not use_invisible_indexes else 20.0, "raw_plan": {}},
        })

    def _fake_once(sql, *, use_invisible_indexes, timeout_ms=60000):
        events.append(("run", use_invisible_indexes))
        return {
            "p95_ms": 1000.0 if not use_invisible_indexes else 200.0,
            "p50_ms": 1000.0 if not use_invisible_indexes else 200.0,
            "rows_examined": 500000 if not use_invisible_indexes else 1000,
            "row_count": 1,
            "result_hash": "sha256:abc",
            "timed_out_runs": 0,
        }

    stages = []
    report = _default_fast_measure(
        query_id="q01",
        original_sql="SELECT 1",
        rewritten_sql="SELECT 1",
        indexes=[{"table": "orders", "index_name": "idx_test", "columns": [{"name": "status"}]}],
        trial_factory=_FakeTrial,
        explain=_fake_explain,
        run_once=_fake_once,
        progress=stages.append,
    )

    assert report["status"] == "passed"
    assert report["mode"] == "fast"
    assert report["measured_runs"] == 1
    assert events == [("create", "idx_test"), ("run", False), ("run", True), ("drop", "idx_test")]
    assert any("SQL gốc" in s for s in stages)
    assert any("xóa index" in s for s in stages)


def test_run_measure_accepts_fast_mode(tmp_path: Path):
    def _fake_greedy(_sql, _qid):
        return {
            "proposals": [{"table": "orders", "index_name": "idx_g", "columns": [{"name": "status"}]}],
            "baseline_cost": 500.0,
            "final_cost": 100.0,
            "cost_reduction_pct": 80.0,
        }

    def _fake_measure(**kwargs):
        assert "progress" in kwargs
        return {
            "status": "passed",
            "failure_reason": None,
            "before": {"p95_ms": 1000.0, "rows_examined": 1000, "row_count": 1, "result_hash": "sha256:1"},
            "after": {"p95_ms": 200.0, "rows_examined": 100, "row_count": 1, "result_hash": "sha256:1"},
            "index_usage": {"idx_g": True},
            "mode": "fast",
            "measured_runs": 1,
        }

    result = run_measure(
        {"query_id": "q02", "sql": "SELECT 1", "source": "greedy", "mode": "fast"},
        store_path=tmp_path / "proposals.sqlite3",
        preflight=lambda _indexes: {},
        greedy_runner=_fake_greedy,
        measure=_fake_measure,
    )
    assert result["status"] == "passed"
    assert result["official"] is False
    assert result["approvable"] is False
    assert result["mode"] == "fast"
    assert result["measured_runs"] == 1
