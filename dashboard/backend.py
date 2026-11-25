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
