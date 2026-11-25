"""
tests/test_validation.py
------------------------

CHỨC NĂNG :
    Test Validation Layer: hash tương đương, rollback khi fail, ngưỡng P95.

PHỤ TRÁCH  : Hải    |    REVIEW: Vũ

THAM KHẢO  : mcp_server/validation/

TRẠNG THÁI : ĐANG LÀM — kiểm thử bước đánh giá bằng chứng bằng dữ liệu giả.
"""

import json
from contextlib import contextmanager
from copy import deepcopy

import pytest

from mcp_server.store.proposals import ProposalStore
from mcp_server.tools import apply as apply_module
from mcp_server.tools.apply import ForeignKeyIndexRisk, TrialIndex
from mcp_server.validation.rollback import recover_interrupted_trials
from mcp_server.validation.validator import (
    assess_index_report,
    validate_index,
    validate_saved_index,
)


def _report():
    return {
        "proposal_id": "p1", "query_id": "q07", "candidate_sql_kind": "original",
        "before": {
            "p95_ms": 100.0, "query_cost": 1000.0, "rows_examined": 100,
            "result_hash": "hash-a", "row_count": 10, "runs": 20, "timed_out_runs": 0,
        },
        "after": {
            "p95_ms": 80.0, "query_cost": 100.0, "rows_examined": 10,
            "result_hash": "hash-a", "row_count": 10, "runs": 20, "timed_out_runs": 0,
            "key_used": "idx_orders_status",
            "raw_plan": {"query_block": {"table": {
                "table_name": "orders", "key": "idx_orders_status",
            }}},
        },
        "write_overhead": {
            "insert_throughput_change_pct": -5.0,
            "before_rows_per_second": 10000.0,
            "after_rows_per_second": 9500.0,
            "sample_rows": 100000,
            "preload_rows": 100000,
            "index_size_bytes": 1024,
            "index_size_source": "table_index_length_delta",
            "index_size_estimated": True,
            "measurement_scope": "isolated_lab",
        },
    }


def _write_measurement():
    return {
        "insert_throughput_change_pct": -5.0,
        "before_rows_per_second": 10000.0,
        "after_rows_per_second": 9500.0,
        "sample_rows": 100000,
        "preload_rows": 100000,
        "measurement_scope": "isolated_lab",
    }


def _size_measurement():
    return {"index_size_bytes": 1024,
            "index_size_source": "table_index_length_delta"}


def _assess(report, **kwargs):
    return assess_index_report(
        report, expected_index_name="idx_orders_status",
        expected_table="orders", original_sql="SELECT id FROM orders",
        **kwargs,
    )


def test_index_evidence_passes_at_exact_twenty_percent_improvement():
    result = _assess(_report())
    assert result["status"] == "passed"
    assert result["evidence_complete"] is True
    assert result["result_equivalent"] is True
    assert result["improvement_ratio"] == pytest.approx(0.2)
    assert result["failure_reason"] is None


def test_index_proof_checks_target_table_in_join_plan():
    sql = ("SELECT o.order_id FROM orders o JOIN addresses a "
           "ON a.customer_id=o.customer_id")
    report = _report()
    report["after"]["raw_plan"] = {"query_block": {"nested_loop": [
        {"table": {"table_name": "a", "key": "idx_other"}},
        {"table": {"table_name": "o", "key": "idx_orders_status"}},
    ]}}
    assert assess_index_report(
        report, expected_index_name="idx_orders_status",
        expected_table="orders", original_sql=sql,
    )["status"] == "passed"
    report["after"]["raw_plan"]["query_block"]["nested_loop"][1]["table"]["key"] = "PRIMARY"
    report["after"]["raw_plan"]["query_block"]["nested_loop"][0]["table"]["key"] = "idx_orders_status"
    assert assess_index_report(
        report, expected_index_name="idx_orders_status",
        expected_table="orders", original_sql=sql,
    )["status"] == "inconclusive"


