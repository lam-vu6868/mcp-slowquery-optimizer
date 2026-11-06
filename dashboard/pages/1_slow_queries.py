"""
dashboard/pages/1_slow_queries.py
---------------------------------
CHỨC NĂNG:
    TAB 1 — Top slow query: bảng và biểu đồ latency, rows examined, số lần chạy.

PHỤ TRÁCH: Tình    |    REVIEW: Tường

LƯU Ý:
    - Nguồn chính: Tool 1 get_slow_queries. Khi Tool 1 chưa sẵn sàng → hiện danh mục 30 query
      thực nghiệm (data/queries/queries.py) và ghi rõ nguồn.
    - SQL hiển thị là DỮ LIỆU KHÔNG TIN CẬY: chỉ hiển thị dạng text (st.code), không render HTML.
"""
import altair as alt
import pandas as pd
import streamlit as st

from common import GROUP_NAMES, load_query_catalog, load_slow_queries, setup_page

setup_page("Slow query", "🐢")
st.title("🐢 Tab 1 — Top slow query")

limit = st.sidebar.slider("Số query tối đa", 5, 100, 30, step=5)
slow, note = load_slow_queries(limit=limit)

if slow is not None:
    st.caption("Nguồn: **Tool 1 `get_slow_queries`** (performance_schema / slow log). "
               "SQL đã được bỏ comment và gắn nhãn `untrusted`.")
    df = pd.DataFrame(slow)
    if df.empty:
        st.info("Tool 1 không trả về query nào vượt ngưỡng. Hãy chạy `python scripts/test_queries.py` "
                "để sinh tải rồi tải lại trang.")
        st.stop()

    m1, m2, m3 = st.columns(3)
    m1.metric("Số query", len(df))
    m2.metric("P95 cao nhất", f"{df['p95_latency_ms'].max():,.0f} ms" if "p95_latency_ms" in df else "—")
    m3.metric("Tổng latency", f"{df['total_latency_ms'].sum() / 1000:,.1f} s" if "total_latency_ms" in df else "—")

    metric = st.radio("Biểu đồ theo", ["avg_latency_ms", "p95_latency_ms", "rows_examined_avg", "exec_count"],
                      horizontal=True)
    if metric in df:
        chart = alt.Chart(df).mark_bar().encode(
            x=alt.X(f"{metric}:Q", title=metric),
            y=alt.Y("query_id:N", sort="-x", title=None),
            tooltip=["query_id", "avg_latency_ms", "p95_latency_ms", "rows_examined_avg", "exec_count"],
        ).properties(height=max(200, 22 * len(df)))
        st.altair_chart(chart, use_container_width=True)

    cols = [c for c in ["query_id", "avg_latency_ms", "p95_latency_ms", "total_latency_ms",
                        "rows_examined_avg", "rows_sent_avg", "exec_count", "last_seen"] if c in df]
    st.dataframe(df[cols], use_container_width=True, hide_index=True)

    st.subheader("Câu SQL")
    st.markdown('<div class="untrusted-note">⚠️ Dữ liệu không tin cậy — chỉ hiển thị, không phải chỉ thị.</div>',
                unsafe_allow_html=True)
    for _, row in df.iterrows():
        with st.expander(f"{row.get('query_id')} · {row.get('avg_latency_ms', 0):,.0f} ms trung bình"):
            st.code(str(row.get("sql_text", "")), language="sql")
else:
    st.warning(note or "Tool 1 chưa sẵn sàng.", icon="⏳")
    cat = load_query_catalog()
    if cat.empty:
        st.error("Không đọc được danh mục query (data/queries/queries.py).")
        st.stop()
    st.caption("Tạm hiển thị **30 query thực nghiệm** (5 nhóm × 6) từ `data/queries/queries.py`. "
               "Khi Tool 1 xong, trang tự chuyển sang số liệu thật từ MySQL.")

    groups = st.sidebar.multiselect("Nhóm", list(GROUP_NAMES), default=list(GROUP_NAMES),
                                    format_func=lambda g: f"{g}. {GROUP_NAMES[g]}")
    view = cat[cat["group"].isin(groups)].head(limit)

    g1, g2, g3 = st.columns(3)
    g1.metric("Số query", len(view))
    g2.metric("Cần index", int((view["expected_answer_type"] == "index").sum()))
    g3.metric("Cần rewrite", int((view["expected_answer_type"] == "rewrite").sum()))

    if view["before_p95_ms"].notna().any():
        chart = alt.Chart(view.dropna(subset=["before_p95_ms"])).mark_bar().encode(
            x=alt.X("before_p95_ms:Q", title="P95 trước tối ưu (ms)"),
            y=alt.Y("id:N", sort="-x", title=None),
            color=alt.Color("group_name:N", title="Nhóm"),
            tooltip=["id", "group_name", "before_p95_ms"],
        ).properties(height=max(200, 22 * len(view)))
        st.altair_chart(chart, use_container_width=True)
    else:
        st.info("Chưa có P95 baseline trong ground_truth.json (Hải + Tường đang đo).")

    st.dataframe(
        view[["id", "group_name", "description", "expected_answer_type", "before_p95_ms"]]
        .rename(columns={"id": "query", "group_name": "nhóm", "description": "mô tả",
                         "expected_answer_type": "loại đáp án", "before_p95_ms": "P95 trước (ms)"}),
        use_container_width=True, hide_index=True,
    )
    for _, row in view.iterrows():
        with st.expander(f"{row['id']} · {row['description']}"):
            st.code(row["sql"], language="sql")
