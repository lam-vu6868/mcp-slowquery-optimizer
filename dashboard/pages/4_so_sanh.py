"""
dashboard/pages/4_so_sanh.py
----------------------------

CHỨC NĂNG :
    TRANG 4 — So sánh trực tiếp (live). Tab 1 so query VỪA CHẠY (gốc vs LLM vs Greedy,
    mỗi bên có nút chạy thật). Tab 2 so sánh khâu phát hiện: pt-query-digest vs Tool 1.
    Phần báo cáo tổng kết 30 query & chỉ số LLM nằm ở Trang 7.

PHỤ TRÁCH  : Tình · Tường    |    REVIEW: Hải

LƯU Ý:
    - 2 baseline: Greedy (chọn index theo EXPLAIN cost) và pt-query-digest (phát hiện).
    - pt-query-digest không đề xuất index nên không nằm trong bảng Precision/Recall.
"""

import asyncio
import sys
from pathlib import Path

import streamlit as st

_ROOT = str(Path(__file__).resolve().parents[2])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from dashboard.backend import DEFAULT_STORE_PATH, load_slow_queries
from dashboard.detection import (
    detection_comparison,
    export_slow_log,
    measure_tool1_ms,
    run_pt,
)
from dashboard.journey import (
    build_live_comparison,
    get_journey,
    job_id_for,
    record_job,
)
from dashboard.lab_jobs import job_status, lab_port_open, running_job_ids, start_job
from dashboard.render import render_measure_result

ROOT = Path(_ROOT)
SLOW_EXPORT = ROOT / "data" / "outputs" / "dashboard_jobs" / "slow_log_export.log"


def _result_for(source: str) -> dict | None:
    job_id = job_id_for(st.session_state, source)
    if not job_id:
        return None
    status = job_status(job_id)
    return status["result"] if status["state"] == "done" else None


@st.fragment(run_every=3)
def _greedy_panel(job_id: str) -> None:
    status = job_status(job_id)
    flag = f"job_prev_{job_id}"
    if status["state"] == "running":
        st.session_state[flag] = "running"
        st.info(f"⏳ Greedy đang chạy ({status['elapsed_s']:.0f} giây): "
                f"{status['progress'] or 'đang khởi động'}")
        return
    if st.session_state.get(flag) == "running":
        st.session_state[flag] = status["state"]
        st.rerun()
    if status["state"] == "failed":
        st.error("Tiến trình Greedy kết thúc bất thường. Xem runner.log.")
    else:
        render_measure_result(status["result"])


st.title("4. So sánh với Baseline")
tab_live, tab_detect = st.tabs([
    "Query vừa chạy (gốc vs LLM vs Greedy)",
    "Phát hiện query chậm (pt-query-digest vs Tool 1)",
])

