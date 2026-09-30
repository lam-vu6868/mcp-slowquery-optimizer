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

TRẠNG THÁI : KHUNG RỖNG — chưa cài đặt. Xóa dòng này khi bắt đầu code.
"""
