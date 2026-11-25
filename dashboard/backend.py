"""
dashboard/backend.py
--------------------

CHỨC NĂNG : Mở proposal store, khôi phục trial bị ngắt và gọi Validation trên cùng store.
PHỤ TRÁCH  : Tình    |    REVIEW: Vũ + Hải
LƯU Ý      : Store runtime nằm ngoài Git; không dùng store của lab đã xóa index.
THAM KHẢO  : docs/api-contract.md (Validation Layer), mcp_server/validation/rollback.py
"""

from pathlib import Path

from mcp_server.store.proposals import ProposalStore
from mcp_server.tools.apply import TrialIndex
from mcp_server.validation.rollback import recover_interrupted_trials
from mcp_server.validation.validator import validate_saved_index

DEFAULT_STORE_PATH = Path(__file__).resolve().parents[1] / "data" / "outputs" / "proposals.sqlite3"


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
    saved = store.get(proposal_id)
    report = saved.get("report")
    if (saved.get("proposal_id") != proposal_id
            or saved.get("trial_state") != "passed"
            or saved.get("proposal", {}).get("type") != "index"
            or not isinstance(report, dict)
            or report.get("proposal_id") != proposal_id
            or report.get("query_id") != saved.get("query_id")
            or report.get("status") != "passed"
            or report.get("evidence_complete") is not True
            or report.get("candidate_sql_kind") != "original"
            or report.get("result_equivalent") is not True
            or report.get("failure_reason") is not None):
        raise ValueError("proposal chưa đủ điều kiện phê duyệt")
    trial = trial_factory(saved["proposal"], proposal_id=proposal_id)
    if trial._index_state() != "owned":
        raise ValueError("index thử không còn hợp lệ để phê duyệt")
    return trial.visible_ddl
