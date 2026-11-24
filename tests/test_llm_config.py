"""
tests/test_llm_config.py
------------------------

CHỨC NĂNG :
    Kiểm tra cấu hình LLM từ settings.yaml trước khi agent dùng.

PHỤ TRÁCH  : Vũ    |    REVIEW: Hải

THAM KHẢO  : mcp_server/utils/config.py, config/settings.yaml
"""

import pytest

from mcp_server.utils.config import load_llm_settings


def test_load_llm_settings_reads_project_config():
    """Model và các giới hạn phải lấy từ file cấu hình của dự án."""
    settings = load_llm_settings()

    assert settings == {
        "model": "openai/gpt-oss-120b",
        "temperature": 0.0,
        "max_tokens": 2000,
        "max_tool_calls_per_query": 8,
        "json_retry": 2,
    }


@pytest.mark.parametrize("field, bad_value", [
    ("model", '""'),
    ("temperature", "0.5"),
    ("max_tokens", "0"),
    ("max_tool_calls_per_query", "0"),
    ("json_retry", "3"),
])
def test_load_llm_settings_rejects_invalid_values(tmp_path, field, bad_value):
    """Cấu hình sai phải bị chặn trước khi gửi request đến LLM."""
    values = {
        "model": '"claude-sonnet-5-5"',
        "temperature": "0.0",
        "max_tokens": "2000",
        "max_tool_calls_per_query": "8",
        "json_retry": "2",
    }
    values[field] = bad_value
    settings_file = tmp_path / "settings.yaml"
    settings_file.write_text(
        "llm:\n" + "".join(f"  {name}: {value}\n" for name, value in values.items()),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=field):
        load_llm_settings(settings_file)
