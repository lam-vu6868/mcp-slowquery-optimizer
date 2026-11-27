# 📑 API CONTRACT — 6 TOOL MCP

> **Trạng thái:** v2 đã chốt về thiết kế ngày 25/11/2026 theo ủy quyền của người dùng thay nhóm review. Chốt contract không đồng nghĩa 6 tool và luồng end-to-end đã hoàn thành.
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
2. Trong luồng MCP runtime, Tool 1–5 chỉ dùng `get_conn()` với `readonly_user`. Mã DDL nội bộ trong `mcp_server/tools/apply.py` dùng `get_admin_conn()` với `index_admin`: các hàm thử index do Validation Layer gọi nội bộ và Tool 6 áp dụng index đã duyệt. Hàm thử **không** là MCP Tool, không cấp cho LLM hoặc Dashboard UI. Script offline `scripts/verify_ground_truth.py` là ngoại lệ lab đã tách khỏi MCP, chỉ chạy khi được phép. Đường thử index runtime vẫn phải được kiểm chứng trên môi trường được phép trước khi đưa vào backend.
3. SQL/comment lấy từ DB là dữ liệu không tin cậy: bỏ comment SQL bằng `strip_sql_comments()`, xử lý comment schema bằng `sanitize_comment()`, giới hạn độ dài, và gắn `"untrusted": true` ở trường text được trả cho LLM. Không đưa bí mật hoặc raw log đầy đủ vào prompt. Giá trị mẫu do Tool 3 trả cũng phải gắn nhãn dữ liệu không tin cậy.
4. LLM host chỉ có registry Tool 1–5. Tool 4–5 cung cấp **giao diện LLM bị giới hạn** riêng với hàm nội bộ validation; không tin LLM tự giữ `mode=estimate` hoặc `use_invisible_indexes=false`. Tool 6 chỉ ở registry/đường gọi riêng của backend Dashboard, luôn kiểm tra approval token một lần.
5. Thời gian: ISO 8601 UTC. Đơn vị latency: `ms`. Dung lượng: `bytes`.
6. Giới hạn trả về: tối đa 100 phần tử mỗi danh sách (bảng, cột, index, khóa ngoại, query); có `truncated: true` nếu bị cắt. Đặt timeout và giới hạn số lượt gọi ở ranh giới DB/LLM.

**Định danh query:** `query_id` là ID của **yêu cầu phân tích** do caller cấp và phải được LLM trả nguyên vẹn. Với bộ 30 query, caller cấp `q01`…`q30`; với query phát hiện từ Tool 1, caller dùng MySQL digest làm ID. Không tự coi digest là `q07`, không suy ra ground truth bằng cách so chuỗi SQL. `target_query_ids` và `original_query_id` dùng cùng ID của yêu cầu. Việc đánh giá so với ground truth chỉ dùng run đã gắn ID catalog `q01`…`q30`.

---

## 2. Cấu trúc dùng chung

### 2.1. `IndexProposal` (LLM đề xuất index)

LLM **không** gửi câu `CREATE INDEX`. Chỉ gửi cấu trúc, server tự sinh DDL sau khi kiểm tra bảng/cột có trong schema.

Proposal có tiền tố cột trùng với khóa ngoại tham chiếu vẫn có thể được LLM đề xuất. Đường Dashboard/runtime mặc định từ chối trước DDL và trả `inconclusive` với `failure_reason="foreign_key_support_risk"`; caller không được đưa report này tới Approve. Nhánh thử riêng `allow_fk_trials=true` chỉ nhận validation lab `127.0.0.1:3309` có marker `mcp-validation-lab-v1`, với snapshot FK/index đã lưu trước DDL. Helper chỉ cho tạo trial khi đúng một FK bị ảnh hưởng và index hỗ trợ có định nghĩa đơn giản có thể khôi phục; nếu MySQL tự bỏ index cũ, helper dựng lại nó **trước khi đo baseline**. Cleanup đối chiếu schema với snapshot. Kết quả lab đã dọn trial không dùng để cấp approval token hoặc áp dụng trên DB chính.

Nếu recovery gặp trial đang là index duy nhất hỗ trợ FK, nó chỉ khôi phục khi có snapshot lưu trước DDL, FK/marker/index hiện tại khớp, trial đang hỗ trợ **chính FK của index bị mất**, và đúng **một index BTREE không unique, visible, không prefix/comment, cột ASC** bị mất. Helper tạo lại đúng tên/cột trong snapshot, xác minh index gốc và trial, rồi mới DROP trial; sau DROP phải đối chiếu schema FK/index với snapshot trước khi chuyển `pending` sang `cleaned`. Nếu thiếu snapshot, metadata đổi, DDL lỗi hoặc không xác minh được, proposal giữ `pending` và trả `recovery_failed` để backend chặn việc mới. Không suy ra định nghĩa index từ tên constraint. Nhánh này mới thử trên bảng nhỏ của validation lab; guard chặn q01 trước CREATE vẫn còn.

