"""
tests/test_llm_parser.py
------------------------

CHỨC NĂNG :
    Test parser JSON của LLM: schema đúng/sai, index_name không hợp lệ, cột không tồn tại.

PHỤ TRÁCH  : Vũ    |    REVIEW: Tường

THAM KHẢO  : mcp_server/llm/parsers.py

TRẠNG THÁI : Đang làm.
"""
import json

import pytest

from mcp_server.llm.parsers import parse_llm_response


def test_parse_llm_response_keeps_caller_query_id():
    """JSON hợp lệ được trả về nguyên vẹn khi ID trùng với ID caller gửi."""
    response = {
        "query_id": "q07",
        "diagnosis": "Thiếu index",
        "proposals": [],
        "confidence": "medium",
    }

    assert parse_llm_response(json.dumps(response), "q07") == response


def test_parse_llm_response_rejects_wrong_query_id():
    """Từ chối câu trả lời gắn nhầm sang yêu cầu phân tích khác."""
    response = '{"query_id": "q08", "diagnosis": "x", "proposals": [], "confidence": "low"}'

    with pytest.raises(ValueError, match="query_id"):
        parse_llm_response(response, "q07")


@pytest.mark.parametrize(
    ("field", "bad_value", "error_type"),
    [
        ("diagnosis", None, TypeError),
        ("proposals", {}, TypeError),
        ("confidence", "certain", ValueError),
    ],
)
def test_parse_llm_response_rejects_invalid_top_level_fields(field, bad_value, error_type):
    """Mỗi trường chung sai kiểu hoặc sai giá trị đều phải bị từ chối."""
    response = {
        "query_id": "q07",
        "diagnosis": "Thiếu index",
        "proposals": [],
        "confidence": "medium",
    }
    response[field] = bad_value

    with pytest.raises(error_type, match=field):
        parse_llm_response(json.dumps(response), "q07")


@pytest.mark.parametrize(
    ("index_name", "column_count", "order", "error_field"),
    [
        ("bad_name", 1, "ASC", "index_name"),
        ("idx_orders_status", 0, "ASC", "columns"),
        ("idx_orders_status", 6, "ASC", "columns"),
        ("idx_orders_status", 1, "SIDEWAYS", "order"),
    ],
)
def test_parse_llm_response_rejects_invalid_index_proposal(
    index_name, column_count, order, error_field
):
    """Từ chối đề xuất index sai tên, số cột hoặc chiều sắp xếp."""
    proposal = {
        "type": "index",
        "table": "orders",
        "columns": [{"name": "status", "order": order} for _ in range(column_count)],
        "index_name": index_name,
        "rationale": "Lọc theo status",
        "target_query_ids": ["q07"],
    }
    response = {
        "query_id": "q07",
        "diagnosis": "Thiếu index",
        "proposals": [proposal],
        "confidence": "medium",
    }

    with pytest.raises(ValueError, match=error_field):
        parse_llm_response(json.dumps(response), "q07")


def _valid_index_response():
    """Tạo câu trả lời index hợp lệ để mỗi test chỉ thay một điều kiện."""
    return {
        "query_id": "q07",
        "diagnosis": "Thiếu index",
        "proposals": [{
            "type": "index",
            "table": "orders",
            "columns": [{"name": "status", "order": "ASC"}],
            "index_name": "idx_orders_status",
            "rationale": "Lọc theo status",
            "target_query_ids": ["q07"],
        }],
        "confidence": "medium",
    }


SCHEMA_DATA = {
    "tables": [{
        "name": "orders",
        "columns": [{"name": "order_id"}, {"name": "status"}],
        "indexes": [{"name": "PRIMARY", "columns": ["order_id"]}],
    }],
}


def test_parse_llm_response_accepts_index_with_known_table_and_column():
    """Parser dùng danh sách bảng/cột do Tool 2 trả để chấp nhận index."""
    response = _valid_index_response()

    assert parse_llm_response(json.dumps(response), "q07", SCHEMA_DATA) == response


def test_parse_llm_response_requires_schema_for_index():
    """Không xác nhận index khi caller chưa cung cấp schema để đối chiếu."""
    with pytest.raises(ValueError, match="schema"):
        parse_llm_response(json.dumps(_valid_index_response()), "q07")


@pytest.mark.parametrize(
    ("change", "error_field"),
    [
        ({"table": "missing"}, "table"),
        ({"columns": [{"name": "missing", "order": "ASC"}]}, "name"),
        ({"index_name": "idx_orders_existing"}, "index_name"),
        ({"target_query_ids": ["q08"]}, "target_query_ids"),
        ({"rationale": ""}, "rationale"),
    ],
)
def test_parse_llm_response_rejects_index_not_matching_context(change, error_field):
    """Từ chối index sai schema, ID yêu cầu hoặc thiếu lý do đề xuất."""
    response = _valid_index_response()
    response["proposals"][0].update(change)
    schema_data = SCHEMA_DATA
    if change.get("index_name") == "idx_orders_existing":
        schema_data = {"tables": [{
            "name": "orders",
            "columns": [{"name": "status"}],
            "indexes": [{"name": "idx_orders_existing", "columns": ["status"]}],
        }]}

    with pytest.raises(ValueError, match=error_field):
        parse_llm_response(json.dumps(response), "q07", schema_data)


def _valid_rewrite_response():
    """Tạo câu trả lời rewrite hợp lệ cho các test bên dưới."""
    return {
        "query_id": "q07",
        "diagnosis": "Điều kiện lọc chưa dùng được index",
        "proposals": [{
            "type": "rewrite",
            "original_query_id": "q07",
            "rewritten_sql": "SELECT order_id FROM orders WHERE status = 'paid'",
            "rationale": "Giữ điều kiện lọc trực tiếp trên cột",
        }],
        "confidence": "medium",
    }


def test_parse_llm_response_accepts_rewrite():
    """Rewrite hợp lệ không cần schema để kiểm tra cấu trúc."""
    response = _valid_rewrite_response()

    assert parse_llm_response(json.dumps(response), "q07") == response


@pytest.mark.parametrize(
    ("field", "bad_value"),
    [
        ("original_query_id", "q08"),
        ("rewritten_sql", ""),
        ("rationale", ""),
    ],
)
def test_parse_llm_response_rejects_invalid_rewrite(field, bad_value):
    """Từ chối rewrite sai ID hoặc thiếu SQL/lý do."""
    response = _valid_rewrite_response()
    response["proposals"][0][field] = bad_value

    with pytest.raises(ValueError, match=field):
        parse_llm_response(json.dumps(response), "q07")
