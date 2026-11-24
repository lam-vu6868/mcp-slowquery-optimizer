# 📑 API CONTRACT — 6 TOOL MCP

> **Trạng thái:** DRAFT v2 ngày 22/11/2026 — đã đối chiếu đề bài môn học; chờ Vũ, Hải, Tường, Tình review trước khi coi là contract đã chốt.
> **Người giữ file:** Vũ. Thay đổi contract phải qua PR vào `dev` và báo các caller chịu ảnh hưởng.
> Căn cứ: đề bài do nhóm cung cấp, [ROADMAP.md](../project-management/ROADMAP.md) mục 2, [architecture.md](architecture.md) và code hiện tại. Đây là **đích triển khai**, không phải tuyên bố 6 Tool và Dashboard đã chạy đầu cuối.
> **Lab:** MySQL 8.0, `shopdb.multitable-v1`, 5 bảng/tổng 5 triệu dòng. Case study 12 triệu đơn hàng/CPU 98% là bối cảnh đề bài, chưa được tái hiện hoặc đo trên lab.
> **Ánh xạ case study:** đề bài dùng `(created_at, status)` trên 12 triệu đơn; schema lab có `orders.order_date` thay `created_at`. Query q07 đo `(status, order_date)` và `(order_date, status)` trên 1,5 triệu `orders`; chỉ dùng để thảo luận thứ tự composite, không coi là tái hiện chính xác sự cố Black Friday.
> **LLM:** contract không phụ thuộc nhà cung cấp; lab đang thử Groq với model `openai/gpt-oss-120b`. Nếu đổi model hoặc nhà cung cấp, vẫn phải giữ cùng schema proposal và ranh giới Tool 1–5.

---

## 1. Quy ước chung

**Định dạng phản hồi (mọi tool):**

```json
{
  "ok": true,
  "data": {},
  "error": null,
  "meta": { "tool": "get_schema", "duration_ms": 12, "truncated": false }
}
```

Khi lỗi:

```json
{
  "ok": false,
  "data": null,
  "error": { "code": "VALIDATION_FAILED", "message": "…", "detail": {} },
  "meta": { "tool": "explain_query", "duration_ms": 3, "truncated": false }
}
```

**Mã lỗi chuẩn:**

| Code                | Ý nghĩa                                             |
| ------------------- | --------------------------------------------------- |
| `INVALID_INPUT`     | Sai kiểu/thiếu tham số                              |
| `AST_REJECTED`      | SQL không qua AST whitelist (kèm `rule` bị vi phạm) |
| `NOT_FOUND`         | Bảng/cột/proposal không tồn tại                     |
| `TIMEOUT`           | Vượt `MAX_EXECUTION_TIME`                           |
| `VALIDATION_FAILED` | Đề xuất làm kết quả sai hoặc chậm hơn               |
| `MEASUREMENT_INVALID` | Không đủ lượt đo, timeout hoặc thiếu bằng chứng để kết luận |
| `TOKEN_INVALID`     | Token thiếu, sai, hết hạn hoặc đã dùng              |
| `FORBIDDEN`         | Không có quyền gọi tool này                         |
| `INTERNAL`          | Lỗi hệ thống                                        |

**Quy tắc bắt buộc:**

1. Mọi SQL nhận từ ngoài (Tool 4–5, rewrite để validation) phải qua `security/ast_whitelist.py` trước khi chạy; parse lỗi → `AST_REJECTED` (fail-closed). DDL của index chỉ sinh từ proposal có cấu trúc sau khi kiểm tra tên bảng/cột/index, không nhận SQL DDL do LLM viết.
2. Trong luồng MCP runtime, Tool 1–5 chỉ dùng `get_conn()` với `readonly_user`. Mã DDL nội bộ trong `mcp_server/tools/apply.py` dùng `get_admin_conn()` với `index_admin`: các hàm thử index do Validation Layer gọi nội bộ và Tool 6 áp dụng index đã duyệt. Hàm thử **không** là MCP Tool, không cấp cho LLM hoặc Dashboard UI. Script offline `scripts/verify_ground_truth.py` là ngoại lệ lab đã tách khỏi MCP, chỉ chạy khi được phép. Việc mở đường thử index runtime phải được Hải và Tình review trước khi triển khai.
3. SQL/comment lấy từ DB là dữ liệu không tin cậy: bỏ comment SQL bằng `strip_sql_comments()`, xử lý comment schema bằng `sanitize_comment()`, giới hạn độ dài, và gắn `"untrusted": true` ở trường text được trả cho LLM. Không đưa bí mật hoặc raw log đầy đủ vào prompt. Giá trị mẫu do Tool 3 trả cũng phải gắn nhãn dữ liệu không tin cậy.
4. LLM host chỉ có registry Tool 1–5. Tool 4–5 cung cấp **giao diện LLM bị giới hạn** riêng với hàm nội bộ validation; không tin LLM tự giữ `mode=estimate` hoặc `use_invisible_indexes=false`. Tool 6 chỉ ở registry/đường gọi riêng của backend Dashboard, luôn kiểm tra approval token một lần.
5. Thời gian: ISO 8601 UTC. Đơn vị latency: `ms`. Dung lượng: `bytes`.
6. Giới hạn trả về: tối đa 100 phần tử mỗi danh sách (bảng, cột, index, khóa ngoại, query); có `truncated: true` nếu bị cắt. Đặt timeout và giới hạn số lượt gọi ở ranh giới DB/LLM.

