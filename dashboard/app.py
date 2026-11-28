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

import sys
from pathlib import Path

import streamlit as st

_ROOT = str(Path(__file__).resolve().parents[1])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from dashboard.backend import initialize_backend

if hasattr(st, "set_page_config"):
    st.set_page_config(page_title="MCP Slow Query Optimizer", layout="wide")


@st.cache_resource
def _startup_backend():
    return initialize_backend()


try:
    proposal_store = _startup_backend()
    st.session_state["proposal_store"] = proposal_store
except Exception:  # noqa: BLE001 - không cho Dashboard nhận việc khi recovery lỗi
    st.error("Không khôi phục được index thử. Kiểm tra trial pending trước khi tiếp tục.")
    st.stop()

if hasattr(st, "title"):
    st.title("MCP Slow Query Optimizer")
    st.write(
        "Đi theo **Hành trình của 1 query** ở thanh menu bên trái:\n"
        "1. **Chọn query chậm** — chạy thử 1 trong 30 query hoặc slow log trên DB chính `3307` (đo ms).\n"
        "2. **LLM đề xuất** — gửi query cho Groq (qua MCP Tool 1–5 chỉ đọc) sinh index/rewrite.\n"
        "3. **Chạy thử đề xuất** — đo trước/sau bằng INVISIBLE INDEX trên lab `3309` (Đo nhanh / Đo đầy đủ).\n"
        "4. **So sánh** — so query vừa chạy (Gốc vs LLM vs Greedy) và so phát hiện (pt-query-digest vs Tool 1).\n"
        "5. **Bảo mật** — bấm chạy trực tiếp 20 kịch bản Prompt Injection & xem Audit log Tool 6.\n"
        "6. **Duyệt & áp dụng** — Validation chính thức và Approve (token 1 lần) / Reject."
    )
    st.info("DB chính 3307 chỉ đọc; mọi DDL thử chạy tách biệt trên lab 3309.")
