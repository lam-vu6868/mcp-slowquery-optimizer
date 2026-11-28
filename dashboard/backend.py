"""
dashboard/backend.py
--------------------

CHỨC NĂNG : Mở proposal store, khôi phục trial, gọi Validation và Tool 6 cục bộ.
PHỤ TRÁCH  : Tình    |    REVIEW: Vũ + Hải
LƯU Ý      : Store runtime nằm ngoài Git; không dùng store của lab đã xóa index.
             Người duyệt là OS account chạy Streamlit; chỉ dùng khi Dashboard nghe loopback.
THAM KHẢO  : docs/api-contract.md (Validation Layer), mcp_server/validation/rollback.py
"""

import asyncio
import getpass
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from mcp_server.dashboard_server import make_dashboard_mcp
from mcp_server.llm.agent import analyze_query
from mcp_server.llm.groq import create_gemini_client, create_groq_client
from mcp_server.llm.prompts import build_analysis_prompt
from mcp_server.store.audit_log import AuditLog
from mcp_server.store.proposals import ProposalStore
from mcp_server.tools.apply import OptimizationApplier, TrialIndex, check_approval
from mcp_server.tools.slow_queries import get_slow_queries
from mcp_server.utils.config import Config
from mcp_server.utils.db import current_db_identity, get_conn
from mcp_server.validation.rollback import (
    expire_waiting_trials,
    recover_interrupted_trials,
    reject_saved_index,
)
from mcp_server.validation.validator import validate_saved_index
from security.approval import ApprovalTokens
from security.ast_whitelist import check as ast_check

DEFAULT_STORE_PATH = Path(os.getenv("DASHBOARD_STORE_PATH") or (
    Path(__file__).resolve().parents[1] / "data" / "outputs" / "proposals.sqlite3"
))
DEFAULT_TOKEN_PATH = DEFAULT_STORE_PATH.with_name("approval_tokens.sqlite3")
DEFAULT_AUDIT_PATH = DEFAULT_STORE_PATH.with_name("audit.sqlite3")


def initialize_backend(store_path: Path = DEFAULT_STORE_PATH) -> ProposalStore:
    """Dọn trial pending trước khi trả store cho backend Dashboard."""
    store = ProposalStore(store_path)
    results = recover_interrupted_trials(store)
    failed = [proposal_id for proposal_id, result in results.items()
              if result == "recovery_failed"]
    if failed:
        raise RuntimeError("Không khôi phục được trial: " + ", ".join(failed))
    expired = expire_waiting_trials(store)
    failed = [proposal_id for proposal_id, result in expired.items()
              if result == "cleanup_failed"]
    if failed:
        raise RuntimeError("Không dọn được trial hết hạn: " + ", ".join(failed))
    return store


async def load_slow_queries(source: str, *, limit: int = 10) -> list[dict]:
    """Đọc tối đa `limit` (1–100) query từ Tool 1 và giữ nhãn dữ liệu không tin cậy."""
    if source not in ("performance_schema", "slow_log"):
        raise ValueError("nguồn slow query không hợp lệ")
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("limit phải từ 1 đến 100")
    payload = json.loads(await get_slow_queries(limit=limit, source=source))
    data = payload.get("data") if isinstance(payload, dict) else None
    rows = (data.get("queries") if payload.get("ok") is True
            and isinstance(data, dict) else None)
    if not isinstance(rows, list) or len(rows) > limit or any(
        not isinstance(row, dict)
        or not isinstance(row.get("query_id"), str)
        or not isinstance(row.get("sql_text"), str)
        or row.get("untrusted") is not True
        for row in rows
    ):
        raise ValueError("Tool 1 không trả danh sách slow query hợp lệ")
    return rows


