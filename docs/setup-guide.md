# 🚀 HƯỚNG DẪN CÀI ĐẶT VÀ KIỂM CHỨNG LAB

> **Phụ trách:** Hải (DB/Docker) · Vũ (Python/MCP) · Tình (Dashboard)
> **Cập nhật:** 21/11/2026 — dataset 5 bảng/tổng 5 triệu dòng.
> **Đã xác nhận:** nạp dữ liệu lab, baseline 30/30 valid, đáp án 30/30 đạt P95/hash, 125 unit tests pass. Hải review/GVHD ký và luồng MCP–LLM–Dashboard vẫn chưa hoàn tất.

## 1. Yêu cầu

- Python 3.11+, Git và Docker Desktop đang chạy.
- MySQL 8.0 trong container `mcp_mysql_db`, cổng host `3307`.
- Năm CSV giả lập hiện ở `D:\labt2\data`: `customers.csv`, `addresses.csv`, `products.csv`, `orders.csv`, `order_items.csv`. Đây là dữ liệu ngoài repo; clone repo không tự có các CSV này.
- Chạy lệnh từ thư mục gốc `D:\mcp-slowquery-optimizer`. Các lệnh bên dưới dùng PowerShell, SQL chạy trong MySQL client.

## 2. Python và cấu hình

Nếu đã có `venv` đang dùng thì giữ nguyên. Với checkout mới:

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

Tạo `.env` từ `.env.example` chỉ khi chưa có; không ghi đè cấu hình hiện tại:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Điền cấu hình theo môi trường thực tế, không đưa mật khẩu/key vào Git hoặc lệnh chat:

- `DB_HOST=localhost`, `DB_PORT=3307`, `DB_NAME=shopdb`.
- Tool 1–5 dùng `DB_USER=readonly_user`; thông tin `DB_ADMIN_USER=index_admin` chỉ dành cho đường quản trị index.
- Mật khẩu trong `.env` phải khớp user đã được provision. `db/init.sql` hiện có thông tin lab cố định; sửa `.env` không tự thay mật khẩu user MySQL trong volume hiện có.
- LLM và approval secret xem tên biến trong `.env.example`; chưa cần gọi LLM để chạy unit test hoặc audit file bằng chứng.

## 3. Khởi động MySQL

```powershell
docker compose up -d
docker compose ps
```

Chờ container healthy, rồi mở MySQL client và nhập mật khẩu khi được hỏi:

```powershell
docker compose exec db mysql -u root -p shopdb
```

```sql
SHOW TABLES;
```

Kỳ vọng: `customers`, `addresses`, `products`, `orders`, `order_items`.

`docker-compose.yml` mount `db/schema.sql` rồi `db/init.sql` để khởi tạo **volume mới/rỗng**. Với volume đã tồn tại, Docker không tự chạy lại hai file này. Nếu vẫn thấy cấu trúc cũ, dừng tại đây để Hải kiểm tra; không dùng `down -v` hoặc reset DB để sửa nhanh.

## 4. Cấu hình slow log

Trong MySQL client bằng tài khoản quản trị:

```sql
SHOW GLOBAL VARIABLES
WHERE Variable_name IN ('slow_query_log','long_query_time','log_output','local_infile');
```

Kỳ vọng `slow_query_log=ON`, `long_query_time=0.5`, `log_output=FILE,TABLE`. Nếu cấu hình chưa đúng, thiết lập trên lab:

```sql
SET PERSIST slow_query_log = ON;
SET PERSIST long_query_time = 0.5;
SET PERSIST log_output = 'FILE,TABLE';
```

`SET PERSIST` giữ cấu hình qua restart; kiểm tra lại các biến sau khi reconnect. Trên Windows, file `my.cnf` mount có thể bị bỏ qua do quyền file, nên cần kiểm tra giá trị thực tế. Tool 1 mặc định dùng Performance Schema. Nhánh `source="slow_log"` cần `readonly_user` có quyền đọc riêng bảng log; lab hiện tại đã được người dùng cấp quyền và đã đọc thử qua MCP. Với DB khác, sau khi Hải/Tình review quyền và phạm vi SQL đưa cho LLM, người quản trị chạy **chỉ** lệnh sau (không chạy lại toàn bộ `db/init.sql`, vì file đó tạo lại user):

