"""
dashboard/pages/2_proposals.py
------------------------------
CHỨC NĂNG:
    TAB 2 — Đề xuất của LLM + trạng thái Validation + nút Approve / Reject.

PHỤ TRÁCH: Tình    |    REVIEW: Tường
THAM KHẢO: docs/api-contract.md (Tool 6, mục 4), security/approval.py

LUỒNG APPROVE:
    người tick xác nhận + bấm Approve
      → server sinh DDL từ proposal (build_ddl) → issue_token (1 lần, 10 phút)
      → ghi audit 'token_issued' → gọi Tool 6 apply_optimization(proposal_id, token)
    Token chỉ tồn tại trong biến cục bộ của lần bấm, không hiển thị, không lưu session, không log.

LƯU Ý:
    - Proposal 'rewrite' chỉ HIỂN THỊ, không có nút Apply.
    - Chỉ cho Approve khi validation_report.status == 'passed' (trạng thái 'validated').
"""
import json

import streamlit as st

from common import STATUS_LABELS, badge, fmt_bytes, load_proposals, run_async, setup_page

setup_page("Đề xuất", "🧠")
st.title("🧠 Tab 2 — Đề xuất của LLM")

from mcp_server.store import audit_log, proposals as store  # noqa: E402
from mcp_server.tools.apply import apply_optimization, build_ddl, rollback_ddl  # noqa: E402
from security import approval  # noqa: E402
from security.ast_whitelist import check as ast_check  # noqa: E402

try:
    from mcp_server.validation.validator import validate_proposal  # Hải
except ImportError:
    validate_proposal = None

# ------------------------------------------------------------------
# SIDEBAR: lọc + người duyệt + nhập proposal thủ công
# ------------------------------------------------------------------
status_filter = st.sidebar.multiselect(
    "Trạng thái", list(STATUS_LABELS), default=list(STATUS_LABELS),
    format_func=lambda s: STATUS_LABELS[s][0],
)
approver = st.sidebar.text_input("Người duyệt", value=st.session_state.get("approver", ""),
                                 placeholder="vd: tinh").strip()
st.session_state["approver"] = approver

with st.sidebar.expander("➕ Nhập proposal thủ công (JSON)"):
    st.caption("Dùng khi test/demo không qua LLM. Proposal vẫn phải qua Validation trước khi duyệt.")
    raw = st.text_area("IndexProposal / RewriteProposal", height=180, value=json.dumps({
        "type": "index", "table": "sales_data",
        "columns": [{"name": "region", "order": "ASC"}],
        "index_name": "idx_sales_region", "rationale": "…", "target_query_ids": ["q01"],
    }, ensure_ascii=False, indent=2))
    if st.button("Lưu proposal"):
        try:
            payload = json.loads(raw)
            if payload.get("type") == "index":
                build_ddl(payload)
            elif payload.get("type") == "rewrite":
                ok, reason = ast_check(payload.get("rewritten_sql", ""))
                if not ok:
                    raise ValueError(f"rewritten_sql bị AST từ chối: {reason}")
            else:
                raise ValueError("type phải là 'index' hoặc 'rewrite'")
            pid = store.save_proposal(payload, source="manual")
            st.success(f"Đã lưu {pid}")
        except (ValueError, json.JSONDecodeError) as e:
            st.error(f"Không hợp lệ: {e}")

# ------------------------------------------------------------------
# DANH SÁCH
# ------------------------------------------------------------------
proposals, err = load_proposals()
if err:
    st.error(err)
    st.stop()
proposals = [p for p in proposals if p["status"] in status_filter]

secret_ok = approval.is_configured()
if not secret_ok:
    st.error("APPROVAL_SECRET chưa cấu hình trong `.env` → không thể sinh token, nút Approve bị khóa.",
             icon="🔒")

if not proposals:
    st.info("Chưa có đề xuất nào. Đề xuất được tạo khi chạy LLM agent trên các query chậm "
            "(hoặc nhập thủ công ở thanh bên).")
    st.stop()

counts = {s: sum(p["status"] == s for p in proposals) for s in STATUS_LABELS}
cols = st.columns(len(STATUS_LABELS))
for c, (s, (label, _)) in zip(cols, STATUS_LABELS.items()):
    c.metric(label, counts[s])

# Kết quả lần bấm gần nhất (giữ qua rerun, KHÔNG chứa token)
if "last_action" in st.session_state:
    kind, msg = st.session_state.pop("last_action")
    getattr(st, kind)(msg)