**Định danh query:** `query_id` là ID của **yêu cầu phân tích** do caller cấp và phải được LLM trả nguyên vẹn. Với bộ 30 query, caller cấp `q01`…`q30`; với query phát hiện từ Tool 1, caller dùng MySQL digest làm ID. Không tự coi digest là `q07`, không suy ra ground truth bằng cách so chuỗi SQL. `target_query_ids` và `original_query_id` dùng cùng ID của yêu cầu. Việc đánh giá so với ground truth chỉ dùng run đã gắn ID catalog `q01`…`q30`.

---

## 2. Cấu trúc dùng chung

### 2.1. `IndexProposal` (LLM đề xuất index)

LLM **không** gửi câu `CREATE INDEX`. Chỉ gửi cấu trúc, server tự sinh DDL sau khi kiểm tra bảng/cột có trong schema.

```json
{
  "type": "index",
  "table": "orders",
  "columns": [
    { "name": "status", "order": "ASC" },
    { "name": "order_date", "order": "ASC" }
  ],
  "index_name": "idx_orders_status_date",
  "rationale": "status là equality, order_date là range",
  "target_query_ids": ["q07"]
}
```

Ràng buộc: `index_name` khớp `^idx_[a-z0-9_]{1,50}$`; 1–5 cột, `order` chỉ `ASC`/`DESC`; bảng/cột phải thuộc `shopdb`, tên index chưa tồn tại và không trùng hoặc là tiền tố thừa của index hiện có. Backend chuẩn hóa proposal rồi tự sinh DDL với định danh được quote; không nối chuỗi SQL từ LLM. Proposal được lưu với `proposal_id` bất biến trước validation.

### 2.2. `RewriteProposal` (LLM đề xuất viết lại query)

```json
{
  "type": "rewrite",
  "original_query_id": "q12",
  "rewritten_sql": "SELECT …",
  "rationale": "Bỏ hàm DATE() bọc cột order_date để dùng được index"
}
```

`rewritten_sql` phải qua AST whitelist trước EXPLAIN/benchmark. Rewrite **chỉ để đề xuất/hiển thị**, không có đường apply vào DB. Nếu một phương án cần cả rewrite và index, backend ghi rõ hai thành phần và validation đo **cùng SQL đã rewrite + index**; không quy toàn bộ cải thiện cho riêng index. Tool 6 chỉ được áp dụng phần index khi index đó còn đạt validation trên SQL gốc; nếu không, cả phương án kết hợp chỉ để hiển thị.

### 2.3. Định dạng câu trả lời cuối của LLM

```json
{
  "query_id": "q07",
  "diagnosis": "Full table scan do thiếu index",
  "proposals": [
    {
      "type": "index",
      "table": "orders",
      "columns": [
        { "name": "status", "order": "ASC" },
        { "name": "order_date", "order": "ASC" }
      ],
      "index_name": "idx_orders_status_date",
      "rationale": "Lọc status rồi giới hạn khoảng ngày",
      "target_query_ids": ["q07"]
    }
  ],
  "confidence": "medium"
}
```

Parser (`llm/parsers.py`) kiểm tra bằng JSON Schema: `query_id` phải bằng ID caller gửi, `proposals` là danh sách `IndexProposal`/`RewriteProposal`, `confidence` chỉ `low|medium|high`. Sai schema → retry tối đa 2 lần, sau đó đánh dấu `parse_failed` (tính vào thống kê); không chuyển proposal lỗi sang validation.

