"""
mcp_server/llm/agent.py
-----------------------

CHỨC NĂNG :
    Agent loop: gọi Claude, cho phép gọi Tool 1-5, thu về đề xuất cuối cùng dạng JSON.

PHỤ TRÁCH  : Vũ    |    REVIEW: Tường

LƯU Ý:
    - CHỈ nạp danh sách Tool 1-5 cho LLM (không có apply_optimization).
    - Ghim model version, temperature thấp (0-0.2) để Consistency Rate có ý nghĩa; lấy từ config/settings.yaml.
    - Ghi lại mọi lần chạy (prompt, tool call, kết quả) vào data/outputs/runs/ để tái lập.
    - Có giới hạn số lượt tool call và ngân sách token mỗi query.

CẦN LÀM:
    [ ] Vòng lặp tool-use.
    [ ] Retry khi JSON sai schema (tối đa 2 lần).

THAM KHẢO  : docs/api-contract.md (mục 2.3), config/settings.yaml

TRẠNG THÁI : ĐANG LÀM — đã có bước gọi LLM cuối; chưa có vòng tool-use/retry.
"""

from mcp_server.llm.parsers import parse_llm_response
from mcp_server.llm.prompts import SYSTEM_PROMPT, build_analysis_prompt

ALLOWED_TOOL_NAMES = frozenset({
    "get_slow_queries", "get_schema", "get_table_stats",
    "explain_query", "benchmark_query",
})


async def analyze_query(
    query_id: str,
    sql: str,
    *,
    llm_client,
    mcp_client,
    llm_settings: dict,
    schema_data: dict | None = None,
) -> dict:
    """Gửi một lượt phân tích và kiểm tra JSON cuối bằng parser.

    Client được truyền từ caller để test bằng LLM/MCP giả; vòng gọi tool sẽ làm sau.
    """
    user_prompt = build_analysis_prompt(query_id, sql)
    tool_list = await mcp_client.list_tools()
    available = {
        tool.name: tool for tool in tool_list.tools
        if tool.name in ALLOWED_TOOL_NAMES
    }
    if set(available) != ALLOWED_TOOL_NAMES:
        raise RuntimeError("MCP chưa cung cấp đủ Tool 1–5")

    # Lọc tại host để Tool 6 không lọt vào danh sách gửi cho LLM.
    tools = [{
        "name": tool.name,
        "description": tool.description or "",
        "input_schema": tool.input_schema,
    } for tool in available.values()]
    response = await llm_client.messages.create(
        model=llm_settings["model"],
        max_tokens=llm_settings["max_tokens"],
        temperature=llm_settings["temperature"],
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
        tools=tools,
    )
    if response.stop_reason == "tool_use":
        raise RuntimeError("tool_use chưa được xử lý ở bước này")
    if response.stop_reason != "end_turn":
        raise RuntimeError(f"LLM dừng trước câu trả lời cuối: {response.stop_reason}")

    text = "".join(block.text for block in response.content if block.type == "text")
    if not text:
        raise ValueError("LLM không trả JSON")
    return parse_llm_response(text, query_id, schema_data)
