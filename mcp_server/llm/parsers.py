"""
mcp_server/llm/parsers.py
-------------------------

CHỨC NĂNG :
    Phân tích và kiểm tra câu trả lời JSON của LLM (IndexProposal / RewriteProposal).

PHỤ TRÁCH  : Vũ    |    REVIEW: Tường

LƯU Ý:
    - Kiểm bằng JSON Schema; sai schema thì báo để agent retry.
    - Ràng buộc index_name: ^idx_[a-z0-9_]{1,50}$, tối đa 5 cột, cột phải tồn tại trong schema.
    - Sau retry vẫn hỏng thì đánh dấu parse_failed (có tính vào thống kê).

THAM KHẢO  : docs/api-contract.md (mục 2), tests/test_llm_parser.py

TRẠNG THÁI : Đang làm.
"""
import json

from jsonschema import Draft202012Validator

NONEMPTY_STRING = {"type": "string", "pattern": r"\S"}
COLUMN_SCHEMA = {
    "type": "object",
    "properties": {
        "name": NONEMPTY_STRING,
        "order": {"enum": ["ASC", "DESC"]},
    },
    "required": ["name", "order"],
    "additionalProperties": False,
}
INDEX_SCHEMA = {
    "type": "object",
    "properties": {
        "type": {"const": "index"},
        "table": NONEMPTY_STRING,
        "columns": {
            "type": "array", "items": COLUMN_SCHEMA, "minItems": 1, "maxItems": 5,
        },
        "index_name": {"type": "string", "pattern": r"^idx_[a-z0-9_]{1,50}$"},
        "rationale": NONEMPTY_STRING,
        "target_query_ids": {
            "type": "array", "items": NONEMPTY_STRING,
            "minItems": 1, "uniqueItems": True,
        },
    },
    "required": ["type", "table", "columns", "index_name", "rationale", "target_query_ids"],
    "additionalProperties": False,
}
REWRITE_SCHEMA = {
    "type": "object",
    "properties": {
        "type": {"const": "rewrite"},
        "original_query_id": NONEMPTY_STRING,
        "rewritten_sql": NONEMPTY_STRING,
        "rationale": NONEMPTY_STRING,
    },
    "required": ["type", "original_query_id", "rewritten_sql", "rationale"],
    "additionalProperties": False,
}
RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "query_id": NONEMPTY_STRING,
        "diagnosis": NONEMPTY_STRING,
        "proposals": {"type": "array", "items": {"type": "object"}},
        "confidence": {"enum": ["low", "medium", "high"]},
    },
    "required": ["query_id", "diagnosis", "proposals", "confidence"],
    "additionalProperties": False,
}

RESPONSE_VALIDATOR = Draft202012Validator(RESPONSE_SCHEMA)
INDEX_VALIDATOR = Draft202012Validator(INDEX_SCHEMA)
REWRITE_VALIDATOR = Draft202012Validator(REWRITE_SCHEMA)


def _validate_schema(value: object, validator: Draft202012Validator) -> None:
    """Đổi lỗi JSON Schema thành lỗi ngắn theo tên trường để agent retry."""
    error = next(validator.iter_errors(value), None)
    if error is None:
        return
    if error.validator == "required":
        field = next(name for name in error.validator_value if name not in error.instance)
    elif error.validator == "additionalProperties":
        field = next(name for name in error.instance if name not in error.schema["properties"])
    else:
        field = ".".join(map(str, error.path)) or "response"
    message = f"{field}: sai JSON Schema ({error.validator})"
    if error.validator == "type":
        raise TypeError(message)
    raise ValueError(message)


def parse_llm_response(
    text: str, expected_query_id: str, schema_data: dict | None = None,
) -> dict:
    """Kiểm JSON Schema và đối chiếu index với phần ``data`` của Tool 2.

    ``expected_query_id`` do caller cấp; thiếu schema thì không chấp nhận index.
    """
    result = json.loads(text)
    _validate_schema(result, RESPONSE_VALIDATOR)
    # LLM phải trả đúng ID yêu cầu; digest slow log và ID q01–q30 là hai loại ID khác nhau.
    if result["query_id"] != expected_query_id:
        raise ValueError("query_id không khớp yêu cầu phân tích")

    # Kiểm tra từng đề xuất; loại chưa hỗ trợ phải bị từ chối.
    for proposal in result["proposals"]:
        if proposal.get("type") == "rewrite":
            _validate_schema(proposal, REWRITE_VALIDATOR)
            if proposal["original_query_id"] != expected_query_id:
                raise ValueError("original_query_id không khớp query_id của caller")
            continue

        if proposal.get("type") != "index":
            raise ValueError("type proposal chưa được hỗ trợ")
        _validate_schema(proposal, INDEX_VALIDATOR)
        if any(query_id != expected_query_id for query_id in proposal["target_query_ids"]):
            raise ValueError("target_query_ids phải khớp query_id của caller")

        # Schema lấy từ Tool 2, không đọc DB thêm trong parser.
        if schema_data is None:
            raise ValueError("schema_data là bắt buộc với index proposal")
        if not isinstance(schema_data, dict) or not isinstance(schema_data.get("tables"), list):
            raise TypeError("schema_data phải chứa danh sách tables")

        table_name = proposal["table"]
        table = next(
            (item for item in schema_data["tables"]
             if isinstance(item, dict) and item.get("name") == table_name),
            None,
        )
        if table is None:
            raise ValueError("table không tồn tại trong schema")
        if not isinstance(table.get("columns"), list) or not isinstance(table.get("indexes"), list):
            raise TypeError("schema_data thiếu columns hoặc indexes của table")

        known_columns = {
            item.get("name") for item in table["columns"] if isinstance(item, dict)
        }
        for column in proposal["columns"]:
            name = column["name"]
            if name not in known_columns:
                raise ValueError("column name không tồn tại trong table")

        known_indexes = {
            item.get("name") for item in table["indexes"] if isinstance(item, dict)
        }
        if proposal["index_name"] in known_indexes:
            raise ValueError("index_name đã tồn tại trong table")

        # Tool 2 chỉ trả tên cột của index; so theo tiền tố tên cột, chưa xét ASC/DESC.
        proposed_columns = [column["name"] for column in proposal["columns"]]
        for index in table["indexes"]:
            existing_columns = index.get("columns") if isinstance(index, dict) else None
            if isinstance(existing_columns, list) and (
                proposed_columns == existing_columns[:len(proposed_columns)]
            ):
                raise ValueError("columns là tiền tố thừa của index hiện có")

    return result
