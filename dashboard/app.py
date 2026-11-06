"""
dashboard/app.py
----------------
CHỨC NĂNG:
    Trang chủ Dashboard Streamlit: tổng quan (số query chậm, đề xuất chờ duyệt,
    trạng thái hệ thống). 4 tab nằm trong dashboard/pages/.

PHỤ TRÁCH: Tình    |    REVIEW: Tường

CHẠY:
    streamlit run dashboard/app.py
    # Dữ liệu demo (không phải số liệu thật), dùng khi quay video/kiểm giao diện:
    python scripts/seed_demo_dashboard.py
    META_DB_PATH=data/meta/demo.sqlite3 streamlit run dashboard/app.py        (bash)
    $env:META_DB_PATH="data/meta/demo.sqlite3"; streamlit run dashboard/app.py (PowerShell)

LƯU Ý:
    - Mọi nguồn dữ liệu đều có try/except: thiếu dữ liệu thì hiện hướng dẫn, không crash.
    - Dashboard KHÔNG tự chạy DDL: chỉ gọi Tool 6 kèm approval token sau khi người bấm Approve.
"""
import streamlit as st

from common import (
    load_audit, load_injection_results, load_proposals, load_query_catalog,
    load_slow_queries, setup_page, system_status,
)

setup_page("Tổng quan", "🛢️")

st.title("🛢️ MCP Slow Query Optimizer")
st.caption("LLM đề xuất · Validation Layer kiểm chứng · **con người duyệt** · Tool 6 áp dụng bằng approval token")

slow, slow_note = load_slow_queries(limit=100)
catalog = load_query_catalog()
proposals, _ = load_proposals()
audit = load_audit()
inj, _ = load_injection_results()

n_by_status = {}
for p in proposals:
    n_by_status[p["status"]] = n_by_status.get(p["status"], 0) + 1
token_rejects = int((audit["error_code"] == "TOKEN_INVALID").sum()) if not audit.empty else 0

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Query chậm", len(slow) if slow is not None else len(catalog),
          help="Từ Tool 1" if slow is not None else "Tool 1 chưa sẵn sàng — đang hiện số query trong bộ thực nghiệm")
c2.metric("Đề xuất chờ duyệt", n_by_status.get("validated", 0))
c3.metric("Đã áp dụng", n_by_status.get("applied", 0))
c4.metric("Token bị từ chối", token_rejects)
c5.metric("Injection bị chặn",
          f"{inj['summary']['blocked']}/{inj['summary']['total']}" if inj else "—")

st.divider()
left, right = st.columns([3, 2])

with left:
    st.subheader("Luồng xử lý")
    st.markdown(
        """
1. **Tab 1 – Slow query:** Tool 1 lấy top query chậm từ `performance_schema` / slow log.
2. **LLM** gọi Tool 1–5 để phân tích, trả về đề xuất *có cấu trúc* (index hoặc rewrite).
3. **Validation Layer** tạo index `INVISIBLE`, đo P95 trước/sau, so hash kết quả.
4. **Tab 2 – Đề xuất:** người xem số liệu và bấm **Approve** → server sinh token một lần (10 phút) → gọi Tool 6.
5. **Tab 3 – So sánh:** P95, Query Cost, rows examined, dung lượng index, write overhead; LLM vs baseline.
6. **Tab 4 – Bảo mật:** 20 kịch bản injection và audit log của Tool 6.
"""
    )
    st.info("LLM chỉ được cấp Tool 1–5. Tool 6 `apply_optimization` chỉ gọi được từ Dashboard, "
            "bằng approval token mà LLM không bao giờ nhìn thấy.", icon="🔐")

with right:
    st.subheader("Trạng thái hệ thống")
    s = system_status()
    st.markdown(f"{'🟢' if s['mysql'] else '🔴'} **MySQL** (readonly_user) "
                f"{'kết nối được' if s['mysql'] else 'chưa kết nối được'}")
    st.markdown(f"{'🟢' if s['approval_secret'] else '🔴'} **APPROVAL_SECRET** "
                f"{'đã cấu hình' if s['approval_secret'] else 'chưa cấu hình — nút Approve sẽ bị khóa'}")
    st.markdown(f"{'🟢' if slow is not None else '🟡'} **Tool 1** "
                f"{'hoạt động' if slow is not None else '— ' + (slow_note or '')}")
    st.markdown(f"{'🟢' if inj else '🟡'} **Kết quả injection** "
                f"{'có' if inj else 'chưa chạy'}")
    st.caption(f"Meta DB (proposals/audit): `{s['meta_db']}`")
    if not s["approval_secret"]:
        st.code('python -c "import secrets; print(secrets.token_hex(32))"', language="bash")
        st.caption("Dán kết quả vào `APPROVAL_SECRET=` trong file `.env` rồi chạy lại Dashboard.")

    if n_by_status:
        st.subheader("Đề xuất theo trạng thái")
        from common import STATUS_LABELS
        import pandas as pd
        st.bar_chart(pd.Series({STATUS_LABELS.get(k, (k,))[0]: v for k, v in n_by_status.items()},
                               name="số đề xuất"), horizontal=True, height=220)
