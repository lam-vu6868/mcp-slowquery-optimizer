# 👥 PHÂN CÔNG NHÓM

> **Nhóm 4 người:** Vũ – Hải – Tình – Tường
> **GVHD:** Dương Quang Sinh
> **Thời gian:** 12 tuần (23/09 → 15/12)
> ⚠️ **Deadline và tiêu chí Done chỉ ghi ở [ROADMAP.md](ROADMAP.md) (mục 5).** File này chỉ nói về _ai làm gì_, để không bị lệch số liệu giữa các file.

---

## 🎯 TỔNG QUAN VAI TRÒ

| Thành viên | Vai trò                      | Phụ trách chính                                                                  |
| ---------- | ---------------------------- | -------------------------------------------------------------------------------- |
| **Vũ** ⭐  | 🧠 Team Lead + MCP Architect | Điều phối, `server.py`, Tool 1–3, tích hợp LLM, docs, báo cáo chương 1–3         |
| **Hải**    | 🗄️ DB Engineer + Validation  | CSDL 5M, Tool 4 (`explain`), Validation Layer + rollback, verify ground truth    |
| **Tình**   | 🛡️ Security + Frontend       | AST whitelist, **Tool 6 + approval token**, 20 injection, Dashboard, video demo  |
| **Tường**  | 📊 Data Analyst + Metrics    | 30 query, ground truth, **Tool 5 (`benchmark`)**, metrics, **baseline**, biểu đồ |

### Thay đổi so với bản trước

| Việc                                           | Trước                  | Nay                                 | Lý do                                                                   |
| ---------------------------------------------- | ---------------------- | ----------------------------------- | ----------------------------------------------------------------------- |
| `apply.py` (Tool 6)                            | Vũ                     | **Tình**                            | Code bảo mật trọng yếu, hợp với vai Security; giảm tải cho Vũ           |
| `benchmark.py` (Tool 5)                        | Hải                    | **Tường**                           | Tường ít việc dev đầu dự án; Hải đang giữ đường găng (seed, validation) |
| Baseline (pt-query-digest, greedy, rule-based) | Hải                    | **Tường** (Hải hỗ trợ)              | Cân tải, gắn liền với việc đo metrics                                   |
| Verify ground truth                            | Tường tự làm           | **Tường soạn, Hải verify, GVHD ký** | Tường mới học EXPLAIN, cần người kiểm chéo                              |
| Quy tắc sửa file                               | "Chỉ 1 người được sửa" | **CODEOWNERS + bắt buộc review**    | Tránh nghẽn khi người chính bận                                         |

---

## 👤 CHI TIẾT TỪNG NGƯỜI

### 🧠 VŨ — Team Lead + MCP Architect

**Trách nhiệm:**

- Điều phối tiến độ, chủ trì standup, gửi weekly report GVHD
- `server.py` + Tool 1 `get_slow_queries`, Tool 2 `get_schema`, Tool 3 `get_table_stats`
- Tích hợp LLM (`agent.py`, `prompts.py`, `parsers.py`), sanitize dữ liệu đưa vào LLM
- Giữ `api-contract.md`, `architecture.md`
- Báo cáo chương 1–3, Kết luận, tổng hợp cuối

**File phụ trách:**

```
mcp_server/server.py
mcp_server/tools/slow_queries.py   # Tool 1
mcp_server/tools/schema.py         # Tool 2
mcp_server/tools/stats.py          # Tool 3
mcp_server/llm/                    # agent, prompts, parsers
docs/                              # api-contract, architecture, handover
reports/
```

**Đã hoàn thành:**

- ✅ Setup repo + cấu trúc
- ✅ 5 file .md quản lý dự án
- ✅ `docker-compose.yml`
- ✅ `docs/api-contract.md`
- ✅ `docs/architecture.md`
- ✅ `utils/config.py`, `utils/logger.py`
- ✅ `scripts/verify_setup.py`

**Đang làm:**

