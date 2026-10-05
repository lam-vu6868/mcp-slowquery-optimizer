# 🚀 HƯỚNG DẪN CÀI ĐẶT TỪ A ĐẾN Z

> **Phụ trách:** Hải (DB/Docker) · Vũ (Python/MCP) · Tình (Dashboard)
> **Trạng thái:** Đã hoàn thiện phần CSDL & Docker
> **Mục tiêu:** Người mới clone repo làm theo file này chạy được, không cần hỏi.

---

## 1. YÊU CẦU HỆ THỐNG

### Bắt buộc

- **Docker Desktop** — đã cài đặt và đang chạy (icon Docker dưới taskbar chuyển xanh)
- **Git** — để clone repo
- **Python 3.11+** — cho MCP Server + Dashboard

### Cấu hình máy đề xuất

| Thành phần  | Tối thiểu | Khuyến nghị |
| ----------- | --------- | ----------- |
| RAM         | 8 GB      | 16 GB       |
| Ổ đĩa trống | 5 GB      | 10 GB       |
| CPU         | 4 core    | 8 core      |

**Lý do:** MySQL cần nạp 5M dòng vào buffer pool. Máy yếu sẽ chậm hoặc tràn RAM.

---

## 2. CÀI ĐẶT MÔI TRƯỜNG

### 2.1. Clone repo

```cmd
cd D:\
git clone https://github.com/lam-vu6868/mcp-slowquery-optimizer.git
cd mcp-slowquery-optimizer
```

### 2.2. Tạo môi trường ảo Python

```cmd
python -m venv .venv
.venv\Scripts\activate
```

### 2.3. Cài thư viện

```cmd
pip install -r requirements.txt
```

**Kiểm tra:**

```cmd
python -c "import numpy, faker, pymysql, sqlglot; print('OK')"
```

---

## 3. CẤU HÌNH `.env`

### 3.1. Tạo file `.env`

```cmd
copy .env.example .env
notepad .env
```

### 3.2. Điền các biến DATABASE

```env
# ---------- DATABASE ----------
MYSQL_ROOT_PASSWORD=root
MYSQL_DATABASE=shopdb

DB_HOST=localhost
DB_PORT=3307
DB_NAME=shopdb

# User read-only (Tool 1-5 dùng)
DB_USER=readonly_user
DB_PASSWORD=readonly_pass

# User admin (Tool 6 dùng — chỉ CREATE/DROP/ALTER INDEX)
DB_ADMIN_USER=index_admin
DB_ADMIN_PASSWORD=admin_pass
```

⚠️ **Lưu ý:**

- `MYSQL_ROOT_PASSWORD`: Đặt đơn giản như `root` — KHÔNG dùng tiếng Việt có dấu, KHÔNG dùng ký tự đặc biệt
- `DB_PORT=3307`: Container map ra cổng 3307 (tránh conflict với MySQL local)

### 3.3. Điền các biến LLM (Vũ phụ trách)

```env
# ---------- LLM ----------
ANTHROPIC_API_KEY=sk-ant-...    # Điền key thật
LLM_MODEL=claude-sonnet-4-5
LLM_TEMPERATURE=0.0

# ---------- SECURITY ----------
# Tạo bằng: python -c "import secrets; print(secrets.token_hex(32))"
APPROVAL_SECRET=<chuỗi 64 ký tự random>
APPROVAL_TOKEN_TTL=600
```

---

## 4. KHỞI ĐỘNG MYSQL

### 4.1. Khởi động Container

```cmd
docker compose up -d
```

**Lần đầu** sẽ mất 30-60 giây để pull image MySQL 8.0.

**Kết quả mong đợi:**

```
[+] Running 3/3
 ✔ Network mcp-slowquery-optimizer_default    Created
 ✔ Volume "mcp-slowquery-optimizer_mysql_data"  Created
 ✔ Container mcp_mysql_db                     Started
```

### 4.2. Đợi MySQL khởi động

```cmd
timeout /t 30
docker ps
```

**Kết quả mong đợi:**

```
CONTAINER ID   IMAGE       STATUS
xxxxx          mysql:8.0   Up 30 seconds (healthy)
```

