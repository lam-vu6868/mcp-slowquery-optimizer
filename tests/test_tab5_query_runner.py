"""Unit tests và AppTest cho hành trình 6 trang mới (query_runner, journey, detection, lab_demo_runner)."""

from contextlib import contextmanager
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from dashboard.detection import detection_comparison, slow_log_rows_to_text
from dashboard.journey import (
    build_live_comparison,
    record_original_run,
    record_proposals,
    select_query,
)
from dashboard.query_runner import run_query_once
from mcp_server.store.proposals import ProposalStore
from scripts.lab_demo_runner import run_measure


def test_tab1_and_tab3_render_without_error():
    root = Path(__file__).resolve().parents[1] / "dashboard" / "pages"
    for name in ("1_chon_query_cham.py", "3_chay_thu_de_xuat.py"):
        at = AppTest.from_file(root / name)
        at.run(timeout=15)
        assert not at.exception


def test_run_query_once_with_fake_db_connection():
    class FakeCursor:
        def __init__(self):
            self._batches = [[{"category": "Sach", "revenue": 100}], []]
            self._idx = 0

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, sql):
            self.last_sql = sql

        def fetchall(self):
            return [{"Variable_name": "Handler_read_rnd_next", "Value": "123"}]

        def fetchmany(self, _size):
            if self._idx >= len(self._batches):
                return []
            b = self._batches[self._idx]
            self._idx += 1
            return b

    class FakeConn:
        def cursor(self, *_args):
            return FakeCursor()

    @contextmanager
    def fake_conn():
        yield FakeConn()

    result = run_query_once("SELECT 1", conn_factory=fake_conn)
    assert result["row_count"] == 1
    assert result["latency_ms"] >= 0
    assert result["preview"] == [{"category": "Sach", "revenue": "100"}]

    with pytest.raises(ValueError, match="AST whitelist"):
        run_query_once("DELETE FROM orders", conn_factory=fake_conn)


def test_journey_and_live_comparison_only_shows_ran_steps():
    state = {}
    j = select_query(state, "q07", "SELECT 1", "catalog")
    record_original_run(state, {
        "latency_ms": 1200.0, "row_count": 5, "rows_examined": 10000,
        "exceeded_slow_threshold": True,
    })
    record_proposals(state, ["p1"])
    rows = build_live_comparison(j, {"llm": None, "greedy": None})
    assert rows[0]["P95 trước (ms)"] == 1200.0
    assert rows[1]["Phương án"] == "chưa chạy"
    assert rows[2]["Phương án"] == "chưa chạy"


def test_detection_export_and_compare():
    text = slow_log_rows_to_text([
        {"query_time": 1.5, "lock_time": 0.0, "rows_sent": 2, "rows_examined": 1000,
         "sql_text": b"SELECT * FROM orders WHERE status='paid'"},
    ])
    assert "# Query_time: 1.500000" in text
    cmp = detection_comparison(
        [{"sql_text": "SELECT * FROM orders WHERE status='shipped'", "exec_count": 1, "avg_latency_ms": 1500}],
        {"engine": "python_slow_log_fallback", "duration_ms": 2.0,
         "top_queries": [{"fingerprint_id": "x", "count": 1, "avg_latency_ms": 1500, "sample_sql": "SELECT 1"}]},
        tool1_ms=5.0,
    )
    assert "summary" in cmp and len(cmp["tool1"]) == 1


def test_lab_demo_runner_quick_mode_with_mocks(tmp_path):
    store_path = tmp_path / "p.sqlite3"
    store = ProposalStore(store_path)
    pid = store.add("q07", "SELECT order_id FROM orders", {
        "type": "index", "table": "orders", "index_name": "idx_orders_status",
        "columns": [{"name": "status", "order": "ASC"}],
    })

    def fake_measure(**kwargs):
        assert kwargs["warmup_runs"] == 1 and kwargs["measured_runs"] == 5
        return {
            "status": "passed", "failure_reason": None, "mode": "quick", "measured_runs": 5,
            "before": {"p95_ms": 1000.0, "result_hash": "h", "row_count": 1, "rows_examined": 100},
            "after": {"p95_ms": 200.0, "result_hash": "h", "row_count": 1, "rows_examined": 10},
            "index_usage": {"idx_orders_status": True},
        }

    out = run_measure(
        {"query_id": "q07", "sql": "SELECT order_id FROM orders", "source": "llm",
         "mode": "quick", "proposal_ids": [pid]},
        store_path=store_path, preflight=lambda _idx: {}, measure=fake_measure,
    )
    assert out["status"] == "passed"
    assert out["official"] is False
    assert out["approvable"] is False
