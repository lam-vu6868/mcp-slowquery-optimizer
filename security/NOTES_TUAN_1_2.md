# Ghi chú bàn giao tuần 1–2 — Tình (Security + Frontend)

> Cập nhật: 05/10/2026 · Nhánh: `feat/tinh-dashboard` · Người review: Vũ (security), Tường (dashboard), Hải (quyền DB)

## 1. Việc đã xong

| Tuần | Việc (ROADMAP mục 4) | File | Kiểm chứng |
| :--: | -------------------- | ---- | ---------- |
| 1 | Test quyền `readonly_user` (DDL bị chặn) | `tests/test_db_permissions.py` | 26 pass + 1 xfail trên MySQL 8.0 chạy `db/init.sql` |
| 1 | Streamlit skeleton (trang chủ + 4 tab, không crash khi trống) | `dashboard/app.py`, `dashboard/ui_common.py`, `dashboard/pages/*.py`, `dashboard/assets/style.css` | `tests/test_dashboard_smoke.py` (AppTest), thử cả dữ liệu giả |
| 2 | AST whitelist v1 + test đơn vị | `security/ast_whitelist.py`, `tests/test_ast_whitelist.py` | 115 test, mỗi quy tắc ROADMAP 2.2 có ca chặn + ca hợp lệ |

Chạy lại:

```bash
pytest -v                                             # toàn bộ (test DB tự skip nếu MySQL chưa chạy)
pytest tests/test_db_permissions.py -v -m integration # cần docker compose up -d, DB_PORT=3307
streamlit run dashboard/app.py
```

## 2. AST whitelist v1 — thay đổi so với bản trước

Bản trước để lọt các câu sau (đã kiểm chứng bằng chạy thật), bản v1 chặn hết:

| Câu SQL | Bản trước | v1 (rule) |
| ------- | :-------: | --------- |
| `EXPLAIN DELETE FROM orders` | lọt | `statement_type` |
| `EXPLAIN ANALYZE SELECT ...` | lọt | `explain_analyze` (Tool 4 tự thêm ANALYZE sau khi kiểm) |
| `SELECT * FROM ordеrs` (chữ "е" Cyrillic) | lọt | `non_ascii_code` |
| `SELECT * FROM otherdb.t` với `allowed_schemas={"shopdb"}` | lọt | `schema_not_allowed` |
| `SELECT @@version`, `SELECT id INTO @x ...` | lọt | `variable` / `into_clause` |
| `SELECT ... FOR SHARE` | lọt | `locking_read` |

Và không còn chặn nhầm: `'a;b'` trong chuỗi, `UNION`, CTE, chuỗi tiếng Việt, optimizer hint `/*+ ... */`.

API mới cho tool (đúng api-contract mục 1, mã lỗi `AST_REJECTED` kèm `rule`):

```python
from security.ast_whitelist import check
r = check(sql, allowed_schemas={"shopdb"})
if not r["ok"]:
    return error("AST_REJECTED", r["message"], {"rule": r["rule"]})
sql = r["sql"]
```

`validate_sql` / `is_allowed_sql` giữ nguyên tên. `SQLRejected` là lớp con của `ValueError`, nên code cũ vẫn chạy.

**Giới hạn (ghi vào chương Bảo mật):**
- Whitelist chỉ chặn SQL nguy hiểm khi **chạy**. Chỉ thị nhắm vào LLM nằm trong comment thường (A1, A2, A4, A5, B1–B4 trong bộ payload) là việc của `sanitize` (Vũ + Tình, tuần 4).
- Tokenizer của sqlglot hiểu `\'` là ký tự escape giống MySQL mặc định. Nếu bật `sql_mode=NO_BACKSLASH_ESCAPES` thì hai bên sẽ hiểu khác nhau, nên **không bật** chế độ này. Ngoài ra, kết nối pymysql nên giữ mặc định không bật `MULTI_STATEMENTS` để có thêm một lớp chặn.

## 3. Vấn đề phát hiện, cần nhóm quyết định

1. **[Cao] `index_admin` xóa được cột** (Hải + Vũ). `init.sql` cấp `ALTER` để chạy `ALTER INDEX ... VISIBLE`, nhưng quyền `ALTER` của MySQL cũng cho phép `ALTER TABLE orders DROP COLUMN status`. Đã thử trên MySQL 8.0 và lệnh chạy thành công. Đề xuất:
   - (a) Bỏ `ALTER`, chỉ giữ `INDEX`. Tool 6 không "bật VISIBLE" mà `CREATE INDEX` thật sau khi validation pass (validation dùng index INVISIBLE tạo bằng `CREATE INDEX ... INVISIBLE`, chỉ cần quyền `INDEX`). Nhược điểm: tạo index 2 lần.
   - (b) Giữ `ALTER`, ghi rõ vào phần giới hạn. Tool 6 chỉ chạy DDL do server sinh, đã được approval token gắn hash.
   - Test `test_index_admin_has_no_alter_privilege` đang để `xfail` cho đến khi chốt.
2. **[Trung bình] Cổng DB lệch nhau** (Hải): `docker-compose.yml` map `3307:3306`, còn `.env.example` ghi `DB_PORT=3306`. Ngoài ra `docker-compose.yml` dùng `MYSQL_ROOT_PASSWORD`, `MYSQL_DATABASE` mà `.env.example` không có.
3. **[Trung bình] `db/schema.sql` có dòng `GO`** (cú pháp SQL Server), chạy trên MySQL sẽ lỗi. Schema chỉ có `sales_data`, trong khi README, seed và payload dùng `orders`/`users`. Cần chốt dùng bảng nào.
4. **[Trung bình] Báo cáo injection 18/20 chưa phản ánh đúng** (việc của Tình, tuần 5): lớp "sanitize" trong `run_tests.py` mới chỉ kiểm tra chuỗi có `/*` hay `--`, còn lớp "token validation" luôn gọi `verify_token("invalid_token")`. Sẽ làm lại khi có `sanitize.py` và Tool 6. Trước mắt **không dùng con số 18/20 trong báo cáo**.
5. **[Thấp]** `security/approval.py`: danh sách token đã dùng nằm trong RAM (restart là mất), và secret mặc định là `"dev-secret"`. Sẽ sửa cùng Tool 6 (tuần 5): lưu token đã dùng vào store, báo lỗi nếu thiếu `APPROVAL_SECRET`.

## 4. Dashboard — quy ước cho người nối dữ liệu

`dashboard/ui_common.py` đọc dữ liệu qua các hàm sau. Mỗi hàm trả `None` nếu module chưa có, nên Dashboard không crash:

| Hàm | Gọi tới (khi các bạn cài đặt) | Định dạng mong đợi |
| --- | ------------------------------ | ------------------ |
| `load_slow_queries` | `mcp_server.tools.slow_queries.get_slow_queries(limit=)` | dict `{ok, data: {queries: [...]}}` theo api-contract Tool 1 |
| `load_proposals` | `mcp_server.store.proposals.list_proposals()` | list proposal, mỗi cái có `validation_report.status` |
| `load_audit_log` | `mcp_server.store.audit_log.list_entries()` | list dict |
| `load_comparison` | `data/metrics/comparison.csv` | cột `query_id, p95_before_ms, p95_after_ms, ...` |

SQL và rationale từ DB/LLM luôn hiển thị bằng `st.code` / `st.text` (không render HTML). Nút Approve đang khóa (`TOOL6_READY = False`) cho tới tuần 5.