async def generate_proposals_from_dashboard(
    store: ProposalStore, query_id: str, sql: str,
) -> list[str]:
    """Kiểm SQL, gọi LLM với Tool 1–5 rồi lưu đề xuất đã qua parser."""
    if not isinstance(query_id, str) or not 1 <= len(query_id.strip()) <= 128:
        raise ValueError("query_id không hợp lệ")
    if not isinstance(sql, str) or not ast_check(sql)[0]:
        raise ValueError("SQL không qua AST whitelist")
    build_analysis_prompt(query_id, sql)  # kiểm giới hạn SQL trước khi gọi API

    provider = (os.getenv("LLM_PROVIDER") or "groq").strip().lower()
    llm_client = create_gemini_client() if provider == "gemini" else create_groq_client()
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "mcp_server.server"],
        cwd=str(Path(__file__).resolve().parents[1]),
    )
    try:
        async with (
            asyncio.timeout(180),
            stdio_client(params) as (read_stream, write_stream),
            ClientSession(read_stream, write_stream) as session,
        ):
            await session.initialize()
            result = await analyze_query(
                query_id, sql, llm_client=llm_client, mcp_client=session,
            )
    finally:
        await llm_client.close()

    if (result.get("query_id") != query_id
            or not isinstance(result.get("proposals"), list)):
        raise ValueError("LLM không trả đề xuất hợp lệ")
    return store.add_many(query_id, sql, result["proposals"])


async def validate_proposal(
    store: ProposalStore, proposal_id: str, *, write_csv_dir: Path,
) -> dict:
    """Dùng store đã qua recovery để lưu trạng thái trial và report."""
    return await validate_saved_index(store, proposal_id, write_csv_dir=write_csv_dir)


async def validate_from_dashboard(
    store: ProposalStore, proposal_id: str, *, write_csv_dir: Path,
) -> dict:
    """Chỉ mở đường Validation từ UI trên validation lab riêng đã kiểm marker."""
    if (Config.DB_HOST != "127.0.0.1" or Config.DB_PORT != 3309
            or Config.DB_NAME != "shopdb"):
        raise ValueError("Dashboard chỉ chạy Validation trên lab 3309")
    saved = store.get(proposal_id)
    if saved["trial_state"] != "new" or saved["proposal"].get("type") != "index":
        raise ValueError("proposal không ở trạng thái chờ Validation")
    write_csv_dir = Path(write_csv_dir)
    if not (write_csv_dir / f"{saved['proposal']['table']}.csv").is_file():
        raise ValueError("thiếu CSV của bảng đề xuất")
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT marker FROM mcp_validation_lab_identity LIMIT 1")
        row = cur.fetchone()
    if not row or row.get("marker") != "mcp-validation-lab-v1":
        raise ValueError("DB không có marker validation lab hợp lệ")
    return await validate_proposal(store, proposal_id, write_csv_dir=write_csv_dir)


def reject_from_dashboard(store: ProposalStore, proposal_id: str) -> str:
    """Dọn trial đã pass qua guard DB/marker/snapshot của Validation."""
    return reject_saved_index(store, proposal_id)


def approval_precheck(store: ProposalStore, proposal_id: str, *,
                      trial_factory=TrialIndex) -> str:
    """Trả DDL chuẩn nếu report đạt và trial vẫn thuộc proposal, chưa cấp token."""
    return check_approval(store, proposal_id, trial_factory=trial_factory,
                          identity_reader=current_db_identity)


def issue_approval_token(store: ProposalStore, proposal_id: str, *,
                         token_path: Path = DEFAULT_TOKEN_PATH,
                         trial_factory=TrialIndex) -> str:
    """Ký đúng DDL của proposal đã qua precheck; chỉ backend Dashboard gọi."""
    ddl = approval_precheck(store, proposal_id, trial_factory=trial_factory)
    version = store.get(proposal_id)["version"]
    return ApprovalTokens(token_path, secret=Config.APPROVAL_SECRET).issue_token(
        proposal_id, version, ddl,
    )


async def apply_from_dashboard(store: ProposalStore, proposal_id: str, *,
                               token_path: Path = DEFAULT_TOKEN_PATH,
                               audit_path: Path = DEFAULT_AUDIT_PATH) -> dict:
    """Luồng cục bộ: lấy OS account, cấp token rồi gọi registry Tool 6 riêng."""
    approver = getpass.getuser().strip()
    if not approver:
        raise ValueError("không xác định được tài khoản cục bộ")
    token = issue_approval_token(store, proposal_id, token_path=token_path)
    applier = OptimizationApplier(
        store, ApprovalTokens(token_path, secret=Config.APPROVAL_SECRET),
        AuditLog(audit_path), approver=approver,
    )
    result = await make_dashboard_mcp(applier).call_tool(
        "apply_optimization", {"proposal_id": proposal_id, "approval_token": token},
    )
    if result.is_error:
        raise RuntimeError("Tool 6 không áp dụng được đề xuất; kiểm tra audit")
    return json.loads(result.content[0].text)