```sql
GRANT SELECT ON mysql.slow_log TO 'readonly_user'@'%';
```

Sau đó gọi `get_slow_queries(source="slow_log", limit=1)` để kiểm tra đường đọc; không xóa slow log hoặc digest đang giữ làm bằng chứng. Quyền này chỉ áp dụng cho `mysql.slow_log`, không phải `mysql.*`.

## 5. Nạp 5 CSV — chỉ dành cho DB mới và các bảng rỗng

**DB hiện tại đã đủ 5M dòng thì bỏ qua toàn bộ bước nạp.** Không nạp lại để đo query; trùng PK hoặc ghi thêm dữ liệu sẽ làm thay đổi bộ thực nghiệm.

Số dòng đã xác nhận:

| Bảng | Số dòng |
| --- | ---: |
| customers | 500.000 |
| addresses | 500.000 |
| products | 50.000 |
| orders | 1.500.000 |
| order_items | 2.450.000 |
| **Tổng** | **5.000.000** |

Schema theo `db/schema.sql`. VARCHAR không tự mã hóa; không coi email/phone/street/postal_code đã được mã hóa chỉ vì có kiểu VARCHAR. Bộ CSV hiện là dữ liệu giả lập, phần mã hóa cần kiểm chứng riêng nếu đưa vào phạm vi báo cáo.

CSV hiện tại có header, dấu phẩy, UTF-8, newline CRLF (`\r\n`), cột đúng thứ tự bên dưới. Nếu dùng bộ CSV khác, kiểm tra lại encoding/newline và quy ước NULL trước khi nhập. Không dùng `data/seed/seed_all.py` để sinh bộ này: các file seed còn khung và mô tả bộ cũ; `scripts/generate_orders_csv.py` không có trong repo.

Thoát MySQL, rồi copy thư mục CSV vào container:

```powershell
docker cp "D:\labt2\data" mcp_mysql_db:/tmp/mcp-lab-data
docker compose exec db mysql --local-infile=1 -u root -p shopdb
```

Kiểm tra `local_infile=ON` bằng `SHOW GLOBAL VARIABLES LIKE 'local_infile'`; nếu OFF, quản trị viên bật trên lab bằng `SET GLOBAL local_infile=ON;` rồi reconnect client với `--local-infile=1`.

Trong MySQL, kiểm tra các bảng đều rỗng trước khi chạy bất kỳ LOAD nào (câu đếm ở mục 6). Giữ kiểm tra FK; nạp theo thứ tự cha trước con:

```sql
SET SESSION time_zone = '+00:00';

LOAD DATA LOCAL INFILE '/tmp/mcp-lab-data/customers.csv'
INTO TABLE customers CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"' ESCAPED BY '"'
LINES TERMINATED BY '\r\n' IGNORE 1 LINES
(customer_id, full_name, email, phone, created_at);
SHOW WARNINGS LIMIT 20;

LOAD DATA LOCAL INFILE '/tmp/mcp-lab-data/products.csv'
INTO TABLE products CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"' ESCAPED BY '"'
LINES TERMINATED BY '\r\n' IGNORE 1 LINES
(product_id, product_name, category, price, stock_quantity);
SHOW WARNINGS LIMIT 20;

LOAD DATA LOCAL INFILE '/tmp/mcp-lab-data/addresses.csv'
INTO TABLE addresses CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"' ESCAPED BY '"'
LINES TERMINATED BY '\r\n' IGNORE 1 LINES
(address_id, customer_id, street, city, state, postal_code, country);
SHOW WARNINGS LIMIT 20;

LOAD DATA LOCAL INFILE '/tmp/mcp-lab-data/orders.csv'
INTO TABLE orders CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"' ESCAPED BY '"'
LINES TERMINATED BY '\r\n' IGNORE 1 LINES
(order_id, customer_id, order_date, total_amount, status);
SHOW WARNINGS LIMIT 20;

LOAD DATA LOCAL INFILE '/tmp/mcp-lab-data/order_items.csv'
INTO TABLE order_items CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"' ESCAPED BY '"'
LINES TERMINATED BY '\r\n' IGNORE 1 LINES
(order_item_id, order_id, product_id, quantity, unit_price);
SHOW WARNINGS LIMIT 20;
```

