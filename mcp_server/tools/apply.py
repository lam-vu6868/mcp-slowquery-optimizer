"""
mcp_server/tools/apply.py
-------------------------
CHỨC NĂNG:
    TOOL 6 — apply_optimization: áp dụng THẬT một đề xuất index đã được người duyệt.

PHỤ TRÁCH: Tình    |    REVIEW: Vũ + Hải (BẮT BUỘC cả hai)
THAM KHẢO: docs/api-contract.md (Tool 6), security/approval.py, docs/architecture.md (5.4)

QUY TẮC CỨNG (đã cài đặt):
    1. KHÔNG cấp cho LLM. server.py chỉ đăng ký Tool 1–5 cho LLM host; Tool 6 chỉ backend
       Dashboard gọi (xem LLM_EXPOSED = False bên dưới để server.py kiểm).
    2. Input CHỈ gồm proposal_id + approval_token. Không có tham số SQL/DDL/approved.
    3. DDL do server tự sinh từ proposal có cấu trúc (build_ddl), định danh kiểm bằng regex
       và đối chiếu schema thật; DDL sinh ra còn phải qua AST whitelist.
    4. Proposal 'rewrite' → FORBIDDEN. Chưa pass validation → VALIDATION_FAILED.
    5. Token: đúng chữ ký, chưa hết hạn, chưa dùng, khớp proposal_id + hash DDL → nếu không: TOKEN_INVALID.
    6. Dùng tài khoản index_admin (chỉ INDEX/ALTER/SELECT trên shopdb).
    7. MỌI lần gọi (kể cả bị từ chối) đều ghi audit_log. Không ghi token.

THỨ TỰ KIỂM TRA:
    input → proposal tồn tại → loại → trạng thái/validation → sinh DDL + AST → token (đốt)
    → schema thật (bảng/cột) → trạng thái index → chạy DDL → audit.
    Token chỉ bị "đốt" sau khi các kiểm tra không cần DB đã qua, để lỗi cấu hình không làm
    mất token oan.
"""
import sys
import os

sys.path.insert(
    0,
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import json
import re
import time
from typing import Optional, Protocol

from mcp_server.store import audit_log, proposals as store
from mcp_server.utils.logger import get_logger
from security import approval
from security.ast_whitelist import check as ast_check

logger = get_logger(__name__)

TOOL_NAME = "apply_optimization"
LLM_EXPOSED = False  # server.py PHẢI kiểm cờ này và không đăng ký tool cho LLM

PROPOSAL_ID_RE = re.compile(r"^p_[A-Za-z0-9_]{1,60}$")
INDEX_NAME_RE = re.compile(r"^idx_[a-z0-9_]{1,50}$")
IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
MAX_INDEX_COLUMNS = 5


# ============================================================
# SINH DDL TỪ PROPOSAL CÓ CẤU TRÚC
# ============================================================

def _normalize_columns(columns) -> list[tuple[str, str]]:
    if not isinstance(columns, list) or not columns:
        raise ValueError("columns phải là danh sách không rỗng")
    if len(columns) > MAX_INDEX_COLUMNS:
        raise ValueError(f"Tối đa {MAX_INDEX_COLUMNS} cột")
    out, seen = [], set()
    for c in columns:
        if isinstance(c, str):
            name, order = c, "ASC"
        elif isinstance(c, dict):
            name, order = c.get("name"), (c.get("order") or "ASC")
        else:
            raise ValueError(f"Cột không hợp lệ: {c!r}")
        if not isinstance(name, str) or not IDENT_RE.fullmatch(name):
            raise ValueError(f"Tên cột không hợp lệ: {name!r}")
        order = str(order).upper()
        if order not in ("ASC", "DESC"):
            raise ValueError(f"order phải là ASC/DESC: {order!r}")
        if name.lower() in seen:
            raise ValueError(f"Cột trùng: {name}")
        seen.add(name.lower())
        out.append((name, order))
    return out


def build_ddl(payload: dict) -> str:
    """
    Sinh câu CREATE INDEX từ IndexProposal. Ném ValueError nếu cấu trúc sai.
    Hàm thuần (không đụng DB) — Dashboard dùng để lấy DDL ký token, Tool 6 dùng lại để so khớp.
    """
    if not isinstance(payload, dict) or payload.get("type") != "index":
        raise ValueError("Chỉ proposal loại 'index' mới sinh DDL")
    table = payload.get("table")
    index_name = payload.get("index_name")
    if not isinstance(table, str) or not IDENT_RE.fullmatch(table):
        raise ValueError(f"Tên bảng không hợp lệ: {table!r}")
    if not isinstance(index_name, str) or not INDEX_NAME_RE.fullmatch(index_name):
        raise ValueError(f"index_name phải khớp {INDEX_NAME_RE.pattern}: {index_name!r}")
    cols = _normalize_columns(payload.get("columns"))
    col_sql = ", ".join(f"`{n}`" + (" DESC" if o == "DESC" else "") for n, o in cols)
    return f"CREATE INDEX `{index_name}` ON `{table}` ({col_sql})"


def rollback_ddl(payload: dict) -> str:
    build_ddl(payload)  # validate
    return f"DROP INDEX `{payload['index_name']}` ON `{payload['table']}`"


# ============================================================
# TRUY CẬP DB (index_admin) — tách ra để test bằng fake
# ============================================================

class IndexAdminDB(Protocol):
    def table_columns(self, table: str) -> set[str]: ...
    def index_state(self, table: str, index_name: str) -> Optional[dict]: ...
    def execute_ddl(self, ddl: str) -> None: ...
    def index_size_bytes(self, table: str, index_name: str) -> Optional[int]: ...


class MySQLIndexAdmin:
    """Cài đặt thật bằng tài khoản index_admin."""

    def __init__(self):
        from mcp_server.utils.config import Config
        from mcp_server.utils.db import get_admin_conn
        self._get_conn = get_admin_conn
        self._schema = Config.DB_NAME

    def table_columns(self, table: str) -> set[str]:
        with self._get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s",
                (self._schema, table),
            )
            return {r["COLUMN_NAME"].lower() for r in cur.fetchall()}

    def index_state(self, table: str, index_name: str) -> Optional[dict]:
        with self._get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT COLUMN_NAME, SEQ_IN_INDEX, IS_VISIBLE FROM information_schema.STATISTICS "
                "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND INDEX_NAME = %s "
                "ORDER BY SEQ_IN_INDEX",
                (self._schema, table, index_name),
            )
            rows = cur.fetchall()
        if not rows:
            return None
        return {
            "columns": [r["COLUMN_NAME"].lower() for r in rows],
            "visible": str(rows[0]["IS_VISIBLE"]).upper() == "YES",
        }

    def execute_ddl(self, ddl: str) -> None:
        with self._get_conn() as conn, conn.cursor() as cur:
            cur.execute("SET SESSION lock_wait_timeout = 30")
            cur.execute(ddl)
            conn.commit()

    def index_size_bytes(self, table: str, index_name: str) -> Optional[int]:
        try:
            with self._get_conn() as conn, conn.cursor() as cur:
                cur.execute(
                    "SELECT stat_value * @@innodb_page_size AS size_bytes "
                    "FROM mysql.innodb_index_stats WHERE database_name = %s "
                    "AND table_name = %s AND index_name = %s AND stat_name = 'size'",
                    (self._schema, table, index_name),
                )
                row = cur.fetchone()
                return int(row["size_bytes"]) if row and row["size_bytes"] is not None else None
        except Exception:  # index_admin có thể không có quyền đọc mysql.* → bỏ qua
            return None


