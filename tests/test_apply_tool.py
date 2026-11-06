"""
tests/test_apply_tool.py
------------------------
CHỨC NĂNG: Test Tool 6 apply_optimization với DB giả (không cần MySQL).
PHỤ TRÁCH: Tình    |    REVIEW: Vũ + Hải
THAM KHẢO: mcp_server/tools/apply.py, docs/api-contract.md (Tool 6)

Phủ "Done tuần 5": Tool 6 từ chối khi thiếu/sai token; mọi lần gọi đều ghi audit_log.
"""
import asyncio
import inspect
import json

import pytest

from mcp_server.store import audit_log, proposals as store
from mcp_server.tools import apply as tool6
from security import approval

PAYLOAD = {
    "type": "index", "table": "sales_data",
    "columns": [{"name": "region", "order": "ASC"}, {"name": "order_date", "order": "ASC"}],
    "index_name": "idx_sales_region_date", "rationale": "test", "target_query_ids": ["q07"],
}
PASSED_REPORT = {"status": "passed", "before": {"p95_ms": 2000}, "after": {"p95_ms": 40},
                 "result_equivalent": True}


class FakeDB:
    def __init__(self, columns=("id", "region", "order_date", "country"), index_state=None, fail=False):
        self.columns = set(columns)
        self.state = index_state
        self.fail = fail
        self.executed = []

    def table_columns(self, table):
        return self.columns if table == "sales_data" else set()

    def index_state(self, table, index_name):
        return self.state

    def execute_ddl(self, ddl):
        if self.fail:
            raise RuntimeError("Access denied")
        self.executed.append(ddl)

    def index_size_bytes(self, table, index_name):
        return 123456


def run(coro):
    return json.loads(asyncio.run(coro))


@pytest.fixture
def validated(security_env):
    pid = store.save_proposal(dict(PAYLOAD))
    store.save_validation_report(pid, PASSED_REPORT)
    return pid


def _token(pid, payload=PAYLOAD):
    return approval.issue_token(pid, tool6.build_ddl(payload)).token


class TestContract:
    def test_signature_has_no_sql_or_approved_param(self):
        params = set(inspect.signature(tool6.apply_optimization).parameters)
        assert {"proposal_id", "approval_token"} <= params
        for forbidden in ("sql", "ddl", "approved", "query"):
            assert forbidden not in params
        assert tool6.LLM_EXPOSED is False

    def test_build_ddl(self):
        assert tool6.build_ddl(PAYLOAD) == \
            "CREATE INDEX `idx_sales_region_date` ON `sales_data` (`region`, `order_date`)"

    @pytest.mark.parametrize("patch", [
        {"index_name": "idx_x; DROP TABLE sales_data"},
        {"index_name": "IDX_UPPER"},
        {"table": "sales_data`; DROP TABLE x; --"},
        {"columns": ["region) ; DROP TABLE sales_data; -- "]},
        {"columns": []},
        {"columns": ["a", "b", "c", "d", "e", "f"]},
        {"columns": ["region", "region"]},
        {"columns": [{"name": "region", "order": "ASC; DROP"}]},
        {"type": "rewrite"},
    ])
    def test_build_ddl_rejects_bad_structure(self, patch):
        with pytest.raises(ValueError):
            tool6.build_ddl({**PAYLOAD, **patch})

    def test_generated_ddl_passes_ast(self):
        from security.ast_whitelist import check
        assert check(tool6.build_ddl(PAYLOAD))[0] is True


class TestHappyPath:
    def test_creates_index_when_absent(self, validated):
        db = FakeDB()
        r = run(tool6.apply_optimization(validated, _token(validated), db=db, actor="tinh"))
        assert r["ok"] is True and r["data"]["applied"] is True
        assert db.executed == [tool6.build_ddl(PAYLOAD)]
        assert r["data"]["rollback_ddl"].startswith("DROP INDEX")
        assert store.get_proposal(validated)["status"] == store.STATUS_APPLIED
        last = audit_log.list_entries(limit=1)[0]
        assert last["result"] == "success" and last["actor"] == "tinh"

    def test_makes_invisible_index_visible(self, validated):
        db = FakeDB(index_state={"columns": ["region", "order_date"], "visible": False})
        r = run(tool6.apply_optimization(validated, _token(validated), db=db))
        assert r["ok"] and db.executed == [
            "ALTER TABLE `sales_data` ALTER INDEX `idx_sales_region_date` VISIBLE"]

    def test_token_never_written_to_audit(self, validated):
        tok = _token(validated)
        run(tool6.apply_optimization(validated, tok, db=FakeDB()))
        dump = json.dumps(audit_log.list_entries(), ensure_ascii=False)
        assert tok not in dump and tok.split(".")[3] not in dump