---

## 3. Chi tiết 6 tool

### Tool 1 — `get_slow_queries`

|               |                                                                                        |
| ------------- | -------------------------------------------------------------------------------------- |
| **Người làm** | Vũ                                                                                     |
| **Quyền DB**  | `readonly_user`                                                                        |
| **Nguồn**     | Chính: `performance_schema.events_statements_summary_by_digest`; nguồn slow log `mysql.slow_log` chỉ bật sau khi cấp quyền đọc riêng và kiểm thử sanitize |

**Input:**

```json
{
  "limit": 10,
  "min_avg_latency_ms": 500,
  "order_by": "total_latency",
  "since": "2025-10-01T00:00:00Z"
}
```

`limit` mặc định 10, tối đa 100; `min_avg_latency_ms` lọc theo **latency trung bình** của digest. `since` tùy chọn: với `performance_schema`, chỉ lọc `LAST_SEEN >= since`; `exec_count`, P95 và latency vẫn là **số liệu tích lũy của digest**, không phải số đo riêng từ `since`. Không dùng chúng để vẽ biểu đồ cửa sổ thời gian. Không có digest đạt ngưỡng thì trả `ok=true, queries=[]`.

**Output `data`:**

```json
{
  "queries": [
    {
      "query_id": "a1b2c3…",
      "digest": "a1b2c3…",
      "source": "performance_schema",
      "sql_text": "SELECT … (đã strip comment)",
      "untrusted": true,
      "exec_count": 1520,
      "avg_latency_ms": 2310.4,
      "p95_latency_ms": 4120.0,
      "total_latency_ms": 3511808.0,
      "rows_examined_avg": 11987432,
      "rows_sent_avg": 84,
      "first_seen": "…",
      "last_seen": "…"
    }
  ]
}
```

`query_id` ở nguồn chính là digest MySQL, không phải ID catalog `q01`…`q30`; `source` xác định xuất xứ. Bản code hiện mới dùng `performance_schema`. Để đáp ứng yêu cầu đọc slow query log của đề bài, nhánh `mysql.slow_log` phải được triển khai với quyền `SELECT` chỉ trên bảng đó (không cấp `mysql.*`), giới hạn dòng/timeout, loại comment và gắn `untrusted`; ID của bản ghi log dùng `slowlog:` + SHA-256 của SQL đã chuẩn hóa. Trước khi cấp quyền, không mô tả nguồn phụ là đã hoạt động. File slow log vẫn dùng cho `pt-query-digest` dù nhánh bảng chưa được bật.

### Tool 2 — `get_schema`

|               |                 |
| ------------- | --------------- |
| **Người làm** | Vũ              |
| **Quyền DB**  | `readonly_user` |

**Input:** `{ "tables": ["orders", "customers"] }` — danh sách rỗng hoặc bỏ qua = tất cả bảng trong `shopdb`; tên lặp được gộp, bảng không tồn tại → `NOT_FOUND`.

**Output `data`:**

```json
{
  "tables": [
    {
      "name": "orders",
      "engine": "InnoDB",
      "columns": [
        {
          "name": "order_id",
          "type": "bigint",
          "nullable": false,
          "key": "PRI",
          "comment": "",
          "untrusted": true
        },
        {
          "name": "customer_id",
          "type": "bigint",
          "nullable": true,
          "key": "MUL",
          "comment": "",
          "untrusted": true
        }
      ],
      "indexes": [
        {
          "name": "PRIMARY",
          "columns": ["order_id"],
          "unique": true,
          "visible": true,
          "size_bytes": null
        },
        {
          "name": "fk_orders_customer",
          "columns": ["customer_id"],
          "unique": false,
          "visible": true,
          "size_bytes": null
        }
      ],
      "foreign_keys": [
        {
          "name": "fk_orders_customer",
          "columns": ["customer_id"],
          "referenced_table": "customers",
          "referenced_columns": ["customer_id"]
        }
      ]
    }
  ]
}
```

`comment` luôn qua `sanitize_comment()` và gắn `untrusted`.

`size_bytes` hiện trả `null` vì Tool 2 chưa có nguồn đo kích thước từng index với quyền `readonly_user`. MySQL lưu số trang từng index trong `mysql.innodb_index_stats`, nhưng tài khoản này không có quyền đọc bảng đó. Caller phải coi `null` là "chưa biết", không coi là 0 byte. Tool 2 không dùng tổng `INDEX_LENGTH` của bảng để giả làm kích thước từng index; dung lượng **index phát sinh trong thử nghiệm** được đo và ghi riêng ở Validation Layer.

