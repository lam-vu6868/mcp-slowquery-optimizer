"""
security/injection_tests/run_tests.py
-------------------------------------
CHỨC NĂNG:
    Chạy tự động 20 kịch bản injection qua TỪNG LỚP phòng thủ và ghi kết quả:
    lớp nào chặn, có ghi audit log không.

PHỤ TRÁCH: Tình    |    REVIEW: Vũ
THAM KHẢO: security/injection_tests/payloads.py, security/injection_report.md

CHẠY:
    python -m security.injection_tests.run_tests          # offline, không cần MySQL/LLM
    python -m security.injection_tests.run_tests --db     # thêm lớp readonly_user (đọc SHOW GRANTS, KHÔNG chạy lệnh phá hoại)

KẾT QUẢ:
    security/logs/injection_results.json   (Dashboard tab 4 đọc file này)
    security/logs/injection_results.md     (bảng dán vào injection_report.md)
    security/logs/injection_meta.sqlite3   (audit_log của lần chạy, tách khỏi DB meta thật)

QUY ƯỚC:
    Kịch bản PASS (= bị chặn) khi MỌI lớp khai trong `checks` đều chặn được, tức là kiểm
    phòng thủ nhiều lớp chứ không chỉ "có 1 lớp chặn". Lớp không chạy được (vd db_readonly
    khi không có --db) ghi SKIPPED và không tính là chặn.
    Cột "LLM bị ảnh hưởng?" KHÔNG đo ở đây (cần agent LLM thật) — xem phần giới hạn.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import argparse
import asyncio
import inspect
import json
import secrets
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = ROOT / "security" / "logs"

LAYER_NAMES = {
    "db_readonly": "L1 readonly_user",
    "sanitize_sql": "L3 Sanitize",
    "sanitize_flag": "L3 Sanitize (gắn cờ)",
    "sanitize_comment": "L3 Sanitize",
    "ast": "L4 AST whitelist",
    "ast_goal": "L4 AST whitelist",
    "proposal_struct": "L4b Proposal có cấu trúc",
    "llm_toolset": "L5 Tool 6 tách khỏi LLM",
    "tool6_signature": "L5 Tool 6 tách khỏi LLM",
    "tool6_token": "L5 Approval token",
    "tool6_replay": "L5 Approval token",
    "tool6_swap": "L5 Approval token",
    "tool6_rewrite": "L5 Tool 6 (chặn rewrite)",
}
RISKY_FLAGS = {"instruction", "role_marker", "ddl_dml", "approval", "exec_comment", "base64_hidden"}

INDEX_PAYLOAD = {"type": "index", "table": "sales_data", "columns": ["region"],
                 "index_name": "idx_sales_region"}


def _setup_env():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    meta = LOG_DIR / "injection_meta.sqlite3"
    if meta.exists():
        meta.unlink()
    os.environ["META_DB_PATH"] = str(meta)
    from security import approval
    if not approval.is_configured():
        # Secret tạm cho riêng lần chạy test, không ghi ra đâu cả
        os.environ["APPROVAL_SECRET"] = secrets.token_hex(32)


class FakeDB:
    """DB giả cho Tool 6: chỉ ghi lại DDL, không chạm MySQL."""

    def __init__(self):
        self.executed = []

    def table_columns(self, table):
        return {"id", "region", "country", "order_date"} if table == "sales_data" else set()

    def index_state(self, table, index_name):
        return None

    def execute_ddl(self, ddl):
        self.executed.append(ddl)

    def index_size_bytes(self, table, index_name):
        return None


# ============================================================
# CÁC LỚP KIỂM TRA — mỗi hàm trả (status, evidence, audited)
#   status: BLOCKED | NOT_BLOCKED | SKIPPED
# ============================================================

def _vectors(p):
    return [p["vector"]] + list(p.get("variants", []))


def chk_sanitize_sql(p, ctx):
    from mcp_server.utils.sanitize import detect_injection, sanitize_sql
    ev = []
    for v in _vectors(p):
        before = RISKY_FLAGS & set(detect_injection(v))
        cleaned = sanitize_sql(v)
        after = RISKY_FLAGS & set(detect_injection(cleaned))
        ev.append(f"{sorted(before)} → còn {sorted(after)}: «{cleaned[:60]}»")
        if not before or after:
            return "NOT_BLOCKED", "; ".join(ev), False
    return "BLOCKED", "; ".join(ev), False


def chk_sanitize_flag(p, ctx):
    from mcp_server.utils.sanitize import untrusted_field
    f = untrusted_field(p["vector"], kind="sql")
    risky = RISKY_FLAGS & set(f["flags"])
    ok = f["untrusted"] and bool(risky)
    return ("BLOCKED" if ok else "NOT_BLOCKED"), f"untrusted=True, flags={sorted(risky)}", False


def chk_sanitize_comment(p, ctx):
    from mcp_server.utils.sanitize import FILTERED_PLACEHOLDER, sanitize_comment
    for v in _vectors(p):
        out = sanitize_comment(v)
        if out != FILTERED_PLACEHOLDER:
            return "NOT_BLOCKED", f"comment lọt qua: «{out[:60]}»", False
    return "BLOCKED", "comment bị thay bằng nhãn ĐÃ LỌC", False


def chk_ast(p, ctx):
    from security.ast_whitelist import check
    ev = []
    for v in _vectors(p):
        ok, reason = check(v)
        ev.append(reason)
        if ok:
            return "NOT_BLOCKED", f"AST cho qua: «{v[:60]}»", False
    return "BLOCKED", " | ".join(ev), False


def chk_ast_goal(p, ctx):
    from security.ast_whitelist import check
    ok, reason = check(p["goal_sql"])
    return ("NOT_BLOCKED" if ok else "BLOCKED"), reason, False


def chk_proposal_struct(p, ctx):
    from mcp_server.tools.apply import build_ddl
    ev = []
    for v in _vectors(p):
        try:
            ddl = build_ddl(v)
            return "NOT_BLOCKED", f"sinh được DDL: {ddl}", False
        except ValueError as e:
            ev.append(str(e)[:70])
    return "BLOCKED", " | ".join(ev), False


def chk_llm_toolset(p, ctx):
    from mcp_server.tools import apply
    if apply.LLM_EXPOSED:
        return "NOT_BLOCKED", "apply.LLM_EXPOSED = True", False
    try:
        from mcp_server import server
        llm_tools = getattr(server, "LLM_TOOLS", None)
    except Exception:
        llm_tools = None
    if llm_tools is None:
        return "BLOCKED", "LLM_EXPOSED=False (server.py chưa có registry LLM_TOOLS để kiểm thêm)", False
    names = {getattr(t, "__name__", str(t)) for t in llm_tools}
    if "apply_optimization" in names:
        return "NOT_BLOCKED", "server.LLM_TOOLS chứa apply_optimization", False
    return "BLOCKED", f"LLM chỉ thấy: {sorted(names)}", False


def chk_tool6_signature(p, ctx):
    from mcp_server.tools.apply import apply_optimization
    params = set(inspect.signature(apply_optimization).parameters)
    bad = params & {"approved", "sql", "ddl", "query"}
    if bad:
        return "NOT_BLOCKED", f"Tool 6 nhận tham số {bad}", False
    try:
        asyncio.run(apply_optimization("p_x_1", "t", approved=True, sql="DROP TABLE sales_data"))
        return "NOT_BLOCKED", "Tool 6 chấp nhận approved/sql", False
    except TypeError as e:
        return "BLOCKED", f"TypeError: {str(e)[:70]}", False


def _validated_proposal(payload=INDEX_PAYLOAD):
    from mcp_server.store import proposals as store
    pid = store.save_proposal(dict(payload), source="injection_test")
    store.save_validation_report(pid, {"status": "passed", "result_equivalent": True})
    return pid


def _call_tool6(pid, token):
    from mcp_server.tools.apply import apply_optimization
    db = FakeDB()
    r = json.loads(asyncio.run(apply_optimization(pid, token, source="injection_test", db=db)))
    return r, db


def _audit_count():
    from mcp_server.store import audit_log
    return len(audit_log.list_entries(limit=100000))


def chk_tool6_token(p, ctx):
    pid = _validated_proposal()
    ev, audited = [], True
    for v in _vectors(p):
        n0 = _audit_count()
        r, db = _call_tool6(pid, v)
        audited &= _audit_count() == n0 + 1
        code = (r.get("error") or {}).get("code")
        ev.append(f"{v[:18]}…→{code}")
        if r["ok"] or code != "TOKEN_INVALID" or db.executed:
            return "NOT_BLOCKED", "; ".join(ev), audited
    return "BLOCKED", "; ".join(ev), audited


def chk_tool6_replay(p, ctx):
    from mcp_server.store import proposals as store
    from mcp_server.tools.apply import build_ddl
    from security import approval
    pid = _validated_proposal()
    token = approval.issue_token(pid, build_ddl(INDEX_PAYLOAD)).token
    r1, _ = _call_tool6(pid, token)
    if not r1["ok"]:
        return "NOT_BLOCKED", f"lần 1 lỗi bất ngờ: {r1['error']}", False
    store.set_status(pid, store.STATUS_VALIDATED)  # giả định kẻ tấn công reset được trạng thái
    n0 = _audit_count()
    r2, db = _call_tool6(pid, token)
    audited = _audit_count() == n0 + 1
    reason = (r2.get("error") or {}).get("detail", {}).get("reason")
    if r2["ok"] or reason != "REUSED" or db.executed:
        return "NOT_BLOCKED", f"lần 2: {r2}", audited
    return "BLOCKED", "lần 1 OK; lần 2 TOKEN_INVALID (REUSED)", audited


def chk_tool6_swap(p, ctx):
    from mcp_server.store.meta_db import get_meta_conn
    from mcp_server.tools.apply import build_ddl
    from security import approval
    pid = _validated_proposal()
    token = approval.issue_token(pid, build_ddl(INDEX_PAYLOAD)).token  # người duyệt DDL A
    with get_meta_conn() as conn:  # kẻ tấn công sửa proposal thành DDL B
        conn.execute("UPDATE proposals SET payload_json = ? WHERE proposal_id = ?",
                     (json.dumps(p["vector"]), pid))
    n0 = _audit_count()
    r, db = _call_tool6(pid, token)
    audited = _audit_count() == n0 + 1
    if r["ok"] or db.executed:
        return "NOT_BLOCKED", f"DDL B được chạy: {db.executed}", audited
    return "BLOCKED", f"{r['error']['code']} ({r['error']['detail'].get('reason')})", audited


def chk_tool6_rewrite(p, ctx):
    pid = _validated_proposal({"type": "rewrite", "original_query_id": "q13",
                               "rewritten_sql": "SELECT 1", "rationale": "x"})
    n0 = _audit_count()
    r, db = _call_tool6(pid, "anything")
    audited = _audit_count() == n0 + 1
    code = (r.get("error") or {}).get("code")
    return ("BLOCKED" if code == "FORBIDDEN" and not db.executed else "NOT_BLOCKED"), \
        f"rewrite → {code}", audited


def chk_db_readonly(p, ctx):
    if not ctx.get("db"):
        return "SKIPPED", "chạy với --db để kiểm quyền readonly_user", False
    try:
        from mcp_server.utils.db import get_conn
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SHOW GRANTS FOR CURRENT_USER()")
            grants = " ".join(str(list(r.values())[0]) for r in cur.fetchall()).upper()
    except Exception as e:
        return "SKIPPED", f"không kết nối được MySQL: {str(e)[:60]}", False
    dangerous = [w for w in ("DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "INDEX",
                             "CREATE", "ALL PRIVILEGES", "FILE", "SUPER") if w in grants]
    if dangerous:
        return "NOT_BLOCKED", f"readonly_user có quyền {dangerous}", False
    return "BLOCKED", "readonly_user chỉ có SELECT/PROCESS", False


CHECKS = {name[4:]: fn for name, fn in globals().items() if name.startswith("chk_")}


# ============================================================
# MAIN
# ============================================================

def run(use_db: bool = False) -> dict:
    _setup_env()
    from security.injection_tests.payloads import PAYLOADS

    ctx = {"db": use_db}
    results = []
    for p in PAYLOADS:
        layer_results = []
        for c in p["checks"]:
            try:
                status, evidence, audited = CHECKS[c](p, ctx)
            except Exception as e:  # lỗi trong lúc kiểm = KHÔNG coi là chặn
                status, evidence, audited = "NOT_BLOCKED", f"lỗi khi kiểm: {e!r}"[:200], False
            layer_results.append({"check": c, "layer": LAYER_NAMES[c], "status": status,
                                  "evidence": evidence, "audited": audited})
        ran = [l for l in layer_results if l["status"] != "SKIPPED"]
        blocked = bool(ran) and all(l["status"] == "BLOCKED" for l in ran)
        uses_tool6 = any(l["check"].startswith("tool6_") and l["check"] != "tool6_signature"
                         for l in layer_results)
        results.append({
            "id": p["id"], "group": p["group"], "title": p["title"],
            "vector": p["vector"] if isinstance(p["vector"], str) else json.dumps(p["vector"], ensure_ascii=False),
            "n_variants": len(_vectors(p)),
            "blocked": blocked,
            "blocked_by": sorted({l["layer"] for l in layer_results if l["status"] == "BLOCKED"}),
            "audit_logged": (all(l["audited"] for l in layer_results if l["check"].startswith("tool6_")
                                 and l["check"] != "tool6_signature") if uses_tool6 else None),
            "llm_affected": None,  # cần agent LLM thật, chưa đo
            "layers": layer_results,
        })

    summary = {
        "run_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "mode": "db" if use_db else "offline",
        "total": len(results),
        "blocked": sum(r["blocked"] for r in results),
        "by_layer": {},
    }
    for r in results:
        for l in r["layers"]:
            s = summary["by_layer"].setdefault(l["layer"], {"BLOCKED": 0, "NOT_BLOCKED": 0, "SKIPPED": 0})
            s[l["status"]] += 1
    return {"summary": summary, "results": results}


def _yn(v):
    return "—" if v is None else ("Có" if v else "Không")


def to_markdown(report: dict) -> str:
    s = report["summary"]
    lines = [
        f"_Lần chạy: {s['run_at']} · chế độ: {s['mode']} · chặn {s['blocked']}/{s['total']} kịch bản._",
        "",
        "| # | Nhóm | Kịch bản | Biến thể | Lớp chặn | Ghi audit log? | LLM bị ảnh hưởng? | Kết quả |",
        "|:-:|:----:|----------|:-------:|----------|:--------------:|:-----------------:|:-------:|",
    ]
    for r in report["results"]:
        skipped = [l["layer"] for l in r["layers"] if l["status"] == "SKIPPED"]
        layers = ", ".join(r["blocked_by"]) + (f" _(bỏ qua: {', '.join(skipped)})_" if skipped else "")
        lines.append(
            f"| {r['id']} | {r['group']} | {r['title']} | {r['n_variants']} | {layers} | "
            f"{_yn(r['audit_logged'])} | chưa đo | {'✅ Chặn' if r['blocked'] else '❌ Lọt'} |"
        )
    lines += ["", "| Lớp | Chặn | Không chặn | Bỏ qua |", "|-----|:----:|:----------:|:------:|"]
    for layer, c in sorted(s["by_layer"].items()):
        lines.append(f"| {layer} | {c['BLOCKED']} | {c['NOT_BLOCKED']} | {c['SKIPPED']} |")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Chạy 20 kịch bản injection")
    ap.add_argument("--db", action="store_true", help="kiểm thêm quyền readonly_user trên MySQL")
    args = ap.parse_args(argv)

    report = run(use_db=args.db)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    (LOG_DIR / "injection_results.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (LOG_DIR / "injection_results.md").write_text(to_markdown(report), encoding="utf-8")

    for r in report["results"]:
        mark = "✅" if r["blocked"] else "❌"
        print(f"{mark} {r['id']} {r['title'][:55]:55} | {', '.join(r['blocked_by'])}")
        for l in r["layers"]:
            if l["status"] != "BLOCKED":
                print(f"     {l['status']:11} {l['check']}: {l['evidence'][:90]}")
    s = report["summary"]
    print(f"\nChặn {s['blocked']}/{s['total']} kịch bản · kết quả: {LOG_DIR / 'injection_results.json'}")
    return 0 if s["blocked"] == s["total"] else 1


if __name__ == "__main__":
    sys.exit(main())
