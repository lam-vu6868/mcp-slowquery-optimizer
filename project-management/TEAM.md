# 👥 PHÂN CÔNG NHÓM

> **Nhóm 4 người:** Vũ – Hải – Tình – Tường
> **GVHD:** Dương Quang Sinh
> **Thời gian:** 12 tuần (23/09/2025 → 15/12/2025)

---

## 🎯 TỔNG QUAN VAI TRÒ

| Thành viên | Vai trò                      | Chuyên môn phụ trách                               |
| ---------- | ---------------------------- | -------------------------------------------------- |
| **Vũ** ⭐  | 🧠 Team Lead + MCP Architect | Điều phối, MCP Server core, tích hợp LLM, báo cáo  |
| **Hải**    | 🗄️ DB Engineer + Backend     | CSDL 12M records, 6 tool backend, Validation Layer |
| **Tình**   | 🛡️ Security + Frontend       | AST whitelist, 20 injection test, Dashboard        |
| **Tường**  | 📊 Data Analyst + Metrics    | Ground truth, đo metrics, biểu đồ                  |

---

## 👤 CHI TIẾT TỪNG NGƯỜI

### 🧠 VŨ — Team Lead + MCP Architect ⭐

**Trách nhiệm chính:**

- Điều phối tiến độ nhóm, chủ trì standup hàng ngày
- Viết MCP Server core (entry point + 3 tool đầu)
- Tích hợp LLM (Claude/GPT/Qwen)
- Viết báo cáo chương 1–3 + tổng hợp cuối
- Liên hệ GVHD, gửi weekly report

**File/thư mục phụ trách:**

```
mcp_server/server.py              ⭐ Chỉ Vũ sửa
mcp_server/tools/slow_queries.py  # Tool 1
mcp_server/tools/schema.py        # Tool 2
mcp_server/tools/stats.py         # Tool 3
mcp_server/llm/agent.py           # Tích hợp LLM
mcp_server/llm/prompts.py         # System prompt
mcp_server/llm/parsers.py         # Parse JSON
docs/                             # Tài liệu
reports/                          # Báo cáo + slide
README.md, TEAM.md, PROGRESS.md, ROADMAP.md
```

**Deliverable chịu trách nhiệm:**

- MCP Server hoàn chỉnh (entry + 3 tool core)
- LLM tích hợp chạy được, trả JSON hợp lệ
- Chương 1-3 báo cáo + tổng hợp cuối

**Deadline chính:**

- 15/10: Xong 3 tool core
- 18/10: LLM tích hợp xong
- 09/12: Báo cáo hoàn chỉnh

**Hỗ trợ từ nhóm:**

- Tình (cựu Lead) hỗ trợ MCP protocol 2 tuần đầu
- Hải hỗ trợ test tích hợp tool

---

### 🗄️ HẢI — DB Engineer + Backend

**Trách nhiệm chính:**

- Xây CSDL 12M records (users, orders, order_items, products, payments)
- Viết 2 tool backend (`explain_query`, `benchmark_query`)
- Xây Validation Layer (đo trước/sau + rollback)
- Chạy baseline pt-query-digest, so sánh với LLM
- Viết README + tài liệu kỹ thuật

**File/thư mục phụ trách:**

```
db/schema.sql                     # Schema 5 bảng
db/init.sql                       # Config + users readonly/admin
db/conf/my.cnf                    # MySQL config
data/seed/                        # Toàn bộ script seed
mcp_server/tools/explain.py       # Tool 4
mcp_server/tools/benchmark.py     # Tool 5
mcp_server/validation/            # Cả thư mục
mcp_server/utils/db.py            # Kết nối DB
```

**Deliverable chịu trách nhiệm:**

- CSDL 12M orders + 20M items, có slow log
- 2 tool backend chạy được (EXPLAIN + benchmark)
- Validation Layer tự rollback khi đề xuất fail
- Bảng so sánh LLM vs pt-query-digest

**Deadline chính:**

- 05/10: Seed xong 12M records
- 15/10: Xong 2 tool backend
- 22/10: Validation Layer chạy được
- 29/10: Baseline pt-query-digest xong

**Hỗ trợ từ nhóm:**

- Vũ hỗ trợ MySQL setup 1 tuần đầu
- Tường hỗ trợ verify phân bố dữ liệu

---

### 🛡️ TÌNH — Security + Frontend

**Trách nhiệm chính:**

- Viết AST whitelist chặn DDL/DML nguy hiểm (dùng `sqlglot`)
- 20 kịch bản prompt injection + test tự động
- Xây Dashboard Streamlit 4 tab
- Quay video demo 5–10 phút
- Viết báo cáo chương "Bảo mật"

**File/thư mục phụ trách:**

```
security/ast_whitelist.py         # ⭐ Chỉ Tình sửa
security/injection_tests/         # 20 payload
security/injection_report.md      # Báo cáo bảo mật
dashboard/app.py                  # Entry point
dashboard/pages/                  # 4 tab
dashboard/assets/style.css
```

**Deliverable chịu trách nhiệm:**