### Tool 3 — `get_table_stats`

|               |                 |
| ------------- | --------------- |
| **Người làm** | Vũ              |
| **Quyền DB**  | `readonly_user` |

**Input:** `{ "table": "orders", "columns": ["status", "order_date"] }` — `table` bắt buộc; `columns` bỏ qua hoặc rỗng = các cột của bảng (tối đa 10). Bảng/cột phải thuộc `shopdb`; sai tên → `NOT_FOUND`.

**Output `data`:**

```json
{
  "table": "orders",
  "row_count_estimate": 1500000,
  "data_bytes": 210000000,
  "index_bytes": 80000000,
  "sample": {
    "method": "pk_windows",
    "max_rows": 1000,
    "observed_rows": 1000,
    "seed": "shopdb.multitable-v1:orders"
  },
  "columns": [
    {
      "name": "status",
      "cardinality": 3,
      "null_ratio": 0.0,
      "top_values": [
        { "value": "paid", "ratio": 0.85, "untrusted": true },
        { "value": "pending", "ratio": 0.07, "untrusted": true }
      ],
      "min": null,
      "max": null
    }
  ]
}
```

`row_count_estimate`, `data_bytes`, `index_bytes` lấy từ `information_schema.TABLES` (`TABLE_ROWS`, `DATA_LENGTH`, `INDEX_LENGTH`); đây là **ước lượng của InnoDB**, không phải số đếm chính xác hay dung lượng từng index. `cardinality` là số giá trị khác nhau **trong mẫu**, không suy rộng thành số distinct toàn bảng. `null_ratio`, `top_values[].ratio`, `min` và `max` cũng chỉ tính trên mẫu; mẫu rỗng → `cardinality=0`, `null_ratio=null`, `top_values=[]`, `min/max=null`.

**Quy tắc lấy mẫu cần triển khai:** 5 bảng lab đều có PK số nguyên. Mỗi lần gọi đọc tối đa 1.000 dòng bằng 10 cửa sổ PK, mỗi cửa sổ tối đa 100 dòng (`WHERE pk >= anchor ORDER BY pk LIMIT 100`); anchor xác định từ hash của `dataset_version`, tên bảng và số thứ tự cửa sổ. Gộp theo PK, không dùng `ORDER BY RAND()`, không `COUNT(*)` toàn bảng hoặc quét toàn bảng mỗi lần gọi. `sample.observed_rows` là số dòng thật đã lấy sau gộp. Chọn cột bằng danh sách từ `information_schema`, quote định danh sau kiểm tra; không chèn tên cột/bảng do caller gửi thẳng vào SQL.

`top_values` có tối đa 10 giá trị, chỉ cho cột phân loại không nhạy cảm (`status`, `category`, `city`, `state`, `country`) khi `cardinality <= 50`; các cột khác trả `[]`. Giá trị chuỗi giới hạn độ dài, bỏ ký tự điều khiển, gắn `untrusted: true`; không trả các giá trị tên, email, điện thoại, địa chỉ đường phố. Tỷ lệ là số lần xuất hiện trong mẫu / `observed_rows`. Thời gian và số lần đọc phải có giới hạn; không lấy số liệu này làm ground truth phân bố toàn bảng.

### Tool 4 — `explain_query`

|               |                 |
| ------------- | --------------- |
| **Người làm** | Hải             |
| **Quyền DB**  | `readonly_user` |

**Input:**

```json
{
  "sql": "SELECT …",
  "mode": "estimate",
  "use_invisible_indexes": false
}
```

- `estimate`: `EXPLAIN FORMAT=JSON` (không chạy query).
- `analyze`: `EXPLAIN ANALYZE` **có chạy query**; chỉ Validation Layer được gọi nội bộ sau AST whitelist và với timeout cả ở MySQL lẫn host.
- `use_invisible_indexes`: dùng cho Validation Layer; LLM không được truyền tham số này.
- Trên mỗi kết nối, đặt rõ `SET SESSION optimizer_switch='use_invisible_indexes=off'` khi `false`, hoặc `on` khi `true`; không kế thừa giá trị global cho phép đo trước tối ưu. Không đổi input/output hoặc cấu hình global.

**Output `data`:**

