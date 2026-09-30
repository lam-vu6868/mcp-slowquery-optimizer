# Hướng dẫn cài đặt từ A đến Z

> **Phụ trách:** Hải (phần DB/Docker), Vũ (phần Python/MCP), Tình (phần Dashboard) · **Trạng thái:** KHUNG RỖNG.
> Mục tiêu: người mới clone repo làm theo file này là chạy được, không cần hỏi.

## 1. Yêu cầu hệ thống

_TODO: Python 3.11+, Docker Desktop, Git, RAM/ổ đĩa tối thiểu cho 12M dòng._

## 2. Cài đặt môi trường

_TODO: venv, `pip install -r requirements.txt`, `pip install -e .`._

## 3. Cấu hình `.env`

_TODO: giải thích từng biến (API key, mật khẩu `readonly_user`, `index_admin`, `APPROVAL_SECRET`)._

## 4. Khởi động MySQL

_TODO: `docker compose up -d`, kiểm tra slow log bằng `scripts/verify_setup.py`._

## 5. Seed dữ liệu

_TODO: `python data/seed/seed_all.py`, thời gian dự kiến, cách giảm còn 5M._

## 6. Chạy MCP Server và Dashboard

_TODO._

## 7. Chạy test

_TODO._

## 8. Lỗi thường gặp

_TODO: mỗi lỗi 1 dòng: triệu chứng, nguyên nhân, cách sửa._