- 🟡 Tool 1 `slow_queries.py`
- ⬜ Tool 2 `schema.py`
- ⬜ Tool 3 `stats.py`
- ⬜ `server.py`

**Hỗ trợ:** Tình (cựu MCP) hỗ trợ MCP protocol 2 tuần đầu · Vũ pair với Hải import dataset tuần 2.
**Lưu ý rủi ro:** Vũ là điểm nghẽn lớn nhất. Nếu bận, ưu tiên theo thứ tự: chốt contract → review PR chặn người khác → LLM → báo cáo.

---

### 🗄️ HẢI — DB Engineer + Validation

**Trách nhiệm:**

- CSDL 5M dòng từ dataset `sales_data`, đảm bảo `order_date`/`ship_date` không NULL
- Cấu hình `log_output = FILE,TABLE`, slow log 0.5s
- Tool 4 `explain_query`
- **Validation Layer:** INVISIBLE INDEX, đo trước/sau, hash so sánh kết quả, rollback, đo write overhead
- Verify ground truth cùng Tường (EXPLAIN + benchmark)
- Đo trade-off dung lượng index
- Chương "Cài đặt"

**File phụ trách:**

```
db/                                # schema.sql, init.sql, conf/
mcp_server/tools/explain.py        # Tool 4
mcp_server/validation/
mcp_server/utils/db.py
```

**Đã hoàn thành:**

- ✅ Setup MySQL + slow log
- ✅ `readonly_user` + `index_admin`
- ✅ Import dataset 5M dòng
- ✅ Fix NULL `order_date` + `ship_date`
- ✅ `utils/db.py`
- ✅ `docs/setup-guide.md`
- ✅ Tool 4 `explain.py` (7 tests pass)

**Đang làm:**

- ⬜ Đo P95 baseline cho 30 query
- ⬜ Validation Layer (tuần 4)

**Hỗ trợ:** Vũ pair import dataset tuần 2 · Tường hỗ trợ verify phân bố dữ liệu.
**Lưu ý rủi ro:** đang nằm trên đường găng (import → tool → validation).

---

### 🛡️ TÌNH — Security + Frontend

**Trách nhiệm:**

- AST whitelist bằng `sqlglot` (theo bộ quy tắc ROADMAP mục 2.2), **fail-closed**
- **Tool 6 `apply_optimization` + approval token + audit log**
- 20 kịch bản injection (4 nhóm × 5, gồm cả injection gián tiếp), test tự động, báo cáo có phần "giới hạn"
- Dashboard Streamlit 4 tab (nút Approve sinh token)
- Video demo 5–10 phút + video dự phòng
- Chương "Bảo mật"

**File phụ trách:**

```
security/ast_whitelist.py
security/approval.py               # sinh/kiểm tra token
security/injection_tests/
security/injection_report.md
mcp_server/tools/apply.py          # Tool 6
dashboard/
```

**Đã hoàn thành:**

- ✅ `security/ast_whitelist.py` (47 unit tests pass)
- ✅ `tests/test_ast_whitelist.py`
- ✅ Test quyền readonly user
- ✅ Streamlit skeleton

**Đang làm:**

- ⬜ Tool 6 `apply.py` (tuần 5)
- ⬜ `security/approval.py` (tuần 5)
- ⬜ 20 kịch bản injection (tuần 5)
- ⬜ Dashboard 4 tab (tuần 6-7)

**Hỗ trợ:** Vũ bàn giao code mẫu `sqlglot` **kèm test** trong 2 tuần đầu.
**Lưu ý:** `apply.py` và `approval.py` cần **2 người review (Vũ + Hải)** trước khi merge.

---

### 📊 TƯỜNG — Data Analyst + Metrics

**Trách nhiệm:**