# ============================================================
# RESPONSE + AUDIT HELPERS
# ============================================================

def _meta(t_start: float) -> dict:
    return {"tool": TOOL_NAME, "duration_ms": round((time.perf_counter() - t_start) * 1000, 2),
            "truncated": False}


def _reject(code: str, message: str, t_start: float, *, proposal_id=None, ddl_hash=None,
            actor=None, source=None, detail=None, result="rejected") -> str:
    try:
        audit_id = audit_log.log(
            action=audit_log.ACTION_APPLY, result=result, proposal_id=proposal_id,
            ddl_hash=ddl_hash, error_code=code, message=message, actor=actor, source=source,
        )
    except Exception as e:  # audit hỏng không được làm lộ lỗi khác, nhưng phải log
        logger.error(f"Không ghi được audit_log: {e}")
        audit_id = None
    logger.warning(f"Tool 6 từ chối [{code}] proposal={proposal_id}: {message}")
    return json.dumps({
        "ok": False,
        "data": None,
        "error": {"code": code, "message": message, "detail": {**(detail or {}), "audit_id": audit_id}},
        "meta": _meta(t_start),
    }, ensure_ascii=False)


# ============================================================
# TOOL 6
# ============================================================

async def apply_optimization(
    proposal_id: str,
    approval_token: str,
    *,
    actor: Optional[str] = None,
    source: str = "dashboard",
    db: Optional[IndexAdminDB] = None,
) -> str:
    """
    Áp dụng proposal index đã được duyệt.

    Args:
        proposal_id: id proposal trong store (vd p_20251020_ab12cd)
        approval_token: token do security.approval.issue_token sinh khi người bấm Approve
        actor/source: thông tin ghi audit (ai duyệt, gọi từ đâu) — không ảnh hưởng quyền
        db: chỉ dùng trong test để thay MySQL bằng fake

    Returns:
        JSON string theo api-contract (Tool 6)
    """
    t_start = time.perf_counter()
    ctx = {"actor": actor, "source": source}

    # 1. Input
    if not isinstance(proposal_id, str) or not PROPOSAL_ID_RE.fullmatch(proposal_id):
        return _reject("INVALID_INPUT", "proposal_id không hợp lệ", t_start,
                       proposal_id=str(proposal_id)[:80] if proposal_id else None, **ctx)

    # 2. Proposal
    prop = store.get_proposal(proposal_id)
    if prop is None:
        return _reject("NOT_FOUND", "Không tìm thấy proposal", t_start, proposal_id=proposal_id, **ctx)
    payload = prop["payload"]

    # 3. Loại
    if prop["type"] == "rewrite" or payload.get("type") == "rewrite":
        return _reject("FORBIDDEN", "Proposal rewrite chỉ để hiển thị, không được áp dụng vào DB",
                       t_start, proposal_id=proposal_id, **ctx)

    # 4. Trạng thái + validation
    if prop["status"] == store.STATUS_APPLIED:
        return _reject("INVALID_INPUT", "Proposal đã được áp dụng trước đó", t_start,
                       proposal_id=proposal_id, **ctx)
    report = store.get_validation_report(proposal_id)
    # apply_failed (vd mất kết nối DB) được thử lại với token MỚI vì validation vẫn hợp lệ
    approvable = (store.STATUS_VALIDATED, store.STATUS_APPLY_FAILED)
    if prop["status"] not in approvable or not report or report.get("status") != "passed":
        return _reject("VALIDATION_FAILED", "Proposal chưa pass Validation Layer", t_start,
                       proposal_id=proposal_id, detail={"status": prop["status"]}, **ctx)

    # 5. Sinh DDL + AST (phòng thủ chiều sâu)
    try:
        ddl = build_ddl(payload)
    except ValueError as e:
        return _reject("INVALID_INPUT", f"Proposal sai cấu trúc: {e}", t_start,
                       proposal_id=proposal_id, **ctx)
    dhash = approval.ddl_hash(ddl)
    ok, reason = ast_check(ddl)
    if not ok or not ddl.upper().startswith("CREATE INDEX"):
        return _reject("AST_REJECTED", f"DDL sinh ra không qua AST whitelist: {reason}", t_start,
                       proposal_id=proposal_id, ddl_hash=dhash, **ctx)

    # 6. Token (đốt token nếu hợp lệ)
    chk = approval.verify_token(approval_token, proposal_id, ddl, consume=True)
    if not chk.ok:
        return _reject("TOKEN_INVALID", chk.message, t_start, proposal_id=proposal_id,
                       ddl_hash=dhash, detail={"reason": chk.reason}, **ctx)

    # 7. Đối chiếu schema thật + trạng thái index, rồi chạy DDL
    db = db or MySQLIndexAdmin()
    table, index_name = payload["table"], payload["index_name"]
    wanted_cols = [n.lower() for n, _ in _normalize_columns(payload["columns"])]
    try:
        cols = db.table_columns(table)
        if not cols:
            return _reject("NOT_FOUND", f"Bảng không tồn tại: {table}", t_start,
                           proposal_id=proposal_id, ddl_hash=dhash, **ctx)
        missing = [c for c in wanted_cols if c not in cols]
        if missing:
            return _reject("NOT_FOUND", f"Cột không tồn tại: {missing}", t_start,
                           proposal_id=proposal_id, ddl_hash=dhash, **ctx)

        state = db.index_state(table, index_name)
        if state is not None and state["columns"] != wanted_cols:
            return _reject("INVALID_INPUT",
                           f"Đã có index tên {index_name} nhưng khác cột {state['columns']}",
                           t_start, proposal_id=proposal_id, ddl_hash=dhash, **ctx)

        if state is None:
            executed = ddl
            db.execute_ddl(ddl)
        elif not state["visible"]:
            # Validation Layer đã tạo index INVISIBLE → chỉ cần bật lên
            executed = f"ALTER TABLE `{table}` ALTER INDEX `{index_name}` VISIBLE"
            db.execute_ddl(executed)
        else:
            executed = None  # đã visible: không làm gì (idempotent)

        size = db.index_size_bytes(table, index_name)
    except Exception as e:
        store.set_status(proposal_id, store.STATUS_APPLY_FAILED)
        return _reject("INTERNAL", f"Lỗi khi chạy DDL: {str(e)[:200]}", t_start,
                       proposal_id=proposal_id, ddl_hash=dhash, result="error", **ctx)

    # 8. Thành công
    store.set_status(proposal_id, store.STATUS_APPLIED)
    audit_id = audit_log.log(
        action=audit_log.ACTION_APPLY, result="success", proposal_id=proposal_id,
        ddl_hash=dhash, message=executed or "index đã visible sẵn", **ctx,
    )
    logger.info(f"Tool 6 áp dụng {proposal_id}: {executed}")
    return json.dumps({
        "ok": True,
        "data": {
            "applied": True,
            "ddl": ddl,
            "executed_ddl": executed,
            "index_visible": True,
            "index_size_bytes": size,
            "audit_id": audit_id,
            "rollback_ddl": rollback_ddl(payload),
        },
        "error": None,
        "meta": _meta(t_start),
    }, ensure_ascii=False)