with tab_live:
    journey = get_journey(st.session_state)
    if not journey:
        st.info("Chưa có query nào. Hãy làm bước 1, 2, 3 trước.")
    else:
        st.write("**Query:**", journey["query_id"])
        llm_result, greedy_result = _result_for("llm"), _result_for("greedy")
        if llm_result is None:
            st.warning("Chưa có kết quả LLM. Hãy chạy thử đề xuất LLM ở bước 3.")

        st.subheader("Baseline Greedy (thuật toán chọn index theo EXPLAIN cost)")
        st.caption("Greedy thử từng cột, hỏi MySQL EXPLAIN xem index nào giảm cost nhiều nhất, "
                   "rồi được đo trước/sau trên cùng lab để so công bằng với LLM.")
        lab_up = lab_port_open(3309)
        if not lab_up:
            st.error("Chưa kết nối được lab 3309. Chạy: `docker start mcp_validation_lab_db`.")
        mode = st.radio(
            "Chế độ đo Greedy", ["fast", "quick", "full"], key="greedy_mode",
            format_func=lambda m: {
                "fast": "Thử siêu nhanh (1 lượt trước + 1 lượt sau) — chỉ để demo",
                "quick": "Đo nhanh (1 warm-up + 5 lượt)",
                "full": "Đo đầy đủ (3 warm-up + 20 lượt)",
            }[m],
        )
        busy = bool(running_job_ids())
        if busy:
            st.warning("Đang có một phép đo chạy trên lab. Hãy đợi nó xong.")
        if st.button("▶ Chạy baseline Greedy cho query này", type="primary",
                     disabled=not lab_up or busy):
            try:
                job_id = start_job("greedy", query_id=journey["query_id"],
                                   sql=journey["sql"], mode=mode, store_path=DEFAULT_STORE_PATH)
            except Exception as exc:  # noqa: BLE001
                st.error(f"Không khởi động được Greedy: {type(exc).__name__}")
            else:
                record_job(st.session_state, "greedy", job_id)
                st.rerun()
        greedy_job = job_id_for(st.session_state, "greedy")
        if greedy_job:
            _greedy_panel(greedy_job)

        st.divider()
        st.subheader("Bảng so sánh (chỉ gồm những gì đã chạy thật)")
        rows = build_live_comparison(journey, {"llm": llm_result, "greedy": greedy_result})
        st.dataframe(rows, hide_index=True, width="stretch")
        chart = {row["Phương pháp"]: {"P95 trước (ms)": row["P95 trước (ms)"],
                                      "P95 sau (ms)": row["P95 sau (ms)"]}
                 for row in rows
                 if isinstance(row["P95 trước (ms)"], (int, float))
                 and isinstance(row["P95 sau (ms)"], (int, float))}
        if chart:
            st.bar_chart({"Phương pháp": list(chart),
                          "P95 trước (ms)": [v["P95 trước (ms)"] for v in chart.values()],
                          "P95 sau (ms)": [v["P95 sau (ms)"] for v in chart.values()]},
                         x="Phương pháp", y=["P95 trước (ms)", "P95 sau (ms)"])

with tab_detect:
    st.write("Cùng một DB, **pt-query-digest** đọc slow log (xuất từ `mysql.slow_log`) còn "
             "**Tool 1** của hệ thống đọc nguồn bạn chọn. Hai bên có xếp hạng top query giống nhau không?")
    source = st.selectbox("Nguồn của Tool 1", ["performance_schema", "slow_log"], key="det_source")
    if st.button("▶ So sánh pt-query-digest vs Tool 1", key="det_run"):
        with st.spinner("Đang xuất slow log, chạy pt-query-digest và Tool 1..."):
            try:
                exported = export_slow_log(SLOW_EXPORT)
                if exported == 0:
                    raise ValueError("mysql.slow_log chưa có bản ghi nào")
                pt_result = run_pt(SLOW_EXPORT, limit=10)
                tool1_limit = 100 if source == "slow_log" else 10
                tool1_rows, tool1_ms = measure_tool1_ms(
                    lambda: asyncio.run(load_slow_queries(source, limit=tool1_limit)))
                st.session_state["detection_result"] = {
                    "exported": exported, "pt_engine": pt_result["engine"],
                    **detection_comparison(tool1_rows, pt_result, tool1_ms=tool1_ms),
                }
            except Exception as exc:  # noqa: BLE001
                st.error(f"Không so sánh được: {type(exc).__name__}. "
                         "Kiểm tra quyền đọc mysql.slow_log và nguồn đã chọn.")
    found = st.session_state.get("detection_result")
    if not found:
        st.info("Chưa chạy so sánh phát hiện. Bấm nút ở trên.")
    else:
        summary = found["summary"]
        st.caption(f"Đã xuất {found['exported']} bản ghi slow log. Công cụ: **{found['pt_engine']}** "
                   "(nếu máy chưa cài pt-query-digest thì dùng parser Python cùng định dạng).")
        a, b, c, d = st.columns(4)
        a.metric("Query trùng trong top 10", summary["overlap_count"])
        b.metric("Độ giống (Jaccard)", f"{summary['jaccard_similarity']:.2%}")
        c.metric("pt-query-digest (ms)", summary.get("pt_duration_ms"))
        d.metric("Tool 1 (ms)", summary.get("tool1_duration_ms"))
        left, right = st.columns(2)
        left.write("**Top query theo pt-query-digest**")
        left.dataframe(found["pt"], hide_index=True, width="stretch")
        right.write("**Top query theo Tool 1**")
        right.dataframe(found["tool1"], hide_index=True, width="stretch")
