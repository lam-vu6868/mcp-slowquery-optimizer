"""
mcp_server/server.py
--------------------

CHỨC NĂNG :
    Điểm vào (entry point) của MCP Server: đăng ký Tool 1-5 cho LLM host.

PHỤ TRÁCH  : Vũ    |    REVIEW: Hải

LƯU Ý:
    - Chạy: python -m mcp_server.server
    - Tool 6 (apply_optimization) KHÔNG được cấp cho LLM host: chỉ Tool 1-5.
    - Tool 4/5 cấp cho LLM qua explain_for_llm/benchmark_for_llm, không đăng ký hàm đầy đủ tham số.
    - Tool 6 chỉ gọi được từ backend Dashboard, kèm approval token.
    - Mọi SQL nhận từ bên ngoài phải qua security/ast_whitelist.py trước khi chạy.
    - Dữ liệu lấy từ DB (comment, SQL trong log) phải qua sanitize và gắn nhãn untrusted.

CẦN LÀM:
    [ ] Tách registry riêng cho Tool 6.

THAM KHẢO  : docs/api-contract.md, docs/architecture.md

TRẠNG THÁI : ĐANG LÀM — Tool 1-5 đã đăng ký; Tool 6 và LLM host chưa tích hợp.
"""
from mcp.server.mcpserver import MCPServer

from mcp_server.tools.benchmark import benchmark_for_llm
from mcp_server.tools.explain import explain_for_llm
from mcp_server.tools.schema import get_schema
from mcp_server.tools.slow_queries import get_slow_queries
from mcp_server.tools.stats import get_table_stats

mcp = MCPServer("mcp-slowquery-optimizer")
mcp.tool()(get_slow_queries)
mcp.tool()(get_schema)
mcp.tool()(get_table_stats)
mcp.tool(name="explain_query")(explain_for_llm)
mcp.tool(name="benchmark_query")(benchmark_for_llm)


if __name__ == "__main__":
    mcp.run(transport="stdio")