Trước `begin_trial`, backend đọc FK và các index hỗ trợ trên bảng bằng `readonly_user`. `begin_trial` ghi snapshot này cùng `trial_state=pending` trong một giao dịch SQLite; lỗi đọc/ghi dừng trước DDL. Snapshot gồm tên và thứ tự cột FK, tên/cột/thứ tự cột/kiểu/tính duy nhất/visibility/comment của index hỗ trợ. Hiện snapshot chỉ phục vụ đối chiếu về sau, chưa cho phép tự dựng lại index hay duyệt q01.

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
| **Nguồn**     | Chính: `performance_schema.events_statements_summary_by_digest`; nguồn slow log `mysql.slow_log` cần quyền đọc riêng và đã được thử trên lab |

**Input:**

```json
{
  "limit": 10,
  "min_avg_latency_ms": 500,
  "order_by": "total_latency",
  "since": "2025-10-01T00:00:00Z",
  "source": "performance_schema"
}
```

`limit` mặc định 10, tối đa 100. `source` mặc định `performance_schema`; chọn `slow_log` để đọc từng lần chạy từ `mysql.slow_log` khi đã cấp quyền `SELECT` riêng trên bảng đó. `min_avg_latency_ms` lọc theo **latency trung bình** của digest ở nguồn chính, hoặc thời gian của từng lần chạy ở slow log. `since` tùy chọn: với `performance_schema`, chỉ lọc `LAST_SEEN >= since`; `exec_count`, P95 và latency vẫn là **số liệu tích lũy của digest**, không phải số đo riêng từ `since`. Với `slow_log`, `since` lọc `start_time`. Không dùng thống kê digest để vẽ biểu đồ cửa sổ thời gian. Không có bản ghi đạt ngưỡng thì trả `ok=true, queries=[]`.

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

`query_id` ở nguồn chính là digest MySQL, không phải ID catalog `q01`…`q30`; `source` xác định xuất xứ. Nhánh `slow_log` trả **từng bản ghi**, không gom digest: `digest=null`, `exec_count=1`, `avg_latency_ms` và `total_latency_ms` bằng thời gian lần chạy, `p95_latency_ms=null`, `first_seen=last_seen=start_time`; `rows_*_avg` là số của lần chạy đó. `order_by=exec_count` trên nguồn này sắp theo `start_time` vì mỗi bản ghi có cùng `exec_count=1`; các cách sắp latency dùng `query_time`. ID là `slowlog:` + SHA-256 của SQL sau khi bỏ comment. SQL dài hơn 8.000 byte bị loại trước khi chuyển về Python; truy vấn giới hạn 5 giây và tối đa `limit+1` dòng, strip comment và gắn `untrusted`. Nếu chưa có quyền `SELECT` riêng trên `mysql.slow_log`, trả `FORBIDDEN` và không tự chuyển nguồn. File slow log vẫn dùng cho `pt-query-digest`.

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