```json
{
  "query_cost": 2412345.6,
  "access_type": "ALL",
  "key_used": null,
  "rows_examined_estimate": 11987432,
  "rows_examined_actual": null,
  "using_filesort": true,
  "using_temporary": false,
  "warnings": ["Full table scan on orders"],
  "raw_plan": {}
}
```

`rows_examined_actual` chỉ có khi `mode = analyze`.

**Giao diện cấp cho LLM:** chỉ nhận `sql`, cố định `mode="estimate"` và `use_invisible_indexes=false` tại backend. `server.py` đã đăng ký `explain_for_llm` dưới tên public `explain_query`; không đăng ký trực tiếp hàm đầy đủ. Hàm đầy đủ dành cho Validation Layer nội bộ.

### Tool 5 — `benchmark_query`

|               |                    |
| ------------- | ------------------ |
| **Người làm** | Tường (Hải review) |
| **Quyền DB**  | `readonly_user`    |

**Input:**

```json
{
  "sql": "SELECT …",
  "warmup_runs": 3,
  "measured_runs": 20,
  "timeout_ms": 30000,
  "use_invisible_indexes": false,
  "compute_result_hash": true
}
```

Giới hạn: `measured_runs` 5–50, `timeout_ms` ≤ 60000.

**Giao diện cấp cho LLM:** chỉ nhận `sql`; backend cố định `warmup_runs=1`, `measured_runs=5`, `timeout_ms=5000`, `use_invisible_indexes=false`, `compute_result_hash=false` và giới hạn số lần gọi. Validation Layer gọi hàm nội bộ với 3 warm-up + 20 lượt đo, hash đầy đủ và timeout theo cấu hình lab. `server.py` đã đăng ký `benchmark_for_llm` dưới tên public `benchmark_query`; không cấp trực tiếp các cờ nội bộ cho LLM.

**Quy tắc triển khai và đo:**

- Đọc kết quả bằng server-side cursor theo từng lô; P50/P95 bao gồm thời gian MySQL xử lý và truyền hết kết quả.
- P95 tính theo phương pháp nearest-rank. Warm-up không được đưa vào mẫu đo.
- `rows_examined` lấy từ chênh lệch các bộ đếm `Handler_read*` trước/sau từng lượt và trả về trung vị.
- Hash được tính trong một lượt riêng, không tính vào P50/P95.
- Query không có `ORDER BY` được chuẩn hóa và sắp xếp trên ổ đĩa trước khi hash.
- Kết quả thiếu số lượt yêu cầu, timeout hoặc thiếu hash khi `compute_result_hash=true` phải trả `ok=false`, `MEASUREMENT_INVALID` (hoặc `TIMEOUT` nếu toàn bộ lượt timeout); không trả P95 thành công để caller dùng làm baseline. Giao diện LLM được cố định `compute_result_hash=false`, nên không bắt buộc có hash. Code Tool 5 đã xử lý trường hợp này; Validation Layer vẫn chưa triển khai.
- `use_invisible_indexes` cũng được đặt OFF/ON rõ ràng theo session như Tool 4. `true` cho phép optimizer cân nhắc index INVISIBLE, không đảm bảo index được chọn; cần đối chiếu EXPLAIN. Chỉ dùng nội bộ validation/lab, không cấp quyền bật cho LLM.
- `rows_examined` từ `Handler_read*` là số đo thay thế của hoạt động đọc, không phải số `ROWS_EXAMINED` chính xác từ Performance Schema; cần ghi rõ khi báo cáo.

**Output `data`:**

```json
{
  "p50_ms": 2100.3,
  "p95_ms": 2890.1,
  "min_ms": 1980.0,
  "max_ms": 3020.4,
  "stddev_ms": 210.7,
  "runs": 20,
  "timed_out_runs": 0,
  "rows_examined": 11987432,
  "cache_state": "warm",
  "result_hash": "sha256:…",
  "row_count": 84,
  "deterministic_order": true,
  "warnings": []
}
```

Nếu query không có `ORDER BY` xác định, tool sort kết quả theo mọi cột trước khi hash và đặt `deterministic_order: false` kèm cảnh báo.

### Tool 6 — `apply_optimization` ⚠️

|                 |                                                                            |
| --------------- | -------------------------------------------------------------------------- |
| **Người làm**   | Tình (Vũ + Hải review bắt buộc)                                            |
| **Quyền DB**    | `index_admin` (chỉ `CREATE/DROP INDEX`, `ALTER INDEX … VISIBLE/INVISIBLE`) |
| **Ai được gọi** | **Chỉ backend Dashboard**. Không nằm trong danh sách tool cấp cho LLM      |