class TestRejections:
    def _code(self, r):
        assert r["ok"] is False
        return r["error"]["code"]

    @pytest.mark.parametrize("tok", [None, "", "approved", "true", "v1.fake.123.sig"])
    def test_missing_or_fake_token(self, validated, tok):
        db = FakeDB()
        r = run(tool6.apply_optimization(validated, tok, db=db))
        assert self._code(r) == "TOKEN_INVALID" and db.executed == []

    def test_replay(self, validated):
        tok = _token(validated)
        assert run(tool6.apply_optimization(validated, tok, db=FakeDB()))["ok"]
        store.set_status(validated, store.STATUS_VALIDATED)  # giả sử ai đó reset trạng thái
        r = run(tool6.apply_optimization(validated, tok, db=FakeDB()))
        assert self._code(r) == "TOKEN_INVALID" and r["error"]["detail"]["reason"] == "REUSED"

    def test_token_of_other_proposal(self, validated):
        other = store.save_proposal({**PAYLOAD, "index_name": "idx_sales_other"})
        store.save_validation_report(other, PASSED_REPORT)
        r = run(tool6.apply_optimization(validated, _token(other, {**PAYLOAD, "index_name": "idx_sales_other"}),
                                         db=FakeDB()))
        assert self._code(r) == "TOKEN_INVALID"

    def test_proposal_changed_after_approval(self, validated):
        tok = _token(validated)
        from mcp_server.store.meta_db import get_meta_conn
        evil = {**PAYLOAD, "columns": ["region", "country"]}
        with get_meta_conn() as conn:
            conn.execute("UPDATE proposals SET payload_json=? WHERE proposal_id=?",
                         (json.dumps(evil), validated))
        db = FakeDB()
        r = run(tool6.apply_optimization(validated, tok, db=db))
        assert self._code(r) == "TOKEN_INVALID" and db.executed == []

    def test_rewrite_forbidden(self, security_env):
        pid = store.save_proposal({"type": "rewrite", "original_query_id": "q13",
                                   "rewritten_sql": "SELECT 1", "rationale": "x"})
        store.save_validation_report(pid, PASSED_REPORT)
        assert self._code(run(tool6.apply_optimization(pid, "x", db=FakeDB()))) == "FORBIDDEN"

    def test_not_validated(self, security_env):
        pid = store.save_proposal(dict(PAYLOAD))
        r = run(tool6.apply_optimization(pid, _token(pid), db=FakeDB()))
        assert self._code(r) == "VALIDATION_FAILED"

    def test_failed_validation(self, security_env):
        pid = store.save_proposal(dict(PAYLOAD))
        store.save_validation_report(pid, {"status": "failed"})
        assert self._code(run(tool6.apply_optimization(pid, _token(pid), db=FakeDB()))) == "VALIDATION_FAILED"

    def test_not_found(self, security_env):
        assert self._code(run(tool6.apply_optimization("p_nope_1", "x", db=FakeDB()))) == "NOT_FOUND"

    @pytest.mark.parametrize("pid", ["", None, "1; DROP TABLE x", "p_" + "a" * 100, "../../etc"])
    def test_bad_proposal_id(self, security_env, pid):
        assert self._code(run(tool6.apply_optimization(pid, "x", db=FakeDB()))) == "INVALID_INPUT"

    def test_missing_column_in_real_schema(self, validated):
        r = run(tool6.apply_optimization(validated, _token(validated), db=FakeDB(columns=("id", "region"))))
        assert self._code(r) == "NOT_FOUND"

    def test_index_name_conflict(self, validated):
        db = FakeDB(index_state={"columns": ["country"], "visible": True})
        r = run(tool6.apply_optimization(validated, _token(validated), db=db))
        assert self._code(r) == "INVALID_INPUT" and db.executed == []

    def test_db_error_marks_apply_failed(self, validated):
        r = run(tool6.apply_optimization(validated, _token(validated), db=FakeDB(fail=True)))
        assert self._code(r) == "INTERNAL"
        assert store.get_proposal(validated)["status"] == store.STATUS_APPLY_FAILED

    def test_retry_after_apply_failed_with_new_token(self, validated):
        old = _token(validated)
        run(tool6.apply_optimization(validated, old, db=FakeDB(fail=True)))
        assert store.get_proposal(validated)["status"] == store.STATUS_APPLY_FAILED
        assert self._code(run(tool6.apply_optimization(validated, old, db=FakeDB()))) == "TOKEN_INVALID"
        assert run(tool6.apply_optimization(validated, _token(validated), db=FakeDB()))["ok"]

    def test_already_applied(self, validated):
        run(tool6.apply_optimization(validated, _token(validated), db=FakeDB()))
        r = run(tool6.apply_optimization(validated, _token(validated), db=FakeDB()))
        assert self._code(r) == "INVALID_INPUT"

    def test_every_call_is_audited(self, validated):
        before = len(audit_log.list_entries(limit=1000))
        run(tool6.apply_optimization(validated, None, db=FakeDB()))
        run(tool6.apply_optimization("p_nope_1", "x", db=FakeDB()))
        run(tool6.apply_optimization("bad id", "x", db=FakeDB()))
        run(tool6.apply_optimization(validated, _token(validated), db=FakeDB()))
        assert len(audit_log.list_entries(limit=1000)) == before + 4