**Ranh giới LLM host (27/11/2026):** Public output của Tool 2 ở trên không đổi. Trước khi chuyển response `get_schema` cho LLM, `llm/agent.py` loại những bảng có `name` không khớp `^[A-Za-z_][A-Za-z0-9_]*$`; cùng danh sách đã lọc được dùng để kiểm index proposal. Bảng hợp lệ vẫn giữ, kể cả khi response có bảng không hợp lệ. Việc lọc áp dụng cả response `truncated`; response raw và nội dung chuyển tiếp có hash riêng trong run metadata khi có lọc. Caller không được lấy tên bảng bị lọc làm bằng chứng proposal hợp lệ. Quy tắc này phù hợp guard identifier của `TrialIndex`, nhưng không chứng minh mọi nội dung schema đều chống prompt injection.

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
- Kết quả thiếu số lượt yêu cầu, timeout hoặc thiếu hash khi `compute_result_hash=true` phải trả `ok=false`, `MEASUREMENT_INVALID` (hoặc `TIMEOUT` nếu toàn bộ lượt timeout); không trả P95 thành công để caller dùng làm baseline. Giao diện LLM được cố định `compute_result_hash=false`, nên không bắt buộc có hash. Validation Layer đã thử q05 trên lab đủ 5M dòng; chưa kiểm đủ 30 query hoặc nối Tool 6.
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
4. Tool 6 đọc lại proposal và report của chính môi trường đang áp dụng, kiểm tra index thử còn INVISIBLE, có marker/định nghĩa khớp proposal và report chưa mất hiệu lực; không dùng report từ lab đã dọn index hoặc từ DB khác để cấp token. Sau đó xác thực token, đánh dấu đã dùng theo cách nguyên tử, chạy đúng lệnh ALTER đã hash và ghi audit cả khi thành công hoặc bị từ chối. Nếu DDL lỗi, không coi là đã áp dụng.

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
  "index_size_source": "innodb_index_stats_pages",
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
  "db_identity": {"server_uuid": "mysql-server-uuid", "schema": "shopdb", "host": "127.0.0.1", "port": 3307},
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
    "key_used": "idx_orders_status_date",
    "raw_plan": {"query_block": {"table": {"table_name": "orders", "key": "idx_orders_status_date"}}}
  },
  "result_equivalent": true,
  "improvement_ratio": 0.986,
  "write_overhead": {
    "insert_throughput_change_pct": -6.5,
    "before_rows_per_second": 63425.38,
    "after_rows_per_second": 59296.73,
    "sample_rows": 100000,
    "preload_rows": 100000,
    "index_size_bytes": 310000000,
    "index_size_source": "innodb_index_stats_pages",
    "index_size_estimated": true,
    "measurement_scope": "isolated_lab"
  },
  "evidence_complete": true,
  "failure_reason": null
}
```

**Luồng kiểm chứng index:** dùng SQL gốc đã qua AST; ghi hai số đo nền cấp bảng trước khi tạo một index INVISIBLE từ proposal có cấu trúc trên lab được phép thử. Helper kiểm tra FK trước DDL; đường mặc định từ chối tiền tố FK với `inconclusive/foreign_key_support_risk`. Nhánh lab 3309 có cờ riêng, snapshot bền vững và đủ điều kiện khôi phục sẽ tạo trial rồi bảo đảm index FK gốc có mặt trước lượt đo. Đo baseline với `use_invisible_indexes=off`, đo sau với `on`, đối chiếu EXPLAIN xem optimizer có chọn index mới trên **đúng bảng proposal**, kể cả khi bảng đó nằm sau trong JOIN. Caller lưu report phải giữ `after.raw_plan` từ Tool 4: `key_used` đơn lẻ chỉ mô tả bảng đầu tiên và không đủ chứng minh. Nếu alias bảng trong SQL bị dùng lại cho bảng khác hoặc thiếu plan, validation trả `inconclusive`. Mỗi bên có 3 warm-up + 20 lượt đo thành công, cùng cache warm và timeout; tính P95 theo nearest-rank. Hash toàn bộ kết quả và số dòng phải khớp. `rows_examined` của Tool 5 là proxy `Handler_read*`, phải ghi nguồn trong báo cáo, không gọi là số MySQL `ROWS_EXAMINED` chính xác. Query Cost lấy từ EXPLAIN JSON; dashboard lưu trước/sau từng query và tính tổng trên các query hợp lệ.

**Dung lượng và chi phí ghi:** `TrialIndex.size_delta()` trả `index_size_bytes` và `index_size_source`. Nguồn ưu tiên `innodb_index_stats_pages` lấy số trang `size` của **đúng index thử** từ `mysql.innodb_index_stats`, nhân `@@innodb_page_size`; tài khoản `index_admin` chỉ cần `SELECT` trên bảng stats này, không cần quyền `INSERT` để chạy `ANALYZE TABLE`. Nếu thiếu quyền hoặc hàng stats, dùng `table_index_length_delta`: chênh lệch `information_schema.TABLES.INDEX_LENGTH` trước/sau với `information_schema_stats_expiry=0`. Nếu số đó chưa tăng, dùng `tablespace_allocated_growth_delta`: mức tăng `INNODB_TABLESPACES.ALLOCATED_SIZE` của file riêng bảng. Hai nguồn dự phòng là **ước lượng cấp bảng**; file có thể tái dùng chỗ trống nên mức tăng bằng 0 không chứng minh index không tốn dung lượng. Nếu không có nguồn nào cho số dương, report `inconclusive`. Caller có callback đo dung lượng nội bộ phải trả cả byte và source theo giao diện mới; giữ `index_size_estimated=true` trong report. Đo INSERT throughput trước/sau với cùng số dòng (`validation.write_overhead_rows` trong `config/settings.yaml`) trên MySQL lab riêng **khác** DB đang giữ index thử, không chèn hàng thử vào bộ ground truth 5M. Báo cáo ghi thêm `before_rows_per_second`, `after_rows_per_second`, `sample_rows`, `preload_rows`; caller lưu report cần giữ các trường này vì Validation kiểm chúng trước khi cho `passed`. Lab hiện dùng hai bảng tạm `CREATE TABLE LIKE`, preload cùng N dòng CSV rồi đo INSERT cùng N dòng tiếp theo; bảng sau có index đề xuất INVISIBLE. `CREATE TABLE LIKE` không sao chép FOREIGN KEY, và mẫu đầu CSV không đại diện toàn bộ workload 5M: phải ghi rõ giới hạn trong report. Chỉ kết quả có nguồn/điều kiện đo rõ ràng mới đưa vào biểu đồ.

**Trạng thái:** `passed` khi hash và số dòng tương đương, P95 giảm ≥20%, đủ 20/20 lượt mỗi bên, không timeout/lỗi và với index proposal có bằng chứng optimizer chọn index mới. `failed` khi đo hợp lệ nhưng sai kết quả hoặc không đạt ngưỡng; `inconclusive` khi thiếu lượt, thiếu số đo bắt buộc hoặc không chứng minh được index được dùng. Tool 6 chỉ nhận `passed` **và** `evidence_complete=true` trên SQL gốc. Report runtime ghi `db_identity` lấy từ kết nối `readonly_user` trước khi tạo trial; gồm UUID server MySQL, schema hiện tại và host/port cấu hình. Backend duyệt đọc lại danh tính này từ DB hiện tại và từ chối report cũ thiếu trường hoặc khác môi trường. Fail/inconclusive/ngoại lệ → dọn index thử và ghi lý do; pass giữ INVISIBLE để chờ người duyệt, Reject hoặc hết hạn chờ duyệt thì dọn. Rewrite thuần chỉ đo SQL gốc và SQL viết lại, không tạo index và không đi qua Tool 6; phương án rewrite + index phải ghi `candidate_sql_kind="rewritten"` và chỉ hiển thị nếu chưa kiểm chứng index độc lập trên SQL gốc.

---

**Thời hạn chờ duyệt (code 26/11):** Store lưu `review_expires_at` cho report `passed` bằng thời điểm lưu cộng `approval.review_ttl_seconds` (86.400 giây). Precheck chung của Dashboard và Tool 6 từ chối khi hết hạn. Backend dọn trial quá hạn lúc khởi động sau recovery bằng cùng kiểm tra DB, marker và snapshot FK của Reject; lỗi dọn khiến backend dừng. Proposal cũ không có hạn không được duyệt hoặc tự DROP theo thời gian. Hạn này tách khỏi token một lần 10 phút, chỉ bắt đầu lúc cấp token. Chưa có lịch nền dọn đúng thời điểm khi Dashboard chạy liên tục.

**Kiểm chứng Dashboard 26/11:** Trang Đề xuất đã gọi Validation trên lab 3309 sau khi kiểm CSV và marker; cả Reject và Approve đã thử qua Streamlit AppTest với MySQL lab thật trên hai proposal riêng. Nhánh Approve dùng token một lần, Tool 6 xác nhận index VISIBLE và ghi audit; index thử đã được dọn sau kiểm chứng trên lab. Chưa bấm Approve từ trình duyệt, chưa áp dụng trên DB chính hoặc nối tạo proposal từ UI.

**Kiểm chứng trình duyệt 26/11:** `DASHBOARD_STORE_PATH` chọn store cục bộ khi khởi động và giữ token/audit cùng thư mục; mặc định vẫn là `data/outputs/proposals.sqlite3`. Playwright đã bấm Validation → Reject trên lab riêng và kiểm index vắng mặt sau cleanup. Chưa bấm Approve qua trình duyệt.

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

## 6. Ảnh hưởng tới caller và kết luận review

- **Tool 1 / Dashboard / LLM host (Vũ, Tình):** `query_id` từ `performance_schema` là digest, từ `mysql.slow_log` là ID `slowlog:`; không phải `q07`. Output thêm `source` (`performance_schema` hoặc `mysql.slow_log`), và `since` trên digest không tạo metric theo cửa sổ thời gian. Nhánh slow log đã chạy với quyền `SELECT` riêng trên lab; lab khác phải cấp quyền tương ứng. Caller phải truyền ID phân tích đúng ngữ cảnh và không tự ghép digest với ground truth.
- **Tool 3 / LLM host (Vũ):** output thêm `sample`; `cardinality`, `null_ratio`, `top_values`, `min/max` chỉ có ý nghĩa trên mẫu PK có giới hạn. Code đã có test mẫu rỗng, cột nhạy cảm, timeout và giới hạn truy vấn; đã đăng ký MCP trong registry LLM.
- **Tool 4–5 / MCP registry (Hải, Tường, Vũ):** đã đăng ký wrapper giới hạn cho LLM; hàm đầy đủ dành cho Validation Layer. Tool 5 trả `MEASUREMENT_INVALID` khi phép đo nội bộ thiếu lượt/hash, thay vì `ok=true` với P95 một phần.
- **Validation / Tool 6 / Dashboard (Hải, Tình, Vũ):** DDL thử nằm trong hàm nội bộ `apply.py`, không là Tool 6 công khai; token phải hash đúng lệnh `ALTER ... VISIBLE`. Report có `candidate_sql_kind`, `evidence_complete`, nguồn/giới hạn size và write overhead. `index_size_bytes` ở Tool 2 vẫn `null`; Tool 6 lấy số đo từ report. Caller phải giữ `failure_reason="foreign_key_support_risk"` khi lưu report và không cho duyệt trạng thái `inconclusive`. Trước khi cấp token, backend phải kiểm report thuộc đúng môi trường, index thử vẫn tồn tại và khớp proposal; report lab đã dọn index không đủ điều kiện. DB chính đang tồn tại chưa có grant `SELECT` trên `mysql.innodb_index_stats` cho `index_admin`; nếu các nguồn dự phòng không cho số dương, validation trả `inconclusive`.
- **Tương thích/trạng thái code 26/11:** đây là contract thiết kế đã chốt, chưa phản ánh đủ code hiện tại. Dashboard gọi recovery khi khởi động với store runtime `data/outputs/proposals.sqlite3`; `dashboard.backend.validate_proposal()` nhận chính store đã khởi tạo để gọi `validate_saved_index()` và lưu trial/report vào đó. Giao diện chưa gọi đường validation này. `ApprovalTokens` đã ký token HMAC gắn proposal/version/hash đúng DDL, hạn 10 phút và ghi nonce dùng một lần vào SQLite; `dashboard.backend.approval_precheck()` kiểm report `passed`/đủ bằng chứng trên SQL gốc, so `db_identity` với kết nối readonly hiện tại, kiểm trial còn INVISIBLE với marker/định nghĩa đúng và trả DDL chuẩn. `dashboard.backend.issue_approval_token()` gọi precheck rồi ký đúng proposal ID, version và DDL đó, lưu nonce vào SQLite riêng. Đường này mới có test giả, chưa thử trên MySQL thật hoặc nối nút Approve. Report cũ thiếu danh tính bị từ chối và cần validation lại trước khi duyệt. Lõi Tool 6 đã dùng chung precheck, tiêu thụ token, xác minh index VISIBLE và ghi audit với DB giả; registry Dashboard riêng chỉ có Tool 6; backend cục bộ đã gọi registry với OS account của tiến trình Streamlit bằng test giả và mặc định nghe loopback. Đường Reject nội bộ đã chuyển trial sang pending trước khi dọn bằng recovery với test giả; chưa có nút Approve/Reject, chưa thử DDL thật. Recovery đã dọn index thử thật trên validation lab riêng 200.000 dòng; q05 và nhánh q01 opt-in đã đo trên lab 5M, trial đều đã dọn. Đường Dashboard mặc định vẫn chặn q01 vì rủi ro FK; không dùng các report lab đã dọn trial để cấp token. Chưa thử áp dụng index trên DB chính. Trước khi tích hợp end-to-end, nối registry riêng cho Dashboard, thử DDL trên lab riêng, thử Dashboard và kiểm thử 20 payload.

**Kết luận review ngày 25/11/2026:** Theo ủy quyền của người dùng, đã tự đối chiếu thiết kế Tool 1–5, registry LLM, parser, Validation Layer, proposal store, helper index thử và test hiện có; chốt contract v2 làm mốc cho caller. Đây không phải xác nhận review/chữ ký của từng thành viên hay GVHD, cũng không đánh dấu các chặng triển khai chưa đạt là Done. Thay đổi giao diện sau mốc này phải cập nhật contract, caller và test liên quan qua PR vào `dev`.

**Nguồn kỹ thuật MySQL 8.0:** [slow query log](https://dev.mysql.com/doc/refman/8.0/en/slow-query-log.html), [ước lượng `TABLE_ROWS`/`INDEX_LENGTH`](https://dev.mysql.com/doc/refman/8.0/en/information-schema-tables-table.html), [thống kê kích thước từng index](https://dev.mysql.com/doc/refman/8.0/en/innodb-persistent-stats.html), [index hỗ trợ khóa ngoại](https://dev.mysql.com/doc/refman/8.0/en/create-table-foreign-keys.html).