for p in proposals:
    pid, payload, status = p["proposal_id"], p["payload"], p["status"]
    report = store.get_validation_report(pid)
    title = (f"`{pid}` · {p.get('query_id') or '—'} · "
             + (f"INDEX {payload.get('index_name')}" if p["type"] == "index" else "REWRITE"))
    with st.expander(title, expanded=(status in ("validated", "apply_failed"))):
        st.markdown(badge(status) + f" &nbsp; nguồn: `{p.get('source')}` · tạo lúc {p['created_at']}",
                    unsafe_allow_html=True)
        left, right = st.columns([3, 2])

        with left:
            if payload.get("rationale"):
                st.markdown(f"**Lý do (LLM):** {payload['rationale']}")
            if p["type"] == "index":
                try:
                    ddl = build_ddl(payload)
                    st.markdown("**DDL do server sinh** (LLM không gửi DDL tự do):")
                    st.code(ddl, language="sql")
                    st.caption("Rollback nếu cần gỡ:")
                    st.code(rollback_ddl(payload), language="sql")
                except ValueError as e:
                    ddl = None
                    st.error(f"Proposal sai cấu trúc, không sinh được DDL: {e}")
            else:
                ddl = None
                st.markdown("**SQL viết lại** (chỉ để tham khảo, không áp dụng vào DB):")
                st.code(payload.get("rewritten_sql", ""), language="sql")

        with right:
            st.markdown("**Validation Layer**")
            if not report:
                st.caption("Chưa có validation report.")
            else:
                b, a = report.get("before") or {}, report.get("after") or {}
                m1, m2 = st.columns(2)
                m1.metric("P95 trước", f"{b.get('p95_ms', 0):,.0f} ms" if b.get("p95_ms") is not None else "—")
                delta = None
                if b.get("p95_ms") and a.get("p95_ms") is not None:
                    delta = f"{(a['p95_ms'] - b['p95_ms']) / b['p95_ms'] * 100:+.1f}%"
                m2.metric("P95 sau", f"{a.get('p95_ms', 0):,.0f} ms" if a.get("p95_ms") is not None else "—",
                          delta=delta, delta_color="inverse")
                eq = report.get("result_equivalent")
                st.markdown(f"Kết quả tương đương (hash): {'✅' if eq else '❌' if eq is False else '—'}")
                w = report.get("write_overhead") or {}
                if w:
                    st.markdown(f"Dung lượng index: **{fmt_bytes(w.get('index_size_bytes'))}** · "
                                f"INSERT throughput: **{w.get('insert_throughput_change_pct', '—')}%**")
                if report.get("failure_reason"):
                    st.warning(report["failure_reason"])

        # ---------------- HÀNH ĐỘNG ----------------
        if status == "pending_validation":
            if validate_proposal is None:
                st.info("Validation Layer (Hải) chưa sẵn sàng — chưa chạy được kiểm chứng.")
            elif st.button("▶️ Chạy Validation", key=f"val_{pid}"):
                with st.spinner("Đang tạo index INVISIBLE và đo P95 trước/sau…"):
                    try:
                        validate_proposal(pid)
                        st.session_state["last_action"] = ("success", f"Đã chạy validation cho {pid}")
                    except Exception as e:
                        st.session_state["last_action"] = ("error", f"Validation lỗi: {e}")
                st.rerun()

        elif status == "validated" and p["type"] == "rewrite":
            st.info("Đề xuất rewrite đã kiểm chứng. Theo thiết kế, rewrite **chỉ hiển thị** — "
                    "không có đường áp dụng vào DB.", icon="ℹ️")

        elif status in ("validated", "apply_failed") and p["type"] == "index" and ddl:
            if status == "apply_failed":
                st.warning("Lần áp dụng trước bị lỗi (xem tab 4). Có thể duyệt lại — hệ thống cấp token mới.")
            confirm = st.checkbox("Tôi đã xem số liệu validation và đồng ý chạy DDL trên vào DB",
                                  key=f"cf_{pid}")
            a1, a2, _ = st.columns([1, 1, 3])
            can_approve = secret_ok and confirm and bool(approver)
            if a1.button("✅ Approve & Apply", key=f"ap_{pid}", type="primary", disabled=not can_approve,
                         help=None if can_approve else "Cần: nhập người duyệt, tick xác nhận, có APPROVAL_SECRET"):
                try:
                    issued = approval.issue_token(pid, ddl)
                    audit_log.log(audit_log.ACTION_TOKEN_ISSUED, "success", proposal_id=pid,
                                  ddl_hash=issued.ddl_hash, actor=approver, source="dashboard")
                    with st.spinner("Đang áp dụng index…"):
                        res = json.loads(run_async(apply_optimization(
                            pid, issued.token, actor=approver, source="dashboard")))
                    del issued
                    if res["ok"]:
                        d = res["data"]
                        st.session_state["last_action"] = (
                            "success", f"Đã áp dụng {pid}: {d.get('executed_ddl') or d['ddl']} "
                                       f"(audit {d['audit_id']})")
                    else:
                        e = res["error"]
                        st.session_state["last_action"] = ("error", f"Tool 6 từ chối [{e['code']}]: {e['message']}")
                except approval.ApprovalConfigError as e:
                    st.session_state["last_action"] = ("error", str(e))
                st.rerun()

            reason = a2.text_input("Lý do từ chối", key=f"rr_{pid}", label_visibility="collapsed",
                                   placeholder="Lý do từ chối")
            if a2.button("❌ Reject", key=f"rj_{pid}", disabled=not approver):
                store.set_status(pid, store.STATUS_REJECTED_BY_USER)
                audit_log.log(audit_log.ACTION_REJECT, "success", proposal_id=pid,
                              ddl_hash=approval.ddl_hash(ddl), message=reason or None,
                              actor=approver, source="dashboard")
                st.session_state["last_action"] = ("info", f"Đã từ chối {pid}")
                st.rerun()
            if not approver:
                st.caption("Nhập tên người duyệt ở thanh bên để bật nút.")