def test_index_proof_rejects_alias_reused_for_another_table():
    report = _report()
    report["after"]["raw_plan"]["query_block"]["table"]["table_name"] = "x"
    sql = ("SELECT x.id FROM orders x WHERE EXISTS "
           "(SELECT 1 FROM addresses x WHERE x.customer_id > 0)")
    assert assess_index_report(
        report, expected_index_name="idx_orders_status",
        expected_table="orders", original_sql=sql,
    )["status"] == "inconclusive"


@pytest.mark.parametrize(("change", "expected_status"), [
    ({"after": {"result_hash": "hash-b"}}, "failed"),
    ({"after": {"p95_ms": 81.0}}, "failed"),
    ({"after": {"result_hash": None}}, "inconclusive"),
    ({"after": {"runs": 19}}, "inconclusive"),
    ({"after": {"timed_out_runs": 1}}, "inconclusive"),
    ({"after": {"key_used": "PRIMARY"}}, "inconclusive"),
    ({"write_overhead": {"index_size_bytes": None}}, "inconclusive"),
    ({"write_overhead": {"index_size_source": "unknown"}}, "inconclusive"),
    ({"write_overhead": {"measurement_scope": None}}, "inconclusive"),
    ({"write_overhead": {"sample_rows": 99999}}, "inconclusive"),
    ({"write_overhead": {"insert_throughput_change_pct": -50}}, "inconclusive"),
])
def test_index_evidence_fails_closed(change, expected_status):
    report = deepcopy(_report())
    for section, fields in change.items():
        report[section].update(fields)
    result = _assess(report)
    assert result["status"] == expected_status
    assert result["failure_reason"]
    if expected_status == "inconclusive":
        assert result["evidence_complete"] is False


def test_index_evidence_accepts_tablespace_growth_with_explicit_source():
    report = _report()
    report["write_overhead"]["index_size_source"] = "tablespace_allocated_growth_delta"
    assert _assess(report)["status"] == "passed"
    report["write_overhead"]["index_size_source"] = "innodb_index_stats_pages"
    assert _assess(report)["status"] == "passed"


def test_index_evidence_overwrites_untrusted_status_and_rejects_weaker_threshold():
    report = _report()
    report["status"] = "passed"
    report["after"]["runs"] = 5
    assert _assess(report)["status"] == "inconclusive"
    with pytest.raises(ValueError, match="required_runs"):
        _assess(_report(), required_runs=5)
    with pytest.raises(ValueError, match="min_improvement_ratio"):
        _assess(_report(), min_improvement_ratio=0.1)


def test_rewritten_sql_cannot_validate_index_for_approval():
    report = _report()
    report["candidate_sql_kind"] = "rewritten"
    result = _assess(report)
    assert result["status"] == "inconclusive"
    assert result["failure_reason"] == "proposal_context_invalid"


def test_report_uses_stricter_configured_thresholds(monkeypatch):
    from mcp_server.validation import validator as validation_module

    monkeypatch.setattr(validation_module, "_settings", lambda: {
        "measured_runs": 25, "min_p95_improvement_pct": 25,
    })
    assert _assess(_report())["status"] == "inconclusive"


