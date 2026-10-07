"""
mcp_server/utils/db.py
----------------------
CHỨC NĂNG:
    Kết nối MySQL. Cung cấp 2 kết nối tách biệt: readonly_user và index_admin.

PHỤ TRÁCH: Hải    |    REVIEW: Vũ

LƯU Ý:
    - Tool 1-5 chỉ dùng kết nối readonly.
    - index_admin chỉ Tool 6 được dùng.
    - Đặt MAX_EXECUTION_TIME cho session phân tích.

THAM KHẢO: db/init.sql
"""
import pymysql
from contextlib import contextmanager
from mcp_server.utils.config import Config


@contextmanager
def get_conn():
    """
    Kết nối READ-ONLY — dùng cho Tool 1-5.
    """
    conn = pymysql.connect(
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        database=Config.DB_NAME,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=10,
    )
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def get_admin_conn():
    """
    Kết nối ADMIN — CHỈ Tool 6 dùng (index_admin).
    """
    conn = pymysql.connect(
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        user=Config.DB_ADMIN_USER,
        password=Config.DB_ADMIN_PASSWORD,
        database=Config.DB_NAME,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=10,
    )
    try:
        yield conn
    finally:
        conn.close()