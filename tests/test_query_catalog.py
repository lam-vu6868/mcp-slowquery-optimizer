"""Kiểm tra bộ query nhiều bảng và tránh dùng nhầm số đo của sales_data cũ."""
import json
from pathlib import Path

import pytest
import sqlglot
from sqlglot import exp

from data.queries.queries import QUERIES
from scripts import measure_p95_baseline, test_queries
from security.ast_whitelist import check

TABLES = {"customers", "addresses", "products", "orders", "order_items"}


def test_catalog_only_reads_current_tables():
    assert len(QUERIES) == 30
    assert len({q["id"] for q in QUERIES}) == 30
    assert len({q["sql"] for q in QUERIES}) == 30
    used_tables = set()
    for query in QUERIES:
        assert check(query["sql"])[0]
        tree = sqlglot.parse_one(query["sql"], dialect="mysql")
        assert isinstance(tree, exp.Select)
        names = {t.name for t in tree.find_all(exp.Table)}
        assert names <= TABLES
        used_tables.update(names)
    assert used_tables == TABLES
    assert all(sum(q["group"] == g for q in QUERIES) == 6 for g in range(1, 6))


def test_ground_truth_does_not_keep_answers_for_deleted_table():
    path = Path(__file__).resolve().parents[1] / "data/queries/ground_truth.json"
    truth = json.loads(path.read_text(encoding="utf-8"))
    assert truth["dataset"] == "shopdb.multitable-v1"
    assert set(truth["queries"]) == {q["id"] for q in QUERIES}
    for entry in truth["queries"].values():
        for answer in entry["acceptable_answers"]:
            if answer["type"] == "index":
                assert answer["table"] in TABLES


def test_baseline_uses_separate_results_for_new_dataset(tmp_path):
    assert measure_p95_baseline.DEFAULT_OUTPUT.name == "p95_baseline_multitable_raw.json"
    payload = measure_p95_baseline.load_output(tmp_path / "new.json")
    assert payload["meta"]["dataset"] == "shopdb.multitable-v1"


@pytest.mark.parametrize("sql", ["DROP TABLE orders", "CREATE INDEX idx_test ON orders(status)"])
def test_screening_rejects_unsafe_sql_before_database_access(sql):
    class NoDatabase:
        def cursor(self, *args):
            pytest.fail("Unsafe SQL must not reach database")

    with pytest.raises((ValueError, TypeError), match="AST"):
        test_queries.run_query_once(NoDatabase(), sql)


def test_screening_does_not_hide_warmup_failure(monkeypatch):
    calls = 0

    def fail(conn, sql):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("warmup timeout")
        return 600, 100, 1

    monkeypatch.setattr(test_queries, "run_query_once", fail)
    result = test_queries.test_query(None, QUERIES[0])
    assert result["status"].endswith("ERROR")
    assert result["avg_ms"] is None


def test_screening_requires_every_measured_run_to_be_slow(monkeypatch):
    durations = iter([600, 400, 600, 600])
    monkeypatch.setattr(test_queries, "WARMUP_RUNS", 1)
    monkeypatch.setattr(test_queries, "MEASURE_RUNS", 3)
    monkeypatch.setattr(test_queries, "run_query_once", lambda conn, sql: (next(durations), 100, 1))
    result = test_queries.test_query(None, QUERIES[0])
    assert result["status"].endswith("FAST")