**Luồng phê duyệt:**

1. Backend lưu `IndexProposal` đã chuẩn hóa thành `proposal_id` bất biến; Validation Layer tạo index thử **INVISIBLE** qua hàm DDL nội bộ trong `apply.py`, đo và lưu `validation_report`. Hàm nội bộ không nhận DDL tự do, không được đăng ký cho LLM.
2. Chỉ proposal index có validation `passed` trên **SQL gốc** mới hiện nút Approve. Khi người dùng bấm, backend tạo lệnh áp dụng chuẩn `ALTER TABLE <table> ALTER INDEX <index> VISIBLE` từ proposal đã lưu. Token một lần ràng buộc `proposal_id`, phiên bản proposal, SHA-256 của **lệnh ALTER này**, nonce và thời hạn 10 phút; bí mật HMAC chỉ ở server.
3. Backend Dashboard gọi `apply_optimization(proposal_id, approval_token)` qua đường/registry riêng; LLM không có Tool 6 hoặc token.
4. Tool 6 đọc lại proposal và report, kiểm tra index còn INVISIBLE và định nghĩa khớp proposal, xác thực token và đánh dấu đã dùng theo cách nguyên tử; sau đó chạy đúng lệnh ALTER đã hash và ghi audit cả khi thành công hoặc bị từ chối. Nếu DDL lỗi, không coi là đã áp dụng.

**Input:**

```json
{ "proposal_id": "p_20251020_0007", "approval_token": "…" }
```

**Output `data`:**

```json
{
  "applied": true,
  "ddl": "ALTER TABLE orders ALTER INDEX idx_orders_status_date VISIBLE",
  "index_visible": true,
  "index_size_bytes": 310000000,
  "index_size_source": "table_index_length_delta",
  "audit_id": "a_000123",
  "rollback_ddl": "DROP INDEX idx_orders_status_date ON orders"
}
```

**Lỗi:** `TOKEN_INVALID` (thiếu/sai/hết hạn/đã dùng/khác DDL), `VALIDATION_FAILED` (proposal chưa pass validation), `NOT_FOUND`.

**Quy tắc cứng:**

- Proposal loại `rewrite`, hoặc phương án index chỉ đạt khi kèm rewrite/hint, → `FORBIDDEN` ở Tool 6 (chỉ hiển thị). Muốn áp dụng index phải kiểm chứng độc lập trên SQL gốc.
- Không có tham số nào cho phép truyền SQL tự do.
- `index_size_bytes` lấy từ `validation_report`, không tự suy đoán ở Tool 6. Mọi lần gọi (kể cả bị từ chối) đều ghi `audit_log`: thời gian, proposal_id, hash lệnh ALTER, kết quả, người duyệt và nguồn gọi; không ghi token/bí mật.

---

## 4. Validation Layer (nội bộ, không phải tool)

Hải xây, backend gọi sau khi parser đã chấp nhận proposal. Đường này không đăng ký thành MCP Tool cho LLM:

```json
{
  "proposal_id": "p_20251020_0007",
  "query_id": "q07",
  "status": "passed",
  "candidate_sql_kind": "original",
  "before": {
    "p95_ms": 2890.1,
    "query_cost": 2412345.6,
    "rows_examined": 11987432,
    "result_hash": "sha256:abc123",
    "row_count": 84,
    "runs": 20,
    "timed_out_runs": 0
  },
  "after": {
    "p95_ms": 41.2,
    "query_cost": 1820.4,
    "rows_examined": 5210,
    "result_hash": "sha256:abc123",
    "row_count": 84,
    "runs": 20,
    "timed_out_runs": 0,
    "key_used": "idx_orders_status_date"
  },
  "result_equivalent": true,
  "improvement_ratio": 0.986,
  "write_overhead": {
    "insert_throughput_change_pct": -6.5,
    "index_size_bytes": 310000000,
    "index_size_source": "table_index_length_delta",
    "index_size_estimated": true,
    "measurement_scope": "isolated_lab"
  },
  "evidence_complete": true,
  "failure_reason": null
}
```

