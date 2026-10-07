"""
dashboard/pages/2_proposals.py
------------------------------

CHỨC NĂNG :
    TAB 2 — Đề xuất của LLM + trạng thái Validation + nút Approve / Reject.

PHỤ TRÁCH  : Tình    |    REVIEW: Tường

LƯU Ý:
    - Nút Approve -> server sinh approval token (dùng 1 lần, hết hạn 10 phút) -> backend gọi Tool 6.
    - Đề xuất loại 'rewrite' chỉ HIỂN THỊ, KHÔNG có nút Apply.
    - Chỉ cho Approve khi validation_report.status == 'passed'.

TRẠNG THÁI : SKELETON (tuần 1) — nút Approve còn khóa, nối Tool 6 ở tuần 5–7.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st  # noqa: E402

from ui_common import empty_state, load_proposals, setup_page, show_untrusted_sql, status_badge  # noqa: E402

TOOL6_READY = False  # bật khi mcp_server/tools/apply.py + approval flow xong (tuần 5)

setup_page("Đề xuất", "💡")
st.title("💡 Đề xuất của LLM")

proposals = load_proposals()
if not proposals:
    empty_state(
        "Chưa có đề xuất nào.",
        "Cần LLM agent (Vũ), Validation Layer và store đề xuất (Hải).",
    )
    st.stop()

for p in proposals:
    ptype = p.get("type", "?")
    report = p.get("validation_report") or {}
    vstatus = report.get("status", "pending")

    with st.container(border=True):
        left, right = st.columns([4, 1])
        left.markdown(f"**{p.get('proposal_id', '?')}** · `{ptype}` · query `{p.get('query_id', '?')}`")
        right.markdown(status_badge(vstatus), unsafe_allow_html=True)

        st.caption("Lý do (LLM viết — dữ liệu không tin cậy)")
        st.text(p.get("rationale", ""))

        if ptype == "rewrite":
            show_untrusted_sql(p.get("rewritten_sql"), label="SQL viết lại (chỉ hiển thị, không áp dụng)")
            continue

        show_untrusted_sql(p.get("ddl"), label="DDL do server sinh")
        can_approve = TOOL6_READY and vstatus == "passed"
        help_text = (
            "Tool 6 chưa sẵn sàng" if not TOOL6_READY
            else "Chỉ duyệt được khi validation = passed"
        )
        b1, b2, _ = st.columns([1, 1, 4])
        b1.button("✅ Approve", key=f"approve_{p.get('proposal_id')}", disabled=not can_approve, help=help_text)
        b2.button("❌ Reject", key=f"reject_{p.get('proposal_id')}", disabled=not TOOL6_READY)
