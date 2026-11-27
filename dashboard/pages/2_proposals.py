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

THAM KHẢO  : docs/api-contract.md (Tool 6, mục 4), security/approval.py

TRẠNG THÁI : ĐANG LÀM — hiển thị proposal, chạy Validation trên lab, Approve/Reject; chưa nối tạo proposal từ UI.
"""

import asyncio
import time
from pathlib import Path

import streamlit as st

from dashboard.backend import (
    apply_from_dashboard,
    initialize_backend,
    reject_from_dashboard,
    validate_from_dashboard,
)

st.title("Đề xuất tối ưu")

try:
    if "proposal_store" not in st.session_state:
        st.session_state["proposal_store"] = initialize_backend()
    store = st.session_state["proposal_store"]
    proposals = store.recent_proposals()
except Exception:  # noqa: BLE001 - không cho thao tác khi store/recovery lỗi
    st.error("Không đọc được đề xuất hoặc khôi phục index thử. Kiểm tra backend.")
    st.stop()

notice = st.session_state.pop("proposal_notice", None)
if notice:
    st.success(notice)

if not proposals:
    st.info("Chưa có đề xuất trong store cục bộ.")
    st.stop()

by_id = {item["proposal_id"]: item for item in proposals}
proposal_id = st.selectbox(
    "Chọn đề xuất", list(by_id),
    format_func=lambda value: f"{by_id[value]['query_id']} · {value}",
)
saved = by_id[proposal_id]
proposal = saved["proposal"]
report = saved.get("report") or {}

st.write("Trạng thái trial:", saved["trial_state"])
st.write("Loại đề xuất:", proposal["type"])
if proposal["type"] == "index":
    st.write("Index:", f"{proposal['table']}.{proposal['index_name']}")
st.write("Validation:", report.get("status", "chưa chạy"))
st.code(saved["original_sql"], language="sql")

if proposal["type"] != "index":
    st.info("Đề xuất viết lại SQL chỉ để xem; không áp dụng tự động.")
    st.stop()

if saved["trial_state"] == "new":
    st.warning("Validation sẽ tạo index thử INVISIBLE trên validation lab 3309.")
    st.caption("Cần Dashboard trỏ DB tới 127.0.0.1:3309 và write lab chạy ở cổng 3308.")
    csv_dir = st.text_input("Thư mục CSV cho write lab", key=f"csv_dir_{proposal_id}")
    confirmed = st.checkbox("Tôi xác nhận chạy Validation trên lab", key=f"validate_{proposal_id}")
    if st.button("Chạy Validation", disabled=not (confirmed and csv_dir.strip())):
        try:
            result = asyncio.run(validate_from_dashboard(
                store, proposal_id, write_csv_dir=Path(csv_dir),
            ))
        except Exception:  # noqa: BLE001 - không hiển thị SQL/chi tiết DB nội bộ
            st.error("Validation không chạy được. Kiểm tra lab 3309, write lab 3308 và CSV.")
        else:
            st.session_state["proposal_notice"] = f"Validation: {result['status']}"
            st.rerun()
    st.stop()

expires_at = saved.get("review_expires_at")
if type(expires_at) is int:
    st.write("Hạn duyệt:", time.strftime("%d/%m/%Y %H:%M:%S", time.localtime(expires_at)))

can_act = saved["trial_state"] == "passed" and report.get("status") == "passed"
can_approve = (can_act and report.get("evidence_complete") is True
               and type(expires_at) is int and expires_at > int(time.time()))
if can_act:
    st.warning("Approve sẽ chuyển index thử thành VISIBLE; Reject sẽ xóa index thử trên MySQL.")
    confirmed = st.checkbox("Tôi xác nhận thao tác trên MySQL", key=f"confirm_{proposal_id}")
    approve_col, reject_col = st.columns(2)
    if approve_col.button("Approve", disabled=not (confirmed and can_approve)):
        try:
            asyncio.run(apply_from_dashboard(store, proposal_id))
        except Exception:  # noqa: BLE001 - backend giữ chi tiết trong audit
            st.error("Không áp dụng được đề xuất. Kiểm tra audit và trạng thái index.")
        else:
            st.session_state["proposal_notice"] = "Đã áp dụng index."
            st.rerun()
    if reject_col.button("Reject", disabled=not confirmed):
        try:
            reject_from_dashboard(store, proposal_id)
        except Exception:  # noqa: BLE001 - không báo đã dọn khi DDL lỗi
            st.error("Không dọn được index thử. Kiểm tra trial pending.")
        else:
            st.session_state["proposal_notice"] = "Đã dọn index thử."
            st.rerun()
elif saved["trial_state"] == "passed":
    st.info("Report chưa đủ điều kiện thao tác; kiểm tra Validation.")