- AST whitelist chặn 100% DDL/DML nguy hiểm
- 20/20 injection test pass
- Dashboard 4 tab chạy được, có nút Approve
- Video demo 5–10 phút

**Deadline chính:**

- 15/10: AST whitelist chạy được
- 25/10: 20/20 injection pass
- 02/11: Dashboard xong
- 05/12: Video demo xong

**Hỗ trợ từ nhóm:**

- Vũ bàn giao code mẫu AST 2 tuần đầu
- Tường hỗ trợ đổ data vào dashboard

---

### 📊 TƯỜNG — Data Analyst + Metrics

**Trách nhiệm chính:**

- Soạn 30 query chậm theo 5 nhóm lỗi
- Viết `ground_truth.json` + xin chữ ký GVHD
- Đo metrics: Precision/Recall/Consistency Rate/FPR
- Vẽ biểu đồ matplotlib (trước/sau, trade-off index)
- Viết báo cáo chương "Thực nghiệm"

**File/thư mục phụ trách:**

```
data/queries/queries.py           # 30 query
data/queries/ground_truth.json    # ⭐ Đáp án chuẩn (GVHD ký)
data/metrics/metrics.py           # Tính chỉ số
data/metrics/comparison.csv       # So sánh
data/metrics/charts/              # Biểu đồ
```

**Deliverable chịu trách nhiệm:**

- 30 query chia 5 nhóm + EXPLAIN gốc mỗi câu
- `ground_truth.json` có chữ ký GVHD ⚠️ bắt buộc
- Bộ metrics đầy đủ + biểu đồ trước/sau
- Chương "Thực nghiệm" báo cáo

**Deadline chính:**

- 08/10: Xong draft 30 query
- 10/10: Ground truth có chữ ký GVHD
- 29/10: Xong metrics + biểu đồ
- 05/12: Chương "Thực nghiệm" xong

**Hỗ trợ từ nhóm:**

- Vũ hỗ trợ EXPLAIN 1 tuần đầu
- Hải verify số liệu benchmark

---

## 📋 BẢNG PHÂN CÔNG THEO TUẦN

|  Tuần  | Vũ (Lead + MCP)                                | Hải (DB + Backend)              | Tình (Security + UI)              | Tường (Metrics)            |
| :----: | ---------------------------------------------- | ------------------------------- | --------------------------------- | -------------------------- |
| **1**  | Setup repo, docker-compose, đọc MCP spec       | Config MySQL, tạo user readonly | Test readonly, Streamlit skeleton | Draft 30 query             |
| **2**  | Khung 6 tool rỗng, bàn giao từ Tình            | **Seed 12M records**            | Draft AST whitelist               | Hoàn thành 30 query        |
| **3**  | Code 3 tool core (slow_queries, schema, stats) | Code explain + benchmark        | Test AST với payload đơn giản     | Đo phân bố dữ liệu         |
| **4**  | Tích hợp Claude API                            | Validation Layer                | **Test 20 injection**             | Ground truth + chữ ký GVHD |
| **5**  | Prompt engineering LLM                         | Rollback mechanism              | Hoàn thiện injection report       | Tính Precision/Recall      |
| **6**  | Fix bug tích hợp                               | Baseline pt-query-digest        | Dashboard skeleton                | Consistency Rate           |
| **7**  | Review code                                    | Trade-off index size            | **Dashboard 4 tab**               | Biểu đồ matplotlib         |
| **8**  | Viết chương 1–3                                | Deploy MCP lên VM               | Test dashboard với data thật      | Viết chương "Thực nghiệm"  |
| **9**  | Viết chương "Kết luận"                         | README + tài liệu               | Quay video demo                   | Rà soát số liệu            |
| **10** | **Tổng hợp báo cáo + slide**                   | Q&A kỹ thuật                    | Q&A bảo mật                       | Q&A số liệu                |
| **11** | Diễn tập thuyết trình                          | Backup source code              | Test demo 3 lần                   | In ấn báo cáo              |
| **12** | **Bảo vệ trước hội đồng**                      | —                               | —                                 | —                          |

---

## 🔒 QUY TẮC FILE — AI SỬA FILE NÀO