@pytest.mark.asyncio
@pytest.mark.parametrize(("after_p95", "expected", "cleanup"), [
    (80.0, "passed", []), (90.0, "failed", ["drop"]),
])
async def test_validation_uses_real_tool_envelopes_and_cleans_failed_trial(
    after_p95, expected, cleanup,
):
    events = []

    def create():
        events.append("create")

    def drop():
        events.append("drop")

    async def explain(sql, *, mode, use_invisible_indexes):
        assert sql == "SELECT id FROM orders"
        assert mode == "estimate"
        return json.dumps({"ok": True, "data": {
            "query_cost": "100.0" if not use_invisible_indexes else "10.0",
            "key_used": None if not use_invisible_indexes else "idx_orders_status",
            "raw_plan": {"query_block": {"table": {
                "table_name": "orders",
                "key": "idx_orders_status" if use_invisible_indexes else None,
            }}},
        }})

    async def benchmark(sql, *, warmup_runs, measured_runs, use_invisible_indexes,
                        compute_result_hash):
        assert (warmup_runs, measured_runs, compute_result_hash) == (3, 20, True)
        return json.dumps({"ok": True, "data": {
            "p95_ms": after_p95 if use_invisible_indexes else 100.0,
            "rows_examined": 10, "result_hash": "sha256:same", "row_count": 1,
            "runs": 20, "timed_out_runs": 0,
        }})

    report = await validate_index(
        proposal_id="p1", query_id="q07", original_sql="SELECT id FROM orders",
        index_name="idx_orders_status", target_table="orders",
        create_trial=create, drop_trial=drop,
        measure_size=_size_measurement,
        measure_write=_write_measurement,
        explain=explain, benchmark=benchmark,
    )
    assert report["status"] == expected
    assert events == ["create", *cleanup]


@pytest.mark.asyncio
async def test_validation_drops_trial_when_tool_fails():
    events = []

    async def broken_explain(*args, **kwargs):
        return json.dumps({"ok": False, "error": {"code": "TIMEOUT"}, "data": None})

    async def unused_benchmark(*args, **kwargs):
        pytest.fail("Không benchmark sau khi EXPLAIN lỗi")

    report = await validate_index(
        proposal_id="p1", query_id="q07", original_sql="SELECT id FROM orders",
        index_name="idx_orders_status", target_table="orders",
        create_trial=lambda: events.append("create"),
        drop_trial=lambda: events.append("drop"), measure_size=_size_measurement,
        measure_write=_write_measurement, explain=broken_explain,
        benchmark=unused_benchmark,
    )
    assert report["status"] == "inconclusive"
    assert events == ["create", "drop"]


@pytest.mark.asyncio
async def test_validation_reports_foreign_key_support_risk_before_measurement():
    events = []

    def create():
        raise ForeignKeyIndexRisk("index may replace foreign key support")

    async def unused_tool(*args, **kwargs):
        pytest.fail("Không đo khi index có thể thay thế hỗ trợ khóa ngoại")

    report = await validate_index(
        proposal_id="p1", query_id="q07", original_sql="SELECT id FROM orders",
        index_name="idx_orders_status", target_table="orders",
        create_trial=create, drop_trial=lambda: events.append("drop"),
        measure_size=_size_measurement, measure_write=_write_measurement,
        explain=unused_tool, benchmark=unused_tool,
    )
    assert report["status"] == "inconclusive"
    assert report["failure_reason"] == "foreign_key_support_risk"
    assert events == ["drop"]


def test_trial_index_builds_only_structured_invisible_ddl():
    trial = TrialIndex({
        "type": "index", "table": "orders", "index_name": "idx_orders_status",
        "columns": [{"name": "status", "order": "ASC"}],
    }, proposal_id="p_test")
    assert trial.create_ddl == (
        "CREATE INDEX `idx_orders_status` ON `orders` (`status` ASC) "
        "COMMENT 'mcp_trial:p_test' INVISIBLE"
    )
    assert trial.drop_ddl == "DROP INDEX `idx_orders_status` ON `orders`"
    trial.drop()  # chưa tạo thì không được gửi DROP
    with pytest.raises(ValueError, match="identifier"):
        TrialIndex({
            "type": "index", "table": "orders; DROP TABLE orders",
            "index_name": "idx_orders_status",
            "columns": [{"name": "status", "order": "ASC"}],
        })


