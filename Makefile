# Makefile
# --------
#
# CHỨC NĂNG :
#     Gom các lệnh hay dùng thành lối tắt (make up, make seed, make test...).
#
# PHỤ TRÁCH  : Vũ    |    REVIEW: Cả nhóm
#
# LƯU Ý:
#     - Makefile bắt buộc thụt lề bằng TAB, không dùng dấu cách.
#     - Windows không có sẵn make: dùng scripts/*.sh qua Git Bash, hoặc bỏ qua file này.
#
# CẦN LÀM:
#     [ ] up        : docker compose up -d
#     [ ] down      : docker compose down
#     [ ] seed      : python data/seed/seed_all.py
#     [ ] server    : python -m mcp_server.server
#     [ ] dashboard : streamlit run dashboard/app.py
#     [ ] test      : pytest tests/ -v
#     [ ] reset-db  : bash scripts/reset_db.sh
#
# THAM KHẢO  : README.md
#
# TRẠNG THÁI : KHUNG RỖNG — chưa cài đặt. Xóa dòng này khi bắt đầu code.