Dừng và kiểm tra nếu có warning/error; không xem LOAD thành công là đủ bằng chứng rằng mọi dòng đã được nạp đúng. Không tự chạy lại LOAD trên bảng đã nạp một phần. Các lệnh nạp trên là hướng dẫn tái lập cho DB mới, **chưa được chạy lại vào lab hiện có** trong lượt cập nhật tài liệu này.

## 6. Kiểm tra dữ liệu và index

Trong MySQL:

```sql
SELECT 'customers' AS table_name, COUNT(*) AS total FROM customers
UNION ALL SELECT 'addresses', COUNT(*) FROM addresses
UNION ALL SELECT 'products', COUNT(*) FROM products
UNION ALL SELECT 'orders', COUNT(*) FROM orders
UNION ALL SELECT 'order_items', COUNT(*) FROM order_items;

SHOW CREATE TABLE addresses;
SHOW CREATE TABLE orders;
SHOW CREATE TABLE order_items;
SHOW INDEX FROM order_items;
```

Đối chiếu số dòng với mục 5, kiểm tra FK và các cột bắt buộc/date/numeric. Đây là kiểm tra lab thủ công, không phải cách triển khai `get_table_stats` bằng COUNT toàn bảng cho mỗi lần gọi.

Sau batch ngày 21/11: không còn `gt_trial_*`; giữ các PK/UNIQUE/FK index gốc. Riêng `order_items.idx_gt_q01_cover(product_id,quantity,unit_price)` đã có từ phép thử q01, vẫn INVISIBLE; `fk_order_items_product(product_id)` vẫn VISIBLE. INVISIBLE index vẫn chiếm dung lượng và được cập nhật khi ghi.

`scripts/verify_setup.py` còn tham chiếu `sales_data`; chưa dùng script đó để kết luận bộ 5 bảng hợp lệ. Bộ cũ đã bị thay thế, nên ví dụ truy vấn theo `region`, `ship_date`, `total_revenue` không còn áp dụng cho dataset hiện tại.

Các ví dụ trong khối `__main__` của Tool 4/5 cũng còn SQL `sales_data`; không dùng `python -m mcp_server.tools.explain` hoặc `python -m mcp_server.tools.benchmark` làm smoke test cho bộ 5 bảng. Phần hàm xử lý đã được dùng bởi script kiểm chứng; phần ví dụ trực tiếp cần sửa riêng nếu muốn dùng lại.

## 7. Kiểm tra test và bằng chứng

Từ PowerShell, chạy cả hai dòng đầu mỗi lần test:

```powershell
$pytestTemp = Join-Path $env:TEMP ("pytest-user-" + [guid]::NewGuid().ToString("N"))
.\venv\Scripts\python.exe -m pytest tests/ -q -p no:cacheprovider --basetemp="$pytestTemp"
.\venv\Scripts\python.exe scripts/verify_ground_truth.py --check
```

Kết quả đã xác nhận: **125 tests pass**, **Evidence audit: 30/30 passed**. Test count có thể thay đổi khi thêm chức năng; không xem con số cố định là tiêu chí duy nhất.

Không dùng lại thư mục tạm mà sandbox đã tạo: pytest đặt quyền riêng cho chủ sở hữu, khiến terminal của user có thể gặp `WinError 5`. Không cần mở Administrator; tạo thư mục mới bằng chính tài khoản đang chạy như trên.