def test_trial_rejects_index_that_could_replace_foreign_key_support(monkeypatch):
    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute(self, sql, params=None):
            self.sql = sql

        def fetchall(self):
            if "information_schema.COLUMNS" in self.sql:
                return [{"COLUMN_NAME": name} for name in
                        ("product_id", "quantity", "unit_price")]
            if "information_schema.STATISTICS" in self.sql:
                return [{"INDEX_NAME": "fk_order_items_product",
                         "COLUMN_NAME": "product_id", "SEQ_IN_INDEX": 1}]
            if "KEY_COLUMN_USAGE" in self.sql:
                return [{"CONSTRAINT_NAME": "fk_order_items_product",
                         "COLUMN_NAME": "product_id", "ORDINAL_POSITION": 1}]
            return []

    class Conn:
        def cursor(self):
            return Cursor()

    @contextmanager
    def readonly():
        yield Conn()

    def forbidden_admin():
        pytest.fail("Không được tạo index trước khi kiểm tra khóa ngoại")

    monkeypatch.setattr(apply_module, "get_conn", readonly)
    monkeypatch.setattr(apply_module, "get_admin_conn", forbidden_admin)
    trial = TrialIndex({
        "type": "index", "table": "order_items",
        "index_name": "idx_lab_full_q01_cover",
        "columns": [{"name": name, "order": "ASC"} for name in
                    ("product_id", "quantity", "unit_price")],
    })

    with pytest.raises(ValueError, match="khóa ngoại"):
        trial.create()


@pytest.mark.parametrize(("index_after", "stats_pages", "expected_source", "expected_size"), [
    (2048, 4, "innodb_index_stats_pages", 65536),
    (2048, None, "table_index_length_delta", 1024),
    (1024, None, "tablespace_allocated_growth_delta", 4096),
])
def test_trial_index_uses_readonly_metadata_and_admin_only_for_ddl(
    monkeypatch, index_after, stats_pages, expected_source, expected_size,
):
    calls = []

    class Cursor:
        def __init__(self, role):
            self.role = role
            self.sql = ""

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute(self, sql, params=None):
            self.sql = sql
            calls.append((self.role, sql))

        def fetchall(self):
            if "information_schema.COLUMNS" in self.sql:
                return [{"COLUMN_NAME": "status"}]
            if "INDEX_COMMENT" in self.sql:
                return [{"COLUMN_NAME": "status", "COLLATION": "A",
                         "INDEX_COMMENT": "mcp_trial:p_test", "IS_VISIBLE": "NO"}]
            return []

        def fetchone(self):
            if "mysql.innodb_index_stats" in self.sql:
                return None if stats_pages is None else {
                    "stat_value": stats_pages, "page_size": 16384,
                }
            if "INDEX_LENGTH" in self.sql:
                count = sum("CREATE INDEX" in sql for _, sql in calls)
                return {"INDEX_LENGTH": index_after if count else 1024}
            if "INNODB_TABLESPACES" in self.sql:
                count = sum("CREATE INDEX" in sql for _, sql in calls)
                return {"SPACE_TYPE": "Single",
                        "ALLOCATED_SIZE": 8192 if count else 4096}
            return None

    class Conn:
        def __init__(self, role):
            self.role = role

        def cursor(self):
            return Cursor(self.role)

    @contextmanager
    def readonly():
        yield Conn("readonly")

    @contextmanager
    def admin():
        yield Conn("admin")

    monkeypatch.setattr(apply_module, "get_conn", readonly)
    monkeypatch.setattr(apply_module, "get_admin_conn", admin)
    trial = TrialIndex({
        "type": "index", "table": "orders", "index_name": "idx_orders_status",
        "columns": [{"name": "status", "order": "ASC"}],
    }, proposal_id="p_test")
    trial.create()
    assert trial.size_delta() == {
        "index_size_bytes": expected_size,
        "index_size_source": expected_source,
    }
    trial.drop()
    assert all(role == "admin" for role, sql in calls
               if "CREATE INDEX" in sql or "DROP INDEX" in sql)
    assert any(role == "admin" and "mysql.innodb_index_stats" in sql
               for role, sql in calls)
    assert any(role == "readonly" and "IS_VISIBLE" in sql for role, sql in calls)


