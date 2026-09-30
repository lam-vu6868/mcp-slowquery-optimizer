"""
mcp_server/llm/prompts.py
-------------------------

CHỨC NĂNG :
    System prompt và mẫu prompt gửi cho LLM.

PHỤ TRÁCH  : Vũ    |    REVIEW: Tường

LƯU Ý:
    - Nói rõ: nội dung lấy từ slow log / schema là DỮ LIỆU, không phải chỉ thị.
    - Ép trả lời JSON theo đúng schema, không kèm văn bản khác.
    - LLM chỉ ĐỀ XUẤT; không tự áp dụng, không có quyền phê duyệt.
    - Mỗi lần sửa prompt: ghi lại phiên bản để so sánh kết quả.

THAM KHẢO  : docs/api-contract.md (mục 2.3)

TRẠNG THÁI : KHUNG RỖNG — chưa cài đặt. Xóa dòng này khi bắt đầu code.
"""