Chữ **`(healthy)`** = MySQL sẵn sàng.

⚠️ **Nếu chưa healthy:** Đợi thêm 30 giây.

### 4.3. Verify database sẵn sàng

```cmd
docker exec -i mcp_mysql_db mysql -uroot -proot -e "USE shopdb; SHOW TABLES;"
```

**Kết quả mong đợi:**

```
Tables_in_shopdb
sales_data
```

### 4.4. Cổng kết nối từ ngoài

Container lắng nghe cổng **`3307`** ở host (map từ 3306 bên trong).

**Khi kết nối từ MySQL Workbench:**

- Host: `localhost`
- Port: **`3307`** ← QUAN TRỌNG, không phải 3306
- User: `root`
- Password: `root` (giá trị `MYSQL_ROOT_PASSWORD` trong `.env`)

---

## 5. SEED DỮ LIỆU 5 TRIỆU DÒNG

### 5.1. Sinh file CSV

**Nếu bạn chưa có file CSV `data_5m.csv`**, chạy script sinh:

```cmd
python scripts\generate_orders_csv.py
```

**File output:** `data\outputs\orders.csv` (~450 MB).

⚠️ **Nếu đã có file CSV** (từ Hải share) → bỏ qua bước này.

### 5.2. Copy CSV vào Container

**Sửa đường dẫn file CSV của bạn cho đúng:**

```cmd
docker cp "D:\mcp-slowquery-optimizer\data\outputs\orders.csv" mcp_mysql_db:/tmp/data_5m.csv
```

**Lưu ý:**

