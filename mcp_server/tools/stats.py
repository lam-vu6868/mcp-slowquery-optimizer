"""
mcp_server/tools/stats.py
-------------------------

CHỨC NĂNG :
    TOOL 3 — get_table_stats: số dòng, cardinality, phân bố giá trị từng cột.

PHỤ TRÁCH  : Vũ    |    REVIEW: Hải

LƯU Ý:
    - Dùng số ước lượng và mẫu cửa sổ PK có giới hạn, KHÔNG COUNT(*) toàn bảng mỗi lần gọi.
    - top_values chỉ trả cho cột có cardinality thấp (<= 50).
    - Giá trị mẫu và nhãn top_values là dữ liệu untrusted; áp giới hạn và làm sạch trước khi trả.
    - Dùng readonly_user.

THAM KHẢO  : docs/api-contract.md (Tool 3)

TRẠNG THÁI : ĐÃ KIỂM CHỨNG — đã có unit test và gọi qua MCP stdio trên MySQL thật.
"""
import hashlib
import json
import time
import unicodedata
from collections import Counter

import pymysql

from mcp_server.utils.config import Config
from mcp_server.utils.db import get_conn
from mcp_server.utils.logger import get_logger

logger = get_logger(__name__)
DATASET_VERSION = "shopdb.multitable-v1"
TOP_VALUE_COLUMNS = {"status", "category", "city", "state", "country"}
ORDERED_TYPES = {
    "tinyint", "smallint", "mediumint", "int", "bigint", "decimal", "float", "double",
    "date", "datetime", "timestamp", "time", "year",
}
INTEGER_TYPES = {"tinyint", "smallint", "mediumint", "int", "bigint"}


def _quote(name: str) -> str:
    """Quote định danh đã lấy từ information_schema."""
    return "`" + name.replace("`", "``") + "`"


def _public_value(value: object) -> str:
    text = str(value)
    return "".join(char for char in text if not unicodedata.category(char).startswith("C"))[:100]


def _column_stats(name: str, data_type: str, rows: list[dict], observed: int) -> dict:
    values = [row[name] for row in rows if row[name] is not None]
    cardinality = len(set(values))
    result = {
        "name": name,
        "cardinality": cardinality,
        "null_ratio": round(1 - len(values) / observed, 4) if observed else None,
        "top_values": [],
        "min": None,
        "max": None,
    }
    if values and data_type in ORDERED_TYPES:
        result["min"] = min(values)
        result["max"] = max(values)
    if name in TOP_VALUE_COLUMNS and cardinality <= 50:
        counts = Counter(values)
        result["top_values"] = [
            {"value": _public_value(value), "ratio": round(count / observed, 4), "untrusted": True}
            for value, count in counts.most_common(10)
        ]
    return result


async def get_table_stats(table: str | None = None, columns: list[str] | None = None) -> str:
    started = time.perf_counter()

    def response(data=None, error=None, truncated=False):
        return json.dumps({
            "ok": error is None,
            "data": data,
            "error": error,
            "meta": {
                "tool": "get_table_stats",
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                "truncated": truncated,
            },
        }, ensure_ascii=False, default=str)

    if (type(table) is not str or not table.strip() or
            columns is not None and (
                type(columns) is not list or len(columns) > 10 or
                any(type(name) is not str or not name.strip() for name in columns)
            )):
        return response(error={"code": "INVALID_INPUT", "message": "table/columns không hợp lệ", "detail": {}})

    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("""
                SELECT TABLE_ROWS, DATA_LENGTH, INDEX_LENGTH
                FROM information_schema.TABLES
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND TABLE_TYPE = 'BASE TABLE'
            """, (Config.DB_NAME, table))
            table_info = cur.fetchone()
            if table_info is None:
                return response(error={"code": "NOT_FOUND", "message": "Bảng không tồn tại", "detail": {}})

            cur.execute("""
                SELECT COLUMN_NAME, DATA_TYPE, COLUMN_KEY
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
                ORDER BY ORDINAL_POSITION
            """, (Config.DB_NAME, table))
            metadata = cur.fetchall()
            available = {row["COLUMN_NAME"]: row for row in metadata}
            names = list(dict.fromkeys(columns)) if columns else list(available)[:10]
            if any(name not in available for name in names):
                return response(error={"code": "NOT_FOUND", "message": "Cột không tồn tại", "detail": {}})
            pk = next((row["COLUMN_NAME"] for row in metadata
                       if row["COLUMN_KEY"] == "PRI" and row["DATA_TYPE"] in INTEGER_TYPES), None)
            if pk is None:
                return response(error={"code": "INVALID_INPUT", "message": "Bảng cần PK số nguyên", "detail": {}})

            quoted_table = _quote(table)
            quoted_pk = _quote(pk)
            cur.execute(f"SET SESSION MAX_EXECUTION_TIME = {min(Config.MAX_EXECUTION_TIME, 5000)}")
            cur.execute(f"SELECT {quoted_pk} FROM {quoted_table} ORDER BY {quoted_pk} LIMIT 1")
            first = cur.fetchone()
            cur.execute(f"SELECT {quoted_pk} FROM {quoted_table} ORDER BY {quoted_pk} DESC LIMIT 1")
            last = cur.fetchone()
            sampled = {}
            if first and last:
                lower, upper = first[pk], last[pk]
                selected = list(dict.fromkeys([pk, *names]))
                fields = ", ".join(_quote(name) for name in selected)
                seed = f"{DATASET_VERSION}:{table}"
                for window in range(10):
                    digest = hashlib.sha256(f"{seed}:{window}".encode()).digest()
                    anchor = lower + int.from_bytes(digest[:8], "big") % (upper - lower + 1)
                    cur.execute(
                        f"SELECT {fields} FROM {quoted_table} "
                        f"WHERE {quoted_pk} >= %s ORDER BY {quoted_pk} LIMIT 100",
                        (anchor,),
                    )
                    for row in cur.fetchall():
                        sampled[row[pk]] = row
            rows = list(sampled.values())[:1000]
    except pymysql.MySQLError as exc:
        logger.error("get_table_stats failed: %s", type(exc).__name__)
        code = "TIMEOUT" if exc.args and exc.args[0] in {3024, 1317} else "INTERNAL"
        return response(error={"code": code, "message": "Không đọc được thống kê bảng", "detail": {}})

    observed = len(rows)
    return response(data={
        "table": table,
        "row_count_estimate": table_info["TABLE_ROWS"],
        "data_bytes": table_info["DATA_LENGTH"],
        "index_bytes": table_info["INDEX_LENGTH"],
        "sample": {
            "method": "pk_windows", "max_rows": 1000, "observed_rows": observed,
            "seed": f"{DATASET_VERSION}:{table}",
        },
        "columns": [_column_stats(name, available[name]["DATA_TYPE"], rows, observed)
                    for name in names],
    }, truncated=not columns and len(available) > 10)
