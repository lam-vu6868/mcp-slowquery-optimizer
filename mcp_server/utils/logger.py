"""
mcp_server/utils/logger.py
--------------------------

CHỨC NĂNG :
    Cấu hình logging thống nhất cho toàn dự án.

PHỤ TRÁCH  : Vũ    |    REVIEW: Hải

LƯU Ý:
    - Không log bí mật (API key, token, mật khẩu).
    - Audit log của Tool 6 tách riêng khỏi log thường.

TRẠNG THÁI : KHUNG RỖNG — chưa cài đặt. Xóa dòng này khi bắt đầu code.
"""
"""
mcp_server/utils/logger.py
--------------------------
CHỨC NĂNG: Logging cho MCP Server.
PHỤ TRÁCH: Vũ    |    REVIEW: Hải
"""
import logging
import os


def get_logger(name: str) -> logging.Logger:
    """
    Tạo logger cho 1 module.
    
    Args:
        name: Tên module (thường dùng __name__)
    
    Returns:
        logging.Logger đã cấu hình
    """
    logger = logging.getLogger(name)
    logger.setLevel(os.getenv("LOG_LEVEL", "INFO"))

    # Tránh add handler trùng lặp
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        ))
        logger.addHandler(handler)

    return logger