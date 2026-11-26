"""
mcp_server/dashboard_server.py
------------------------------

CHỨC NĂNG : Tạo registry MCP riêng cho backend Dashboard, chỉ có Tool 6.
PHỤ TRÁCH  : Vũ    |    REVIEW: Tình + Hải
LƯU Ý      : Không chạy registry này trong LLM host; backend Dashboard cấp applier
             với OS account của tiến trình Streamlit cục bộ trước khi gọi.
THAM KHẢO  : docs/api-contract.md (Tool 6), mcp_server/server.py

TRẠNG THÁI : ĐANG LÀM — backend đã gọi registry trong test giả; giao diện chưa nối.
"""

from mcp.server.mcpserver import MCPServer


def make_dashboard_mcp(applier) -> MCPServer:
    """Chỉ backend Dashboard giữ registry này cùng applier đã cấu hình."""
    mcp = MCPServer("mcp-slowquery-dashboard")

    def apply_optimization(proposal_id: str, approval_token: str) -> dict:
        return applier.apply_optimization(proposal_id, approval_token)

    mcp.tool(name="apply_optimization")(apply_optimization)
    return mcp
