"""
mcp_server/utils/config.py
--------------------------

CHỨC NĂNG :
    Đọc cấu hình từ config/settings.yaml và biến môi trường (.env).

PHỤ TRÁCH  : Vũ    |    REVIEW: Hải

LƯU Ý:
    - Bí mật (API key, mật khẩu DB, APPROVAL_SECRET) chỉ lấy từ .env, không ghi trong yaml.
    - Không in giá trị bí mật ra log.

THAM KHẢO  : config/settings.yaml, .env.example

TRẠNG THÁI : KHUNG RỖNG — chưa cài đặt. Xóa dòng này khi bắt đầu code.
""" 

"""
mcp_server/utils/config.py
--------------------------
CHỨC NĂNG: Đọc cấu hình từ file .env.
PHỤ TRÁCH: Vũ    |    REVIEW: Hải
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Database
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = int(os.getenv("DB_PORT", 3307))
    DB_NAME = os.getenv("DB_NAME", "shopdb")
    DB_USER = os.getenv("DB_USER", "readonly_user")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "readonly_pass")
    DB_ADMIN_USER = os.getenv("DB_ADMIN_USER", "index_admin")
    DB_ADMIN_PASSWORD = os.getenv("DB_ADMIN_PASSWORD", "admin_pass")

    # LLM
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic")
    LLM_MODEL = os.getenv("LLM_MODEL", "claude-sonnet-4-5")
    LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", 0.0))

    # Security
    APPROVAL_SECRET = os.getenv("APPROVAL_SECRET", "")
    APPROVAL_TOKEN_TTL = int(os.getenv("APPROVAL_TOKEN_TTL", 600))

    # App
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    SLOW_QUERY_THRESHOLD = float(os.getenv("SLOW_QUERY_THRESHOLD", 0.5))
    MAX_EXECUTION_TIME = int(os.getenv("MAX_EXECUTION_TIME", 30000))