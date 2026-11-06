"""
dashboard/pages/3_comparison.py
-------------------------------
CHỨC NĂNG:
    TAB 3 — So sánh trước/sau: P95 latency, Query Cost, rows examined, dung lượng index,
    write overhead; kèm bảng so sánh LLM vs baseline.

PHỤ TRÁCH: Tình    |    REVIEW: Tường
THAM KHẢO: project-management/ROADMAP.md (mục 2.3, 2.4)

NGUỒN:
    - validation_report trong store (Hải ghi) → biểu đồ theo TỪNG query, không chỉ trung bình.
    - data/metrics/comparison.csv (Tường) → LLM vs greedy vs rule-based.
      Cột mong đợi (cột nào thiếu thì bỏ qua): method, precision, recall, fpr, consistency_rate,
      rewrite_pass_rate, query_id, p95_before_ms, p95_after_ms.
"""
import altair as alt
import pandas as pd
import streamlit as st

from common import fmt_bytes, load_comparison_csv, load_validation_reports, setup_page

setup_page("So sánh trước/sau", "📊")
st.title("📊 Tab 3 — So sánh trước / sau")

df = load_validation_reports()

if df.empty:
    st.info("Chưa có validation report nào. Số liệu xuất hiện sau khi Validation Layer chạy trên các đề xuất.",
            icon="⏳")
else:
    only_passed = st.sidebar.checkbox("Chỉ đề xuất pass validation", value=False)
    view = df[df["validation"] == "passed"] if only_passed else df

    passed = df[df["validation"] == "passed"]
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Đề xuất đã kiểm chứng", len(df))
    k2.metric("Pass validation", f"{len(passed)}/{len(df)}")
    med = passed["improvement_ratio"].dropna().median() if not passed.empty else None
    k3.metric("Cải thiện P95 (trung vị)", f"{med * 100:.1f}%" if med is not None and pd.notna(med) else "—")
    k4.metric("Tổng dung lượng index (pass)", fmt_bytes(passed["index_size_bytes"].dropna().sum())
              if not passed.empty else "—")

    def before_after(col_before, col_after, title):
        sub = view[["query_id", "proposal_id", col_before, col_after]].dropna(subset=[col_before, col_after])
        if sub.empty:
            st.caption(f"Chưa có số liệu {title}.")
            return
        sub = sub.assign(label=sub["query_id"].fillna(sub["proposal_id"]))
        long = sub.melt(id_vars=["label"], value_vars=[col_before, col_after],
                        var_name="lúc đo", value_name="giá trị")
        long["lúc đo"] = long["lúc đo"].map({col_before: "Trước", col_after: "Sau"})
        chart = alt.Chart(long).mark_bar().encode(
            y=alt.Y("label:N", title=None),
            yOffset=alt.YOffset("lúc đo:N", sort=["Trước", "Sau"]),
            x=alt.X("giá trị:Q", title=title),
            color=alt.Color("lúc đo:N", sort=["Trước", "Sau"],
                            scale=alt.Scale(range=["#c0504d", "#4f81bd"]), title=None),
            tooltip=["label", "lúc đo", alt.Tooltip("giá trị:Q", format=",.1f")],
        ).properties(height=max(160, 34 * sub.shape[0]))
        st.altair_chart(chart, use_container_width=True)

    t1, t2, t3, t4 = st.tabs(["P95 latency", "Query Cost", "Rows examined", "Index & write overhead"])
    with t1:
        before_after("p95_before_ms", "p95_after_ms", "P95 (ms)")
    with t2:
        before_after("cost_before", "cost_after", "Query cost")
    with t3:
        before_after("rows_before", "rows_after", "Rows examined")
    with t4:
        w = view.dropna(subset=["index_size_bytes"])
        if w.empty:
            st.caption("Chưa có số liệu dung lượng index / write overhead.")
        else:
            w = w.assign(label=w["query_id"].fillna(w["proposal_id"]),
                         size_mb=w["index_size_bytes"] / 1024 / 1024)
            c1, c2 = st.columns(2)
            c1.altair_chart(alt.Chart(w).mark_bar(color="#8064a2").encode(
                y=alt.Y("label:N", title=None), x=alt.X("size_mb:Q", title="Dung lượng index (MB)"),
                tooltip=["label", "proposal", alt.Tooltip("size_mb:Q", format=",.1f")],
            ), use_container_width=True)
            if w["insert_throughput_change_pct"].notna().any():
                c2.altair_chart(alt.Chart(w.dropna(subset=["insert_throughput_change_pct"])).mark_bar(
                    color="#f79646").encode(
                    y=alt.Y("label:N", title=None),
                    x=alt.X("insert_throughput_change_pct:Q", title="Thay đổi INSERT throughput (%)"),
                    tooltip=["label", "insert_throughput_change_pct"],
                ), use_container_width=True)

    st.subheader("Chi tiết từng đề xuất")
    show = view[["query_id", "proposal_id", "proposal", "validation", "status", "result_equivalent",
                 "p95_before_ms", "p95_after_ms", "improvement_ratio", "rows_before", "rows_after",
                 "index_size_bytes", "insert_throughput_change_pct", "failure_reason"]]
    st.dataframe(show, use_container_width=True, hide_index=True, column_config={
        "improvement_ratio": st.column_config.NumberColumn("cải thiện", format="percent"),
        "p95_before_ms": st.column_config.NumberColumn("P95 trước (ms)", format="%.1f"),
        "p95_after_ms": st.column_config.NumberColumn("P95 sau (ms)", format="%.1f"),
    })

st.divider()
st.subheader("LLM vs baseline")
cmp_df, note = load_comparison_csv()
if cmp_df is None:
    st.info(note, icon="⏳")
else:
    st.dataframe(cmp_df, use_container_width=True, hide_index=True)
    metric_cols = [c for c in ["precision", "recall", "fpr", "consistency_rate", "rewrite_pass_rate"]
                   if c in cmp_df.columns]
    if "method" in cmp_df.columns and metric_cols:
        agg = cmp_df.groupby("method")[metric_cols].mean(numeric_only=True).reset_index()
        long = agg.melt(id_vars="method", var_name="chỉ số", value_name="giá trị")
        st.altair_chart(alt.Chart(long).mark_bar().encode(
            x=alt.X("chỉ số:N", title=None), xOffset="method:N",
            y=alt.Y("giá trị:Q", title=None), color=alt.Color("method:N", title="Phương pháp"),
            tooltip=["method", "chỉ số", alt.Tooltip("giá trị:Q", format=".3f")],
        ).properties(height=300), use_container_width=True)
