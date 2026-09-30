"""
dashboard/pages/2_proposals.py
------------------------------

CHỨC NĂNG :
    TAB 2 — Đề xuất của LLM + trạng thái Validation + nút Approve / Reject.

PHỤ TRÁCH  : Tình    |    REVIEW: Tường

LƯU Ý:
    - Nút Approve -> server sinh approval token (dùng 1 lần, hết hạn 10 phút) -> backend gọi Tool 6.
    - Đề xuất loại 'rewrite' chỉ HIỂN THỊ, KHÔNG có nút Apply.
    - Chỉ cho Approve khi validation_report.status == 'passed'.

THAM KHẢO  : docs/api-contract.md (Tool 6, mục 4), security/approval.py

TRẠNG THÁI : KHUNG RỖNG — chưa cài đặt. Xóa dòng này khi bắt đầu code.
"""
