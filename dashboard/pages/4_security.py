"""
dashboard/pages/4_security.py
-----------------------------

CHỨC NĂNG :
    TAB 4 — Bảo mật: kết quả 20 kịch bản injection, audit log Tool 6, số lần token bị từ chối.

PHỤ TRÁCH  : Tình    |    REVIEW: Tường

LƯU Ý:
    - Hiển thị 'lớp nào đã chặn' cho từng kịch bản, không chỉ pass/fail.
    - Payload là dữ liệu tấn công: chỉ hiển thị dạng text.

TRẠNG THÁI : SKELETON (tuần 1) — đọc log injection mới nhất; audit log nối ở tuần 7.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st  # noqa: E402

from ui_common import empty_state, load_audit_log, load_latest_injection_log, setup_page  # noqa: E402

setup_page("Bảo mật", "🛡️")
st.title("🛡️ Bảo mật")

st.subheader("Kiểm thử prompt injection")
log = load_latest_injection_log()
if log is None:
    empty_state("Chưa có kết quả kiểm thử.", "Chạy: python -m security.injection_tests")
else:
    c1, c2, c3 = st.columns(3)
    c1.metric("Tổng kịch bản", log.get("total", 0))
    c2.metric("Bị chặn", log.get("passed", 0))
    c3.metric("Lọt qua", log.get("failed", 0))
    st.caption(f"Nguồn: security/logs/{log.get('_file')} · {log.get('timestamp', '')}")

    rows = [
        {
            "ID": p.get("id"),
            "Nhóm": p.get("group"),
            "Kịch bản": p.get("description"),
            "Lớp chặn": ", ".join(p.get("blockers") or []) or "—",
            "Bị chặn": "✅" if p.get("passed") else "❌",
        }
        for p in log.get("payloads", [])
    ]
    st.dataframe(rows, hide_index=True)

    summary = log.get("blockers_summary") or {}
    if summary:
        st.caption("Số kịch bản bị chặn theo từng lớp")
        st.bar_chart(summary)

st.subheader("Audit log Tool 6")
audit = load_audit_log()
if not audit:
    empty_state("Chưa có audit log.", "Có sau khi Tool 6 apply_optimization hoạt động (tuần 5).")
else:
    st.dataframe(audit, hide_index=True)
