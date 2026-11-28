"""Unit tests cho data/baseline/greedy.py và data/baseline/pt_query_digest.py."""

import re

import pytest

from data.baseline.greedy import extract_candidate_columns, greedy_select_indexes
from data.baseline.pt_query_digest import (
    compare_top_n,
    fingerprint_id,
    parse_slow_log_file,
    run_pt_query_digest,
)

INDEX_NAME_RE = re.compile(r"^idx_[a-z0-9_]{1,50}$")


def test_extract_candidate_columns_from_join_where_order():
    sql = (
        "SELECT a.city, SUM(o.total_amount) FROM orders o "
        "JOIN addresses a ON a.customer_id = o.customer_id "
        "WHERE o.status = 'paid' AND o.order_date >= '2024-01-01' "
        "GROUP BY a.city ORDER BY o.order_date DESC"
    )
    cols = extract_candidate_columns(sql)
    assert set(cols["orders"]) == {"status", "order_date", "customer_id"}
    assert set(cols["addresses"]) == {"city", "customer_id"}


def test_greedy_selects_best_composite_and_stops_when_below_threshold():
    sql = (
        "SELECT o.order_id FROM orders o "
        "WHERE o.status = 'paid' AND o.order_date >= '2024-01-01'"
    )
    cost_table = {
        (): 1000.0,
        (("orders", ("status",)),): 400.0,
        (("orders", ("order_date",)),): 600.0,
        (("orders", ("status", "order_date")),): 100.0,
        (("orders", ("status", "order_date", "total_amount")),): 99.0,
    }

    def fake_cost(_sql: str, proposals: list[dict]) -> float:
        key = tuple(
            (p["table"], tuple(c["name"] for c in p["columns"])) for p in proposals
        )
        return cost_table.get(key, 1000.0)

    res = greedy_select_indexes(
        sql, cost_evaluator=fake_cost, query_id="q07", max_columns=3, max_indexes=2
    )
    assert res["baseline_cost"] == 1000.0
    assert res["final_cost"] == 100.0
    assert res["cost_reduction_pct"] == 90.0
    assert len(res["proposals"]) == 1
    p = res["proposals"][0]
    assert p["table"] == "orders"
    assert [c["name"] for c in p["columns"]] == ["status", "order_date"]
    assert INDEX_NAME_RE.match(p["index_name"])


def test_greedy_returns_empty_when_no_improvement():
    sql = "SELECT o.order_id FROM orders o WHERE o.status = 'paid'"
    res = greedy_select_indexes(sql, cost_evaluator=lambda _s, _p: 500.0, query_id="q01")
    assert res["proposals"] == []
    assert res["cost_reduction_pct"] == 0.0


def test_parse_slow_log_and_compare_top_n(tmp_path):
    log_file = tmp_path / "slow.log"
    log_file.write_text(
        "# Time: 2026-11-28T00:00:01Z\n"
        "# User@Host: readonly_user[readonly_user] @ localhost []\n"
        "# Query_time: 2.500000  Lock_time: 0.000100 Rows_sent: 5  Rows_examined: 500000\n"
        "SET timestamp=1700000000;\n"
        "SELECT * FROM orders WHERE status = 'paid';\n"
        "# Query_time: 3.000000  Lock_time: 0.000100 Rows_sent: 5  Rows_examined: 600000\n"
        "SELECT * FROM orders WHERE status = 'shipped';\n"
        "# Query_time: 1.000000  Lock_time: 0.000100 Rows_sent: 2  Rows_examined: 100000\n"
        "SELECT * FROM products WHERE category = 'Sach';\n",
        encoding="utf-8",
    )

    parsed = parse_slow_log_file(log_file, limit=5)
    assert parsed["engine"] == "python_slow_log_fallback"
    assert parsed["total_unique_queries"] == 2
    assert len(parsed["top_queries"]) == 2
    assert parsed["top_queries"][0]["count"] == 2
    assert parsed["top_queries"][0]["total_latency_ms"] == 5500.0
    assert parsed["top_queries"][0]["fingerprint_id"] == fingerprint_id(
        "SELECT * FROM orders WHERE status = 'paid'"
    )

    # Fallback khi binary không tồn tại
    res = run_pt_query_digest(log_file, limit=5, binary="nonexistent_pt_binary_xyz")
    assert res["engine"] == "python_slow_log_fallback"

    # So sánh Top-N với Tool 1
    tool1_mock = [
        {"sql_text": "SELECT * FROM orders WHERE status = 'pending'"},
        {"sql_text": "SELECT * FROM addresses WHERE city = 'Ha Noi'"},
    ]
    cmp = compare_top_n(res, tool1_mock, tool1_duration_ms=12.5, top_n=5)
    assert cmp["overlap_count"] == 1
    assert cmp["pt_count"] == 2
    assert cmp["tool1_count"] == 2
    assert cmp["jaccard_similarity"] == pytest.approx(1 / 3, rel=1e-3)


def test_parse_slow_log_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        parse_slow_log_file(tmp_path / "missing.log")
