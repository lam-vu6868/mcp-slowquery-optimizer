"""
dashboard/pages/1_slow_queries.py
---------------------------------

CHỨC NĂNG :
    TAB 1 — Top slow query: bảng và biểu đồ latency, rows examined, số lần chạy.

PHỤ TRÁCH  : Tình    |    REVIEW: Tường

LƯU Ý:
    - Nguồn dữ liệu: Tool 1 get_slow_queries.
    - SQL hiển thị là dữ liệu không tin cậy, chỉ hiển thị dạng text.

THAM KHẢO  : docs/api-contract.md

TRẠNG THÁI : ĐANG LÀM — đọc Tool 1, hiển thị top query và chuyển SQL sang trang Đề xuất.
"""

import asyncio
import sys
from pathlib import Path

import streamlit as st

_ROOT = str(Path(__file__).resolve().parents[2])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

_ROOT = str(Path(__file__).resolve().parents[2])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from dashboard.backend import load_slow_queries  # noqa: E402

st.title("Slow Query")
source = st.selectbox("Nguồn dữ liệu", ["performance_schema", "slow_log"])
st.caption("performance_schema là thống kê tích lũy; slow_log cần quyền đọc riêng.")

if st.button("Tải slow query"):
    try:
        st.session_state["slow_query_rows"] = asyncio.run(load_slow_queries(source))
        st.session_state["slow_query_source"] = source
    except Exception:  # noqa: BLE001 - không hiển thị SQL hoặc lỗi DB nội bộ
        st.error("Không đọc được slow query. Kiểm tra kết nối và quyền của nguồn đã chọn.")

rows = (st.session_state.get("slow_query_rows", [])
        if st.session_state.get("slow_query_source") == source else [])
if not rows:
    st.info("Chưa có slow query đạt ngưỡng hoặc chưa tải dữ liệu.")
    st.stop()

st.dataframe([{
    "Mã query": row["query_id"],
    "Số lần chạy": row.get("exec_count"),
    "Trung bình (ms)": row.get("avg_latency_ms"),
    "P95 (ms)": row.get("p95_latency_ms"),
    "Dòng đọc trung bình": row.get("rows_examined_avg"),
} for row in rows], hide_index=True)

selected = st.selectbox(
    "Chọn slow query", range(len(rows)),
    format_func=lambda index: rows[index]["query_id"],
)
st.code(rows[selected]["sql_text"], language="sql")
if st.button("Phân tích query này"):
    st.session_state["analysis_query_id"] = rows[selected]["query_id"]
    st.session_state["analysis_sql"] = rows[selected]["sql_text"]
    st.switch_page("pages/2_proposals.py")