def test_index_stats_permission_denied_is_only_fallback_error(monkeypatch):
    trial = TrialIndex({
        "type": "index", "table": "orders", "index_name": "idx_orders_status",
        "columns": [{"name": "status", "order": "ASC"}],
    }, proposal_id="p_test")

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute(self, sql, params):
            raise apply_module.pymysql.err.OperationalError(error_code, "denied")

    class Conn:
        def cursor(self):
            return Cursor()

    @contextmanager
    def admin():
        yield Conn()

    monkeypatch.setattr(apply_module, "get_admin_conn", admin)
    error_code = 1142
    assert trial._index_stats_size() is None
    error_code = 2003
    with pytest.raises(apply_module.pymysql.err.OperationalError):
        trial._index_stats_size()


def test_proposal_store_keeps_original_and_report_immutable(tmp_path):
    store = ProposalStore(tmp_path / "proposals.sqlite3")
    proposal = {
        "type": "index", "table": "orders", "index_name": "idx_orders_status",
        "columns": [{"name": "status", "order": "ASC"}],
    }
    proposal_id = store.add("q07", "SELECT id FROM orders", proposal)
    proposal["table"] = "addresses"
    saved = store.get(proposal_id)
    assert saved["proposal"]["table"] == "orders"
    assert saved["original_sql"] == "SELECT id FROM orders"
    report = _report()
    report["proposal_id"] = proposal_id
    store.begin_trial(proposal_id)
    store.save_report(proposal_id, report)
    assert store.get(proposal_id)["report"]["status"] == "passed"
    with pytest.raises(ValueError, match="report"):
        store.save_report(proposal_id, report)
    with pytest.raises(ValueError, match="SQL"):
        store.add("q07", "DROP TABLE orders", proposal)


def test_store_preserves_foreign_key_risk_reason(tmp_path):
    store = ProposalStore(tmp_path / "proposals.sqlite3")
    proposal_id = store.add("q01", "SELECT order_id FROM order_items", {
        "type": "index", "table": "order_items", "index_name": "idx_items_cover",
        "columns": [{"name": "product_id", "order": "ASC"}],
    })
    store.begin_trial(proposal_id)
    report = {
        "proposal_id": proposal_id, "query_id": "q01",
        "candidate_sql_kind": "original", "before": None, "after": None,
        "write_overhead": None, "failure_reason": "foreign_key_support_risk",
    }

    saved = store.save_report(proposal_id, report)

    assert saved["status"] == "inconclusive"
    assert saved["failure_reason"] == "foreign_key_support_risk"
    assert store.get(proposal_id)["trial_state"] == "cleaned"


@pytest.mark.asyncio
async def test_saved_validation_persists_report_without_accepting_new_sql(
    tmp_path, monkeypatch,
):
    store = ProposalStore(tmp_path / "proposals.sqlite3")
    proposal_id = store.add("q07", "SELECT id FROM orders", {
        "type": "index", "table": "orders", "index_name": "idx_orders_status",
        "columns": [{"name": "status", "order": "ASC"}],
    })
    events = []

    class FakeTrial:
        def __init__(self, proposal, *, proposal_id):
            assert proposal["table"] == "orders"

        def create(self):
            assert store.get(proposal_id)["trial_state"] == "pending"
            events.append("create")

        def drop(self):
            events.append("drop")

        def size_delta(self):
            return _size_measurement()

    async def explain(sql, *, mode, use_invisible_indexes):
        assert sql == "SELECT id FROM orders"
        return json.dumps({"ok": True, "data": {
            "query_cost": "100", "key_used": "idx_orders_status",
            "raw_plan": {"query_block": {"table": {
                "table_name": "orders", "key": "idx_orders_status",
            }}},
        }})

    async def benchmark(sql, *, warmup_runs, measured_runs, use_invisible_indexes,
                        compute_result_hash):
        assert sql == "SELECT id FROM orders"
        return json.dumps({"ok": True, "data": {
            "p95_ms": 80 if use_invisible_indexes else 100,
            "rows_examined": 10, "result_hash": "sha256:same", "row_count": 1,
            "runs": 20, "timed_out_runs": 0,
        }})

    def fake_write(proposal, *, csv_dir):
        assert proposal["table"] == "orders"
        assert csv_dir == tmp_path
        return _write_measurement()

    monkeypatch.setattr(
        "mcp_server.validation.write_overhead.measure_insert_overhead", fake_write,
    )
    result = await validate_saved_index(
        store, proposal_id, write_csv_dir=tmp_path,
        trial_factory=FakeTrial, explain=explain, benchmark=benchmark,
    )
    assert result["status"] == "passed"
    assert store.get(proposal_id)["report"]["status"] == "passed"
    assert store.get(proposal_id)["trial_state"] == "passed"
    assert events == ["create"]


