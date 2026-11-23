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
import re


def parse_llm_response(
    text: str, expected_query_id: str, schema_data: dict | None = None,
) -> dict:
    """Đọc JSON từ LLM và đối chiếu index với phần ``data`` của Tool 2.

    ``expected_query_id`` do caller cấp; thiếu schema thì không chấp nhận index.
    """
    result = json.loads(text)

    if not isinstance(result, dict):
        raise TypeError("Câu trả lời LLM phải là JSON object")
    # LLM phải trả đúng ID yêu cầu; digest slow log và ID q01–q30 là hai loại ID khác nhau.
    if result.get("query_id") != expected_query_id:
        raise ValueError("query_id không khớp yêu cầu phân tích")
    if not isinstance(result.get("diagnosis"), str):
        raise TypeError("diagnosis phải là chuỗi")
    if not isinstance(result.get("proposals"), list):
        raise TypeError("proposals phải là danh sách")
    if result.get("confidence") not in ("low", "medium", "high"):
        raise ValueError("confidence không hợp lệ")

    # Kiểm tra từng đề xuất; loại chưa hỗ trợ phải bị từ chối.
    for proposal in result["proposals"]:
        if not isinstance(proposal, dict):
            raise TypeError("proposal phải là JSON object")
        if proposal.get("type") == "rewrite":
            if proposal.get("original_query_id") != expected_query_id:
                raise ValueError("original_query_id không khớp query_id của caller")

            for field in ("rewritten_sql", "rationale"):
                value = proposal.get(field)
                if not isinstance(value, str):
                    raise TypeError(f"{field} phải là chuỗi")
                if not value.strip():
                    raise ValueError(f"{field} không được rỗng")
            continue

        if proposal.get("type") != "index":
            raise ValueError("type proposal chưa được hỗ trợ")

        index_name = proposal.get("index_name")
        if not isinstance(index_name, str):
            raise TypeError("index_name phải là chuỗi")
        if re.fullmatch(r"idx_[a-z0-9_]{1,50}", index_name) is None:
            raise ValueError("index_name không hợp lệ")

        columns = proposal.get("columns")
        if not isinstance(columns, list):
            raise TypeError("columns phải là danh sách")
        if not 1 <= len(columns) <= 5:
            raise ValueError("columns phải có từ 1 đến 5 cột")

        for column in columns:
            if not isinstance(column, dict):
                raise TypeError("mỗi column phải là JSON object")
            if column.get("order") not in ("ASC", "DESC"):
                raise ValueError("order phải là ASC hoặc DESC")

        rationale = proposal.get("rationale")
        if not isinstance(rationale, str):
            raise TypeError("rationale phải là chuỗi")
        if not rationale.strip():
            raise ValueError("rationale không được rỗng")

        target_ids = proposal.get("target_query_ids")
        if not isinstance(target_ids, list):
            raise TypeError("target_query_ids phải là danh sách")
        if not target_ids or any(query_id != expected_query_id for query_id in target_ids):
            raise ValueError("target_query_ids phải khớp query_id của caller")

        # Schema lấy từ Tool 2, không đọc DB thêm trong parser.
        if schema_data is None:
            raise ValueError("schema_data là bắt buộc với index proposal")
        if not isinstance(schema_data, dict) or not isinstance(schema_data.get("tables"), list):
            raise TypeError("schema_data phải chứa danh sách tables")

        table_name = proposal.get("table")
        if not isinstance(table_name, str):
            raise TypeError("table phải là chuỗi")
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
        for column in columns:
            name = column.get("name")
            if not isinstance(name, str):
                raise TypeError("column name phải là chuỗi")
            if name not in known_columns:
                raise ValueError("column name không tồn tại trong table")

        known_indexes = {
            item.get("name") for item in table["indexes"] if isinstance(item, dict)
        }
        if index_name in known_indexes:
            raise ValueError("index_name đã tồn tại trong table")

    return result