- Dấu `"` bao quanh đường dẫn nếu có dấu cách
- Dùng `/tmp/data_5m.csv` bên trong container
- **KHÔNG dùng `mcp_mysql_db:/tmp\data_5m.csv`** (dấu `\` sẽ lỗi)

**Verify file đã vào:**

```cmd
docker exec mcp_mysql_db ls -lh /tmp/data_5m.csv
```

**Kết quả mong đợi:**

```
-rw-r--r-- 1 root root 450M Oct  5 10:00 /tmp/data_5m.csv
```

### 5.3. Import CSV vào MySQL

⚠️ **QUAN TRỌNG:** Format ngày trong CSV là **`YYYY-MM-DD`** (VD: `2017-04-15`), KHÔNG phải `M/D/YYYY`.

**Lệnh import ĐÚNG:**

```cmd
docker exec -i mcp_mysql_db mysql -uroot -proot --local-infile=1 shopdb -e "SET GLOBAL local_infile=1; LOAD DATA LOCAL INFILE '/tmp/data_5m.csv' INTO TABLE sales_data FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '\"' LINES TERMINATED BY '\n' IGNORE 1 LINES (region, country, item_type, sales_channel, order_priority, order_date_raw, order_id, ship_date_raw, units_sold, unit_price, unit_cost, total_revenue, total_cost, total_profit);"
```

**⏱️ Mất 30-90 giây.**

**Bước 5.3b — Chuyển `order_date_raw` → `order_date` (DATE):**

**Đây là bước CỰC KỲ QUAN TRỌNG — nếu làm sai sẽ bị NULL toàn bộ.**

```cmd
docker exec -i mcp_mysql_db mysql -uroot -proot shopdb -e "UPDATE sales_data SET order_date = STR_TO_DATE(order_date_raw, '%Y-%m-%d'), ship_date = STR_TO_DATE(ship_date_raw, '%Y-%m-%d');"
```

**⏱️ Mất 5-10 phút** (update 5M dòng).

⚠️ **3 điều cần chú ý:**

1. Format `%Y-%m-%d` — ĐÚNG với CSV của nhóm
2. Lệnh phải viết **1 dòng liền** — không ngắt xuống dòng
3. Đợi đến khi prompt `(venv) D:\...>` quay lại — không ngắt giữa chừng

### 5.4. Verify import thành công

**Bước 1 — Đếm dòng:**

```cmd
docker exec -i mcp_mysql_db mysql -uroot -proot shopdb -e "SELECT COUNT(*) AS total FROM sales_data;"
```

**Kết quả mong đợi:** `4,999,999` (hoặc `5,000,000`).

**Bước 2 — Kiểm tra cột DATE KHÔNG bị NULL:**

```cmd
docker exec -i mcp_mysql_db mysql -uroot -proot shopdb -e "SELECT COUNT(*) AS total, SUM(order_date IS NULL) AS order_date_null, SUM(ship_date IS NULL) AS ship_date_null FROM sales_data;"
```

**Kết quả mong đợi:**

```
total    | order_date_null | ship_date_null
4999999  | 0               | 0
```

🚨 **Nếu `order_date_null > 0`** → format ngày SAI. Chạy lại Bước 5.3b.

**Bước 3 — Xem 5 dòng mẫu:**

```cmd
docker exec -i mcp_mysql_db mysql -uroot -proot shopdb -e "SELECT id, region, country, order_date, order_date_raw, total_revenue FROM sales_data LIMIT 5;"
```

**Kết quả mong đợi:**

```
id | region  | country | order_date  | order_date_raw | total_revenue
1  | Europe  | Sweden  | 2017-04-15  | 2017-04-15     | 868082.73
```

**→ Cả `order_date` và `order_date_raw` phải có giá trị.**

### 5.5. Dọn dẹp file tạm

```cmd
docker exec mcp_mysql_db rm /tmp/data_5m.csv
```

---

## 6. CẤU HÌNH SLOW QUERY LOG

Slow log đã được mount qua `my.cnf`, nhưng cần verify:

### 6.1. Kiểm tra slow log bật

```cmd
docker exec -i mcp_mysql_db mysql -uroot -proot -e "SHOW VARIABLES LIKE 'slow_query_log'; SHOW VARIABLES LIKE 'long_query_time'; SHOW VARIABLES LIKE 'log_output';"
```

**Kết quả mong đợi:**

```
slow_query_log       ON
long_query_time      0.500000
log_output           FILE,TABLE
```

### 6.2. Nếu slow log OFF

```cmd
docker exec -i mcp_mysql_db mysql -uroot -proot -e "SET GLOBAL slow_query_log = 'ON'; SET GLOBAL long_query_time = 0.5; SET GLOBAL log_output = 'FILE,TABLE';"
```

### 6.3. Test slow log ghi

```cmd
docker exec -i mcp_mysql_db mysql -uroot -proot shopdb -e "SELECT SLEEP(1);"
```

**Đợi 2 giây rồi check log:**

```cmd
docker exec mcp_mysql_db tail -n 10 /var/lib/mysql/slow.log
```

**Kết quả mong đợi:**

```
# Query_time: 1.002199  Lock_time: 0.000000 Rows_sent: 1  Rows_examined: 1
use shopdb;
SET timestamp=...;
SELECT SLEEP(1);
```

### 6.4. Clear slow log cũ

```cmd
docker exec -i mcp_mysql_db mysql -uroot -proot -e "TRUNCATE TABLE mysql.slow_log;"
```

---

## 7. CHẠY TEST CASE STUDY (VERIFY)

Chạy query tương tự case study Black Friday để kiểm tra:

### 7.1. Query CHẬM (chưa có index)

```cmd
docker exec -i mcp_mysql_db mysql -uroot -proot shopdb -e "SET profiling = 1; SELECT SQL_NO_CACHE SUM(total_revenue) FROM sales_data WHERE region = 'Europe' AND order_date BETWEEN '2017-01-01' AND '2017-12-31'; SHOW PROFILES;"
```

**Kết quả mong đợi:**

```
Duration: ~1.5-2.0 giây   ← Full table scan 5M dòng
```

### 7.2. Tạo index composite

```cmd
docker exec -i mcp_mysql_db mysql -uroot -proot shopdb -e "CREATE INDEX idx_region_date ON sales_data(region, order_date);"
```

**⏱️ Mất 30-90 giây.**

### 7.3. Query lại — đo cải thiện

```cmd
docker exec -i mcp_mysql_db mysql -uroot -proot shopdb -e "SET profiling = 1; SELECT SQL_NO_CACHE SUM(total_revenue) FROM sales_data WHERE region = 'Europe' AND order_date BETWEEN '2017-01-01' AND '2017-12-31'; SHOW PROFILES;"
```

**Kết quả mong đợi:**

```
Duration: ~0.8 giây     ← Nhanh hơn 2 lần
```

### 7.4. Test với COUNT (nhanh hơn)

```cmd
docker exec -i mcp_mysql_db mysql -uroot -proot shopdb -e "SET profiling = 1; SELECT SQL_NO_CACHE COUNT(*) FROM sales_data WHERE region = 'Europe' AND order_date BETWEEN '2017-01-01' AND '2017-12-31'; SHOW PROFILES;"
```

**Kết quả mong đợi:**

```
Duration: ~0.07 giây    ← Nhanh hơn 23 lần
```

### 7.5. XÓA INDEX SAU KHI TEST XONG

⚠️ **QUAN TRỌNG** — Dự án yêu cầu LLM tự đề xuất index. Phải xóa để reset.

```cmd
docker exec -i mcp_mysql_db mysql -uroot -proot shopdb -e "DROP INDEX idx_region_date ON sales_data;"
```

**Verify chỉ còn PRIMARY:**

```cmd
docker exec -i mcp_mysql_db mysql -uroot -proot shopdb -e "SHOW INDEX FROM sales_data;"
```

**Kết quả mong đợi:**

```
Key_name   Column_name
PRIMARY    id
```

### 7.6. Clear log lần cuối

```cmd
docker exec -i mcp_mysql_db mysql -uroot -proot -e "TRUNCATE TABLE mysql.slow_log;"
docker exec -i mcp_mysql_db mysql -uroot -proot -e "TRUNCATE TABLE performance_schema.events_statements_summary_by_digest;"
```

---

## 8. CHẠY MCP SERVER VÀ DASHBOARD

_Vũ & Tình phụ trách — sẽ bổ sung khi code xong._

**Tạm thời:**

```cmd
# Terminal 1 — MCP Server
python -m mcp_server.server

# Terminal 2 — Dashboard
streamlit run dashboard/app.py
```

---

## 9. CHẠY TEST

```cmd
pytest tests/ -v
```

_Vũ bổ sung script `scripts/verify_setup.py` — sẽ cập nhật sau._

---

## 10. LỖI THƯỜNG GẶP

### 🚨 Lỗi 1: `order_date` và `ship_date` bị NULL sau khi import

**Nguyên nhân:** Format ngày trong `STR_TO_DATE` SAI.

**Cách debug:**

```cmd
docker exec -i mcp_mysql_db mysql -uroot -proot shopdb -e "SELECT order_date_raw, LENGTH(order_date_raw), HEX(order_date_raw) FROM sales_data LIMIT 3;"
```

**Chẩn đoán:**

| Kết quả                | Nghĩa             | Format đúng     |
| ---------------------- | ----------------- | --------------- |
| `2017-04-15`, 10 ký tự | Format YYYY-MM-DD | `'%Y-%m-%d'` ✅ |
| `4/15/2017`, 9 ký tự   | Format M/D/YYYY   | `'%m/%d/%Y'`    |
| `15/04/2017`, 10 ký tự | Format D/M/YYYY   | `'%d/%m/%Y'`    |

**Fix (data nhóm = YYYY-MM-DD):**

```cmd
docker exec -i mcp_mysql_db mysql -uroot -proot shopdb -e "UPDATE sales_data SET order_date = STR_TO_DATE(order_date_raw, '%Y-%m-%d'), ship_date = STR_TO_DATE(ship_date_raw, '%Y-%m-%d');"
```

**Verify fix:**

```cmd
docker exec -i mcp_mysql_db mysql -uroot -proot shopdb -e "SELECT SUM(order_date IS NULL) AS null_count FROM sales_data;"
```

Kết quả phải = `0`.

---

### ❌ Lỗi 2: `ERROR 1045 (28000): Access denied`

**Nguyên nhân:** Mật khẩu trong `.env` để trống hoặc sai.

**Fix:**

1. Sửa `.env`: `MYSQL_ROOT_PASSWORD=root`
2. Xóa volume cũ: `docker compose down -v`
3. Khởi động lại: `docker compose up -d`

⚠️ **`docker compose down -v` sẽ XÓA DATA.** Nếu đã có 5M dòng → phải import lại.

---

### ❌ Lỗi 3: `chmod: Read-only file system`

**Nguyên nhân:** File `my.cnf` đã được mount `:ro` (read-only).

**Fix:** Bỏ qua lệnh `chmod`. MySQL vẫn đọc cấu hình bình thường.

---

### ❌ Lỗi 4: Không kết nối được từ MySQL Workbench

**Nguyên nhân:** Dùng sai port.

**Fix:** Đổi port kết nối thành **`3307`** (không phải 3306).

| Trường   | Giá trị     |
| -------- | ----------- |
| Hostname | `localhost` |
| **Port** | **`3307`**  |
| Username | `root`      |
| Password | `root`      |

---

### ❌ Lỗi 5: `docker cp: copying between containers is not supported`

**Nguyên nhân:** Đường dẫn Windows sai format.

**Sai:**

```cmd
docker cp "D:data_5m.csv" mcp_mysql_db:/tmp/data_5m.csv
```

**Đúng:**

```cmd
docker cp "D:\data_5m.csv" mcp_mysql_db:/tmp/data_5m.csv
```

Hoặc dùng `/`:

```cmd
docker cp "D:/data_5m.csv" mcp_mysql_db:/tmp/data_5m.csv
```

---

### ❌ Lỗi 6: `mysql: [Warning] World-writable config file ignored`

**Nguyên nhân:** File `my.cnf` có quyền ghi cho mọi người (Windows mount).

**Fix (tùy chọn):**

```cmd
docker exec -u root mcp_mysql_db chmod 644 /etc/mysql/conf.d/my.cnf
docker restart mcp_mysql_db
```

**→ Không ảnh hưởng chức năng. Có thể bỏ qua.**

---

### ❌ Lỗi 7: `LOAD DATA` chạy lâu (1-2 phút)

**Nguyên nhân:** MySQL đang chuyển đổi `STR_TO_DATE` cho 10 triệu giá trị ngày tháng.

**Cách theo dõi tiến độ:** Mở **CMD mới**, chạy:

```cmd
docker exec -i mcp_mysql_db mysql -uroot -proot shopdb -e "SELECT COUNT(*) FROM sales_data;"
```

Số dòng tăng dần = đang import.

---

### ❌ Lỗi 8: `ERROR 1148: The used command is not allowed`

**Nguyên nhân:** `local_infile` chưa bật.

**Fix:**

```cmd
docker exec -i mcp_mysql_db mysql -uroot -proot -e "SET GLOBAL local_infile=1;"
```

Rồi chạy lại lệnh import.

---

## 11. CHECKLIST HOÀN THÀNH

Sau khi làm xong tất cả các bước, bạn phải có:

- [ ] Docker container `mcp_mysql_db` chạy healthy
- [ ] MySQL kết nối được ở port `3307`
- [ ] Bảng `sales_data` có ~5M dòng
- [ ] `order_date` và `ship_date` KHÔNG bị NULL
- [ ] Slow log bật với `long_query_time = 0.5`
- [ ] Index đã xóa sạch (chỉ còn PRIMARY)
- [ ] File CSV tạm đã dọn

**Verify tổng thể:**

```cmd
docker exec -i mcp_mysql_db mysql -uroot -proot shopdb -e "SELECT COUNT(*) AS total, SUM(order_date IS NULL) AS null_date FROM sales_data;"
```

Kết quả: `total = ~5M`, `null_date = 0`.

---

## 12. LỆNH DOCKER HAY DÙNG

| Lệnh                                                              | Tác dụng               |
| ----------------------------------------------------------------- | ---------------------- |
| `docker compose up -d`                                            | Khởi động              |
| `docker compose down`                                             | Dừng (giữ data)        |
| `docker compose down -v`                                          | Dừng + **xóa data** ⚠️ |
| `docker compose ps`                                               | Xem trạng thái         |
| `docker compose logs mysql`                                       | Xem log                |
| `docker exec -it mcp_mysql_db mysql -uroot -proot`                | Vào MySQL shell        |
| `docker exec -i mcp_mysql_db mysql -uroot -proot shopdb -e "..."` | Chạy 1 lệnh SQL        |

---

**Cập nhật lần cuối:** 05/10/2026 — bởi Hải
