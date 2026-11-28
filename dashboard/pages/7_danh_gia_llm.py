"""
dashboard/pages/7_danh_gia_llm.py
---------------------------------

CHỨC NĂNG :
    TRANG 7 — Đánh giá LLM & Tổng kết 30 query: hiển thị trọn bộ chỉ số định lượng
    (Precision, Recall, False Positive Rate, Consistency Rate 5 lần lặp), bảng so sánh
    LLM vs Greedy (tiếng Việt), nút đo live Consistency Rate 5 lần, và biểu đồ 12 query Rewrite.

PHỤ TRÁCH  : Tường · Tình    |    REVIEW: Hải

LƯU Ý:
    - Bảng tổng kết đọc từ data/metrics/comparison.csv và data/outputs/ (đã đo trước).
    - Nút đo live Consistency Rate gọi LLM qua MCP Tool 1–5 chỉ đọc (không tạo DDL).
"""

import asyncio
import csv
import json
import sys
from pathlib import Path

import streamlit as st

_ROOT = str(Path(__file__).resolve().parents[2])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from data.metrics.metrics import (
    compute_consistency_rate,
    compute_false_positive_rate,
    summarize_rewrite_reports,
)
from data.queries.queries import QUERIES
from mcp_server.llm.agent import analyze_query
from mcp_server.llm.groq import create_llm_client

ROOT = Path(_ROOT)
COMPARISON_CSV = ROOT / "data" / "metrics" / "comparison.csv"
REWRITE_REPORT_DIR = ROOT / "data" / "outputs" / "llm_catalog_20261127"
CONSISTENCY_JSON = ROOT / "data" / "outputs" / "consistency_5runs.json"

METHOD_NAMES = {
    "llm_groq_mcp": "LLM + MCP (Hệ thống của đề tài)",
    "greedy": "Baseline Greedy (Thuật toán tham lam)",
}
STATUS_VN = {
    "passed": "✅ Đạt",
    "failed": "❌ Không đạt",
    "inconclusive": "⚠️ Chưa kết luận",
}
REASON_VN = {
    "p95_below_threshold": "P95 không giảm đủ 20%",
    "result_changed": "Kết quả khác query gốc (lệch hash)",
    "measurement_error": "Quá thời gian / lỗi khi đo",
    "measurement_incomplete": "Thiếu lượt đo hoặc timeout",
}


def _fmt_pct(value) -> str:
    try:
        return f"{float(value) * 100:.2f}%"
    except (TypeError, ValueError):
        return "chưa có"


def _describe_proposals(proposals: list[dict]) -> str:
    parts: list[str] = []
    for p in proposals:
        if p.get("type") == "index":
            cols = ", ".join(c.get("name", "?") for c in p.get("columns", []) if isinstance(c, dict))
            parts.append(f"Index {p.get('table')}({cols})")
        elif p.get("type") == "rewrite":
            parts.append("Viết lại SQL")
    return " + ".join(parts) if parts else "(không có đề xuất)"


def _unwrap_error(exc: BaseException) -> BaseException:
    while isinstance(exc, BaseExceptionGroup) and exc.exceptions:
        exc = exc.exceptions[0]
    return exc


async def _run_consistency_async(query_id: str, sql: str, runs: int, on_step) -> dict:
    client = create_llm_client()
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "mcp_server.server"], cwd=str(ROOT),
    )
    all_runs: list[list[dict]] = []
    details: list[dict] = []
    try:
        async with (
            stdio_client(params) as (read_stream, write_stream),
            ClientSession(read_stream, write_stream) as session,
        ):
            await session.initialize()
            for idx in range(1, runs + 1):
                if idx > 1:
                    await asyncio.sleep(18)
                for attempt in range(4):
                    try:
                        res = await analyze_query(
                            query_id, sql, llm_client=client, mcp_client=session,
                        )
                        break
                    except Exception as exc:  # retry khi gặp 429 TPM hoặc tool_use_failed
                        err_name = type(_unwrap_error(exc)).__name__
                        if err_name not in ("RateLimitError", "BadRequestError") or attempt == 3:
                            raise
                        await asyncio.sleep(20)
                proposals = res.get("proposals") or []
                all_runs.append(proposals)
                details.append({
                    "Lần chạy": idx,
                    "Số đề xuất": len(proposals),
                    "Phương án LLM đưa ra": _describe_proposals(proposals),
                    "Độ tin cậy": res.get("confidence", ""),
                })
                on_step(idx, runs)
    finally:
        await client.close()
    summary = compute_consistency_rate(all_runs)
    return {"query_id": query_id, **summary, "details": details}


