"""Kiểm tra cổng chấp nhận đáp án và rewrite với dữ liệu NULL/trùng dòng."""
import json
import sqlite3

import pytest
import sqlglot
from sqlglot import exp

from data.queries.ground_truth_candidates import CANDIDATES
from data.queries.queries import get_query_by_id
from scripts import verify_ground_truth as verifier
from scripts.verify_ground_truth import (
    answer_for,
    create_sql,
    definitions,
    evaluate,
    identifier,
    optimized_sql,
    validation_settings,
)
from security.ast_whitelist import check


def measurement(**changes):
    return {"status": "valid", "runs": 20, "timed_out_runs": 0, "result_hash": "sha256:example",
            "row_count": 1, "p95_ms": 1000} | changes


@pytest.mark.parametrize("after,expected", [
    (measurement(p95_ms=800), (True, "passed")),
    (measurement(p95_ms=801), (False, "insufficient_improvement")),
    (measurement(p95_ms=100, result_hash="different"), (False, "result_mismatch")),
    (measurement(p95_ms=100, row_count=2), (False, "result_mismatch")),
    (measurement(p95_ms=100, runs=19), (False, "incomplete_measurement")),
    (measurement(p95_ms=100, timed_out_runs=1), (False, "incomplete_measurement")),
])
def test_only_complete_equivalent_measurements_can_pass(after, expected):
    assert evaluate(measurement(), after) == expected


@pytest.mark.parametrize("after,expected", [
    (measurement(p95_ms=100), False),
    (measurement(p95_ms=800), True),
    (measurement(p95_ms=1100), True),
    (measurement(p95_ms=800, result_hash="different"), False),
    (measurement(p95_ms=800, runs=19), False),
])
def test_weak_or_uncertain_gain_gets_a_fresh_baseline(after, expected):
    assert verifier.needs_fresh_baseline(measurement(), after, 20) is expected


def test_all_candidates_and_index_definitions_pass_ast():
    assert set(CANDIDATES) == {f"q{n:02}" for n in range(2, 31)}
    for qid, candidate in CANDIDATES.items():
        assert check(candidate.get("rewritten_sql", get_query_by_id(qid)["sql"]))[0]
        for wrong in ([False, True] if "wrong_indexes" in candidate else [False]):
            for spec in definitions(qid, candidate, wrong):
                ddl = create_sql(spec)
                assert check(ddl.removesuffix(" INVISIBLE"))[0], ddl
                assert ddl.endswith(" INVISIBLE")
        if "wrong_indexes" in candidate:
            good, bad = candidate["indexes"], candidate["wrong_indexes"]
            assert [t for t, _ in good] == [t for t, _ in bad]
            assert all(sorted(g[1]) == sorted(b[1]) for g, b in zip(good, bad, strict=True))
            assert any(g[1] != b[1] for g, b in zip(good, bad, strict=True))


def test_order_comparison_changes_only_trial_index_names():
    a = "SELECT i.quantity FROM order_items i FORCE INDEX(gt_trial_q09_good_0) WHERE i.quantity=4"
    b = a.replace("good_0", "bad_0")
    assert verifier.same_counterfactual_sql(a, b)
    assert not verifier.same_counterfactual_sql(a, b.replace("quantity=4", "quantity=3"))


def test_identifier_rejects_sql_injection():
    with pytest.raises(ValueError):
        identifier("orders; DROP TABLE customers")


def test_validation_settings_reads_p95_key_and_comments(tmp_path):
    config = tmp_path / "settings.yaml"
    config.write_text("validation:\n  warmup_runs: 3\n  measured_runs: 20\n  min_p95_improvement_pct: 20 # threshold\napproval:\n  measured_runs: 1\n", encoding="utf-8")
    assert validation_settings(config) == {"warmup_runs": 3, "measured_runs": 20, "min_p95_improvement_pct": 20}


def test_hint_is_recorded_as_required_sql_not_index_alone():
    query = get_query_by_id("q02")
    candidate = dict(CANDIDATES["q02"], force_indexes=True)
    specs = definitions("q02", candidate)
    sql = optimized_sql(query, candidate, specs)
    assert check(sql)[0]
    assert "FORCE INDEX (gt_trial_q02_good_0)" in sql
    candidate["rewritten_sql"] = sql
    answer = answer_for(candidate, specs, "index")
    assert answer["requires_rewrite"] is True
    assert answer["rewritten_sql"] == sql


def test_sorted_table_can_be_kept_as_join_driver():
    query = get_query_by_id("q19")
    candidate = dict(CANDIDATES["q19"], force_indexes=True, straight_join=True)
    sql = optimized_sql(query, candidate, definitions("q19", candidate))
    assert "STRAIGHT_JOIN" in sql
    assert check(sql)[0]


@pytest.mark.parametrize("qid", [qid for qid, c in CANDIDATES.items() if c.get("force_indexes")])
def test_index_hint_generation_preserves_the_rest_of_the_sql(qid):
    query, candidate = get_query_by_id(qid), CANDIDATES[qid]
    original = sqlglot.parse_one(candidate.get("rewritten_sql", query["sql"]), dialect="mysql")
    hinted = sqlglot.parse_one(optimized_sql(query, candidate, definitions(qid, candidate)), dialect="mysql")
    for table in hinted.find_all(exp.Table):
        table.set("hints", None)
    for join in hinted.find_all(exp.Join):
        if join.args.get("kind") == "STRAIGHT_JOIN":
            join.set("kind", None)
    assert original.sql(dialect="mysql") == hinted.sql(dialect="mysql")


