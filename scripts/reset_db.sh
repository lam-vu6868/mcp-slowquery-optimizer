#!/usr/bin/env bash
# scripts/reset_db.sh
# -------------------
#
# CHỨC NĂNG :
#     Xóa và tạo lại CSDL thực nghiệm (dùng khi cần làm lại từ đầu).
#
# PHỤ TRÁCH  : Hải    |    REVIEW: Vũ
#
# LƯU Ý:
#     - NGUY HIỂM: xóa toàn bộ dữ liệu. Nên yêu cầu người dùng gõ 'yes' xác nhận.
#     - Chạy bằng Git Bash trên Windows.
#
# CẦN LÀM:
#     [ ] docker compose down -v
#     [ ] docker compose up -d
#     [ ] chạy db/schema.sql
#
# TRẠNG THÁI : KHUNG RỖNG — chưa cài đặt. Xóa dòng này khi bắt đầu code.
