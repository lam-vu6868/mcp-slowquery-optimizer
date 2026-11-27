"""Chấm index theo ROADMAP: khớp chính xác tách khỏi tương đương chưa đo."""

import json
import sys
from pathlib import Path

import pytest

from data.metrics import metrics
from data.metrics.metrics import score_index_query


def _truth():
    path = Path(__file__).resolve().parents[1] / "data/queries/ground_truth.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _index(table, names):
    return {"type": "index", "table": table,
            "columns": [{"name": name, "order": "ASC"} for name in names]}


def test_q07_two_exact_indexes_score_one_query_not_two():
    proposals = [
        _index("orders", ["status", "order_date", "customer_id", "total_amount"]),
        _index("addresses", ["customer_id", "city"]),
        {"type": "rewrite", "rewritten_sql": "SELECT 1"},
    ]

    score = score_index_query("q07", proposals, _truth())

    assert score["index_proposals"] == 2
    assert score["exact_matches"] == 2
    assert (score["precision_numerator"], score["precision_denominator"]) == (2, 2)
    assert (score["recall_numerator"], score["recall_denominator"]) == (1, 1)
    assert score["precision"] == 1.0
    assert score["recall"] == 1.0
    assert score["equivalence_needed"] is False
    assert score["full_answer_verified"] is False


def test_wrong_column_order_is_not_claimed_nonmatching_without_p95():
    wrong_order = _index(
        "orders", ["order_date", "status", "customer_id", "total_amount"],
    )

    score = score_index_query("q07", [wrong_order], _truth())

    assert score["exact_matches"] == 0
    assert score["precision"] is None
    assert score["recall"] is None
    assert score["equivalence_needed"] is True


def test_metrics_cli_rejects_missing_store_without_creating_it(monkeypatch, tmp_path):
    missing = tmp_path / "missing.sqlite3"
    monkeypatch.setattr(sys, "argv", [
        "metrics", "--store", str(missing), "--query-id", "q07",
    ])

    with pytest.raises(SystemExit):
        metrics.main()

    assert not missing.exists()
