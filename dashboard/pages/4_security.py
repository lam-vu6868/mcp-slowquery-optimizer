"""
dashboard/pages/4_security.py
-----------------------------

CHỨC NĂNG :
    TAB 4 — Bảo mật: kết quả 20 kịch bản injection, audit log Tool 6, số lần token bị từ chối.

PHỤ TRÁCH  : Tình    |    REVIEW: Tường

LƯU Ý:
    - Hiển thị 'lớp nào đã chặn' cho từng kịch bản, không chỉ pass/fail.

THAM KHẢO  : security/injection_report.md

TRẠNG THÁI : ĐÃ CÀI ĐẶT — hiển thị bảng 20 kịch bản injection kèm lớp chặn và audit log Tool 6.
"""

import os
import sqlite3
from contextlib import closing
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
INJECTION_REPORT = ROOT / "security" / "injection_report.md"


def _parse_injection_table(report_path: Path) -> list[dict]:
    """Đọc bảng kết quả 20 kịch bản từ security/injection_report.md."""
    if not report_path.is_file():
        return []
    rows: list[dict] = []
    for raw in report_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line.startswith("|"):
            continue
        parts = [cell.strip() for cell in line.strip("|").split("|")]
        if len(parts) < 7 or parts[0] in ("#", ":-:") or set(parts[0]) <= {"-", ":"}:
            continue
        rows.append({
            "Mã": parts[0],
            "Nhóm": parts[1],
            "Kịch bản": parts[2],
            "Lớp chặn": parts[3],
            "Audit Tool 6": parts[4],
            "LLM bị ảnh hưởng": parts[5],
            "Kết quả": parts[6],
        })
    return rows


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


st.title("Bảo mật & Kiểm thử Prompt Injection")

st.subheader("1. Kết quả 20 kịch bản Prompt Injection (theo lớp chặn)")
cases = _parse_injection_table(INJECTION_REPORT)
if not cases:
    st.warning("Chưa tìm thấy bảng kết quả trong security/injection_report.md.")
else:
    blocked = sum(1 for c in cases if "chặn" in c["Kết quả"].lower())
    col1, col2, col3 = st.columns(3)
    col1.metric("Tổng kịch bản", len(cases))
    col2.metric("Bị chặn tại ranh giới code", f"{blocked}/{len(cases)}")
    col3.metric("Số lớp phòng thủ kích hoạt", len({c["Lớp chặn"] for c in cases}))

    st.dataframe(cases, width="stretch")
    st.caption(
        "Phạm vi: 20/20 ca kiểm ranh giới code với dữ liệu giả (B05 đã lọc trước Groq); "
        "không tuyên bố an toàn tuyệt đối end-to-end."
    )

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
    c1, c2, c3 = st.columns(3)
    c1.metric("Tổng sự kiện (gần nhất)", len(entries))
    c2.metric("Đã áp dụng (applied)", applied)
    c3.metric("Bị từ chối / TOKEN_INVALID", f"{rejected} / {token_invalid}")
    st.dataframe(entries, width="stretch")