def _run_consistency_live(query_id: str, sql: str, runs: int = 5) -> dict:
    bar = st.progress(0, text=f"Đang chạy lặp 0/{runs} cho {query_id}...")
    return asyncio.run(_run_consistency_async(
        query_id, sql, runs,
        on_step=lambda i, n: bar.progress(i / n, text=f"Hoàn tất lần {i}/{n} cho {query_id}"),
    ))


st.title("7. Đánh giá LLM & Tổng kết 30 query")

# --- 1. Đọc dữ liệu tổng hợp ---
saved_rows: list[dict] = []
if COMPARISON_CSV.is_file():
    with COMPARISON_CSV.open(encoding="utf-8", newline="") as fh:
        saved_rows = list(csv.DictReader(fh))

llm_row = next((r for r in saved_rows if r.get("method") == "llm_groq_mcp"), {})
llm_total = int(llm_row.get("index_proposals") or 0)
llm_exact = int(llm_row.get("exact_index_matches") or 0)
llm_fpr = compute_false_positive_rate(llm_total, llm_exact)

saved_consistency = (
    json.loads(CONSISTENCY_JSON.read_text(encoding="utf-8"))
    if CONSISTENCY_JSON.is_file()
    else None
)

# --- 2. 4 chỉ số đánh giá LLM ---
st.subheader("1. Chỉ số đánh giá chất lượng LLM")
m1, m2, m3, m4 = st.columns(4)
m1.metric("Độ chính xác (Precision)", _fmt_pct(llm_row.get("exact_precision")))
m2.metric("Độ phủ 18 câu index (Recall)", _fmt_pct(llm_row.get("exact_recall")))
m3.metric("Tỉ lệ index thừa/lệch (FPR)", _fmt_pct(llm_fpr))
avg_cons = (saved_consistency or {}).get("avg_consistency_rate")
m4.metric("Độ ổn định 5 lần (Consistency)", _fmt_pct(avg_cons))
st.caption(
    "Precision = số index khớp chính xác / tổng index đề xuất; "
    "Recall = tỉ lệ query nhóm index tìm đúng đáp án; "
    "FPR (False Positive Rate) = tỉ lệ index không khớp chính xác với ground truth; "
    "Consistency Rate = tỉ lệ lặp lại cùng phương án khi chạy lại 5 lần cùng 1 prompt."
)

# --- 3. Consistency Rate (chạy 5 lần lặp) ---
st.divider()
st.subheader("2. Độ ổn định Consistency Rate (chạy lại 5 lần cùng 1 prompt)")
if saved_consistency and saved_consistency.get("queries"):
    st.caption(
        f"Kết quả đã đo sẵn trên {len(saved_consistency['queries'])} query đại diện "
        f"(mỗi query chạy lặp {saved_consistency.get('runs_per_query', 5)} lần):"
    )
    st.dataframe([
        {
            "Mã query": item["query_id"],
            "Số lần chạy": item["runs"],
            "Lặp lại nhiều nhất": f"{item['most_common_count']}/{item['runs']}",
            "Consistency Rate": _fmt_pct(item["consistency_rate"]),
            "Phương án phổ biến nhất": item.get("top_proposal", ""),
        }
        for item in saved_consistency["queries"]
    ], hide_index=True, width="stretch")

