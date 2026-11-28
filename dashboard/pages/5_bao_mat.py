"""
dashboard/pages/5_bao_mat.py
----------------------------

CHỨC NĂNG :
    TRANG 5 — Bảo mật: có nút CHẠY THẬT 20 kịch bản Prompt Injection tại chỗ
    (hiển thị tiến độ từng ca, lớp nào đã chặn, pass/fail) và bảng Audit log Tool 6.

PHỤ TRÁCH  : Tình    |    REVIEW: Vũ

LƯU Ý:
    - Chưa bấm chạy thì báo rõ chưa chạy trong phiên này (không giả làm vừa chạy).
    - Nút chạy gọi trực tiếp security.injection_tests.run_tests.iter_cases() — không gọi Groq hay DDL thật.
"""

import os
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

import streamlit as st

_ROOT = str(Path(__file__).resolve().parents[2])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from security.injection_tests.run_tests import iter_cases

ROOT = Path(_ROOT)
INJECTION_REPORT = ROOT / "security" / "injection_report.md"


def _resolve_audit_db_path() -> Path:
    store_env = os.getenv("DASHBOARD_STORE_PATH")
    if store_env:
        return Path(store_env).with_name("audit.sqlite3")
    return ROOT / "data" / "outputs" / "audit.sqlite3"


def _load_audit_entries(db_path: Path, limit: int = 50) -> list[dict]:
    if not db_path.is_file():
        return []
    with closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            "SELECT audit_id, proposal_id, approver, result, reason, created_at "
            "FROM audit_log ORDER BY audit_id DESC LIMIT ?",
            (limit,),
        )
        return [dict(row) for row in cur.fetchall()]


st.title("5. Bảo mật & Chạy thử 20 kịch bản Prompt Injection")

st.subheader("1. Kiểm thử 20 kịch bản Prompt Injection (chạy trực tiếp)")
st.caption(
    "Chạy trực tiếp 20 payload tấn công (4 nhóm A/B/C/D × 5) qua các lớp bảo vệ thực tế "
    "(cắt comment SQL, sanitize schema, AST whitelist, parser JSON, registry chặn Tool 6 & token giả)."
)

if st.button("▶ Chạy 20 kịch bản Prompt Injection ngay", type="primary"):
    bar = st.progress(0, text="Đang chạy kịch bản 0/20...")
    live_rows: list[dict] = []
    try:
        for idx, item in enumerate(iter_cases(), start=1):
            live_rows.append({
                "Mã": item["id"],
                "Nhóm": item["group"],
                "Kịch bản": item["description"],
                "Lớp chặn": item["layer"],
                "Audit Tool 6": "Có" if item["audit_log"] else "Không tới Tool 6",
                "Kết quả": "✅ Bị chặn" if item["status"] == "blocked" else f"❌ {item['status']}",
            })
            bar.progress(idx / 20, text=f"Đã chạy {idx}/20: {item['id']} ({item['layer']})")
        st.session_state["live_injection_rows"] = live_rows
        bar.progress(1.0, text="Hoàn tất 20/20 kịch bản!")
    except Exception as exc:  # noqa: BLE001
        st.error(f"Lỗi khi chạy bộ kiểm thử injection: {type(exc).__name__}")

live_rows = st.session_state.get("live_injection_rows")
if not live_rows:
    st.info("Chưa chạy bộ kiểm thử trong phiên này. Bấm nút **▶ Chạy 20 kịch bản Prompt Injection ngay** ở trên.")
else:
    blocked = sum(1 for r in live_rows if "Bị chặn" in r["Kết quả"])
    c1, c2, c3 = st.columns(3)
    c1.metric("Tổng kịch bản đã chạy", len(live_rows))
    c2.metric("Bị chặn", f"{blocked}/{len(live_rows)}")
    c3.metric("Số lớp phòng thủ kích hoạt", len({r["Lớp chặn"] for r in live_rows}))
    st.dataframe(live_rows, hide_index=True, width="stretch")
    st.caption(
        "Phạm vi: kiểm ranh giới code trực tiếp bằng dữ liệu giả (không gọi Groq/DDL thật); "
        "không tuyên bố an toàn tuyệt đối end-to-end."
    )

with st.expander("Xem báo cáo bảo mật đã ghi trước (security/injection_report.md)"):
    if INJECTION_REPORT.is_file():
        st.markdown(INJECTION_REPORT.read_text(encoding="utf-8"))
    else:
        st.info("Chưa có file security/injection_report.md.")

st.divider()
st.subheader("2. Audit log Tool 6 & Token bị từ chối")
audit_path = _resolve_audit_db_path()
try:
    entries = _load_audit_entries(audit_path)
except sqlite3.Error:
    st.error("Không đọc được bảng audit_log từ SQLite.")
    entries = []

if not entries:
    st.info(f"Chưa có bản ghi audit Tool 6 tại `{audit_path.name}`.")
else:
    rejected = sum(1 for e in entries if e.get("result") == "rejected")
    token_invalid = sum(1 for e in entries if e.get("reason") == "TOKEN_INVALID")
    applied = sum(1 for e in entries if e.get("result") == "applied")
    a1, a2, a3 = st.columns(3)
    a1.metric("Tổng sự kiện (gần nhất)", len(entries))
    a2.metric("Đã áp dụng (applied)", applied)
    a3.metric("Bị từ chối / TOKEN_INVALID", f"{rejected} / {token_invalid}")
    st.dataframe(entries, hide_index=True, width="stretch")
