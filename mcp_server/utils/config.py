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

TRẠNG THÁI : ĐANG LÀM — đã đọc cấu hình LLM từ settings.yaml.
""" 

"""
mcp_server/utils/config.py
--------------------------
CHỨC NĂNG: Đọc cấu hình từ file .env.
PHỤ TRÁCH: Vũ    |    REVIEW: Hải
"""
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Database
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = int(os.getenv("DB_PORT", "3307"))
    DB_NAME = os.getenv("DB_NAME", "shopdb")
    DB_USER = os.getenv("DB_USER", "readonly_user")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "readonly_pass")
    DB_ADMIN_USER = os.getenv("DB_ADMIN_USER", "index_admin")
    DB_ADMIN_PASSWORD = os.getenv("DB_ADMIN_PASSWORD", "admin_pass")

    # LLM
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic")
    LLM_MODEL = os.getenv("LLM_MODEL", "claude-sonnet-4-5")
    LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.0"))

    # Security
    APPROVAL_SECRET = os.getenv("APPROVAL_SECRET", "")
    APPROVAL_TOKEN_TTL = int(os.getenv("APPROVAL_TOKEN_TTL", "600"))

    # App
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    SLOW_QUERY_THRESHOLD = float(os.getenv("SLOW_QUERY_THRESHOLD", "0.5"))
    MAX_EXECUTION_TIME = int(os.getenv("MAX_EXECUTION_TIME", "30000"))


def load_llm_settings(path: str | Path | None = None) -> dict:
    """Đọc và kiểm tra phần ``llm`` trong settings.yaml, không đọc bí mật."""
    settings_path = Path(path) if path is not None else (
        Path(__file__).resolve().parents[2] / "config" / "settings.yaml"
    )
    with settings_path.open(encoding="utf-8") as file:
        document = yaml.safe_load(file)
    if not isinstance(document, dict):
        raise TypeError("settings.yaml phải là YAML object")
    if "llm" not in document:
        raise ValueError("settings.yaml thiếu phần llm")
    llm = document["llm"]
    if not isinstance(llm, dict):
        raise TypeError("settings.yaml.llm phải là YAML object")
    model = llm.get("model")
    if not isinstance(model, str) or not model.strip():
        raise ValueError("llm.model phải là chuỗi không rỗng")
    temperature = llm.get("temperature")
    if type(temperature) not in (int, float) or not 0 <= temperature <= 0.2:
        raise ValueError("llm.temperature phải từ 0 đến 0.2")
    for key in ("max_tokens", "max_tool_calls_per_query"):
        value = llm.get(key)
        if type(value) is not int or value < 1:
            raise ValueError(f"llm.{key} phải là số nguyên dương")
    retries = llm.get("json_retry")
    if type(retries) is not int or not 0 <= retries <= 2:
        raise ValueError("llm.json_retry phải là số nguyên từ 0 đến 2")

    return {
        "model": model,
        "temperature": temperature,
        "max_tokens": llm["max_tokens"],
        "max_tool_calls_per_query": llm["max_tool_calls_per_query"],
        "json_retry": retries,
    }
