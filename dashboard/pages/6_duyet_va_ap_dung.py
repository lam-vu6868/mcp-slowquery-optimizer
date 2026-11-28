"""
dashboard/pages/6_duyet_va_ap_dung.py
-------------------------------------

CHỨC NĂNG :
    TRANG 6 — Duyệt & áp dụng (Human-in-the-loop): chạy Validation chính thức
    (INVISIBLE INDEX trên lab 3309 + đo chi phí ghi trên write lab 3308), xem trade-off,
    sau đó bấm Approve (sinh approval token 1 lần gọi Tool 6) hoặc Reject (xóa index thử).

PHỤ TRÁCH  : Tình    |    REVIEW: Vũ + Hải

LƯU Ý:
    - Đề xuất 'rewrite' chỉ hiển thị, KHÔNG có nút Apply.
    - Chỉ cho Approve khi validation_report.status == 'passed' và còn hạn 24h.
    - Ô "Thư mục CSV cho write lab" điền sẵn D:\\labt2\\data trong mục Nâng cao.
"""

import asyncio
import math
import sys
import time
from pathlib import Path

import streamlit as st

_ROOT = str(Path(__file__).resolve().parents[2])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from dashboard.backend import (
    apply_from_dashboard,
    initialize_backend,
    reject_from_dashboard,
    validate_from_dashboard,
)
from dashboard.lab_jobs import lab_port_open
from dashboard.lab_session import lab_session

DEFAULT_CSV_DIR = r"D:\labt2\data"

st.title("6. Duyệt & áp dụng (Human-in-the-loop)")

try:
    if "proposal_store" not in st.session_state:
        st.session_state["proposal_store"] = initialize_backend()
    store = st.session_state["proposal_store"]
    proposals = store.recent_proposals()
except Exception:  # noqa: BLE001 - không cho thao tác khi store/recovery lỗi
    st.error("Không đọc được đề xuất hoặc khôi phục index thử. Kiểm tra backend.")
    st.stop()

notice = st.session_state.pop("proposal_notice", None)
if notice:
    st.success(notice)

if not proposals:
    st.info("Chưa có đề xuất trong store cục bộ. Hãy tạo đề xuất ở bước 2 (LLM đề xuất).")
    st.stop()

by_id = {item["proposal_id"]: item for item in proposals}
proposal_id = st.selectbox(
    "Chọn đề xuất", list(by_id),
    format_func=lambda value: f"{by_id[value]['query_id']} · {value}",
)
saved = by_id[proposal_id]
proposal = saved["proposal"]
report = saved.get("report") or {}

st.write("Trạng thái trial:", saved["trial_state"])
st.write("Loại đề xuất:", proposal["type"])
if proposal["type"] == "index":
    st.write("Index:", f"{proposal['table']}.{proposal['index_name']}")
st.write("Validation:", report.get("status", "chưa chạy"))
st.code(saved["original_sql"], language="sql")

if report:
    st.subheader("Số liệu Validation")
    before = report.get("before") or {}
    after = report.get("after") or {}
    write = report.get("write_overhead") or {}
    p95_before = before.get("p95_ms")
    p95_after = after.get("p95_ms")
    if all(type(value) in (int, float) and math.isfinite(value)
           for value in (p95_before, p95_after)):
        before_col, after_col = st.columns(2)
        before_col.metric("P95 trước", f"{p95_before:.2f} ms")
        after_col.metric("P95 sau", f"{p95_after:.2f} ms")
    throughput = write.get("insert_throughput_change_pct")
    size_bytes = write.get("index_size_bytes")
    if type(throughput) in (int, float) and math.isfinite(throughput):
        st.metric("Thay đổi thông lượng INSERT", f"{throughput:+.2f}%")
    if type(size_bytes) in (int, float) and math.isfinite(size_bytes):
        st.metric("Dung lượng index thử (ước tính)", f"{size_bytes / 1048576:.2f} MiB")
    sample_rows = write.get("sample_rows")
    if type(sample_rows) is int:
        st.caption(f"Mẫu INSERT: {sample_rows:,} dòng trên write lab; report này chưa gồm UPDATE hoặc tải đồng thời.")
    if type(report.get("result_equivalent")) is bool:
        st.text("Kết quả tương đương: " + ("có" if report["result_equivalent"] else "không"))
    st.text("Bằng chứng đầy đủ: " + ("có" if report.get("evidence_complete") is True else "chưa"))

if proposal["type"] != "index":
    st.info("Đề xuất viết lại SQL chỉ để xem; không áp dụng tự động.")
    st.stop()

if saved["trial_state"] == "new":
    st.warning("Validation chính thức sẽ tạo index INVISIBLE trên lab 3309 và đo chi phí ghi trên write lab 3308.")
    if not lab_port_open(3309) or not lab_port_open(3308):
        st.caption("Cần bật cả 2 container lab: `docker start mcp_validation_lab_db mcp_write_lab_db`.")
    with st.expander("Nâng cao (Thư mục CSV cho write lab)", expanded=False):
        csv_dir = st.text_input(
            "Thư mục CSV cho write lab",
            value=DEFAULT_CSV_DIR,
            key=f"csv_dir_{proposal_id}",
        )
    confirmed = st.checkbox("Tôi xác nhận chạy Validation trên lab", key=f"validate_{proposal_id}")
    if st.button("Chạy Validation", disabled=not (confirmed and csv_dir.strip())):
        try:
            with lab_session():
                result = asyncio.run(validate_from_dashboard(
                    store, proposal_id, write_csv_dir=Path(csv_dir),
                ))
        except Exception:  # noqa: BLE001 - không hiển thị SQL/chi tiết DB nội bộ
            st.error("Validation không chạy được. Kiểm tra lab 3309, write lab 3308 và thư mục CSV.")
        else:
            st.session_state["proposal_notice"] = f"Validation: {result['status']}"
            st.rerun()
    st.stop()

expires_at = saved.get("review_expires_at")
if type(expires_at) is int:
    st.write("Hạn duyệt:", time.strftime("%d/%m/%Y %H:%M:%S", time.localtime(expires_at)))

can_act = saved["trial_state"] == "passed" and report.get("status") == "passed"
can_approve = (can_act and report.get("evidence_complete") is True
               and type(expires_at) is int and expires_at > int(time.time()))
if can_act:
    st.warning("Approve sẽ chuyển index thử thành VISIBLE; Reject sẽ xóa index thử trên MySQL.")
    confirmed = st.checkbox("Tôi xác nhận thao tác trên MySQL", key=f"confirm_{proposal_id}")
    approve_col, reject_col = st.columns(2)
    if approve_col.button("Approve", disabled=not (confirmed and can_approve)):
        try:
            with lab_session():
                asyncio.run(apply_from_dashboard(store, proposal_id))
        except Exception:  # noqa: BLE001 - backend giữ chi tiết trong audit
            st.error("Không áp dụng được đề xuất. Kiểm tra audit và trạng thái index.")
        else:
            st.session_state["proposal_notice"] = "Đã áp dụng index."
            st.rerun()
    if reject_col.button("Reject", disabled=not confirmed):
        try:
            with lab_session():
                reject_from_dashboard(store, proposal_id)
        except Exception:  # noqa: BLE001 - không báo đã dọn khi DDL lỗi
            st.error("Không dọn được index thử. Kiểm tra trial pending.")
        else:
            st.session_state["proposal_notice"] = "Đã dọn index thử."
            st.rerun()
elif saved["trial_state"] == "passed":
    st.info("Report chưa đủ điều kiện thao tác; kiểm tra Validation.")