@pytest.mark.asyncio
async def test_saved_validation_requires_write_lab_before_trial(tmp_path):
    store = ProposalStore(tmp_path / "proposals.sqlite3")
    proposal_id = store.add("q07", "SELECT id FROM orders", {
        "type": "index", "table": "orders", "index_name": "idx_orders_status",
        "columns": [{"name": "status", "order": "ASC"}],
    })
    with pytest.raises(ValueError, match="write_csv_dir"):
        await validate_saved_index(store, proposal_id)
    assert store.get(proposal_id)["trial_state"] == "new"


@pytest.mark.asyncio
async def test_saved_validation_cleans_passed_trial_when_report_save_fails(monkeypatch):
    events = []

    class FakeStore:
        def get(self, proposal_id):
            return {"query_id": "q07", "original_sql": "SELECT 1",
                    "proposal": {"index_name": "idx_test", "table": "orders"}}

        def save_report(self, proposal_id, report):
            raise OSError("storage unavailable")

        def begin_trial(self, proposal_id):
            pass

    class FakeTrial:
        def __init__(self, proposal, *, proposal_id):
            pass

        def create(self):
            pass

        def size_delta(self):
            return _size_measurement()

        def drop(self):
            events.append("drop")

    async def fake_validate_index(**kwargs):
        return {"status": "passed"}

    monkeypatch.setattr(
        "mcp_server.validation.validator.validate_index", fake_validate_index,
    )
    with pytest.raises(OSError, match="storage unavailable"):
        await validate_saved_index(
            FakeStore(), "p1", measure_write=dict, trial_factory=FakeTrial,
        )
    assert events == ["drop"]


def test_recovery_drops_only_index_owned_by_pending_proposal(tmp_path):
    store = ProposalStore(tmp_path / "proposals.sqlite3")
    proposal_id = store.add("q07", "SELECT id FROM orders", {
        "type": "index", "table": "orders", "index_name": "idx_orders_status",
        "columns": [{"name": "status", "order": "ASC"}],
    })
    store.begin_trial(proposal_id)
    events = []

    class FakeTrial:
        def __init__(self, proposal, *, proposal_id):
            events.append(("inspect", proposal_id))

        def recover_drop(self):
            events.append(("drop", proposal_id))
            return "dropped"

    results = recover_interrupted_trials(store, trial_factory=FakeTrial)
    assert results == {proposal_id: "dropped"}
    assert events == [("inspect", proposal_id), ("drop", proposal_id)]
    saved = store.get(proposal_id)
    assert saved["trial_state"] == "cleaned"
    assert saved["report"]["status"] == "inconclusive"
    assert saved["report"]["failure_reason"] == "interrupted"
    assert recover_interrupted_trials(store, trial_factory=FakeTrial) == {}


def test_recovery_keeps_pending_when_index_ownership_is_uncertain(tmp_path):
    store = ProposalStore(tmp_path / "proposals.sqlite3")
    proposal_id = store.add("q07", "SELECT id FROM orders", {
        "type": "index", "table": "orders", "index_name": "idx_orders_status",
        "columns": [{"name": "status", "order": "ASC"}],
    })
    store.begin_trial(proposal_id)

    class FakeTrial:
        def __init__(self, proposal, *, proposal_id):
            pass

        def recover_drop(self):
            raise RuntimeError("ownership mismatch")

    results = recover_interrupted_trials(store, trial_factory=FakeTrial)
    assert results == {proposal_id: "recovery_failed"}
    assert store.get(proposal_id)["trial_state"] == "pending"
    assert store.get(proposal_id)["report"] is None


