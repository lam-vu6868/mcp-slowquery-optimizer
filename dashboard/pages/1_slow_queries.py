"""
dashboard/pages/1_slow_queries.py
---------------------------------

CHỨC NĂNG :
    TAB 1 — Top slow query: bảng và biểu đồ latency, rows examined, số lần chạy.

PHỤ TRÁCH  : Tình    |    REVIEW: Tường

LƯU Ý:
    - Nguồn dữ liệu: Tool 1 get_slow_queries (qua ui_common.load_slow_queries).
    - SQL hiển thị là dữ liệu không tin cậy, chỉ hiển thị dạng text (st.code).

TRẠNG THÁI : SKELETON (tuần 1) — hoàn thiện ở tuần 6.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st  # noqa: E402

from ui_common import empty_state, load_slow_queries, setup_page, show_untrusted_sql  # noqa: E402

setup_page("Slow query", "🐢")
st.title("🐢 Top slow query")

limit = st.slider("Số query hiển thị", min_value=5, max_value=100, value=10, step=5)
queries = load_slow_queries(limit=limit)

if not queries:
    empty_state(
        "Chưa có dữ liệu slow query.",
        "Cần Tool 1 `get_slow_queries` (Vũ) và dữ liệu đã seed (Hải).",
    )
    st.stop()

import pandas as pd  # noqa: E402

columns = ["query_id", "exec_count", "avg_latency_ms", "p95_latency_ms", "rows_examined_avg", "rows_sent_avg"]
df = pd.DataFrame(queries)
st.dataframe(df[[c for c in columns if c in df.columns]], hide_index=True)

if {"query_id", "p95_latency_ms"} <= set(df.columns):
    st.subheader("P95 latency (ms) theo query")
    st.bar_chart(df.set_index("query_id")["p95_latency_ms"])

st.subheader("Chi tiết")
for q in queries:
    with st.expander(f"{q.get('query_id', '?')} — avg {q.get('avg_latency_ms', '?')} ms"):
        show_untrusted_sql(q.get("sql_text"))
