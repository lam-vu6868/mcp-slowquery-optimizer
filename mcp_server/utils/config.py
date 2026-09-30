"""
mcp_server/utils/config.py
--------------------------

CHỨC NĂNG :
    Đọc cấu hình từ config/settings.yaml và biến môi trường (.env).

PHỤ TRÁCH  : Vũ    |    REVIEW: Hải

LƯU Ý:
    - Bí mật (API key, mật khẩu DB, APPROVAL_SECRET) chỉ lấy từ .env, không ghi trong yaml.
    - Không in giá trị bí mật ra log.

THAM KHẢO  : config/settings.yaml, .env.example

TRẠNG THÁI : KHUNG RỖNG — chưa cài đặt. Xóa dòng này khi bắt đầu code.
"""
