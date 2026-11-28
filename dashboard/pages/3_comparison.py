"""
dashboard/pages/3_comparison.py
-------------------------------

CHỨC NĂNG :
    TAB 3 — So sánh trước/sau: P95 latency, Query Cost, rows examined, dung lượng index, write overhead; kèm bảng so sánh LLM vs baseline.

PHỤ TRÁCH  : Tình    |    REVIEW: Tường

LƯU Ý:
    - Đọc data/metrics/comparison.csv và validation_report.
    - Biểu đồ theo từng query, không chỉ trung bình.

THAM KHẢO  : project-management/ROADMAP.md (mục 2.3, 2.4)

TRẠNG THÁI : ĐÃ CÀI ĐẶT — hiển thị comparison.csv và biểu đồ P95/cost/rows trước-sau theo từng query.
"""

import csv
from pathlib import Path

import streamlit as st

from data.metrics.metrics import summarize_rewrite_reports

ROOT = Path(__file__).resolve().parents[2]
COMPARISON_CSV = ROOT / "data" / "metrics" / "comparison.csv"
REWRITE_REPORT_DIR = ROOT / "data" / "outputs" / "llm_catalog_20261127"

st.title("So sánh hiệu năng & Baseline")

st.subheader("1. Bảng so sánh LLM vs Baseline (comparison.csv)")
if COMPARISON_CSV.is_file():
    with COMPARISON_CSV.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if rows:
        st.dataframe(rows, use_container_width=True)
    else:
        st.info("File comparison.csv chưa có dữ liệu.")
else:
    st.warning("Chưa có data/metrics/comparison.csv. Chạy `python -m data.metrics.metrics --build-comparison`.")

st.caption(
    "Lưu ý (ROADMAP mục 2.5): pt-query-digest không đề xuất index nên không nằm trong bảng Precision/Recall này."
)

st.subheader("2. Kết quả đo trước/sau theo từng query (nhóm Rewrite trên lab 3309)")
summary = summarize_rewrite_reports(REWRITE_REPORT_DIR)
if summary["total"] == 0:
    st.info("Chưa có file report q*_rewrite_measure.json để hiển thị.")
else:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Tổng query đã đo", summary["total"])
    col2.metric("Đạt (passed)", summary["passed"])
    col3.metric("Không đạt (failed)", summary["failed"])
    rate_pct = f"{summary['pass_rate'] * 100:.1f}%" if summary["pass_rate"] is not None else "N/A"
    col4.metric("Tỉ lệ đạt Rewrite", rate_pct)

    st.dataframe(summary["items"], use_container_width=True)

    chart_rows = {
        item["query_id"]: {
            "P95 trước (ms)": item["before_p95_ms"],
            "P95 sau (ms)": item["after_p95_ms"],
        }
        for item in summary["items"]
        if item["before_p95_ms"] is not None and item["after_p95_ms"] is not None
    }
    if chart_rows:
        st.subheader("Biểu đồ P95 trước vs sau theo từng query")
        st.bar_chart(
            {
                "query_id": list(chart_rows.keys()),
                "P95 trước (ms)": [v["P95 trước (ms)"] for v in chart_rows.values()],
                "P95 sau (ms)": [v["P95 sau (ms)"] for v in chart_rows.values()],
            },
            x="query_id",
        )
