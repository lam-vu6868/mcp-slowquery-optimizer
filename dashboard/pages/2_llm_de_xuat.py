"""
dashboard/pages/2_llm_de_xuat.py
--------------------------------

CHỨC NĂNG :
    TRANG 2 — Gửi query đang làm việc cho LLM (Groq qua MCP Tool 1–5, chỉ đọc) và xem
    đề xuất có cấu trúc: index và/hoặc viết lại SQL. Chưa chạy thử đề xuất ở trang này.

PHỤ TRÁCH  : Tình · Vũ    |    REVIEW: Tường

LƯU Ý:
    - Backend kiểm AST whitelist trước khi gọi API; LLM không thấy Tool 6.
    - Đề xuất viết lại SQL chỉ để xem/đo, không có đường tự áp dụng vào DB.
"""

import asyncio
import sys
from pathlib import Path

import streamlit as st

_ROOT = str(Path(__file__).resolve().parents[2])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from dashboard.backend import generate_proposals_from_dashboard, initialize_backend
from dashboard.journey import get_journey, record_proposals, select_query

NEXT_PAGE = "pages/3_chay_thu_de_xuat.py"

st.title("2. LLM phân tích và đề xuất")

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

selected_query_id = st.session_state.pop("analysis_query_id", None)
selected_sql = st.session_state.pop("analysis_sql", None)
if selected_query_id is not None and selected_sql is not None:
    st.session_state["proposal_query_id"] = selected_query_id
    st.session_state["proposal_sql"] = selected_sql
else:
    active_journey = get_journey(st.session_state)
    if active_journey and not st.session_state.get("proposal_query_id"):
        st.session_state["proposal_query_id"] = active_journey["query_id"]
        st.session_state["proposal_sql"] = active_journey["sql"]

st.subheader("Gửi query cho LLM")
query_id_input = st.text_input("Mã query", key="proposal_query_id")
sql_input = st.text_area("SQL cần phân tích", height=140, key="proposal_sql")
st.caption("LLM có thể gọi EXPLAIN/benchmark ở chế độ đọc. "
           "SQL từ performance_schema có thể cần thay dấu ? bằng giá trị cụ thể.")
confirmed_generation = st.checkbox("Tôi xác nhận gửi SQL tới LLM")
if st.button("Phân tích và lưu đề xuất", disabled=not (
    query_id_input.strip() and sql_input.strip() and confirmed_generation
)):
    try:
        with st.spinner("LLM đang đọc schema và phân tích (khoảng 10–60 giây)..."):
            created = asyncio.run(generate_proposals_from_dashboard(
                store, query_id_input.strip(), sql_input,
            ))
    except Exception:  # noqa: BLE001 - không hiển thị SQL hoặc nội dung lỗi API
        st.error("Không tạo được đề xuất. Kiểm tra SQL, cấu hình LLM/MCP và log lần chạy.")
    else:
        if created:
            select_query(st.session_state, query_id_input.strip(), sql_input, "manual")
            record_proposals(st.session_state, created)
            st.session_state["proposal_notice"] = f"Đã lưu {len(created)} đề xuất."
            st.rerun()
        else:
            st.info("LLM không đưa ra đề xuất cho query này.")

st.divider()
st.subheader("Đề xuất của LLM cho query đang làm việc")
journey = get_journey(st.session_state)
if not journey or not journey["proposal_ids"]:
    st.info("Chưa có đề xuất cho query đang làm việc. Hãy gửi query cho LLM ở trên.")
    st.stop()

wanted = set(journey["proposal_ids"])
current = [item for item in proposals if item["proposal_id"] in wanted]
st.write("**Query:**", journey["query_id"])
if not current:
    st.info("Không tìm thấy đề xuất trong store hiện tại.")
    st.stop()

for number, item in enumerate(reversed(current), start=1):
    proposal = item["proposal"]
    if proposal.get("type") == "index":
        columns = ", ".join(c.get("name", "?") for c in proposal.get("columns", []))
        st.markdown(f"**Đề xuất {number} — Tạo index** `{proposal.get('table')}` "
                    f"(`{columns}`) tên `{proposal.get('index_name')}`")
    else:
        st.markdown(f"**Đề xuất {number} — Viết lại SQL** (chỉ để xem và đo, không tự áp dụng)")
        if proposal.get("rewritten_sql"):
            st.code(proposal["rewritten_sql"], language="sql")
    if proposal.get("rationale"):
        st.caption(f"Lý do LLM nêu: {proposal['rationale']}")

st.info("Các đề xuất này CHƯA được chạy thử. Sang trang 3 để đo thật trước/sau trên lab.")
if st.button("Tiếp theo: chạy thử đề xuất →", key="goto_trial"):
    st.switch_page(NEXT_PAGE)
