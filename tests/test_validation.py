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
from mcp_server.tools.apply import TrialIndex
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
        },
        "write_overhead": {
            "insert_throughput_change_pct": -5.0,
            "index_size_bytes": 1024,
            "index_size_source": "table_index_length_delta",
            "index_size_estimated": True,
            "measurement_scope": "isolated_lab",
        },
    }


def test_index_evidence_passes_at_exact_twenty_percent_improvement():
    result = assess_index_report(_report(), expected_index_name="idx_orders_status")
    assert result["status"] == "passed"
    assert result["evidence_complete"] is True
    assert result["result_equivalent"] is True
    assert result["improvement_ratio"] == pytest.approx(0.2)
    assert result["failure_reason"] is None


@pytest.mark.parametrize(("change", "expected_status"), [
    ({"after": {"result_hash": "hash-b"}}, "failed"),
    ({"after": {"p95_ms": 81.0}}, "failed"),
    ({"after": {"result_hash": None}}, "inconclusive"),
    ({"after": {"runs": 19}}, "inconclusive"),
    ({"after": {"timed_out_runs": 1}}, "inconclusive"),
    ({"after": {"key_used": "PRIMARY"}}, "inconclusive"),
    ({"write_overhead": {"index_size_bytes": None}}, "inconclusive"),
    ({"write_overhead": {"measurement_scope": None}}, "inconclusive"),
])
def test_index_evidence_fails_closed(change, expected_status):
    report = deepcopy(_report())
    for section, fields in change.items():
        report[section].update(fields)
    result = assess_index_report(report, expected_index_name="idx_orders_status")
    assert result["status"] == expected_status
    assert result["failure_reason"]
    if expected_status == "inconclusive":
        assert result["evidence_complete"] is False


def test_index_evidence_overwrites_untrusted_status_and_rejects_weaker_threshold():
    report = _report()
    report["status"] = "passed"
    report["after"]["runs"] = 5
    assert assess_index_report(report, expected_index_name="idx_orders_status")["status"] == "inconclusive"
    with pytest.raises(ValueError, match="required_runs"):
        assess_index_report(_report(), expected_index_name="idx_orders_status", required_runs=5)
    with pytest.raises(ValueError, match="min_improvement_ratio"):
        assess_index_report(_report(), expected_index_name="idx_orders_status", min_improvement_ratio=0.1)


def test_rewritten_sql_cannot_validate_index_for_approval():
    report = _report()
    report["candidate_sql_kind"] = "rewritten"
    result = assess_index_report(report, expected_index_name="idx_orders_status")
    assert result["status"] == "inconclusive"
    assert result["failure_reason"] == "proposal_context_invalid"


def test_report_uses_stricter_configured_thresholds(monkeypatch):
    from mcp_server.validation import validator as validation_module

    monkeypatch.setattr(validation_module, "_settings", lambda: {
        "measured_runs": 25, "min_p95_improvement_pct": 25,
    })
    assert assess_index_report(
        _report(), expected_index_name="idx_orders_status",
    )["status"] == "inconclusive"


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
        index_name="idx_orders_status", create_trial=create, drop_trial=drop,
        measure_size=lambda: 1024,
        measure_write=lambda: {
            "insert_throughput_change_pct": -5.0,
            "measurement_scope": "isolated_lab",
        },
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
        index_name="idx_orders_status", create_trial=lambda: events.append("create"),
        drop_trial=lambda: events.append("drop"), measure_size=lambda: 1024,
        measure_write=lambda: {
            "insert_throughput_change_pct": -5.0,
            "measurement_scope": "isolated_lab",
        }, explain=broken_explain, benchmark=unused_benchmark,
    )
    assert report["status"] == "inconclusive"
    assert events == ["create", "drop"]


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


def test_trial_index_uses_readonly_metadata_and_admin_only_for_ddl(monkeypatch):
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
            if "INDEX_LENGTH" in self.sql:
                count = sum("CREATE INDEX" in sql for _, sql in calls)
                return {"INDEX_LENGTH": 2048 if count else 1024}
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
    assert trial.size_delta() == 1024
    trial.drop()
    assert all(role == "admin" for role, sql in calls
               if "CREATE INDEX" in sql or "DROP INDEX" in sql)
    assert any(role == "readonly" and "IS_VISIBLE" in sql for role, sql in calls)


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


@pytest.mark.asyncio
async def test_saved_validation_persists_report_without_accepting_new_sql(tmp_path):
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
            return 1024

    async def explain(sql, *, mode, use_invisible_indexes):
        assert sql == "SELECT id FROM orders"
        return json.dumps({"ok": True, "data": {
            "query_cost": "100", "key_used": "idx_orders_status",
        }})

    async def benchmark(sql, *, warmup_runs, measured_runs, use_invisible_indexes,
                        compute_result_hash):
        assert sql == "SELECT id FROM orders"
        return json.dumps({"ok": True, "data": {
            "p95_ms": 80 if use_invisible_indexes else 100,
            "rows_examined": 10, "result_hash": "sha256:same", "row_count": 1,
            "runs": 20, "timed_out_runs": 0,
        }})

    result = await validate_saved_index(
        store, proposal_id, measure_write=lambda: {
            "insert_throughput_change_pct": -5,
            "measurement_scope": "isolated_lab",
        }, trial_factory=FakeTrial, explain=explain, benchmark=benchmark,
    )
    assert result["status"] == "passed"
    assert store.get(proposal_id)["report"]["status"] == "passed"
    assert store.get(proposal_id)["trial_state"] == "passed"
    assert events == ["create"]


@pytest.mark.asyncio
async def test_saved_validation_cleans_passed_trial_when_report_save_fails(monkeypatch):
    events = []

    class FakeStore:
        def get(self, proposal_id):
            return {"query_id": "q07", "original_sql": "SELECT 1",
                    "proposal": {"index_name": "idx_test"}}

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
            return 1024

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
