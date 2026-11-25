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

TRẠNG THÁI : ĐANG LÀM — đã thử recovery FK trên bảng nhỏ của validation lab; q01 runtime vẫn bị chặn.
"""

from mcp_server.tools.apply import TrialIndex


def recover_interrupted_trials(store, *, trial_factory=TrialIndex) -> dict[str, str]:
    """Chỉ gọi lúc backend khởi động, trước khi nhận validation mới."""
    results = {}
    for proposal_id in store.pending_trials():
        try:
            saved = store.get(proposal_id)
            trial = trial_factory(saved["proposal"], proposal_id=proposal_id)
            if saved["fk_support_snapshot"] is not None:
                trial.restore_fk_support(saved["fk_support_snapshot"])
            results[proposal_id] = trial.recover_drop()
            if (saved["fk_support_snapshot"] is not None
                    and trial.fk_support_snapshot() != saved["fk_support_snapshot"]):
                raise RuntimeError("schema FK/index khác snapshot sau khi dọn trial")
            store.mark_recovered(proposal_id)
        except Exception:  # noqa: BLE001 - leave pending for inspection/retry
            results[proposal_id] = "recovery_failed"
    return results