| Thư mục/File                       | Người CHÍNH  |  Người REVIEW   | Người KHÁC được sửa? |
| ---------------------------------- | ------------ | :-------------: | :------------------: |
| `mcp_server/server.py`             | **Vũ**       |      Tình       |       ❌ Không       |
| `mcp_server/tools/slow_queries.py` | **Vũ**       |       Hải       |          ❌          |
| `mcp_server/tools/schema.py`       | **Vũ**       |       Hải       |          ❌          |
| `mcp_server/tools/stats.py`        | **Vũ**       |       Hải       |          ❌          |
| `mcp_server/tools/explain.py`      | **Hải**      |       Vũ        |          ❌          |
| `mcp_server/tools/benchmark.py`    | **Hải**      |       Vũ        |          ❌          |
| `mcp_server/tools/apply.py`        | **Vũ**       |   **Tình** ⚠️   |          ❌          |
| `mcp_server/llm/`                  | **Vũ**       |      Tường      |          ❌          |
| `mcp_server/validation/`           | **Hải**      |       Vũ        |          ❌          |
| `db/schema.sql`                    | **Hải**      |      Tường      |          ❌          |
| `data/seed/`                       | **Hải**      |      Tường      |          ❌          |
| `data/queries/queries.py`          | **Tường**    |       Hải       |          ❌          |
| `data/queries/ground_truth.json`   | **Tường**    | **GVHD ký** ⚠️  |          ❌          |
| `data/metrics/`                    | **Tường**    |       Hải       |          ❌          |
| `security/ast_whitelist.py`        | **Tình**     |       Vũ        |          ❌          |
| `security/injection_tests/`        | **Tình**     |       Vũ        |          ❌          |
| `dashboard/`                       | **Tình**     |      Tường      |          ❌          |
| `tests/`                           | Ai cũng viết | Người review PR |          ✅          |
| `docs/`, `reports/`                | **Vũ**       |     Cả nhóm     |     ✅ (qua PR)      |

⚠️ **Nguyên tắc vàng:** Muốn sửa file của người khác → tạo Pull Request, nhờ review. Không sửa trực tiếp trên branch của người đó.

---

## 🔄 LỊCH BÀN GIAO KIẾN THỨC (TUẦN 1-2)

Vì có đổi vai trò, cần **bàn giao kiến thức** giữa các thành viên:

|  #  | Người dạy          | Người học | Nội dung                                                                | Thời lượng |
| :-: | ------------------ | --------- | ----------------------------------------------------------------------- | ---------- |
|  1  | Tình (cựu MCP)     | Vũ        | • MCP protocol<br>• Cách viết tool<br>• Kiến trúc server                | 3h         |
|  2  | Vũ (cựu DB)        | Hải       | • MySQL setup<br>• Seed data với LOAD DATA<br>• Tối ưu insert           | 3h         |
|  3  | Vũ (cựu Security)  | Tình      | • AST whitelist với sqlglot<br>• 20 payload injection<br>• Test tự động | 3h         |
|  4  | Tình (cựu Metrics) | Tường     | • EXPLAIN MySQL<br>• Đo P50/P95<br>• Ground truth format                | 3h         |

**Nguyên tắc bàn giao:**

- Mỗi buổi có **demo code cụ thể**, không lý thuyết suông
- Người học phải **tự viết lại được** sau buổi học
- Có **note lại** vào file `docs/handover.md` (nếu cần)

---

## 📞 LIÊN HỆ NHANH

| Việc                          | Liên hệ                  |
| ----------------------------- | ------------------------ |
| Điều phối, deadline, kế hoạch | **Vũ** (Lead)            |
| MCP protocol, LLM API         | **Vũ** (MCP Architect)   |
| MySQL, Docker, seed data      | **Hải** (DB Engineer)    |
| Validation Layer, baseline    | **Hải** (Backend)        |
| Bảo mật, injection, dashboard | **Tình** (Security)      |
| Metrics, số liệu, biểu đồ     | **Tường** (Data Analyst) |
| Không biết hỏi ai             | **Nhóm chat chung**      |

---

## 🗣️ KÊNH LIÊN LẠC

- **Daily standup:** Discord/Zoom 21h mỗi ngày (15 phút)
- **Chat chính:** Group Zalo/Messenger nhóm
- **Tài liệu chung:** Repo GitHub (xem file này)
- **Weekly report:** Gửi GVHD qua email mỗi Chủ nhật — **Vũ** phụ trách

---

## ✅ CAM KẾT CHUNG

1. **Daily standup** — không vắng mặt trừ trường hợp bất khả kháng
2. **Deadline mềm** — trước deadline cứng 3 ngày
3. **Pair programming** — khi bí > 2h thì nhờ người khác
4. **Code review** — mọi PR phải có 1 người approve
5. **Backup video** — demo phải có video dự phòng
6. **Bàn giao kiến thức** — trong tuần 1-2, ai cũ vai trò cũ dạy người mới

---

## 🎯 ĐIỂM MẠNH TỪNG NGƯỜI (GỢI Ý KHAI THÁC)

| Thành viên | Thế mạnh nên phát huy                                 |
| ---------- | ----------------------------------------------------- |
| **Vũ**     | Tổng hợp, viết tài liệu, kết nối nhóm, điều phối      |
| **Hải**    | Code backend, xử lý dữ liệu lớn, tối ưu hiệu năng     |
| **Tình**   | Bảo mật, kiểm thử, UX/UI, quay video                  |
| **Tường**  | Phân tích số liệu, vẽ biểu đồ, viết báo cáo học thuật |

---

## 📌 3 ĐIỀU NHÓM CẦN NHỚ

1. **Vũ là Lead** — mọi quyết định cuối cùng Vũ chốt
2. **Hải là người làm DB chính** — đừng ai đụng vào `db/` mà không báo
3. **Tình là người giữ bảo mật** — chỉ Tình được sửa `ast_whitelist.py`