`--check` chỉ đọc file bằng chứng: đối chiếu SQL, index, đủ lượt đo, P95, hash/số dòng và phép so sánh thứ tự composite; không kết nối hoặc đo lại MySQL. Giữ `data/outputs/` (gitignored), đặc biệt:

- `p95_baseline_multitable_raw.json`: baseline 30 query hiện tại.
- `q01_cover_before.json`, `q01_cover_after.json`: bằng chứng q01.
- `ground_truth_validation/report.json` và các file raw được trỏ tới trong ground truth: kết quả từng phép thử, lịch sử và EXPLAIN.

Không có các file này sau khi clone repo thì audit chưa chạy được; cần bản sao bằng chứng của nhóm hoặc tổ chức đo lại trên lab phù hợp.

## 8. Đo query và kiểm chứng đáp án

Luồng dữ liệu:

1. `data/queries/queries.py`: 30 SQL gốc, 6 query/nhóm.
2. `scripts/test_queries.py`: sàng lọc phía server, 1 warm-up +3 lượt, chưa phải P95 chính thức.
3. `scripts/measure_p95_baseline.py`: gọi Tool 5, 3 warm-up +20 lượt đo và hash riêng; lưu baseline.
4. `data/queries/ground_truth_candidates.py`: index/rewrite/hint ứng viên; không tự áp dụng vào DB.
5. `scripts/verify_ground_truth.py`: thử ứng viên q02–q30 trong lab, chỉ ghi đáp án đạt vào `data/queries/ground_truth.json`; q01 có bằng chứng riêng ở mục 7.

Đo lại một query và lưu file riêng để giữ bằng chứng gốc:

```powershell
.\venv\Scripts\python.exe -u scripts/measure_p95_baseline.py --ids q01 --force --output data/outputs/q01_baseline_recheck.json
```

Tham số `--group 1` chọn nhóm; `--use-invisible-indexes` cho phép dùng INVISIBLE index và bắt buộc output riêng. Chỉ bật sau khi biết chính xác các index INVISIBLE đang tồn tại; bật cờ không tự tạo index hoặc đảm bảo optimizer chọn index đó. Tool 4/5 đặt OFF hoặc ON rõ ràng theo session, không sửa global.

Nhánh đo của `verify_ground_truth.py` có CREATE/DROP index tạm và cập nhật ground truth; chỉ chạy với ủy quyền trên lab phù hợp, không chạy đồng thời benchmark khác. Nó kiểm tra cấu hình index đầu vào, dọn index thử và khôi phục snapshot; nếu run bị gián đoạn có `active_indexes`, phải kiểm tra trạng thái thật trước khi tiếp tục. Đây là script offline, không phải cơ chế apply của MCP/LLM.

Điều kiện chấp nhận: đủ lượt đo, không timeout, hash/số dòng khớp và P95 giảm ≥20%; nhóm composite còn cần đo thứ tự cột đối chứng. Các đáp án chứa `rewritten_sql`, `requires_rewrite`, `required_indexes` phải dùng đủ SQL và index. Không quy mức cải thiện của rewrite/hint cho index đơn thuần. `rows_examined` của Tool 5 hiện là proxy từ Handler_read*, không phải số ROWS_EXAMINED chính xác.

## 9. Phần chưa hoàn tất

- Ground truth: trạng thái `performance_verified_pending_review`; Hải review và GVHD ký còn chờ. Không tuyên bố đáp án tối ưu toàn cục.
- Chưa đo đầy đủ dung lượng index và chi phí ghi cho mọi phương án; đã có một phép đo INSERT mẫu trên write lab riêng (xem mục 10). Metric LLM và so sánh baseline truyền thống còn thiếu.
- Dữ liệu giả hiện khá đều, có tương quan city/status; chưa chứng minh tải lệch/đỉnh Black Friday hoặc CPU 98%/downtime.
- `python -m mcp_server.server` hiện chạy MCP stdio với Tool 1–5 trên MCP SDK 2.x. Tool 6, LLM agent và Dashboard chưa tích hợp; lệnh `streamlit run dashboard/app.py` chưa xác nhận luồng hoàn chỉnh.

