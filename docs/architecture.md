# Kiến trúc hệ thống

> **Phụ trách:** Vũ · **Review:** cả nhóm · **Trạng thái:** KHUNG RỖNG, cần chốt cùng `api-contract.md`.
> Sơ đồ tổng quát xem `README.md`. File này bổ sung phần chi tiết còn thiếu.

## 1. Các thành phần và ranh giới process

_TODO: vẽ sơ đồ. Cần trả lời rõ:_

- **Ai là MCP host / client** (nơi chạy agent loop gọi Claude)? Chạy ở process nào?
- **Streamlit gọi tool bằng cách nào**: import Python trực tiếp, hay qua MCP client?
- **Ai gọi Validation Layer** và ai gọi Tool 6?

## 2. Luồng dữ liệu chính

_TODO: slow log -> Tool 1 -> LLM -> đề xuất -> Validation -> Dashboard -> Approve -> token -> Tool 6._

## 3. Mô hình tin cậy (trust boundaries)

| Nguồn dữ liệu | Tin cậy? | Xử lý |
| ------------- | :------: | ----- |
| SQL trong slow log | Không | Strip comment, gắn nhãn `untrusted` |
| Comment bảng/cột | Không | Lọc, gắn nhãn `untrusted` |
| Đầu ra của LLM | Không | Kiểm JSON Schema + AST whitelist |
| Approval token | Có (do server sinh) | Dùng 1 lần, hết hạn 10 phút, gắn hash DDL |

## 4. Tài khoản DB và quyền

| Tài khoản | Dùng bởi | Quyền |
| --------- | -------- | ----- |
| `readonly_user` | Tool 1-5, Validation (đọc) | SELECT (+ quyền cần cho EXPLAIN) |
| `index_admin` | Chỉ Tool 6 | CREATE/DROP INDEX, ALTER INDEX VISIBLE/INVISIBLE |

## 5. Validation Layer

_TODO: INVISIBLE INDEX, quy trình đo, rollback (xem ROADMAP mục 2.3)._

## 6. Nơi lưu trữ

_TODO: proposals, validation_reports, audit_log nằm ở đâu (SQLite riêng hoặc schema `optimizer_meta`)._

## 7. Quyết định thiết kế và lý do

_TODO: mỗi quyết định lớn ghi 1 dòng: quyết định gì, vì sao, phương án đã bỏ._
