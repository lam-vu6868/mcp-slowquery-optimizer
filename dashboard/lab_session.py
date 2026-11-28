"""
dashboard/lab_session.py
------------------------

CHỨC NĂNG : Tạm trỏ kết nối của tiến trình Dashboard sang validation lab (127.0.0.1:3309)
            trong lúc Validation / Approve / Reject, rồi trả lại cấu hình cũ.
PHỤ TRÁCH  : Tình    |    REVIEW: Hải
LƯU Ý      : Không nới guard của backend: validate_from_dashboard vẫn tự kiểm cổng 3309
             và marker `mcp-validation-lab-v1`. Dashboard một người dùng cục bộ nên đổi
             Config tạm thời là đủ an toàn; việc đo dài chạy ở tiến trình riêng (lab_jobs).
"""

from contextlib import contextmanager

from mcp_server.utils.config import Config

LAB_HOST = "127.0.0.1"
LAB_PORT = 3309
LAB_DB = "shopdb"


@contextmanager
def lab_session():
    saved = (Config.DB_HOST, Config.DB_PORT, Config.DB_NAME)
    Config.DB_HOST, Config.DB_PORT, Config.DB_NAME = LAB_HOST, LAB_PORT, LAB_DB
    try:
        yield
    finally:
        Config.DB_HOST, Config.DB_PORT, Config.DB_NAME = saved
