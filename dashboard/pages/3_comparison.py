"""
dashboard/pages/3_comparison.py
-------------------------------

CHỨC NĂNG :
    TAB 3 — So sánh trước/sau: P95 latency, Query Cost, rows examined, dung lượng index,
    write overhead; kèm bảng so sánh LLM vs baseline.

PHỤ TRÁCH  : Tình    |    REVIEW: Tường

LƯU Ý:
    - Đọc data/metrics/comparison.csv (Tường) và validation_report.
    - Biểu đồ theo từng query, không chỉ trung bình.

TRẠNG THÁI : SKELETON (tuần 1) — hoàn thiện ở tuần 7.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st  # noqa: E402

from ui_common import empty_state, load_comparison, setup_page  # noqa: E402

setup_page("So sánh", "📊")
st.title("📊 So sánh trước / sau")

df = load_comparison()
if df is None:
    empty_state(
        "Chưa có file data/metrics/comparison.csv.",
        "Cần metrics (Tường) và kết quả Validation Layer (Hải).",
    )
    st.stop()

st.dataframe(df, hide_index=True)

if {"query_id", "p95_before_ms", "p95_after_ms"} <= set(df.columns):
    st.subheader("P95 latency theo query (ms)")
    st.bar_chart(df.set_index("query_id")[["p95_before_ms", "p95_after_ms"]])
else:
    st.caption("Biểu đồ P95 cần các cột: query_id, p95_before_ms, p95_after_ms.")