- 30 query chậm (6 query/nhóm × 5 nhóm), **xác nhận cả 30 đều > 0.5s** trên máy nhóm
- `ground_truth.json` dạng _tập đáp án chấp nhận được_, xin chữ ký GVHD
- Tool 5 `benchmark_query` (warm-up, ≥ 20 lần, P50/P95, hash kết quả)
- Metrics: Precision / Recall / Consistency Rate / FPR / metric rewrite (theo ROADMAP mục 2.4)
- Baseline: greedy, rule-based (đề xuất index) + `pt-query-digest` (phát hiện query chậm)
- Biểu đồ matplotlib, chương "Thực nghiệm"

**File phụ trách:**

```
data/queries/queries.py
data/queries/ground_truth.json     # GVHD ký + Hải verify
data/metrics/                      # metrics.py, comparison.csv, charts/
data/baseline/
mcp_server/tools/benchmark.py      # Tool 5
```

**Đã hoàn thành:**

- ✅ 30 query (5 nhóm × 6 query)
- ✅ `ground_truth.json` (draft v2)
- ✅ Test 30 query — 30/30 pass > 0.5s
- ✅ Tool 5 `benchmark.py` (7 tests pass)

**Đang làm:**

- ⬜ Đo P95 baseline cho 30 query
- ⬜ Ground truth có chữ ký GVHD (deadline 20/10)
- ⬜ Baseline greedy + rule-based (tuần 6)

**Hỗ trợ:** Hải cùng chạy EXPLAIN cho 10 query đầu · Tình (cựu Metrics) dạy EXPLAIN/P50/P95 trong buổi bàn giao.
**Lưu ý:** không chỉnh ground truth cho vừa kết quả LLM; báo cáo trung thực.

---

## 🔒 QUY TẮC FILE (CODEOWNERS)

| File / thư mục                                                           | Người chính  | Reviewer bắt buộc        |
| ------------------------------------------------------------------------ | ------------ | ------------------------ |
| `mcp_server/server.py`, `tools/slow_queries.py`, `schema.py`, `stats.py` | Vũ           | Hải                      |
| `mcp_server/tools/explain.py`                                            | Hải          | Vũ                       |
| `mcp_server/tools/benchmark.py`                                          | Tường        | Hải                      |
| `mcp_server/tools/apply.py`, `security/approval.py`                      | Tình         | **Vũ + Hải**             |
| `mcp_server/llm/`                                                        | Vũ           | Tường                    |
| `mcp_server/validation/`                                                 | Hải          | Vũ                       |
| `security/ast_whitelist.py`, `security/injection_tests/`                 | Tình         | Vũ                       |
| `db/`, `data/seed/`                                                      | Hải          | Tường                    |
| `data/queries/queries.py`                                                | Tường        | Hải                      |
| `data/queries/ground_truth.json`                                         | Tường        | **Hải verify + GVHD ký** |
| `data/metrics/`, `data/baseline/`                                        | Tường        | Hải                      |
| `dashboard/`                                                             | Tình         | Tường                    |
| `tests/`                                                                 | Ai cũng viết | Người review PR          |
| `docs/`, `reports/`                                                      | Vũ           | Cả nhóm                  |

**Nguyên tắc:**

1. Mọi thay đổi vào `main`/`dev` đi qua Pull Request, ≥ 1 approve (file bảo mật: 2 approve).
2. Người khác **được phép** sửa file của người chính qua PR (ví dụ sửa bug gấp), nhưng phải tag người chính review.
3. Tuyệt đối không commit trực tiếp lên branch của người khác.
4. Không commit API key, mật khẩu DB, `approval secret` (dùng `.env`, đã có trong `.gitignore`).

---

## 🔄 LỊCH BÀN GIAO KIẾN THỨC (TUẦN 1–2) — ✅ HOÀN THÀNH

|  #  | Người dạy          | Người học | Nội dung                                                                             | Trạng thái |
| :-: | ------------------ | --------- | ------------------------------------------------------------------------------------ | :--------: |
|  1  | Tình (cựu MCP)     | Vũ        | MCP protocol, cách viết tool, kiến trúc server                                       |     ✅     |
|  2  | Vũ (cựu DB)        | Hải       | MySQL setup, `LOAD DATA INFILE`, tối ưu insert, INVISIBLE INDEX                      |     ✅     |
|  3  | Vũ (cựu Security)  | Tình      | `sqlglot`, các bypass phổ biến (`/*!…*/`, multi-statement), 20 payload, test tự động |     ✅     |
|  4  | Tình (cựu Metrics) | Tường     | EXPLAIN MySQL, P50/P95, định dạng ground truth                                       |     ✅     |

