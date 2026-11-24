"""
mcp_server/validation/rollback.py
---------------------------------

CHỨC NĂNG :
    Hoàn tác thay đổi khi validation thất bại hoặc khi cần gỡ index đã áp dụng.

PHỤ TRÁCH  : Hải    |    REVIEW: Vũ

LƯU Ý:
    - Rollback = DROP INDEX (hoặc chuyển lại INVISIBLE).
    - Phải chạy được cả khi validation bị ngắt giữa chừng.

TRẠNG THÁI : ĐANG LÀM — có khôi phục trial pending; chưa nối điểm khởi động backend.
"""

from mcp_server.tools.apply import TrialIndex


def recover_interrupted_trials(store, *, trial_factory=TrialIndex) -> dict[str, str]:
    """Chỉ gọi lúc backend khởi động, trước khi nhận validation mới."""
    results = {}
    for proposal_id in store.pending_trials():
        try:
            saved = store.get(proposal_id)
            trial = trial_factory(saved["proposal"], proposal_id=proposal_id)
            results[proposal_id] = trial.recover_drop()
            store.mark_recovered(proposal_id)
        except Exception:  # noqa: BLE001 - leave pending for inspection/retry
            results[proposal_id] = "recovery_failed"
    return results
