"""
dashboard/pages/1_chon_query_cham.py
------------------------------------

CHỨC NĂNG :
    TRANG 1 — Chọn một query chậm (bộ 30 query của đề tài hoặc slow log của MySQL),
    bấm CHẠY THẬT trên DB hiện tại (3307, readonly_user) để thấy ms, số dòng quét và
    EXPLAIN cost. Kết quả được lưu làm "query gốc" cho các trang sau.

PHỤ TRÁCH  : Tình · Vũ    |    REVIEW: Tường

LƯU Ý:
    - SQL hiển thị là dữ liệu không tin cậy; mọi SQL chạy phải qua AST whitelist.
    - SQL từ performance_schema có dấu ? (đã ẩn giá trị) nên không chạy trực tiếp được.
"""

import asyncio
import json
import sys
from pathlib import Path

import streamlit as st

_ROOT = str(Path(__file__).resolve().parents[2])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from dashboard.backend import load_slow_queries
from dashboard.journey import (
    get_journey,
    record_explain,
    record_original_run,
    select_query,
)
from dashboard.query_runner import SLOW_THRESHOLD_MS, TIMEOUT_MS, run_query_once
from data.queries.queries import QUERIES
from mcp_server.tools.explain import explain_query
from mcp_server.utils.config import Config

NEXT_PAGE = "pages/2_llm_de_xuat.py"
GROUP_LABELS = {
    1: "Nhóm 1 — Thiếu index (q01–q06)",
    2: "Nhóm 2 — Sai thứ tự composite (q07–q12)",
    3: "Nhóm 3 — Hàm bọc cột / non-sargable (q13–q18)",
    4: "Nhóm 4 — SELECT * + filesort (q19–q24)",
    5: "Nhóm 5 — Subquery → JOIN (q25–q30)",
}


def _run_original(query_id: str, sql: str, source: str) -> None:
    select_query(st.session_state, query_id, sql, source)
    with st.spinner(f"Đang chạy {query_id} trên MySQL (tối đa {TIMEOUT_MS // 1000} giây)..."):
        try:
            record_original_run(st.session_state, run_query_once(sql))
        except Exception as exc:  # noqa: BLE001 - không lộ SQL/chi tiết DB
            st.error(f"Không chạy được query (lỗi hoặc quá {TIMEOUT_MS // 1000} giây): "
                     f"{type(exc).__name__}")


def _explain(query_id: str, sql: str, source: str) -> None:
    select_query(st.session_state, query_id, sql, source)
    with st.spinner("Đang chạy EXPLAIN..."):
        try:
            envelope = json.loads(asyncio.run(explain_query(sql, mode="estimate")))
            if not envelope.get("ok"):
                raise ValueError((envelope.get("error") or {}).get("code", "EXPLAIN"))
            record_explain(st.session_state, envelope["data"])
        except Exception as exc:  # noqa: BLE001
            st.error(f"Không chạy được EXPLAIN: {type(exc).__name__}")


st.title("1. Chọn query chậm và chạy thử")
st.caption(f"Query sẽ chạy trên MySQL **{Config.DB_HOST}:{Config.DB_PORT}** "
           "bằng tài khoản chỉ đọc readonly_user.")

tab_catalog, tab_log = st.tabs(["Bộ 30 query của đề tài", "Slow log của MySQL"])

with tab_catalog:
    group = st.selectbox(
        "Lọc theo nhóm lỗi", [0, 1, 2, 3, 4, 5], key="cat_group",
        format_func=lambda g: "Tất cả 30 query (q01–q30)" if g == 0 else GROUP_LABELS[g],
    )
    filtered = [q for q in QUERIES if group == 0 or q["group"] == group]
    position = st.selectbox(
        "Chọn query", range(len(filtered)), key="cat_query",
        format_func=lambda i: f"{filtered[i]['id']} — {filtered[i]['description']}",
    )
    item = filtered[position]
    st.code(item["sql"], language="sql")
    run_col, explain_col = st.columns(2)
    if run_col.button("▶ Chạy query này (đo ms)", type="primary", key="cat_run"):
        _run_original(item["id"], item["sql"], "catalog")
    if explain_col.button("🔍 Xem EXPLAIN", key="cat_explain"):
        _explain(item["id"], item["sql"], "catalog")

with tab_log:
    source = st.selectbox("Nguồn dữ liệu", ["performance_schema", "slow_log"])
    st.caption("performance_schema là thống kê tích lũy trong RAM từ lúc MySQL khởi động; "
               "slow_log lưu bền vững trong bảng mysql.slow_log.")
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
    else:
        st.dataframe([{
            "Mã query": row["query_id"],
            "Số lần chạy": row.get("exec_count"),
            "Trung bình (ms)": row.get("avg_latency_ms"),
            "P95 (ms)": row.get("p95_latency_ms"),
            "Dòng đọc trung bình": row.get("rows_examined_avg"),
        } for row in rows], hide_index=True, width="stretch")
        selected = st.selectbox(
            "Chọn slow query", range(len(rows)),
            format_func=lambda index: rows[index]["query_id"],
        )
        chosen = rows[selected]
        st.code(chosen["sql_text"], language="sql")
        has_placeholder = "?" in chosen["sql_text"]
        if has_placeholder:
            st.caption("SQL có dấu ? (giá trị đã bị ẩn) nên không chạy lại trực tiếp được; "
                       "vẫn có thể gửi sang LLM phân tích.")
        if st.button("Chạy query này (đo ms)", key="log_run", disabled=has_placeholder):
            _run_original(chosen["query_id"], chosen["sql_text"], "slow_log")
        if st.button("Phân tích query này"):
            select_query(st.session_state, chosen["query_id"], chosen["sql_text"], "slow_log")
            st.switch_page(NEXT_PAGE)

st.divider()
st.subheader("Kết quả của query đang làm việc")
journey = get_journey(st.session_state)
if not journey:
    st.info("Chưa chọn query nào. Hãy chọn một query ở trên rồi bấm ▶ Chạy.")
else:
    st.write("**Query:**", journey["query_id"])
    original = journey["original_run"]
    if original is None:
        st.info("Query này chưa được chạy. Bấm ▶ Chạy query này để đo thời gian thật.")
    else:
        m1, m2, m3 = st.columns(3)
        m1.metric("Thời gian chạy", f"{original['latency_ms']:,.2f} ms")
        m2.metric("Số dòng kết quả", f"{original['row_count']:,}")
        m3.metric("Số dòng phải quét", f"{original['rows_examined']:,}")
        if original["exceeded_slow_threshold"]:
            st.warning(f"Query chạy ≥ {SLOW_THRESHOLD_MS:.0f} ms nên được tính là slow query.")
        else:
            st.success(f"Query chạy nhanh hơn {SLOW_THRESHOLD_MS:.0f} ms.")
    if journey["explain"] is not None:
        cost = journey["explain"]["query_cost"]
        st.metric("EXPLAIN Query Cost (MySQL ước tính)",
                  f"{cost:,.2f}" if cost is not None else "không có")
    if st.button("Tiếp theo: nhờ LLM phân tích →", key="goto_llm"):
        st.session_state["analysis_query_id"] = journey["query_id"]
        st.session_state["analysis_sql"] = journey["sql"]
        st.switch_page(NEXT_PAGE)
