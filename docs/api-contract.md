# 📑 API CONTRACT — 6 TOOL MCP

> **Trạng thái:** DRAFT v1 — cần cả nhóm review và chốt trước **03/10**.
> **Người giữ file:** Vũ. Sửa contract sau khi chốt → phải tạo PR và báo cả nhóm (vì đổi contract là đổi code của 3–4 người).
> Căn cứ thiết kế: [ROADMAP.md](../project-management/ROADMAP.md) mục 2.

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
| `TOKEN_INVALID`     | Token thiếu, sai, hết hạn hoặc đã dùng              |
| `FORBIDDEN`         | Không có quyền gọi tool này                         |
| `INTERNAL`          | Lỗi hệ thống                                        |

**Quy tắc bắt buộc:**

1. Mọi `sql` nhận từ bên ngoài đều qua `ast_whitelist.check()` trước khi chạy. Parse lỗi → `AST_REJECTED` (fail-closed).
2. Tool 1–5 dùng `readonly_user`. Chỉ Tool 6 dùng `index_admin`.
3. Mọi text lấy từ DB (SQL trong log, comment bảng/cột) đi qua `sanitize()` và được bọc trường `"untrusted": true` khi trả cho LLM. LLM coi đó là **dữ liệu**, không phải chỉ thị.
4. Danh sách tool cấp cho LLM host: **chỉ Tool 1–5**. Tool 6 chỉ gọi được từ backend Dashboard.
5. Thời gian: ISO 8601 UTC. Đơn vị latency: `ms`. Dung lượng: `bytes`.
6. Giới hạn trả về: tối đa 100 dòng/danh sách, có `truncated: true` nếu bị cắt.

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
    { "name": "created_at", "order": "ASC" }
  ],
  "index_name": "idx_orders_status_created",
  "rationale": "status là equality, created_at là range",
  "target_query_ids": ["q07"]
}
```

Ràng buộc: `index_name` khớp `^idx_[a-z0-9_]{1,50}$`; tối đa 5 cột; cột phải tồn tại; không trùng index hiện có.

### 2.2. `RewriteProposal` (LLM đề xuất viết lại query)

```json
{
  "type": "rewrite",
  "original_query_id": "q12",
  "rewritten_sql": "SELECT …",
  "rationale": "Bỏ hàm DATE() bọc cột created_at để dùng được index"
}
```

`rewritten_sql` phải qua AST whitelist. Rewrite **chỉ để đề xuất/hiển thị**, không có đường apply vào DB.

### 2.3. Định dạng câu trả lời cuối của LLM

```json
{
  "query_id": "q07",
  "diagnosis": "Full table scan do thiếu index",
  "proposals": [{ "…": "IndexProposal hoặc RewriteProposal" }],
  "confidence": "low | medium | high"
}
```

Parser (`llm/parsers.py`) kiểm tra bằng JSON Schema. Sai schema → retry tối đa 2 lần, sau đó đánh dấu `parse_failed` (tính vào thống kê).

---

## 3. Chi tiết 6 tool

### Tool 1 — `get_slow_queries`

|               |                                                                                        |
| ------------- | -------------------------------------------------------------------------------------- |
| **Người làm** | Vũ                                                                                     |
| **Quyền DB**  | `readonly_user`                                                                        |
| **Nguồn**     | Chính: `performance_schema.events_statements_summary_by_digest`. Phụ: `mysql.slow_log` |

**Input:**

```json
{
  "limit": 10,
  "min_avg_latency_ms": 500,
  "order_by": "total_latency | avg_latency | rows_examined",
  "since": "2025-10-01T00:00:00Z"
}
```

`limit` mặc định 10, tối đa 100. `since` tùy chọn.

**Output `data`:**

```json
{
  "queries": [
    {
      "query_id": "q07",
      "digest": "a1b2c3…",
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

### Tool 2 — `get_schema`

|               |                 |
| ------------- | --------------- |
| **Người làm** | Vũ              |
| **Quyền DB**  | `readonly_user` |

**Input:** `{ "tables": ["orders", "users"] }` — rỗng hoặc bỏ qua = tất cả bảng trong schema thực nghiệm.

**Output `data`:**

```json
{
  "tables": [
    {
      "name": "orders",
      "engine": "InnoDB",
      "columns": [
        {
          "name": "id",
          "type": "bigint",
          "nullable": false,
          "key": "PRI",
          "comment": "…",
          "untrusted": true
        }
      ],
      "indexes": [
        {
          "name": "PRIMARY",
          "columns": ["id"],
          "unique": true,
          "visible": true,
          "size_bytes": 512000000
        }
      ],
      "foreign_keys": []
    }
  ]
}
```

`comment` luôn qua `sanitize()` và gắn `untrusted`.

### Tool 3 — `get_table_stats`

|               |                 |
| ------------- | --------------- |
| **Người làm** | Vũ              |
| **Quyền DB**  | `readonly_user` |

**Input:** `{ "table": "orders", "columns": ["status", "created_at"] }`

**Output `data`:**

```json
{
  "table": "orders",
  "row_count_estimate": 12000000,
  "data_bytes": 2100000000,
  "index_bytes": 800000000,
  "columns": [
    {
      "name": "status",
      "cardinality": 5,
      "null_ratio": 0.0,
      "top_values": [
        { "value": "completed", "ratio": 0.85 },
        { "value": "pending", "ratio": 0.07 }
      ],
      "min": null,
      "max": null
    }
  ]
}
```

`top_values` chỉ trả cho cột có cardinality thấp (≤ 50). Dùng số liệu ước lượng/sample, không `COUNT(*)` toàn bảng khi gọi lặp lại.

### Tool 4 — `explain_query`

|               |                 |
| ------------- | --------------- |
| **Người làm** | Hải             |
| **Quyền DB**  | `readonly_user` |

**Input:**

```json
{
  "sql": "SELECT …",
  "mode": "estimate | analyze",
  "use_invisible_indexes": false
}
```

- `estimate`: `EXPLAIN FORMAT=JSON` (không chạy query).
- `analyze`: `EXPLAIN ANALYZE` (**có chạy** query, luôn bị `MAX_EXECUTION_TIME`). Chỉ cho phép sau khi qua AST.
- `use_invisible_indexes`: dùng cho Validation Layer, LLM không được đặt `true`.

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
  "deterministic_order": true
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

1. Validation Layer chạy proposal → lưu `validation_report` gắn `proposal_id`.
2. Người dùng bấm **Approve** trên Dashboard → server sinh token = `HMAC(secret, sha256(ddl) + nonce + expires_at)`, hết hạn 10 phút, dùng một lần.
3. Backend gọi `apply_optimization(proposal_id, approval_token)`.
4. Server kiểm tra token, kiểm tra lại DDL từ proposal khớp hash, chạy `ALTER INDEX … VISIBLE`, ghi `audit_log`.

**Input:**

```json
{ "proposal_id": "p_20251020_0007", "approval_token": "…" }
```

**Output `data`:**

```json
{
  "applied": true,
  "ddl": "CREATE INDEX idx_orders_status_created ON orders (status, created_at)",
  "index_visible": true,
  "index_size_bytes": 310000000,
  "audit_id": "a_000123",
  "rollback_ddl": "DROP INDEX idx_orders_status_created ON orders"
}
```

**Lỗi:** `TOKEN_INVALID` (thiếu/sai/hết hạn/đã dùng/khác DDL), `VALIDATION_FAILED` (proposal chưa pass validation), `NOT_FOUND`.

**Quy tắc cứng:**

- Proposal loại `rewrite` → luôn `FORBIDDEN` (chỉ hiển thị).
- Không có tham số nào cho phép truyền SQL tự do.
- Mọi lần gọi (kể cả bị từ chối) đều ghi `audit_log`: thời gian, proposal_id, hash DDL, kết quả, IP/nguồn gọi.

---

## 4. Validation Layer (nội bộ, không phải tool)

Hải xây, gọi bởi Dashboard backend sau khi LLM đề xuất:

```json
{
  "proposal_id": "p_20251020_0007",
  "status": "passed | failed",
  "before": {
    "p95_ms": 2890.1,
    "query_cost": 2412345.6,
    "rows_examined": 11987432
  },
  "after": { "p95_ms": 41.2, "query_cost": 1820.4, "rows_examined": 5210 },
  "result_equivalent": true,
  "improvement_ratio": 0.986,
  "write_overhead": {
    "insert_throughput_change_pct": -6.5,
    "index_size_bytes": 310000000
  },
  "failure_reason": null
}
```

**Điều kiện pass:** `result_equivalent = true` **và** P95 giảm ≥ 20% **và** không gây lỗi/timeout. Fail → `DROP INDEX` (rollback), proposal chuyển `rejected_by_validation`.

---

## 5. Checklist chốt contract (cả nhóm tick trước 03/10)

- [ ] Vũ: đã xem lại Tool 1–3 và `IndexProposal`/`RewriteProposal`
- [ ] Hải: đã xem lại Tool 4 và mục Validation Layer
- [ ] Tường: đã xem lại Tool 5 và định dạng hash kết quả
- [ ] Tình: đã xem lại Tool 6, luồng token và mã lỗi
- [ ] Cả nhóm: đồng ý quy tắc chung ở mục 1
- [ ] GVHD được gửi bản tóm tắt (không bắt buộc, nhưng nên)