**Luồng kiểm chứng index:** dùng SQL gốc đã qua AST; ghi `INDEX_LENGTH` trước khi tạo một index INVISIBLE từ proposal có cấu trúc trên lab được phép thử; đo baseline với `use_invisible_indexes=off`, đo sau với `on`, đối chiếu EXPLAIN xem optimizer có chọn index mới. Mỗi bên có 3 warm-up + 20 lượt đo thành công, cùng cache warm và timeout; tính P95 theo nearest-rank. Hash toàn bộ kết quả và số dòng phải khớp. `rows_examined` của Tool 5 là proxy `Handler_read*`, phải ghi nguồn trong báo cáo, không gọi là số MySQL `ROWS_EXAMINED` chính xác. Query Cost lấy từ EXPLAIN JSON; dashboard lưu trước/sau từng query và tính tổng trên các query hợp lệ.

**Dung lượng và chi phí ghi:** đo `INDEX_LENGTH` của bảng trước/sau khi chỉ thêm một secondary index trên lab không có ghi đồng thời; đặt `information_schema_stats_expiry=0` trong session đo để tránh dùng cache metadata cũ. Chênh lệch là **ước lượng dung lượng index phát sinh**, kèm `index_size_source` và `index_size_estimated=true`, không phải kích thước chính xác từng index. Đo INSERT throughput trước/sau với cùng số dòng (`validation.write_overhead_rows` trong `config/settings.yaml`) trên bản sao dữ liệu thử riêng, không chèn hàng thử vào bộ ground truth 5M. Nếu chênh lệch size không xác định hoặc thiếu một trong hai số đo thì `evidence_complete=false`; không công bố đã hoàn thành yêu cầu trade-off. `information_schema.TABLES` là nguồn ước lượng; chỉ kết quả có nguồn/điều kiện đo rõ ràng mới đưa vào biểu đồ.

**Trạng thái:** `passed` khi hash và số dòng tương đương, P95 giảm ≥20%, đủ 20/20 lượt mỗi bên, không timeout/lỗi và với index proposal có bằng chứng optimizer chọn index mới. `failed` khi đo hợp lệ nhưng sai kết quả hoặc không đạt ngưỡng; `inconclusive` khi thiếu lượt, thiếu số đo bắt buộc hoặc không chứng minh được index được dùng. Tool 6 chỉ nhận `passed` **và** `evidence_complete=true` trên SQL gốc. Fail/inconclusive/ngoại lệ → dọn index thử và ghi lý do; pass giữ INVISIBLE để chờ người duyệt, Reject hoặc hết hạn chờ duyệt thì dọn. Rewrite thuần chỉ đo SQL gốc và SQL viết lại, không tạo index và không đi qua Tool 6; phương án rewrite + index phải ghi `candidate_sql_kind="rewritten"` và chỉ hiển thị nếu chưa kiểm chứng index độc lập trên SQL gốc.

---

## 5. Đối chiếu đề bài và tiêu chí nghiệm thu

| Yêu cầu đề bài | Bằng chứng cần có trước khi đánh dấu Done |
| --- | --- |
| MySQL ≥ 5M dòng, slow log 0,5s | Kiểm tra số dòng 5 bảng, `slow_query_log=ON`, `long_query_time=0.5`, `log_output`; lưu bằng chứng lab. Case study 12M/CPU 98% chỉ là bối cảnh, không ghi là số đo của nhóm. |
| 30 query, 5 nhóm lỗi, ground truth | 6 query mỗi nhóm; `ground_truth.json` có đáp án và bằng chứng P95/hash; Hải review và GVHD ký. Trạng thái hiện tại là `performance_verified_pending_review`, chưa ký. |
| 6 MCP Tool | Tool 1–5 gọi được qua registry LLM với input/output đúng contract; Tool 6 chỉ qua backend Dashboard và token một lần. Unit test của từng tool không thay thế kiểm tra qua MCP thật. |
| Validation tự động + Human-in-the-loop | Report trước/sau đủ lượt, hash/số dòng khớp, Query Cost, proxy rows examined, index mới thực sự được chọn; index thử được rollback khi fail/reject. Tool 6 chỉ áp dụng sau validation pass, đủ bằng chứng và người duyệt. |
| Biểu đồ P95, Query Cost, rows examined, dung lượng index, trade-off ghi/đọc | Lưu metric trước/sau cho từng query và tổng Query Cost; ghi rõ nguồn/đơn vị/giới hạn của proxy và kích thước index ước lượng; đo INSERT throughput trên bản sao lab. Không dùng số `null`/đo thiếu như 0. |
| Precision/Recall, Consistency, FPR | Chỉ tính với 30 ID catalog sau khi ground truth được review/ký; chạy LLM 5 lần cùng prompt/model/temperature; so index chính xác hoặc tương đương theo ROADMAP mục 2.4; báo cả mẫu số và ca không parse được. |
| ≥20 prompt injection, chặn DDL/DML nguy hiểm | Chạy ít nhất 20 payload qua slow log, schema comment, SQL và đầu ra; mọi payload DDL/DML nguy hiểm trong **bộ đã thử** phải bị từ chối bởi AST whitelist, quyền read-only hoặc chặn Tool 6, có log và test. Báo `20/20` nếu đạt, không tuyên bố an toàn tuyệt đối với mọi payload chưa thử. |
| ≥2 baseline truyền thống | `pt-query-digest` so phát hiện/xếp hạng slow query; greedy và rule-based so đề xuất index. Không lấy `pt-query-digest` làm baseline Precision/Recall index vì nó không đề xuất index. |
| Dashboard Grafana/Streamlit | Streamlit hiển thị top slow query, đề xuất, trạng thái validation/phê duyệt và biểu đồ trước/sau; nút Approve chỉ có khi report đủ điều kiện, gọi Tool 6 qua backend. |

