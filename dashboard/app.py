"""
dashboard/app.py
----------------

CHỨC NĂNG :
    Điểm vào (entry point) của Dashboard Streamlit: trang chủ + cấu hình chung. 4 tab nằm trong thư mục pages/.

PHỤ TRÁCH  : Tình    |    REVIEW: Tường

LƯU Ý:
    - Chạy: streamlit run dashboard/app.py
    - Phải có try/except khi chưa có dữ liệu (trước đây từng crash).
    - Dashboard KHÔNG tự chạy DDL: chỉ gọi Tool 6 kèm approval token sau khi người bấm Approve.

CẦN LÀM:
    [ ] Trang chủ: tổng quan (số query chậm, số đề xuất chờ duyệt, trạng thái hệ thống).

THAM KHẢO  : docs/api-contract.md, dashboard/pages/

TRẠNG THÁI : ĐANG LÀM — giữ store đã recovery cho backend Validation; giao diện 4 tab chưa cài đặt.
"""

import streamlit as st

from dashboard.backend import initialize_backend


@st.cache_resource
def _startup_backend():
    return initialize_backend()


try:
    proposal_store = _startup_backend()
except Exception:  # noqa: BLE001 - không cho Dashboard nhận việc khi recovery lỗi
    st.error("Không khôi phục được index thử. Kiểm tra trial pending trước khi tiếp tục.")
    st.stop()