@pytest.mark.parametrize("tamper", [None, "sql", "hash", "gain", "index"])
def test_offline_audit_rejects_evidence_that_does_not_match_answer(tmp_path, monkeypatch, tamper):
    before = measurement(sql="SELECT 1")
    after = measurement(sql="SELECT 1", p95_ms=100, use_invisible_indexes=True)
    stored = {
        "before_result_file": "before.json", "after_result_file": "after.json",
        "before_p95_ms": 1000, "after_p95_ms": 100, "improvement_pct": 90,
        "before_result_hash": before["result_hash"], "after_result_hash": after["result_hash"],
        "before_row_count": 1, "after_row_count": 1,
    }
    if tamper == "sql":
        after["sql"] = "SELECT 2"
    if tamper == "hash":
        stored["after_result_hash"] = "not-the-measured-hash"
    if tamper == "gain":
        stored["improvement_pct"] = 99
    for name, value in (("before.json", before), ("after.json", after)):
        (tmp_path / name).write_text(json.dumps(value), encoding="utf-8")
    answer = {"type": "index", "table": "order_items", "index_name": "idx_gt_q01_cover",
              "columns": ["product_id", "quantity", "unit_price"]}
    if tamper == "index":
        answer["columns"] = ["order_id"]
    truth = {"queries": {"q01": {"measurement": stored, "acceptable_answers": [answer]}}}
    truth_path = tmp_path / "ground_truth.json"
    truth_path.write_text(json.dumps(truth), encoding="utf-8")
    monkeypatch.setattr(verifier, "ROOT", tmp_path)
    monkeypatch.setattr(verifier, "TRUTH", truth_path)
    monkeypatch.setattr(verifier, "QUERIES", [{"id": "q01", "sql": "SELECT 1"}])
    assert verifier.audit() == (0 if tamper is None else 1)


@pytest.mark.parametrize("qid", ["q04", "q08", "q12", "q17", "q24", "q25", "q26", "q27", "q28", "q29"])
def test_rewrites_preserve_duplicates_and_null_semantics(qid):
    with sqlite3.connect(":memory:") as conn:
        conn.executescript("""
            CREATE TABLE customers(customer_id INTEGER PRIMARY KEY);
            CREATE TABLE addresses(address_id INTEGER PRIMARY KEY, customer_id INTEGER, city TEXT);
            CREATE TABLE products(product_id INTEGER PRIMARY KEY, category TEXT, price INTEGER);
            CREATE TABLE orders(order_id INTEGER PRIMARY KEY, customer_id INTEGER,
                                order_date TEXT, total_amount INTEGER, status TEXT);
            CREATE TABLE order_items(order_item_id INTEGER PRIMARY KEY, order_id INTEGER,
                                     product_id INTEGER, quantity INTEGER, unit_price INTEGER);
            INSERT INTO customers VALUES (1),(2),(3);
            INSERT INTO addresses VALUES (1,1,'Ha Noi'),(2,1,'Ha Noi'),(3,2,'Da Nang'),(4,NULL,'Ha Noi');
            INSERT INTO products VALUES (1,'Dien tu',6000),(2,'The thao',7000),(3,NULL,100),(4,'Sach',5000);
            INSERT INTO orders VALUES
                (1,1,'2024-01-01',100,'paid'),(2,1,'2024-01-01',150300,'completed'),
                (3,2,'2024-01-01',200000,NULL),(4,3,'2024-01-01',100,'cancelled'),
                (5,NULL,'2024-01-01',500,'paid'),(6,2,'2024-06-01',5000,'shipped');
            INSERT INTO order_items VALUES
                (1,1,1,1,6000),(2,1,1,2,7000),(3,1,2,4,8000),
                (4,2,2,2,9000),(5,2,1,1,4000),(6,3,NULL,4,6000),
                (7,NULL,1,4,7000),(8,5,2,1,6000),(9,1,4,2,7000),
                (10,1,4,3,7000),(11,2,4,1,7000),(12,1,2,4,8000),
                (13,3,2,2,6000),(14,3,2,1,7000),(15,6,1,2,5000),(16,6,2,3,6000);
        """)
        original = conn.execute(get_query_by_id(qid)["sql"]).fetchall()
        rewritten = conn.execute(CANDIDATES[qid]["rewritten_sql"]).fetchall()
        if qid == "q24":
            assert original == rewritten
        else:
            assert sorted(original, key=repr) == sorted(rewritten, key=repr)


@pytest.mark.parametrize("mismatch", [False, True])
def test_q30_mysql_fixture_checks_actual_rewrite_and_rejects_mismatch(mismatch):
    class Cursor:
        def __init__(self):
            self.statements = []

        def execute(self, sql):
            self.statements.append(sql)
            assert check(sql)[0]

        def fetchall(self):
            if mismatch and len(self.statements) == 2:
                return [{"status": "paid", "n": 2}]
            return [{"status": "paid", "n": 1}, {"status": None, "n": 1}]

    cursor = Cursor()
    sql = CANDIDATES["q30"]["rewritten_sql"]
    if mismatch:
        with pytest.raises(ValueError, match="fixture mismatch"):
            verifier.q30_edge_check(cursor, sql)
    else:
        assert verifier.q30_edge_check(cursor, sql)["passed"]
    assert cursor.statements[1].endswith(sql)
    assert "LATERAL" in cursor.statements[1]
