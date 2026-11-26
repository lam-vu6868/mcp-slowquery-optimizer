"""
dashboard/backend.py
--------------------

CHỨC NĂNG : Mở proposal store, khôi phục trial, gọi Validation và Tool 6 cục bộ.
PHỤ TRÁCH  : Tình    |    REVIEW: Vũ + Hải
LƯU Ý      : Store runtime nằm ngoài Git; không dùng store của lab đã xóa index.
             Người duyệt là OS account chạy Streamlit; chỉ dùng khi Dashboard nghe loopback.
THAM KHẢO  : docs/api-contract.md (Validation Layer), mcp_server/validation/rollback.py
"""

import getpass
import json
from pathlib import Path

from mcp_server.dashboard_server import make_dashboard_mcp
from mcp_server.store.audit_log import AuditLog
from mcp_server.store.proposals import ProposalStore
from mcp_server.tools.apply import OptimizationApplier, TrialIndex, check_approval
from mcp_server.utils.config import Config
from mcp_server.utils.db import current_db_identity
from mcp_server.validation.rollback import recover_interrupted_trials
from mcp_server.validation.validator import validate_saved_index
from security.approval import ApprovalTokens

DEFAULT_STORE_PATH = Path(__file__).resolve().parents[1] / "data" / "outputs" / "proposals.sqlite3"
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
    return store


async def validate_proposal(
    store: ProposalStore, proposal_id: str, *, write_csv_dir: Path,
) -> dict:
    """Dùng store đã qua recovery để lưu trạng thái trial và report."""
    return await validate_saved_index(store, proposal_id, write_csv_dir=write_csv_dir)


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
