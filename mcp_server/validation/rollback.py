"""
mcp_server/validation/rollback.py
---------------------------------

CHỨC NĂNG :
    Hoàn tác thay đổi khi validation thất bại hoặc khi cần gỡ index đã áp dụng.

PHỤ TRÁCH  : Hải    |    REVIEW: Vũ

LƯU Ý:
    - Rollback = DROP INDEX (hoặc chuyển lại INVISIBLE).
    - Phải chạy được cả khi validation bị ngắt giữa chừng.
    - Với snapshot FK hợp lệ, khôi phục index hỗ trợ bị mất và đối chiếu schema sau dọn; sai lệch để pending.

TRẠNG THÁI : ĐANG LÀM — Reject/recovery kiểm DB của report mới bằng test giả; chưa thử Reject trên MySQL thật.
"""

import time

from mcp_server.tools.apply import TrialIndex
from mcp_server.utils.db import current_db_identity


def _cleanup_pending_trial(store, proposal_id: str, trial_factory,
                           identity_reader) -> str:
    saved = store.get(proposal_id)
    report = saved.get("report")
    if (isinstance(report, dict) and report.get("db_identity") is not None
            and report["db_identity"] != identity_reader()):
        raise ValueError("report không thuộc DB đang dọn")
    trial = trial_factory(saved["proposal"], proposal_id=proposal_id)
    snapshot = saved["fk_support_snapshot"]
    if snapshot is not None:
        trial.restore_fk_support(snapshot)
    result = trial.recover_drop()
    if snapshot is not None and trial.fk_support_snapshot() != snapshot:
        raise RuntimeError("schema FK/index khác snapshot sau khi dọn trial")
    store.mark_recovered(proposal_id)
    return result


def reject_saved_index(store, proposal_id: str, *, trial_factory=TrialIndex,
                       identity_reader=current_db_identity) -> str:
    """Reject trial đã pass; ghi pending trước DROP để có thể recovery."""
    saved = store.get(proposal_id)
    report = saved.get("report")
    if (saved.get("trial_state") != "passed" or not isinstance(report, dict)
            or not isinstance(report.get("db_identity"), dict)
            or report["db_identity"] != identity_reader()):
        raise ValueError("proposal hoặc DB không hợp lệ để Reject")
    store.begin_cleanup(proposal_id)
    return _cleanup_pending_trial(store, proposal_id, trial_factory, identity_reader)


def recover_interrupted_trials(store, *, trial_factory=TrialIndex,
                               identity_reader=current_db_identity) -> dict[str, str]:
    """Chỉ gọi lúc backend khởi động, trước khi nhận validation mới."""
    results = {}
    for proposal_id in store.pending_trials():
        try:
            results[proposal_id] = _cleanup_pending_trial(
                store, proposal_id, trial_factory, identity_reader,
            )
        except Exception:  # noqa: BLE001 - leave pending for inspection/retry
            results[proposal_id] = "recovery_failed"
    return results


def expire_waiting_trials(store, *, now: int | None = None,
                          trial_factory=TrialIndex,
                          identity_reader=current_db_identity) -> dict[str, str]:
    """Dọn trial đã pass quá hạn; lỗi để lại trạng thái để kiểm tra/recovery."""
    now = int(time.time()) if now is None else now
    results = {}
    for proposal_id in store.expired_passed(now):
        try:
            results[proposal_id] = reject_saved_index(
                store, proposal_id, trial_factory=trial_factory,
                identity_reader=identity_reader,
            )
        except Exception:  # noqa: BLE001 - không bỏ qua lỗi dọn index
            results[proposal_id] = "cleanup_failed"
    return results
