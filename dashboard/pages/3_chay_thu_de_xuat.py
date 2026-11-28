"""
dashboard/pages/3_chay_thu_de_xuat.py
-------------------------------------

CHỨC NĂNG :
    TRANG 3 — Chạy thử đề xuất của LLM trên validation lab 3309: tạo index INVISIBLE tạm
    và/hoặc chạy SQL viết lại, đo trước/sau (ms), kiểm hash kết quả, rồi tự xóa index thử.

PHỤ TRÁCH  : Tình · Vũ    |    REVIEW: Hải

LƯU Ý:
    - Chạy ở tiến trình riêng (scripts/lab_demo_runner.py) nên trang không bị đứng.
    - Đo nhanh = 1 warm-up + 3 lượt (minh họa); Đo đầy đủ = 3 warm-up + 20 lượt (chính thức).
    - Phép đo ở đây không cấp token; muốn áp dụng index phải qua trang 6.
"""

import sys
from pathlib import Path

import streamlit as st

_ROOT = str(Path(__file__).resolve().parents[2])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from dashboard.backend import DEFAULT_STORE_PATH, initialize_backend
from dashboard.journey import get_journey, job_id_for, record_job
from dashboard.lab_jobs import job_status, lab_port_open, running_job_ids, start_job
from dashboard.render import render_measure_result

NEXT_PAGE = "pages/4_so_sanh.py"
MODE_LABELS = {
    "fast": "Thử siêu nhanh (1 lượt trước + 1 lượt sau) — ~10–60 giây, chỉ để demo",
    "quick": "Đo nhanh (1 warm-up + 5 lượt) — vài phút, chỉ để minh họa",
    "full": "Đo đầy đủ (3 warm-up + 20 lượt) — chính thức, có thể 15–20 phút",
}


@st.fragment(run_every=3)
def _job_panel(job_id: str) -> None:
    status = job_status(job_id)
    flag = f"job_prev_{job_id}"
    if status["state"] == "running":
        st.session_state[flag] = "running"
        st.info(f"⏳ Đang đo trên lab ({status['elapsed_s']:.0f} giây): "
                f"{status['progress'] or 'đang khởi động'}")
        return
    if st.session_state.get(flag) == "running":
        st.session_state[flag] = status["state"]
        st.rerun()
    if status["state"] == "failed":
        st.error("Tiến trình đo kết thúc bất thường. Xem runner.log trong "
                 "data/outputs/dashboard_jobs/.")
    else:
        render_measure_result(status["result"])


st.title("3. Chạy thử đề xuất của LLM")

journey = get_journey(st.session_state)
if not journey:
    st.info("Chưa chọn query. Hãy làm bước 1 (Chọn query chậm).")
    st.stop()
if not journey["proposal_ids"]:
    st.info("Query này chưa có đề xuất LLM. Hãy làm bước 2 (LLM đề xuất).")
    st.stop()

try:
    if "proposal_store" not in st.session_state:
        st.session_state["proposal_store"] = initialize_backend()
    store = st.session_state["proposal_store"]
    saved = [item for item in store.recent_proposals()
             if item["proposal_id"] in set(journey["proposal_ids"])]
except Exception:  # noqa: BLE001
    st.error("Không đọc được đề xuất từ store. Kiểm tra backend.")
    st.stop()

st.write("**Query:**", journey["query_id"])
st.subheader("Sẽ chạy thử những gì?")
for item in reversed(saved):
    proposal = item["proposal"]
    if proposal.get("type") == "index":
        columns = ", ".join(c.get("name", "?") for c in proposal.get("columns", []))
        st.markdown(f"- Tạo index tạm `{proposal.get('table')}({columns})`")
    else:
        st.markdown("- Chạy SQL viết lại của LLM (so với SQL gốc)")
        if proposal.get("rewritten_sql"):
            st.code(proposal["rewritten_sql"], language="sql")

lab_up = lab_port_open(3309)
if not lab_up:
    st.error("Chưa kết nối được validation lab 127.0.0.1:3309. Bật container bằng lệnh: "
             "`docker start mcp_validation_lab_db` rồi đợi khoảng 30 giây.")

mode = st.radio("Chế độ đo", list(MODE_LABELS), format_func=MODE_LABELS.get, key="trial_mode")
confirmed = st.checkbox("Tôi xác nhận tạo index INVISIBLE tạm trên lab 3309 (DB chính 3307 không bị đổi)")
busy = bool(running_job_ids())
if busy:
    st.warning("Đang có một phép đo chạy trên lab. Hãy đợi nó xong.")
if st.button("▶ Chạy thử đề xuất LLM trên lab", type="primary",
             disabled=not (lab_up and confirmed) or busy):
    try:
        job_id = start_job(
            "llm", query_id=journey["query_id"], sql=journey["sql"], mode=mode,
            proposal_ids=journey["proposal_ids"], store_path=DEFAULT_STORE_PATH,
        )
    except Exception as exc:  # noqa: BLE001
        st.error(f"Không khởi động được phép đo: {type(exc).__name__}")
    else:
        record_job(st.session_state, "llm", job_id)
        st.rerun()

job_id = job_id_for(st.session_state, "llm")
if job_id:
    st.divider()
    st.subheader("Kết quả đo trên lab")
    _job_panel(job_id)
    if st.button("Tiếp theo: so sánh với baseline →", key="goto_compare"):
        st.switch_page(NEXT_PAGE)
else:
    st.info("Chưa chạy thử. Chọn chế độ đo, tick xác nhận rồi bấm ▶ Chạy thử.")