Mục tiêu số học và deadline vẫn lấy từ [ROADMAP.md](../project-management/ROADMAP.md) mục 2.4–5. `PROGRESS.md` ghi trạng thái đã kiểm chứng; không suy ra “đã xong” từ ví dụ trong contract.

## 6. Ảnh hưởng tới caller và việc cần review

- **Tool 1 / Dashboard / LLM host (Vũ, Tình):** `query_id` từ Tool 1 là digest, không phải `q07`; output thêm `source`, và `since` không tạo metric theo cửa sổ thời gian. Nhánh đọc `mysql.slow_log` cùng quyền `SELECT` riêng hiện chưa có. Caller phải truyền ID phân tích đúng ngữ cảnh và không tự ghép digest với ground truth.
- **Tool 3 / LLM host (Vũ):** output thêm `sample`; `cardinality`, `null_ratio`, `top_values`, `min/max` chỉ có ý nghĩa trên mẫu PK có giới hạn. Code đã có test mẫu rỗng, cột nhạy cảm, timeout và giới hạn truy vấn; đã đăng ký MCP trong registry LLM.
- **Tool 4–5 / MCP registry (Hải, Tường, Vũ):** đã đăng ký wrapper giới hạn cho LLM; hàm đầy đủ dành cho Validation Layer. Tool 5 trả `MEASUREMENT_INVALID` khi phép đo nội bộ thiếu lượt/hash, thay vì `ok=true` với P95 một phần.
- **Validation / Tool 6 / Dashboard (Hải, Tình, Vũ):** DDL thử nằm trong hàm nội bộ `apply.py`, không là Tool 6 công khai; token hash đúng lệnh `ALTER ... VISIBLE` sẽ chạy. Report thêm `candidate_sql_kind`, `evidence_complete`, nguồn/giới hạn size và write overhead. `index_size_bytes` ở Tool 2 vẫn `null`; Tool 6 lấy số đo từ report. Cần review thiết kế quyền, rollback và đồng bộ lại sơ đồ trong `architecture.md` trước khi triển khai.
- **Tương thích:** đây là contract đích, chưa phản ánh đủ code hiện tại. Không sửa Tool 4–6 hoặc tài liệu của thành viên khác chỉ để làm test xanh; mỗi owner/reviewer cập nhật phần của mình qua PR. Trước khi tích hợp end-to-end, chạy test contract, thử MySQL/Dashboard thật và kiểm thử 20 payload.

**Review còn chờ:** Vũ (Tool 1–3, ID query, registry); Hải (Validation, quyền thử index, Tool 4); Tường (Tool 5, số đo/ground truth); Tình (Tool 6, token, injection, Dashboard). Chỉ đổi trạng thái DRAFT sau khi các review liên quan hoàn tất.

**Nguồn kỹ thuật MySQL 8.0:** [slow query log](https://dev.mysql.com/doc/refman/8.0/en/slow-query-log.html), [ước lượng `TABLE_ROWS`/`INDEX_LENGTH`](https://dev.mysql.com/doc/refman/8.0/en/information-schema-tables-table.html), [thống kê kích thước từng index](https://dev.mysql.com/doc/refman/8.0/en/innodb-persistent-stats.html).