**Nguyên tắc:** mỗi buổi có demo code cụ thể · người học phải **tự viết lại được** · ghi chú vào `docs/handover.md` · buổi 3 người dạy giao **code mẫu có test** cho người học.

---

## 📋 PHÂN CÔNG THEO TUẦN (tóm tắt)

Chi tiết từng việc và deadline xem [ROADMAP.md](ROADMAP.md) mục 4–5.

| Tuần | Vũ                                      | Hải                        | Tình                                  | Tường                       |
| :--: | --------------------------------------- | -------------------------- | ------------------------------------- | --------------------------- |
|  1   | ✅ Setup repo, docker                   | ✅ Config MySQL, user      | ✅ Test readonly, Streamlit           | ✅ Draft 30 query           |
|  2   | ✅ Chốt contract + architecture, utils  | ✅ Import 5M + fix NULL    | ✅ AST whitelist v1                   | ✅ Hoàn thành 30 query      |
|  3   | 🟡 Tool 1–3, server.py                  | ✅ Tool 4 explain          | ✅ AST + 47 tests                     | ✅ Tool 5 benchmark         |
|  4   | LLM agent + sanitize                    | Validation Layer           | Bổ sung quy tắc AST                   | Ground truth có chữ ký      |
|  5   | Prompt engineering                      | Rollback                   | Tool 6 + token + 20 injection         | Precision/Recall lần 1      |
|  6   | Chương 1–3 đầy đủ                       | Trade-off write overhead   | Dashboard tab 1–2, injection report   | Consistency, FPR, baseline  |
|  7   | Review, code freeze 10/11               | Buffer / hỗ trợ            | Dashboard tab 3–4                     | Biểu đồ matplotlib          |
|  8   | Chương Mở đầu/Kiến trúc/Kết luận        | Chương Cài đặt             | Chương Bảo mật                        | Chương Thực nghiệm          |
| 9–10 | Slide (mở đầu/kiến trúc), chỉnh báo cáo | Slide (DB/validation), Q&A | Video demo, slide (bảo mật/dashboard) | Slide (kết quả), rà số liệu |
|  11  | Nộp báo cáo, diễn tập                   | Backup source/data         | Test máy demo                         | In báo cáo                  |
|  12  | **Bảo vệ 15/12**                        | —                          | —                                     | —                           |

---

## 🗣️ KÊNH LIÊN LẠC & NHỊP LÀM VIỆC

- **Standup:** 21h mỗi ngày (Discord/Zoom), 15 phút
- **Chat chính:** group Zalo/Messenger
- **Tài liệu:** repo GitHub
- **Weekly report GVHD:** email mỗi Chủ nhật, **Vũ** phụ trách

## ✅ CAM KẾT CHUNG

1. Standup đầy đủ, không vắng trừ bất khả kháng
2. Deadline mềm = trước deadline cứng 3 ngày
3. Bí > 2 giờ thì nhờ người khác pair
4. Mọi PR có ≥ 1 approve
5. Backup: source, dump dữ liệu, `ground_truth.json` bản ký, video demo, ở ≥ 2 nơi
6. Nói sớm khi trễ: báo ngay trong standup, đừng đợi cuối tuần

## 🔑 3 ĐIỀU NHÓM CẦN NHỚ

1. **Vũ là Lead** — quyết định cuối cùng Vũ chốt, nhưng thay đổi contract phải báo cả nhóm
2. **Hải giữ DB** — ai cần đụng `db/` phải báo Hải
3. **Tình giữ bảo mật** — sửa `ast_whitelist.py`, `apply.py`, `approval.py` cần review 2 người, không ai tự merge
