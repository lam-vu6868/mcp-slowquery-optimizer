"""
mcp_server/validation/write_overhead.py
---------------------------------------

CHỨC NĂNG :
    Đo chi phí INSERT của index đề xuất trên MySQL lab riêng bằng cùng dữ liệu CSV.

PHỤ TRÁCH  : Hải    |    REVIEW: Vũ

LƯU Ý:
    - Chỉ kết nối lab ở 127.0.0.1:3308 và kiểm marker trước mọi DDL/INSERT.
    - Hai bảng TEMPORARY có cùng mẫu ban đầu; chỉ bảng sau có index đề xuất.
    - CREATE TABLE LIKE không sao chép FOREIGN KEY; report phải ghi giới hạn này.

THAM KHẢO : docs/api-contract.md (mục 4), config/settings.yaml

TRẠNG THÁI : ĐANG LÀM — đã đo mẫu orders trên MySQL write lab thật; chưa đo đủ các bảng.
"""

import csv
import os
import time
from contextlib import contextmanager
from itertools import islice
from pathlib import Path

import pymysql
from dotenv import dotenv_values

from mcp_server.tools.apply import TrialIndex, _quote_identifier
from mcp_server.validation.validator import _settings

LAB_HOST = "127.0.0.1"
LAB_PORT = 3308
LAB_MARKER = "mcp-write-lab-v1"
LAB_DB = "shopdb"
BEFORE_TABLE = "mcp_write_before"
AFTER_TABLE = "mcp_write_after"
BATCH_SIZE = 1000


@contextmanager
def get_write_lab_conn():
    """Kết nối riêng, không sử dụng tài khoản index_admin của shopdb chính."""
    env_path = Path(__file__).resolve().parents[2] / ".env.write-lab"
    password = os.getenv("WRITE_LAB_ROOT_PASSWORD") or dotenv_values(env_path).get(
        "WRITE_LAB_ROOT_PASSWORD"
    )
    if not password:
        raise ValueError("thiếu WRITE_LAB_ROOT_PASSWORD cho lab riêng")
    conn = pymysql.connect(
        host=LAB_HOST, port=LAB_PORT, user="root", password=password,
        database=LAB_DB, charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=10, read_timeout=60, write_timeout=60,
        autocommit=False,
    )
    try:
        yield conn
    finally:
        conn.close()


def _read_batch(reader, columns: list[str], size: int) -> list[tuple]:
    rows = list(islice(reader, size))
    if len(rows) != size:
        raise ValueError("CSV không đủ số dòng cho hai pha đo")
    return [tuple(None if row[col] == r"\N" else row[col] for col in columns)
            for row in rows]


def measure_insert_overhead(proposal: dict, *, csv_dir: str | Path,
                            connect=get_write_lab_conn) -> dict:
    """Đo cùng N INSERT trên hai bảng tạm, sau khi preload cùng N dòng."""
    trial = TrialIndex(proposal)
    required_rows = _settings()["write_overhead_rows"]
    source = Path(csv_dir) / f"{trial.table_name}.csv"
    if not source.is_file():
        raise FileNotFoundError("không tìm thấy CSV của bảng đề xuất")

    before = _quote_identifier(BEFORE_TABLE)
    after = _quote_identifier(AFTER_TABLE)
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT marker FROM mcp_write_lab_identity LIMIT 1")
        identity = cur.fetchone()
        if not identity or identity.get("marker") != LAB_MARKER:
            raise RuntimeError("DB không có marker của write lab riêng")
        cur.execute(
            "SELECT COLUMN_NAME, EXTRA FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s ORDER BY ORDINAL_POSITION",
            (LAB_DB, trial.table_name),
        )
        schema_columns = cur.fetchall()
        if not schema_columns or "auto_increment" not in schema_columns[0]["EXTRA"]:
            raise ValueError("bảng lab thiếu khóa chính AUTO_INCREMENT")
        header = [item["COLUMN_NAME"] for item in schema_columns]
        if any(name not in header for name in trial.column_names):
            raise ValueError("cột index không có trong lab")
        cur.execute(
            "SELECT 1 FROM information_schema.STATISTICS "
            "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND INDEX_NAME=%s LIMIT 1",
            (LAB_DB, trial.table_name, trial.index_name),
        )
        if cur.fetchone() is not None:
            raise ValueError("index đề xuất đã tồn tại trong lab")

        with source.open(encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            if reader.fieldnames != header:
                raise ValueError("header CSV không khớp schema lab")
            columns = header[1:]  # khóa chính được MySQL tự cấp trên mỗi bảng tạm
            col_sql = ", ".join(_quote_identifier(name) for name in columns)
            placeholders = ", ".join(["%s"] * len(columns))
            inserts = {
                BEFORE_TABLE: f"INSERT INTO {before} ({col_sql}) VALUES ({placeholders})",
                AFTER_TABLE: f"INSERT INTO {after} ({col_sql}) VALUES ({placeholders})",
            }
            cur.execute(f"CREATE TEMPORARY TABLE {before} LIKE {trial.table}")
            cur.execute(f"CREATE TEMPORARY TABLE {after} LIKE {trial.table}")
            elapsed = {BEFORE_TABLE: 0.0, AFTER_TABLE: 0.0}
            for phase in ("preload", "measure"):
                if phase == "measure":
                    parts = ", ".join(
                        f"{_quote_identifier(name)} {direction}"
                        for name, direction in trial.column_parts
                    )
                    cur.execute(
                        f"CREATE INDEX {trial.name} ON {after} ({parts}) INVISIBLE"
                    )
                remaining = required_rows
                batch_no = 0
                while remaining:
                    count = min(BATCH_SIZE, remaining)
                    batch = _read_batch(reader, columns, count)
                    order = (BEFORE_TABLE, AFTER_TABLE) if batch_no % 2 == 0 else (
                        AFTER_TABLE, BEFORE_TABLE
                    )
                    for table in order:
                        started = time.perf_counter()
                        cur.executemany(inserts[table], batch)
                        conn.commit()
                        if phase == "measure":
                            elapsed[table] += time.perf_counter() - started
                    remaining -= count
                    batch_no += 1

    before_seconds = elapsed[BEFORE_TABLE]
    after_seconds = elapsed[AFTER_TABLE]
    if before_seconds <= 0 or after_seconds <= 0:
        raise ValueError("không đo được thời gian INSERT")
    before_rate = required_rows / before_seconds
    after_rate = required_rows / after_seconds
    return {
        "insert_throughput_change_pct": round((after_rate / before_rate - 1) * 100, 2),
        "before_rows_per_second": round(before_rate, 2),
        "after_rows_per_second": round(after_rate, 2),
        "before_seconds": round(before_seconds, 3),
        "after_seconds": round(after_seconds, 3),
        "sample_rows": required_rows,
        "preload_rows": required_rows,
        "measurement_scope": "isolated_lab",
        "lab_sample": "CSV sample; TEMPORARY tables omit foreign keys",
    }
