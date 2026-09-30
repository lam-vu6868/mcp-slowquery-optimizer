"""
mcp_server/server.py
--------------------

CHỨC NĂNG :
    Điểm vào (entry point) của MCP Server: đăng ký 6 tool và phục vụ yêu cầu từ LLM host.

PHỤ TRÁCH  : Vũ    |    REVIEW: Hải

LƯU Ý:
    - Chạy: python -m mcp_server.server
    - Tool 6 (apply_optimization) KHÔNG được cấp cho LLM host: chỉ Tool 1-5.
    - Tool 6 chỉ gọi được từ backend Dashboard, kèm approval token.
    - Mọi SQL nhận từ bên ngoài phải qua security/ast_whitelist.py trước khi chạy.
    - Dữ liệu lấy từ DB (comment, SQL trong log) phải qua sanitize và gắn nhãn untrusted.

CẦN LÀM:
    [ ] Đăng ký Tool 1-5 cho LLM.
    [ ] Tách registry riêng cho Tool 6.

THAM KHẢO  : docs/api-contract.md, docs/architecture.md

TRẠNG THÁI : KHUNG RỖNG — chưa cài đặt. Xóa dòng này khi bắt đầu code.
"""
