"""
mcp_server/tools/schema.py
--------------------------

CHỨC NĂNG :
    TOOL 2 — get_schema: trả cấu trúc bảng (cột, index hiện có, khóa ngoại).

PHỤ TRÁCH  : Vũ    |    REVIEW: Hải

LƯU Ý:
    - Comment của bảng/cột là kênh injection: phải lọc và gắn untrusted.
    - Trả trạng thái visible/invisible; size_bytes=null khi không có quyền đo từng index.
    - Dùng readonly_user.

THAM KHẢO  : docs/api-contract.md (Tool 2)

TRẠNG THÁI : ĐANG LÀM — hàm đã thử với MySQL; chưa đăng ký MCP.
"""
import json
import time

import pymysql

from mcp_server.utils.config import Config
from mcp_server.utils.db import get_conn
from mcp_server.utils.logger import get_logger
from mcp_server.utils.sanitize import sanitize_comment

logger = get_logger(__name__)


async def get_schema(tables: list[str] | None = None) -> str:
    started = time.perf_counter()

    def response(data=None, error=None, truncated=False):
        return json.dumps({
            "ok": error is None,
            "data": data,
            "error": error,
            "meta": {
                "tool": "get_schema",
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                "truncated": truncated,
            },
        }, ensure_ascii=False)

    if tables is not None and (
        type(tables) is not list
        or len(tables) > 100
        or any(type(name) is not str or not name.strip() for name in tables)
    ):
        return response(error={
            "code": "INVALID_INPUT", "message": "tables phải là danh sách tối đa 100 tên bảng", "detail": {},
        })

    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("""
                SELECT TABLE_NAME, ENGINE
                FROM information_schema.TABLES
                WHERE TABLE_SCHEMA = %s AND TABLE_TYPE = 'BASE TABLE'
                ORDER BY TABLE_NAME
            """, (Config.DB_NAME,))
            available = {row["TABLE_NAME"]: row for row in cur.fetchall()}
            names = list(dict.fromkeys(tables)) if tables else list(available)
            missing = [name for name in names if name not in available]
            if missing:
                return response(error={
                    "code": "NOT_FOUND", "message": "Bảng không tồn tại trong schema thực nghiệm", "detail": {},
                })
            truncated = len(names) > 100
            names = names[:100]
            if not names:
                return response(data={"tables": []})

            placeholders = ", ".join(["%s"] * len(names))
            params = (Config.DB_NAME, *names)
            cur.execute(f"""
                SELECT TABLE_NAME, COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_KEY, COLUMN_COMMENT
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME IN ({placeholders})
                ORDER BY TABLE_NAME, ORDINAL_POSITION
            """, params)
            column_rows = cur.fetchall()
            cur.execute(f"""
                SELECT TABLE_NAME, INDEX_NAME, COLUMN_NAME, SEQ_IN_INDEX, NON_UNIQUE, IS_VISIBLE
                FROM information_schema.STATISTICS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME IN ({placeholders})
                ORDER BY TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX
            """, params)
            index_rows = cur.fetchall()
            cur.execute(f"""
                SELECT TABLE_NAME, CONSTRAINT_NAME, COLUMN_NAME, REFERENCED_TABLE_NAME,
                       REFERENCED_COLUMN_NAME, ORDINAL_POSITION
                FROM information_schema.KEY_COLUMN_USAGE
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME IN ({placeholders})
                  AND REFERENCED_TABLE_NAME IS NOT NULL
                ORDER BY TABLE_NAME, CONSTRAINT_NAME, ORDINAL_POSITION
            """, params)
            foreign_key_rows = cur.fetchall()
    except pymysql.MySQLError as exc:
        logger.error("get_schema failed: %s", type(exc).__name__)
        return response(error={
            "code": "INTERNAL", "message": "Không đọc được cấu trúc bảng", "detail": {},
        })

    result = {name: {
        "name": name,
        "engine": available[name]["ENGINE"],
        "columns": [],
        "indexes": [],
        "foreign_keys": [],
    } for name in names}
    for row in column_rows:
        columns = result[row["TABLE_NAME"]]["columns"]
        if len(columns) >= 100:
            truncated = True
            continue
        columns.append({
            "name": row["COLUMN_NAME"],
            "type": row["COLUMN_TYPE"],
            "nullable": row["IS_NULLABLE"] == "YES",
            "key": row["COLUMN_KEY"],
            "comment": sanitize_comment(row["COLUMN_COMMENT"]),
            "untrusted": True,
        })

    indexes = {}
    for row in index_rows:
        table_name = row["TABLE_NAME"]
        key = (table_name, row["INDEX_NAME"])
        if key not in indexes:
            table_indexes = result[table_name]["indexes"]
            if len(table_indexes) >= 100:
                truncated = True
                continue
            index = {
                "name": row["INDEX_NAME"], "columns": [],
                "unique": row["NON_UNIQUE"] == 0,
                "visible": row["IS_VISIBLE"] == "YES",
                "size_bytes": None,
            }
            indexes[key] = index
            table_indexes.append(index)
        if key in indexes:
            indexes[key]["columns"].append(row["COLUMN_NAME"])

    foreign_keys = {}
    for row in foreign_key_rows:
        table_name = row["TABLE_NAME"]
        key = (table_name, row["CONSTRAINT_NAME"])
        if key not in foreign_keys:
            table_foreign_keys = result[table_name]["foreign_keys"]
            if len(table_foreign_keys) >= 100:
                truncated = True
                continue
            foreign_key = {
                "name": row["CONSTRAINT_NAME"], "columns": [],
                "referenced_table": row["REFERENCED_TABLE_NAME"], "referenced_columns": [],
            }
            foreign_keys[key] = foreign_key
            table_foreign_keys.append(foreign_key)
        if key in foreign_keys:
            foreign_keys[key]["columns"].append(row["COLUMN_NAME"])
            foreign_keys[key]["referenced_columns"].append(row["REFERENCED_COLUMN_NAME"])

    return response(data={"tables": list(result.values())}, truncated=truncated)
