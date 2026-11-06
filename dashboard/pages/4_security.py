"""
dashboard/pages/4_security.py
-----------------------------
CHỨC NĂNG:
    TAB 4 — Bảo mật: kết quả 20 kịch bản injection, audit log Tool 6, số lần token bị từ chối.

PHỤ TRÁCH: Tình    |    REVIEW: Tường
THAM KHẢO: security/injection_report.md

LƯU Ý:
    - Hiển thị 'lớp nào đã chặn' cho từng kịch bản, không chỉ pass/fail.
    - Nút "Chạy lại" gọi runner trong TIẾN TRÌNH RIÊNG (subprocess) để không đổi META_DB_PATH
      của Dashboard (runner dùng DB meta riêng cho test).
"""
import subprocess
import sys

import altair as alt
import pandas as pd
import streamlit as st

from common import ROOT, load_audit, load_injection_results, setup_page

setup_page("Bảo mật", "🛡️")
st.title("🛡️ Tab 4 — Bảo mật")

tab_inj, tab_audit, tab_layers = st.tabs(["20 kịch bản injection", "Audit log Tool 6", "Các lớp phòng thủ"])

# ------------------------------------------------------------------
# INJECTION
# ------------------------------------------------------------------
with tab_inj:
    top = st.columns([4, 1])
    if top[1].button("🔁 Chạy lại 20 kịch bản"):
        with st.spinner("Đang chạy…"):
            proc = subprocess.run([sys.executable, "-m", "security.injection_tests.run_tests"],
                                  cwd=str(ROOT), capture_output=True, text=True, timeout=120)
        (st.success if proc.returncode == 0 else st.error)(
            "Hoàn tất." if proc.returncode == 0 else "Có kịch bản lọt — xem chi tiết bên dưới.")

    report, note = load_injection_results()
    if report is None:
        st.info(note, icon="⏳")
    else:
        s = report["summary"]
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Bị chặn", f"{s['blocked']}/{s['total']}")
        m2.metric("Chế độ chạy", s["mode"])
        m3.metric("Lần chạy (UTC)", s["run_at"][:10], help=s["run_at"])
        n_vec = sum(r["n_variants"] for r in report["results"])
        m4.metric("Vector (gồm biến thể)", n_vec)

        layer_rows = [{"lớp": k, "kết quả": st_, "số lần": v}
                      for k, d in s["by_layer"].items() for st_, v in d.items() if v]
        if layer_rows:
            st.altair_chart(alt.Chart(pd.DataFrame(layer_rows)).mark_bar().encode(
                y=alt.Y("lớp:N", title=None, axis=alt.Axis(labelLimit=260)),
                x=alt.X("số lần:Q", title="Số lần kiểm"),
                color=alt.Color("kết quả:N", scale=alt.Scale(
                    domain=["BLOCKED", "NOT_BLOCKED", "SKIPPED"], range=["#4caf50", "#e53935", "#bdbdbd"])),
                tooltip=["lớp", "kết quả", "số lần"],
            ).properties(height=34 * len({r["lớp"] for r in layer_rows}) + 40), use_container_width=True)

        group = st.radio("Nhóm", ["Tất cả", "A", "B", "C", "D"], horizontal=True,
                         format_func=lambda g: {"Tất cả": "Tất cả", "A": "A · Slow log", "B": "B · Schema",
                                                "C": "C · Cấu trúc SQL", "D": "D · Đầu ra & token"}[g])
        for r in report["results"]:
            if group != "Tất cả" and r["group"] != group:
                continue
            icon = "✅" if r["blocked"] else "❌"
            with st.expander(f"{icon} {r['id']} · {r['title']}"):
                chips = "".join(f'<span class="layer-chip">{l}</span>' for l in r["blocked_by"])
                st.markdown(f"**Lớp chặn:** {chips or '—'}", unsafe_allow_html=True)
                st.markdown(
                    f"**Ghi audit log:** {'—' if r['audit_logged'] is None else ('Có' if r['audit_logged'] else 'Không')}"
                    f" · **LLM bị ảnh hưởng:** chưa đo (cần agent LLM thật)")
                st.markdown("**Vector tấn công** (dữ liệu, hiển thị dạng text):")
                st.code(r["vector"], language="sql")
                st.dataframe(pd.DataFrame(r["layers"])[["layer", "check", "status", "evidence"]],
                             use_container_width=True, hide_index=True)

# ------------------------------------------------------------------
# AUDIT LOG
# ------------------------------------------------------------------
with tab_audit:
    audit = load_audit(limit=1000)
    if audit.empty:
        st.info("Audit log trống: chưa có lần gọi Tool 6 / thao tác duyệt nào.")
    else:
        apply_rows = audit[audit["action"] == "apply_optimization"]
        a1, a2, a3, a4 = st.columns(4)
        a1.metric("Lần gọi Tool 6", len(apply_rows))
        a2.metric("Thành công", int((apply_rows["result"] == "success").sum()))
        a3.metric("Token bị từ chối", int((apply_rows["error_code"] == "TOKEN_INVALID").sum()))
        a4.metric("Token đã cấp", int((audit["action"] == "token_issued").sum()))

        rej = apply_rows[apply_rows["result"] != "success"]
        if not rej.empty:
            st.altair_chart(alt.Chart(rej.fillna({"error_code": "?"})).mark_bar(color="#e53935").encode(
                x=alt.X("count():Q", title="Số lần"), y=alt.Y("error_code:N", title="Mã lỗi", sort="-x"),
            ).properties(height=160), use_container_width=True)

        actions = st.multiselect("Lọc action", sorted(audit["action"].unique()),
                                 default=sorted(audit["action"].unique()))
        st.dataframe(
            audit[audit["action"].isin(actions)][
                ["audit_id", "ts", "action", "result", "error_code", "proposal_id", "ddl_hash",
                 "actor", "source", "message"]],
            use_container_width=True, hide_index=True,
        )
        st.caption("Audit log chỉ ghi thêm (trigger SQLite chặn UPDATE/DELETE) và không bao giờ chứa token.")

# ------------------------------------------------------------------
# CÁC LỚP
# ------------------------------------------------------------------
with tab_layers:
    st.markdown(
        """
| Lớp | Cơ chế | Chặn gì |
|:-:|---|---|
| L1 | `readonly_user` cho Tool 1–5 | Mọi lệnh ghi/DDL từ đường phân tích |
| L2 | `index_admin` chỉ INDEX/ALTER/SELECT, chỉ Tool 6 dùng | DROP TABLE, DELETE… kể cả từ Tool 6 |
| L3 | Sanitize: bỏ comment SQL, NFKC + bỏ ký tự vô hình, lọc comment schema, phát hiện base64 | Chỉ thị giấu trong slow log / schema |
| L4 | AST whitelist `sqlglot` fail-closed | Multi-statement, `/*! */`, OUTFILE, SLEEP, FOR UPDATE/SHARE, schema hệ thống |
| L4b | Proposal có cấu trúc, server tự sinh DDL | SQL nối lệnh qua tên bảng/cột/index |
| L5 | Approval token HMAC, 1 lần, 10 phút, gắn proposal + hash DDL; Tool 6 không cấp cho LLM | LLM tự duyệt, token giả, replay, đổi DDL sau khi duyệt |
| L6 | Audit log append-only | Truy vết mọi lần gọi Tool 6 |
"""
    )
    st.caption("Giới hạn còn lại: xem `security/injection_report.md` mục 4.")
