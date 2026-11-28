"""Unit tests cho data/baseline/rule_based.py (luật cứng E-R-S)."""

import json
import re
from pathlib import Path

from data.baseline.rule_based import evaluate_catalog, propose_indexes
from data.queries.queries import QUERIES

INDEX_NAME_RE = re.compile(r"^idx_[a-z0-9_]{1,50}$")


def test_equality_before_range_before_order_by():
    sql = (
        "SELECT o.customer_id, o.total_amount FROM orders o "
        "WHERE o.order_date >= '2024-01-01' AND o.status = 'paid' "
        "ORDER BY o.total_amount DESC"
    )
    proposals = propose_indexes(sql, query_id="q07")
    assert len(proposals) == 1
    p = proposals[0]
    assert p["type"] == "index"
    assert p["table"] == "orders"
    assert p["columns"] == [
        {"name": "status", "order": "ASC"},
        {"name": "order_date", "order": "ASC"},
        {"name": "total_amount", "order": "DESC"},
    ]
    assert INDEX_NAME_RE.match(p["index_name"])
    assert p["target_query_ids"] == ["q07"]


def test_between_and_in_clause_and_dedup():
    sql = (
        "SELECT i.order_item_id FROM order_items i "
        "WHERE i.unit_price BETWEEN 1000 AND 20000 AND i.quantity IN (1, 2) "
        "ORDER BY i.unit_price DESC"
    )
    proposals = propose_indexes(sql, query_id="q05")
    assert len(proposals) == 1
    assert proposals[0]["columns"] == [
        {"name": "quantity", "order": "ASC"},
        {"name": "unit_price", "order": "ASC"},
    ]


def test_ignores_non_sargable_wrapped_columns():
    """Hàm bọc cột (nhóm 3) không sinh được index theo luật cứng."""
    sql = (
        "SELECT o.order_id FROM orders o "
        "WHERE YEAR(o.order_date) = 2024 AND UPPER(o.status) = 'PAID'"
    )
    assert propose_indexes(sql, query_id="q13") == []


def test_skips_redundant_default_pk_or_fk_prefix():
    sql = "SELECT o.order_id FROM orders o WHERE o.customer_id = 42"
    assert propose_indexes(sql) == []


def test_handles_invalid_or_non_select_sql_safely():
    assert propose_indexes("") == []
    assert propose_indexes("DELETE FROM orders WHERE status = 'paid'") == []
    assert propose_indexes("SELECT FROM WHERE ???") == []


def test_max_columns_limit_and_name_length():
    sql = (
        "SELECT o.order_id FROM orders o "
        "WHERE o.status = 'paid' AND o.customer_id = 1 AND o.total_amount = 10 "
        "AND o.order_date >= '2024-01-01' "
        "ORDER BY o.order_id DESC, o.status DESC"
    )
    proposals = propose_indexes(sql, max_columns=3)
    assert len(proposals) == 1
    assert len(proposals[0]["columns"]) == 3
    assert INDEX_NAME_RE.match(proposals[0]["index_name"])


def test_evaluate_catalog_runs_all_18_index_queries():
    truth_path = Path(__file__).resolve().parents[1] / "data" / "queries" / "ground_truth.json"
    truth = json.loads(truth_path.read_text(encoding="utf-8"))
    summary = evaluate_catalog(QUERIES, truth)
    assert summary["method"] == "rule_based"
    assert summary["index_group_query_count"] == 18
    assert summary["total_index_proposals"] > 0
    for item in summary["per_query"]:
        for idx in item["proposed_indexes"]:
            assert INDEX_NAME_RE.match(idx["index_name"])
