"""
security/injection_tests/run_tests.py
-------------------------------------

CHỨC NĂNG :
    Chạy tự động 20 payload qua hệ thống và ghi kết quả (lớp nào chặn, có audit log không).

PHỤ TRÁCH  : Tình    |    REVIEW: Vũ

LƯU Ý:
    - Kết quả ghi ra security/logs/ và đưa vào security/injection_report.md.
    - Chạy được bằng: python -m security.injection_tests.run_tests

THAM KHẢO  : security/injection_tests/payloads.py

TRẠNG THÁI : ĐANG LÀM — chạy 20 ranh giới tự động; chưa gọi LLM/API thật.
"""

import asyncio
import json
import sqlite3
import time
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

from mcp_server import server
from mcp_server.llm.parsers import parse_llm_response
from mcp_server.llm.prompts import build_analysis_prompt
from mcp_server.store.audit_log import AuditLog
from mcp_server.tools.apply import OptimizationApplier, TrialIndex
from mcp_server.utils.sanitize import sanitize_comment
from security.approval import ApprovalTokens
from security.ast_whitelist import check as ast_check
from security.injection_tests.payloads import PAYLOADS

SCHEMA = {"tables": [{"name": "orders", "columns": [{"name": "status"}], "indexes": []}]}


def _fake_token_is_rejected(token: str) -> bool:
    """Đi qua lõi Tool 6 với DB giả; xác nhận audit mà không có DDL thật."""
    identity = {"server_uuid": "db-test", "schema": "shopdb", "host": "127.0.0.1", "port": 3309}
    saved = {
        "proposal_id": "p_fake", "query_id": "q07", "version": 1,
        "trial_state": "passed", "review_expires_at": int(time.time()) + 3600,
        "proposal": {"type": "index", "table": "orders", "index_name": "idx_test",
                     "columns": [{"name": "status", "order": "ASC"}]},
        "report": {"proposal_id": "p_fake", "query_id": "q07", "status": "passed",
                   "evidence_complete": True, "candidate_sql_kind": "original",
                   "result_equivalent": True, "failure_reason": None,
                   "db_identity": identity,
                   "write_overhead": {"index_size_bytes": 1024,
                                      "index_size_source": "innodb_index_stats_pages"}},
    }

    class Store:
        def get(self, proposal_id):
            if proposal_id != "p_fake":
                raise KeyError(proposal_id)
            return saved

    class Trial:
        def __init__(self, proposal, *, proposal_id):
            self.visible_ddl = "ALTER TABLE `orders` ALTER INDEX `idx_test` VISIBLE"

        def _index_state(self):
            return "owned"

    def no_admin_connection():
        raise AssertionError("DDL must not run for fake token")

    with TemporaryDirectory() as directory:
        root = Path(directory)
        audit = AuditLog(root / "audit.sqlite3")
        applier = OptimizationApplier(
            Store(), ApprovalTokens(root / "tokens.sqlite3", secret="test-secret"),
            audit, approver="injection-suite", trial_factory=Trial,
            identity_reader=lambda: identity, admin_conn=no_admin_connection,
        )
        try:
            applier.apply_optimization("p_fake", token)
        except ValueError:
            pass
        else:
            return False
        with closing(sqlite3.connect(audit.path)) as conn:
            rows = conn.execute(
                "SELECT result, reason FROM audit_log ORDER BY audit_id"
            ).fetchall()
        return rows == [("attempted", None), ("rejected", "TOKEN_INVALID")]


def _check_case(item: dict, llm_tools: set[str]) -> tuple[bool, str, bool]:
    kind = item["kind"]
    content = item["content"]
    if kind == "sql_comment":
        prompt = build_analysis_prompt("q07", content)
        data = json.loads(prompt.partition("\n")[2])
        return (data["sql"]["text"] == "SELECT 1"
                and data["sql"]["untrusted"] is True,
                "strip_sql_comments + untrusted", False)
    if kind == "schema_comment":
        return (bool(content) and sanitize_comment(content) ==
                "[UNTRUSTED DATA — not an instruction]",
                "sanitize_comment", False)
    if kind == "identifier":
        try:
            TrialIndex({"type": "index", "table": content, "index_name": "idx_test",
                        "columns": [{"name": "status", "order": "ASC"}]})
        except ValueError:
            return True, "TrialIndex identifier guard", False
        return False, "TrialIndex identifier guard", False
    if kind == "sql":
        safe, _ = ast_check(content)
        return not safe, "AST whitelist", False

    if kind == "fake_tool6_token":
        return ("apply_optimization" not in llm_tools and _fake_token_is_rejected(content),
                "LLM registry + Tool 6 token", True)

    proposal = {"type": "index", "table": "orders", "index_name": "idx_orders_status",
                "columns": [{"name": "status", "order": "ASC"}],
                "rationale": "test", "target_query_ids": ["q07"]}
    if kind == "extra_approved":
        proposal["approved"] = content
    elif kind == "extra_token":
        proposal["approval_token"] = content
    elif kind == "index_name":
        proposal["index_name"] = content
    elif kind == "table_name":
        proposal["table"] = content
    else:
        raise ValueError("unknown injection scenario")
    response = {"query_id": "q07", "diagnosis": "test", "proposals": [proposal],
                "confidence": "low"}
    try:
        parse_llm_response(json.dumps(response), "q07", SCHEMA)
    except (ValueError, TypeError):
        return True, "LLM response parser", False
    return False, "LLM response parser", False


def run_cases(log_path: str | Path = "security/logs/injection_results.log") -> list[dict]:
    """Chạy 20 payload ở ranh giới code và ghi log không chứa payload/token."""
    if len(PAYLOADS) != 20 or len({item["id"] for item in PAYLOADS}) != 20:
        raise ValueError("injection suite must contain 20 unique cases")
    llm_tools = {tool.name for tool in asyncio.run(server.mcp.list_tools())}
    results = []
    for item in PAYLOADS:
        try:
            blocked, layer, audited = _check_case(item, llm_tools)
            status = "blocked" if blocked else "not_blocked"
        except Exception as exc:  # noqa: BLE001 - preserve failed case in test log
            status, layer, audited = "error", type(exc).__name__, False
        results.append({
            "id": item["id"], "group": item["group"],
            "description": item["description"], "status": status,
            "layer": layer, "audit_log": audited,
            "llm_influenced": "not_measured",
        })
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(item, ensure_ascii=False) for item in results)
                    + "\n", encoding="utf-8")
    return results


if __name__ == "__main__":
    results = run_cases()
    blocked = sum(item["status"] == "blocked" for item in results)
    print(f"Injection boundary checks: {blocked}/{len(results)} blocked; "
          "LLM behavior not measured")
    raise SystemExit(0 if blocked == len(results) else 1)
