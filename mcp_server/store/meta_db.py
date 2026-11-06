"""
mcp_server/store/meta_db.py
---------------------------
CHỨC NĂNG:
    Kết nối SQLite cho dữ liệu "meta" của hệ thống: proposals, validation_reports,
    audit_log, used_tokens. TÁCH HẲN khỏi MySQL thực nghiệm (shopdb), nên
    readonly_user và LLM không đọc/ghi được.

PHỤ TRÁCH: Hải (store)  |  Tình viết phần bảo mật (audit_log, used_tokens)  |  REVIEW: Vũ

LƯU Ý:
    - Đường dẫn file lấy từ biến môi trường META_DB_PATH, mặc định
      data/meta/optimizer_meta.sqlite3 (đã thêm vào .gitignore).
    - Test đặt META_DB_PATH sang thư mục tạm để không đụng dữ liệu thật.
"""
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_META_DB = PROJECT_ROOT / "data" / "meta" / "optimizer_meta.sqlite3"

SCHEMA = """
CREATE TABLE IF NOT EXISTS proposals (
    proposal_id   TEXT PRIMARY KEY,
    query_id      TEXT,
    type          TEXT NOT NULL CHECK (type IN ('index', 'rewrite')),
    payload_json  TEXT NOT NULL,
    status        TEXT NOT NULL,
    source        TEXT NOT NULL DEFAULT 'llm',
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS validation_reports (
    proposal_id   TEXT PRIMARY KEY REFERENCES proposals(proposal_id),
    status        TEXT NOT NULL CHECK (status IN ('passed', 'failed')),
    report_json   TEXT NOT NULL,
    created_at    TEXT NOT NULL
);

-- Audit log: CHỈ GHI THÊM. Trigger bên dưới chặn UPDATE/DELETE.
CREATE TABLE IF NOT EXISTS audit_log (
    seq           INTEGER PRIMARY KEY AUTOINCREMENT,
    ts            TEXT NOT NULL,
    action        TEXT NOT NULL,
    proposal_id   TEXT,
    ddl_hash      TEXT,
    result        TEXT NOT NULL,
    error_code    TEXT,
    message       TEXT,
    actor         TEXT,
    source        TEXT
);

CREATE TRIGGER IF NOT EXISTS audit_log_no_update
BEFORE UPDATE ON audit_log
BEGIN
    SELECT RAISE(ABORT, 'audit_log is append-only');
END;

CREATE TRIGGER IF NOT EXISTS audit_log_no_delete
BEFORE DELETE ON audit_log
BEGIN
    SELECT RAISE(ABORT, 'audit_log is append-only');
END;

-- Nonce của token đã dùng (chống dùng lại). PRIMARY KEY => INSERT trùng sẽ lỗi.
CREATE TABLE IF NOT EXISTS used_tokens (
    nonce         TEXT PRIMARY KEY,
    proposal_id   TEXT NOT NULL,
    used_at       TEXT NOT NULL
);
"""


def meta_db_path() -> Path:
    return Path(os.getenv("META_DB_PATH") or DEFAULT_META_DB)


@contextmanager
def get_meta_conn():
    """Mở kết nối SQLite meta, tự tạo bảng nếu chưa có. Commit khi thoát êm."""
    path = meta_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(SCHEMA)
        yield conn
    finally:
        conn.close()
