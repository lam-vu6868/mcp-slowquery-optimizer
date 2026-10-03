# Hướng dẫn cài đặt từ A đến Z

> **Phụ trách:** Hải (phần DB/Docker), Vũ (phần Python/MCP), Tình (phần Dashboard) · **Trạng thái:** Đã hoàn thiện phần CSDL & Docker (Hải).
> Mục tiêu: người mới clone repo làm theo file này là chạy được, không cần hỏi.

## 1. Yêu cầu hệ thống

* **Docker Desktop:** Đã cài đặt và đang chạy.
* **Yêu cầu ổ đĩa & RAM (Cho phần DB):**
  * **RAM:** Tối thiểu 8 GB (khuyên dùng 16 GB để MySQL nạp 5M - 12M dòng không bị tràn memory).
  * **Ổ đĩa trống:** Tối thiểu 5 GB dung lượng khả dụng (chứa Docker Image, Volume và file CSV ~700MB).

_TODO (Vũ & Tình): Python 3.11+, Git..._

## 2. Cài đặt môi trường

_TODO (Vũ phụ trách): venv, `pip install -r requirements.txt`, `pip install -e .`._

## 3. Cấu hình `.env`

Copy file `.env.example` thành `.env`:
```cmd
copy .env.example .env
```

Cấu hình các biến môi trường CSDL trong file `.env`:
```env
# ---------- DATABASE (Hải) ----------
MYSQL_ROOT_PASSWORD= Mật khẩu tự điền trong MySQL
MYSQL_DATABASE=shopdb

DB_HOST=localhost
DB_PORT=3307          # Cổng 3307 bên ngoài máy host (map từ 3306 trong container)

# User read-only (Dành cho Tool 1-5 đọc dữ liệu)
DB_USER=readonly_user
DB_PASSWORD=readonly_pass

# User admin (CHỈ Dành cho Tool 6 thao tác CREATE/DROP/ALTER INDEX)
DB_ADMIN_USER=index_admin
DB_ADMIN_PASSWORD=admin_pass
```

_TODO (Vũ & Tình phụ trách): Giải thích từng biến API key, APPROVAL_SECRET..._

## 4. Khởi động MySQL

Hệ thống sử dụng Docker Container `mcp_mysql_db` (MySQL 8.0). File `schema.sql` và `init.sql` được mount tự động vào `/docker-entrypoint-initdb.d/` để tự động tạo cấu trúc bảng, cấu hình slow log và khởi tạo 2 user CSDL ngay khi container bật.

### 4.1 Khởi tạo Container sạch
```cmd
docker compose down -v
docker compose up -d
```
*(Chờ 10-15 giây để MySQL tự động hoàn tất khởi tạo schema và user).*

### 4.2 Kiểm tra container
```cmd
docker ps
```
> **Lưu ý:** Container lắng nghe cổng **`3307`** ra bên ngoài host (`0.0.0.0:3307->3306/tcp`) để tránh đụng độ với MySQL/XAMPP/Laragon sẵn có trên máy.

## 5. Seed dữ liệu

Sử dụng cờ `--local-infile=1` và lệnh `LOAD DATA LOCAL INFILE` để rút ngắn thời gian nạp 5 triệu dòng xuống còn **30 - 60 giây**.

### 5.1 Copy file CSV vào Container
```cmd
docker cp "C:\ProgramData\MySQL\MySQL Server 8.0\Uploads\data_5m.csv" mcp_mysql_db:/tmp/data_5m.csv
```
*(Đổi lại đường dẫn file CSV trên Windows nếu bạn lưu ở thư mục khác).*

### 5.2 Thực thi nạp dữ liệu siêu tốc
```cmd
docker exec -i mcp_mysql_db mysql -uroot -p<MAT_KHAU_MYSQL>  --local-infile=1 shopdb -e "SET GLOBAL local_infile=1; USE shopdb; SET autocommit=0; SET unique_checks=0; SET foreign_key_checks=0; LOAD DATA LOCAL INFILE '/tmp/data_5m.csv' INTO TABLE sales_data FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '\"' LINES TERMINATED BY '\n' IGNORE 1 LINES (region, country, item_type, sales_channel, order_priority, order_date_raw, order_id, ship_date_raw, units_sold, unit_price, unit_cost, total_revenue, total_cost, total_profit) SET order_date = STR_TO_DATE(order_date_raw, '%m/%d/%Y'), ship_date = STR_TO_DATE(ship_date_raw, '%m/%d/%Y'); COMMIT; SET unique_checks=1; SET foreign_key_checks=1; SET autocommit=1;"
```

### 5.3 Kiểm tra đếm số dòng
```cmd
docker exec -i mcp_mysql_db mysql -uroot -p<MAT_KHAU_MYSQL> shopdb -e "SELECT COUNT(*) FROM sales_data;"
```
* **Kết quả kỳ vọng:** `4999999` dòng.

### 5.4 Chạy 5 dữ liệu mẫu
```cmd
docker exec -i mcp_mysql_db mysql -uroot -p<MAT_KHAU_MYSQL> shopdb -e "SELECT * FROM sales_data LIMIT 5;"
```

### 5.4 Dọn dẹp file tạm
```cmd
docker exec mcp_mysql_db rm /tmp/data_5m.csv
```

## 6. Chạy MCP Server và Dashboard

_TODO (Vũ & Tình phụ trách): Hướng dẫn lệnh chạy MCP Server và Streamlit Dashboard._

## 7. Chạy test

_TODO (Vũ phụ trách): `pytest` và `scripts/verify_setup.py`._

## 8. Lỗi thường gặp (Phần DB & Docker)

* **`ERROR 1045 (28000): Access denied`**: Mật khẩu trong `.env` bị để trống hoặc dùng tiếng Việt có dấu. Sửa `MYSQL_ROOT_PASSWORD=root` trong `.env`, sau đó chạy `docker compose down -v` rồi `docker compose up -d`.
* **`chmod: Read-only file system`**: Do file `my.cnf` đã được gắn cờ `:ro` trong `docker-compose.yml`. Bỏ qua lệnh `chmod`, MySQL vẫn đọc cấu hình bình thường.
* **Không kết nối được từ DBeaver / Workbench**: Kiểm tra xem đã đổi cổng kết nối sang **`3307`** chưa (thay vì 3306 mặc định).
* **Lệnh `LOAD DATA` chạy lâu (1 - 2 phút)**: Do MySQL đang chuyển đổi `STR_TO_DATE` cho 10 triệu giá trị ngày tháng. Mở cửa sổ CMD mới gõ `SELECT COUNT(*) FROM sales_data;` để xem số dòng tăng dần.