def test_recovery_marks_missing_trial_as_interrupted_without_ddl(tmp_path):
    store = ProposalStore(tmp_path / "proposals.sqlite3")
    proposal_id = store.add("q07", "SELECT id FROM orders", {
        "type": "index", "table": "orders", "index_name": "idx_orders_status",
        "columns": [{"name": "status", "order": "ASC"}],
    })
    store.begin_trial(proposal_id)

    class FakeTrial:
        def __init__(self, proposal, *, proposal_id):
            pass

        def recover_drop(self):
            return "absent"

    assert recover_interrupted_trials(store, trial_factory=FakeTrial) == {
        proposal_id: "absent",
    }
    assert store.get(proposal_id)["trial_state"] == "cleaned"
    assert store.get(proposal_id)["report"]["failure_reason"] == "interrupted"


def test_recover_drop_refuses_index_with_other_owner(monkeypatch):
    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute(self, sql, params=None):
            pass

        def fetchall(self):
            return [{"COLUMN_NAME": "status", "COLLATION": "A",
                     "INDEX_COMMENT": "mcp_trial:p_other", "IS_VISIBLE": "NO"}]

    class Conn:
        def cursor(self):
            return Cursor()

    @contextmanager
    def readonly():
        yield Conn()

    def forbidden_admin():
        pytest.fail("Không được gọi DROP INDEX khi marker không khớp")

    monkeypatch.setattr(apply_module, "get_conn", readonly)
    monkeypatch.setattr(apply_module, "get_admin_conn", forbidden_admin)
    trial = TrialIndex({
        "type": "index", "table": "orders", "index_name": "idx_orders_status",
        "columns": [{"name": "status", "order": "ASC"}],
    }, proposal_id="p_ours")
    with pytest.raises(RuntimeError, match="không thuộc trial"):
        trial.recover_drop()


def test_store_keeps_trial_pending_if_cleanup_failed(tmp_path):
    store = ProposalStore(tmp_path / "proposals.sqlite3")
    proposal_id = store.add("q07", "SELECT id FROM orders", {
        "type": "index", "table": "orders", "index_name": "idx_orders_status",
        "columns": [{"name": "status", "order": "ASC"}],
    })
    store.begin_trial(proposal_id)
    report = _report()
    report.update(proposal_id=proposal_id, failure_reason="cleanup_failed")
    saved = store.save_report(proposal_id, report)
    assert saved["status"] == "inconclusive"
    assert store.get(proposal_id)["trial_state"] == "pending"


def test_trial_checks_ownership_after_ambiguous_create_error(monkeypatch):
    trial = TrialIndex({
        "type": "index", "table": "orders", "index_name": "idx_orders_status",
        "columns": [{"name": "status", "order": "ASC"}],
    }, proposal_id="p_ours")
    monkeypatch.setattr(trial, "_check_schema", lambda: None)
    monkeypatch.setattr(trial, "_index_length", lambda: 1024)
    monkeypatch.setattr(trial, "_tablespace_allocated_size", lambda: 4096)
    checked = []
    monkeypatch.setattr(trial, "recover_drop", lambda: checked.append("inspect"))

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute(self, sql):
            if "CREATE INDEX" in sql:
                raise OSError("connection lost after DDL")

    class Conn:
        def cursor(self):
            return Cursor()

    @contextmanager
    def admin():
        yield Conn()

    monkeypatch.setattr(apply_module, "get_admin_conn", admin)
    with pytest.raises(OSError, match="connection lost"):
        trial.create()
    trial.drop()
    assert checked == ["inspect"]
