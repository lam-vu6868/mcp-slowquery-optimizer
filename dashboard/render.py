"""
dashboard/render.py
-------------------

CHỨC NĂNG : Hàm hiển thị dùng chung cho các trang: kết quả đo trước/sau trên lab và
            bảng so sánh của "hành trình query".
PHỤ TRÁCH  : Tình    |    REVIEW: Tường
LƯU Ý      : Chỉ hiển thị số đã đo thật; thiếu số liệu thì ghi "chưa chạy" thay vì số giả.
"""

import streamlit as st

from dashboard.journey import improvement_pct

FAILURE_TEXT = {
    "p95_below_threshold": "Không đạt: P95 không giảm đủ 20% so với query gốc.",
    "result_changed": "Không đạt: kết quả khác query gốc (hash lệch) nên bị chặn.",
    "measurement_incomplete": "Chưa kết luận: thiếu lượt đo hoặc có lượt bị timeout.",
    "measurement_error": "Chưa kết luận: lỗi khi đo (đã tự dọn index thử).",
    "ast_rejected": "SQL không qua AST whitelist.",
    "cleanup_failed": "Cảnh báo: dọn index thử lỗi, cần kiểm tra lab.",
    "proposal_context_invalid": "Đề xuất không hợp lệ để đo.",
    "no_proposal": "Không có đề xuất index/rewrite nào để đo.",
    "runner_error": "Tiến trình đo bị lỗi; xem log trong data/outputs/dashboard_jobs/.",
}


def _fmt_ms(value) -> str:
    return f"{value:,.2f} ms" if type(value) in (int, float) else "chưa có"


def describe_result(result: dict) -> str:
    """Mô tả ngắn phương án đã đo: index và/hoặc viết lại SQL."""
    parts = [f"Index {item['table']}({', '.join(item['columns'])})"
             for item in result.get("indexes", [])]
    if result.get("rewrite_changed"):
        parts.append("viết lại SQL")
    return " + ".join(parts) if parts else "không có đề xuất"


def render_measure_result(result: dict) -> None:
    """Hiển thị 1 kết quả đo (LLM hoặc baseline) với đầy đủ nhãn trung thực."""
    status = result.get("status")
    if status == "error":
        st.error(FAILURE_TEXT["runner_error"] + f" ({result.get('error_type')})")
        return
    if status == "no_proposal":
        st.warning(FAILURE_TEXT["no_proposal"])
        greedy = result.get("greedy")
        if greedy:
            st.caption(f"Greedy không tìm được index giảm cost ≥ 5% "
                       f"(cost {greedy['baseline_cost']:,.2f}).")
        return

    before, after = result.get("before") or {}, result.get("after") or {}
    is_fast = result.get("mode") == "fast"
    st.write("**Phương án đã đo:**", describe_result(result))
    c1, c2, c3 = st.columns(3)
    c1.metric("Thời gian trước (1 lượt)" if is_fast else "P95 trước", _fmt_ms(before.get("p95_ms")))
    c2.metric("Thời gian sau (1 lượt)" if is_fast else "P95 sau", _fmt_ms(after.get("p95_ms")))
    gain = improvement_pct(before.get("p95_ms"), after.get("p95_ms"))
    c3.metric("Mức giảm" if is_fast else "Mức giảm P95",
              f"{gain:+.2f}%" if gain is not None else "chưa có")
    d1, d2, d3 = st.columns(3)
    d1.metric("Số dòng phải quét (trước)", f"{before.get('rows_examined', 0):,}")
    d2.metric("Số dòng phải quét (sau)", f"{after.get('rows_examined', 0):,}")
    same = (before.get("result_hash") is not None
            and before.get("result_hash") == after.get("result_hash")
            and before.get("row_count") == after.get("row_count"))
    d3.metric("Kết quả giống query gốc", "Có (hash khớp)" if same else "Không / chưa rõ")

    usage = result.get("index_usage") or {}
    if usage:
        st.write("**Index có được MySQL dùng khi chạy không:**")
        st.dataframe([{"Index": name, "Được dùng": "✅ Có" if used else "❌ Không"}
                      for name, used in usage.items()], hide_index=True, width="stretch")

    runs = result.get("measured_runs")
    mode_text = ("Đo đầy đủ" if result.get("official")
                 else ("Thử siêu nhanh (1 lượt)" if is_fast else "Đo nhanh"))
    st.caption(f"{mode_text}: {runs} lượt đo mỗi phía, mất {result.get('elapsed_s')} giây. "
               "Index thử là INVISIBLE trên lab 3309 và đã được xóa sau khi đo.")
    if not result.get("official"):
        st.warning(f"{mode_text} chỉ để minh họa — chưa phải kết quả chính thức "
                   "(chính thức cần 3 warm-up + 20 lượt).")
    if status == "passed":
        st.success("Đạt: kết quả đúng và thời gian giảm ≥ 20%." if is_fast
                   else "Đạt: kết quả đúng và P95 giảm ≥ 20%.")
    else:
        st.error(FAILURE_TEXT.get(result.get("failure_reason"), "Không đạt."))