Lịch sử import một bảng và các kết quả đo cũ xem [PROGRESS](../project-management/PROGRESS.md). Thiết kế mục tiêu xem [architecture](architecture.md); input/output tool xem [api-contract](api-contract.md).

## 10. Đo chi phí INSERT và thử Validation trên hai MySQL lab riêng

`docker-compose.write-lab.yml` tạo MySQL thứ hai ở `127.0.0.1:3308` và volume riêng. DB chính ở cổng 3307 không nhận INSERT từ phép đo này. Lab chỉ có schema và marker `mcp-write-lab-v1`; phép đo dùng hai bảng TEMPORARY và 200.000 dòng đầu từ CSV của bảng: 100.000 dòng preload giống nhau, sau đó đo 100.000 INSERT giống nhau trước/sau index. Bảng tạm tự mất khi đóng kết nối. Đây là **mẫu**, không phải bản sao đầy đủ 5M dòng hoặc phép đo tải sản xuất; `CREATE TABLE LIKE` không sao chép FOREIGN KEY.

Service `validation_lab_db` trong cùng compose dùng cổng `127.0.0.1:3309`, volume và marker `mcp-validation-lab-v1` riêng. Nó giữ dữ liệu mẫu để Tool 4/5 và `TrialIndex` đo index thật. Không trỏ `TrialIndex` vào write lab cổng 3308: phép đo INSERT đòi bảng gốc ở write lab chưa có index đề xuất. Hai lab chỉ dùng để kiểm tra luồng; kết quả trên 200.000 dòng không thay thế phép đo của bộ 5M.

Tạo mật khẩu lab cục bộ (file `.env.write-lab` đã gitignore, không in/commit mật khẩu), rồi khởi động đúng compose riêng:

```powershell
.\venv\Scripts\python.exe -c "from pathlib import Path; from secrets import token_hex; p=Path('.env.write-lab'); p.write_text('WRITE_LAB_ROOT_PASSWORD='+token_hex(24)+'\n', encoding='utf-8') if not p.exists() else None"
docker compose -p mcp-write-lab --env-file .env.write-lab -f docker-compose.write-lab.yml up -d write_lab_db
```

Để chạy cả hai lab, dùng cùng file môi trường với project Docker riêng:

```powershell
docker compose -p mcp-write-lab --env-file .env.write-lab -f docker-compose.write-lab.yml up -d write_lab_db validation_lab_db
```

Trước khi tạo index thử, nạp dữ liệu mẫu vào `validation_lab_db` và kiểm tra marker; chỉ đổi `DB_HOST=127.0.0.1`, `DB_PORT=3309` trong tiến trình chạy validation, không sửa `.env` của DB chính. Tài khoản root lab có thể chạy `ANALYZE TABLE` trước/sau index để làm mới thống kê dung lượng; code mặc định vẫn trả `inconclusive` nếu `INDEX_LENGTH` không tăng. Sau phép thử, giữ file bằng chứng trong `data/outputs/`, kiểm index thử đã dọn rồi mới xóa các volume lab.

Chạy từ root repo với CSV ở `D:\labt2\data` (đổi `--csv-dir` theo máy). Lệnh không nhận SQL tự do; index được sinh từ tên bảng/cột đã kiểm tra. Output nằm trong `data/outputs/` và không ghi đè file cũ:

```powershell
.\venv\Scripts\python.exe -m scripts.measure_write_overhead --table orders --index-name idx_orders_status_date --columns status:ASC order_date:ASC --csv-dir D:\labt2\data --output data\outputs\write_overhead_orders_status_date.json
```

Code chỉ chấp nhận lab có marker đúng. CSV phải có đủ `2 × validation.write_overhead_rows` dòng và header khớp schema. Thiếu điều kiện thì phép đo thất bại, không tạo report `passed`. Kết quả này chỉ là phần chi phí ghi; Validation Layer còn cần P95/hash/EXPLAIN và dung lượng index trước khi duyệt proposal.