with st.expander("Chạy thử Consistency Rate trực tiếp (5 lần lặp) cho 1 query bất kỳ"):
    pos = st.selectbox(
        "Chọn query để kiểm tra độ ổn định (5 lần gọi LLM chỉ đọc)",
        range(len(QUERIES)),
        format_func=lambda i: f"{QUERIES[i]['id']} — {QUERIES[i]['description']}",
        key="cons_query",
    )
    if st.button("▶ Chạy lặp 5 lần để đo Consistency Rate", type="primary"):
        item = QUERIES[pos]
        try:
            st.session_state["live_consistency"] = _run_consistency_live(item["id"], item["sql"], runs=5)
        except Exception as exc:  # noqa: BLE001
            inner = _unwrap_error(exc)
            if type(inner).__name__ == "RateLimitError":
                st.error("Groq Free Tier đang chạm giới hạn token/phút (429). "
                         "Hãy đợi khoảng 30–60 giây rồi bấm thử lại.")
            else:
                st.error(f"Không chạy được đo Consistency: {type(inner).__name__}")
    live_cons = st.session_state.get("live_consistency")
    if live_cons:
        c1, c2, c3 = st.columns(3)
        c1.metric("Query vừa đo", live_cons["query_id"])
        c2.metric("Consistency Rate", _fmt_pct(live_cons["consistency_rate"]))
        c3.metric("Lặp lại nhiều nhất", f"{live_cons['most_common_count']}/{live_cons['runs']}")
        st.dataframe(live_cons["details"], hide_index=True, width="stretch")

# --- 4. Bảng so sánh LLM vs Greedy (tiếng Việt) ---
st.divider()
st.subheader("3. Bảng so sánh tổng hợp LLM vs Baseline Greedy (trên 30 query)")
if saved_rows:
    vn_rows = []
    for row in saved_rows:
        total_idx = int(row.get("index_proposals") or 0)
        exact_idx = int(row.get("exact_index_matches") or 0)
        fpr = compute_false_positive_rate(total_idx, exact_idx)
        vn_rows.append({
            "Phương pháp": METHOD_NAMES.get(row.get("method", ""), row.get("method", "")),
            "Tổng index đề xuất": total_idx,
            "Khớp chính xác GT": exact_idx,
            "Precision": _fmt_pct(row.get("exact_precision")),
            "Recall": _fmt_pct(row.get("exact_recall")),
            "False Positive Rate": _fmt_pct(fpr),
            "Rewrite đạt": f"{row.get('rewrite_passed', 0)}/{row.get('rewrite_total', 12)}",
            "Tỉ lệ Rewrite đạt": _fmt_pct(row.get("rewrite_pass_rate")),
        })
    st.dataframe(vn_rows, hide_index=True, width="stretch")
    st.caption(
        "Lưu ý: Baseline pt-query-digest chỉ phát hiện query chậm (xem Trang 4 — Tab 2), "
        "không đề xuất index nên không nằm trong bảng Precision/Recall."
    )
else:
    st.info("Chưa có data/metrics/comparison.csv.")

# --- 5. Chi tiết & biểu đồ 12 query Rewrite ---
st.divider()
st.subheader("4. Kết quả đo P95 thực tế trên 12 query Rewrite (Nhóm 3 & Nhóm 5)")
summary = summarize_rewrite_reports(REWRITE_REPORT_DIR)
if summary["total"]:
    r1, r2, r3, r4 = st.columns(4)
    r1.metric("Tổng query Rewrite đã đo", summary["total"])
    r2.metric("Đạt", summary["passed"])
    r3.metric("Không đạt", summary["failed"])
    r4.metric("Tỉ lệ đạt", _fmt_pct(summary["pass_rate"]))
    st.dataframe([
        {
            "Mã query": item["query_id"],
            "Kết quả": STATUS_VN.get(item["status"], item["status"]),
            "Lý do (nếu không đạt)": REASON_VN.get(item["failure_reason"] or "", ""),
            "P95 trước (ms)": item["before_p95_ms"],
            "P95 sau (ms)": item["after_p95_ms"],
            "Giảm P95 (%)": item["p95_improvement_pct"],
            "Cost trước": item["before_cost"],
            "Cost sau": item["after_cost"],
            "Dòng quét trước": item["before_rows_examined"],
            "Dòng quét sau": item["after_rows_examined"],
        }
        for item in summary["items"]
    ], hide_index=True, width="stretch")
    chart_rows = [
        item for item in summary["items"]
        if item["before_p95_ms"] is not None and item["after_p95_ms"] is not None
    ]
    if chart_rows:
        st.bar_chart(
            {
                "query_id": [i["query_id"] for i in chart_rows],
                "P95 trước (ms)": [i["before_p95_ms"] for i in chart_rows],
                "P95 sau (ms)": [i["after_p95_ms"] for i in chart_rows],
            },
            x="query_id",
            y=["P95 trước (ms)", "P95 sau (ms)"],
        )
