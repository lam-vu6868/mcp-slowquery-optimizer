"""
dashboard/app.py
----------------

CHỨC NĂNG :
    Điểm vào của Dashboard Streamlit: trang tổng quan. 4 tab nằm trong pages/.

PHỤ TRÁCH  : Tình    |    REVIEW: Tường

CHẠY      : streamlit run dashboard/app.py

LƯU Ý:
    - Mọi nguồn dữ liệu đọc qua ui_common.load_* nên KHÔNG crash khi chưa có dữ liệu.
    - Dashboard KHÔNG tự chạy DDL: chỉ gọi Tool 6 kèm approval token sau khi
      người bấm Approve (tab 2, làm ở tuần 5–7).

TRẠNG THÁI : SKELETON (tuần 1) — khung + trạng thái hệ thống; nối dữ liệu thật
             khi Tool 1–6 xong.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st  # noqa: E402

from ui_common import (  # noqa: E402
    db_status,
    load_latest_injection_log,
    load_proposals,
    load_slow_queries,
    setup_page,
)

setup_page("Tổng quan", "🛢️")

st.title("🛢️ MCP Slow Query Optimizer")
st.caption(
    "LLM chỉ **đề xuất**. Mọi thay đổi index phải qua Validation Layer và "
    "được **người duyệt** trên Dashboard trước khi áp dụng."
)

# ---------- Số liệu tổng quan ----------
slow = load_slow_queries(limit=100)
proposals = load_proposals()
injection = load_latest_injection_log()

pending = None
if proposals is not None:
    # Chờ duyệt = chưa applied/rejected và validation chưa fail.
    def _status(p):
        return p.get("status") or (p.get("validation_report") or {}).get("status")

    pending = sum(1 for p in proposals if _status(p) in {"pending", "passed"})

c1, c2, c3 = st.columns(3)
c1.metric("Query chậm (> 0.5s)", len(slow) if slow is not None else "—")
c2.metric("Đề xuất chờ duyệt", pending if pending is not None else "—")
c3.metric(
    "Injection bị chặn",
    f"{injection['passed']}/{injection['total']}" if injection else "—",
)

# ---------- Trạng thái hệ thống ----------
st.subheader("Trạng thái hệ thống")

db = db_status()
if db["ok"]:
    st.success(f"MySQL {db['version']} — kết nối readonly OK ({db['host']}:{db['port']})", icon="✅")
else:
    st.warning(
        f"Chưa kết nối được MySQL tại {db['host']}:{db['port']}. "
        "Kiểm tra `docker compose up -d` và DB_PORT trong .env (docker map 3307).",
        icon="⚠️",
    )
    with st.expander("Chi tiết lỗi"):
        st.code(db["error"] or "", language="text")

components = [
    ("Tool 1–5 (MCP)", slow is not None, "Vũ · Hải · Tường"),
    ("Store đề xuất + Validation", proposals is not None, "Hải"),
    ("Kiểm thử injection", injection is not None, "Tình"),
]
st.table(
    {
        "Thành phần": [c[0] for c in components],
        "Trạng thái": ["✅ Có dữ liệu" if c[1] else "⬜ Chưa sẵn sàng" for c in components],
        "Phụ trách": [c[2] for c in components],
    }
)

st.divider()
st.markdown(
    "**Các tab:** 1 · Slow query  ·  2 · Đề xuất & duyệt  ·  3 · So sánh trước/sau  ·  4 · Bảo mật  "
    "— chọn ở thanh bên trái."
)
