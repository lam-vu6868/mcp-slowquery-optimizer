# 🚀 MCP Slow Query Optimizer

> **Dự án môn học:** Tối ưu Slow Query và Chỉ mục CSDL bằng LLM thông qua kiến trúc MCP (Model Context Protocol).

---

## 📖 Dự án này làm gì?

Hệ thống hỗ trợ **tìm và đề xuất cách sửa các câu truy vấn MySQL chậm** bằng LLM, với con người quyết định cuối cùng:

1. **Đọc** slow query log / `performance_schema` → tìm query chạy > 0.5s
2. **Phân tích** bằng LLM (đang thử Groq GPT-OSS 120B) qua các tool MCP: schema, thống kê dữ liệu, EXPLAIN
3. **Đề xuất** dạng có cấu trúc: thêm index, hoặc viết lại query
4. **Kiểm chứng tự động** bằng INVISIBLE INDEX: đo P95 trước/sau, so sánh kết quả có tương đương không, tự rollback nếu kém
5. **Con người duyệt** trên Dashboard → hệ thống sinh **approval token dùng một lần** → mới áp dụng thật

> **Lưu ý:** LLM chỉ **đề xuất**. LLM không có quyền tự áp dụng thay đổi và không thấy tool `apply_optimization`. Đề xuất _viết lại query_ chỉ để hiển thị, không tự áp dụng vào DB.

### 🎬 Case study: Sự cố Black Friday

Đề bài mô tả nghẽn báo cáo doanh thu trên 12 triệu đơn hàng, CPU 98% và ảnh hưởng thanh toán. Đây là bối cảnh đề bài, không phải sự cố hoặc số đo của nhóm.

Lab hiện dùng **5 bảng, tổng 5 triệu dòng**, trong đó `orders` có 1,5 triệu dòng. Nhóm đo truy vấn lọc `status` và `order_date`, đối chiếu thứ tự composite bằng EXPLAIN và benchmark. Kết quả lab không chứng minh đã tái hiện CPU 98% hoặc downtime.

---

## 🏗️ Kiến trúc tổng thể

```mermaid
flowchart TD
    A[MySQL 8.0<br/>5 bảng · tổng 5M dòng] -->|slow log / performance_schema| B[MCP Server<br/>Tool 1-5]
    B <-->|gọi tool| C[LLM host<br/>Groq đang thử nghiệm]
    C -->|đề xuất có cấu trúc| V[Validation Layer]
    V --> V1[INVISIBLE INDEX<br/>đo P95 trước/sau]
    V --> V2[Hash so sánh kết quả]
    V --> V3[AST whitelist]
    V --> V4[Rollback nếu fail]
    V --> D[Dashboard Streamlit]
    D -->|Người bấm Approve| T[Sinh approval token<br/>dùng một lần]
    T --> B6[Tool 6 apply_optimization<br/>tài khoản index_admin]
    B6 -.->|ALTER INDEX VISIBLE| A
```

**Lớp bảo mật:** `readonly_user` cho tool phân tích → sanitize dữ liệu đưa vào LLM → AST whitelist (fail-closed) → approval token → tài khoản `index_admin` chỉ có `CREATE/DROP INDEX` → audit log.

### 6 Tool của MCP Server

|  #  | Tool                 | Chức năng                                                 |      LLM gọi được?       |
| :-: | -------------------- | --------------------------------------------------------- | :----------------------: |
|  1  | `get_slow_queries`   | Top N query chậm (digest, latency, rows examined)         |            ✅            |
|  2  | `get_schema`         | Cấu trúc bảng + index hiện có                             |            ✅            |
|  3  | `get_table_stats`    | Số dòng, cardinality, phân bố giá trị                     |            ✅            |
|  4  | `explain_query`      | `EXPLAIN FORMAT=JSON` / `EXPLAIN ANALYZE`                 |            ✅            |
|  5  | `benchmark_query`    | Đo P50/P95, hash kết quả                                  |            ✅            |
|  6  | `apply_optimization` | ⚠️ Áp dụng thật, **cần approval token** do Dashboard sinh | ❌ Chỉ backend Dashboard |

> Input/output chi tiết: [docs/api-contract.md](docs/api-contract.md)

---

## 👥 Thành viên & Vai trò

| Thành viên | Vai trò                      | Phụ trách chính                                            |
| ---------- | ---------------------------- | ---------------------------------------------------------- |
| **Vũ**     | 🧠 Team Lead + MCP Architect | Điều phối, `server.py`, Tool 1–3, tích hợp LLM, báo cáo    |
| **Hải**    | 🗄️ DB Engineer + Validation  | CSDL 5M, Tool 4, P95, Validation     |
| **Tình**   | 🛡️ Security + Frontend       | AST whitelist, Tool 6 + token, 20 injection, Dashboard     |
| **Tường**  | 📊 Data Analyst + Metrics    | 30 query, ground truth, Tool 5, metrics, baseline, biểu đồ |

> 📖 Chi tiết: [project-management/TEAM.md](project-management/TEAM.md)

---

## 📊 Tiến độ hiện tại

| Giai đoạn                              |   Trạng thái    |
| -------------------------------------- | :-------------: |
| Setup môi trường                       |     ✅ Done     |
| Thiết kế contract v2 + architecture | ✅ Contract v2 đã chốt ngày 25/11; triển khai vẫn theo từng chặng |
| CSDL 5 bảng, tổng 5M dòng              |     ✅ Đã nạp và kiểm tra     |
| 30 query + ground truth                | 🟡 30 đáp án đạt đo kiểm chứng; chờ Hải review/GVHD ký |
| AST whitelist + 47 unit tests          |     ✅ Done     |
| Tool 4 `explain_query`                 |     ✅ Done     |
| Tool 5 `benchmark_query`               |     ✅ Done     |
| Đo P95 bộ 30 query                     | ✅ Baseline 30/30 valid; đáp án 30/30 đạt P95/hash |
| Tool 1–5 MCP                           | 🟡 Đã kiểm chứng 5/5 qua stdio/MySQL; chặng chưa đánh dấu Done |
| Validation Layer                       | 🟡 q01/q05 đạt trên lab 5M; Validation → Reject đã thử qua Streamlit AppTest trên lab riêng; q01 runtime vẫn chặn FK |
| Tool 6 + approval token                | 🟡 Approve qua Streamlit AppTest đã chạy trên lab riêng; chưa thử trình duyệt thật hoặc 20 injection |
| 20 Prompt Injection                    | ⬜ Chưa bắt đầu |
| Dashboard                              | 🟡 Trang Đề xuất đã nối Validation/Approve/Reject; Reject đã thử trên trình duyệt với lab riêng, Approve qua AppTest; chưa nối tạo proposal từ UI |
| Báo cáo + Demo                         | ⬜ Chưa bắt đầu |

**Chú thích:** ✅ Done | 🟡 Đang làm | ⬜ Chưa làm | 🔴 Trễ hạn

Các mốc dưới đây giữ theo thời điểm thực hiện; trạng thái mới nhất xem [PROGRESS.md](project-management/PROGRESS.md) ngày 25/11/2026.

**Bàn giao 26/11/2026:** q01 đã đo đủ trên validation lab 5M qua nhánh FK opt-in, giữ index FK trước baseline và dọn trial sau report; đường Dashboard mặc định vẫn chặn trường hợp FK này. Report Validation mới ghi danh tính DB; đã thử đọc danh tính trên MySQL thật bằng `readonly_user`. Backend cấp token HMAC sau precheck; lõi Tool 6 dùng chung kiểm report/DB/index, tiêu thụ token và ghi audit với DB giả. Registry Dashboard riêng chỉ có Tool 6, còn LLM chỉ thấy Tool 1–5. Dashboard cục bộ mặc định nghe `127.0.0.1`; backend lấy OS account làm người duyệt và gọi registry riêng trong test giả. Reject đã có đường dọn trial với test giả, kiểm DB trước khi DROP và recovery khi dọn lỗi. **314 unit tests pass**; chưa có nút Approve/Reject hoặc thử DDL thật từ Dashboard, chưa áp dụng index trên DB chính.

**Bước tiếp 26/11/2026:** Trial `passed` được chờ duyệt 24 giờ từ lúc lưu report. Backend từ chối duyệt sau hạn và dọn trial quá hạn khi Dashboard khởi động; token một lần vẫn có hạn 10 phút từ lúc cấp. Bản ghi cũ thiếu hạn duyệt cần Validation lại. Đã kiểm bằng DB giả; chưa thử DROP thật cho nhánh quá hạn.

**Trang Đề xuất 26/11/2026:** Có danh sách tối đa 50 proposal mới nhất, hiển thị trạng thái Validation và nút Approve/Reject sau xác nhận. Rewrite chỉ hiển thị; proposal quá hạn không thể Approve. AppTest kiểm giao diện với backend giả; chưa chạy thao tác từ Dashboard trên MySQL thật.

Nút **Chạy Validation** cho proposal mới yêu cầu nhập thư mục CSV và xác nhận. Backend chỉ chấp nhận `DB_HOST=127.0.0.1`, `DB_PORT=3309`, `DB_NAME=shopdb` với marker validation lab hợp lệ; write lab cổng 3308 phải sẵn sàng để đo INSERT. Đã thử Validation → Reject trên lab riêng qua Streamlit AppTest: report `passed`, index thử được dọn.

**Thử Approve trên lab 26/11/2026:** Một proposal mẫu khác cũng `passed`; bấm Approve qua AppTest khiến Tool 6 đổi index thử sang VISIBLE, tiêu thụ token một lần và ghi audit `attempted`/`applied`. Sau khi kiểm, script lab dọn riêng index này và xác nhận số dòng không đổi. SQLite lab vẫn lưu trạng thái `applied` như bằng chứng lần áp dụng, dù index thử đã được dọn ngoài luồng sau thử. Chưa bấm từ trình duyệt hoặc áp dụng trên DB chính.

**Thử trình duyệt trên lab 26/11/2026:** `DASHBOARD_STORE_PATH` cho phép trỏ Dashboard tới store SQLite riêng; token/audit cũng nằm cạnh store đó. Trên `127.0.0.1:8502`, Playwright đã bấm Validation → Reject của một proposal mẫu. Report `passed`, sau Reject trang hiển thị `cleaned` và DB không còn index thử. Đã sửa trang tự làm mới trạng thái sau thao tác; chưa bấm Approve từ trình duyệt. Bằng chứng trong `data/outputs/lab_only_browser_d614ad48.json` (gitignored).

**Kiểm chứng ngày 21/11/2026:** mỗi phép đo chính thức có 3 warm-up + 20 lượt, hash/số dòng khớp và P95 giảm ít nhất 20%. Đã đo đối chứng thứ tự composite cho q07–q12; 125 unit tests pass. Đây là kết quả script lab, chưa phải luồng MCP–LLM–Dashboard hoàn chỉnh. Chưa đo đầy đủ dung lượng index/chi phí ghi hoặc metric LLM.

**Cập nhật 22/11/2026:** [api-contract.md](docs/api-contract.md) v2 đang chờ nhóm review; [architecture.md](docs/architecture.md) giữ vai trò mô tả luồng hệ thống. Tool 1 đọc `performance_schema`, Tool 2 đọc schema, Tool 4–5 có wrapper tham số giới hạn cho LLM nhưng chưa đăng ký MCP. Tool 3 và `server.py` còn là khung; chưa có luồng end-to-end.

**Tiếp theo trong ngày 22/11/2026:** Tool 3 `get_table_stats` đã có code, 9 test đơn vị pass và đã đọc thử MySQL thật bằng `readonly_user` trên `orders`/`addresses`. Lấy mẫu tối đa 1.000 dòng qua cửa sổ PK; `server.py` vẫn là khung nên Tool 1–5 chưa thành MCP tool gọi được.

**Tích hợp MCP trong ngày 22/11/2026:** `server.py` đã đăng ký Tool 1–3 và wrapper giới hạn của Tool 4–5 qua MCP SDK 2.x trên stdio. Danh sách tool LLM thấy chỉ có 5 tool; Tool 6 chưa được đăng ký. Chưa có LLM host, Validation Layer hoặc Dashboard end-to-end.

**Thử Groq ngày 24/11/2026:** adapter Groq đã gọi API với tool mẫu; sau đó q07 chạy qua Groq–MCP–MySQL và có một lượt trả JSON hợp lệ gồm 2 index + 1 rewrite. Hai lượt prompt v1 bị `parse_failed`, một lượt v2 lỗi HTTP 400; chưa đo độ ổn định, hiệu năng đề xuất hoặc toàn bộ 30 query. Model thử nghiệm được ghim trong `config/settings.yaml`.

**Kiểm tra lại ngày 24/11/2026:** bốn lượt q07 mới qua Python host → Groq → MCP → MySQL đều trả JSON hợp lệ, mỗi lượt có 3 proposal; một lượt gọi thêm Tool 3 ngoài Tool 2. HTTP 400 cũ chưa tái hiện và bản ghi cũ không có mã lỗi chi tiết, nên chưa xác định nguyên nhân. Run mới chỉ lưu mã/loại lỗi API đã lọc, không lưu nội dung phản hồi. Toàn bộ 208 unit tests pass; chưa đo metric ổn định hoặc hiệu năng đề xuất.

**Tool 1 ngày 24/11/2026:** nhánh `source="slow_log"` đã có code và test. Sau khi người dùng cấp `SELECT` riêng trên `mysql.slow_log`, gọi trực tiếp và qua MCP stdio đều `ok=true` với 1 bản ghi thật; nguồn mặc định `performance_schema` cũng `ok=true`. Xem [setup-guide](docs/setup-guide.md#4-cấu-hình-slow-log) cho cách cấp quyền trên lab khác; chưa đánh dấu chặng Tool 1–5 Done. Toàn bộ 211 unit tests pass.

**Kiểm chứng Tool 1–5 ngày 24/11/2026:** qua MCP stdio và MySQL thật, registry chỉ có 5 tool, Tool 4–5 chỉ nhận `sql`, cả 5 trả `ok=true` với input đọc giới hạn. Tool 1 đã thử cả hai nguồn; Tool 5 đo 5 lượt trên một query PK ngắn. Đây là kiểm chứng kỹ thuật; contract v2 đã chốt về thiết kế ngày 25/11/2026, còn Tool 6/Validation/Dashboard chưa có luồng hoàn chỉnh.

> 📖 Chi tiết: [project-management/PROGRESS.md](project-management/PROGRESS.md) · Lịch và deadline: [project-management/ROADMAP.md](project-management/ROADMAP.md)

---

## 🚀 Cài đặt & Chạy

### Yêu cầu

- Python 3.11+
- Docker Desktop
- Git
- MySQL 8.0 (qua Docker) — cần 8.0 để dùng INVISIBLE INDEX
- 5 file CSV của dataset: `customers`, `addresses`, `products`, `orders`, `order_items` — xem hướng dẫn bên dưới
- (Tùy chọn) Percona Toolkit để chạy `pt-query-digest`

### Các bước

```bash
# 1. Clone repo
git clone https://github.com/lam-vu6868/mcp-slowquery-optimizer.git
cd mcp-slowquery-optimizer

# 2. Tạo môi trường ảo
python -m venv venv
source venv/bin/activate    # Mac/Linux
venv\Scripts\activate       # Windows

# 3. Cài thư viện
pip install -r requirements.txt

# 4. Cấu hình môi trường
cp .env.example .env
# Sửa .env: GROQ_API_KEY, mật khẩu DB (readonly_user, index_admin), APPROVAL_SECRET
# ⚠️ Không commit file .env

# 5. Khởi động MySQL
docker compose up -d
timeout /t 30

# 6. Chỉ với DB mới/rỗng: nạp 5 CSV theo thứ tự khóa ngoại
#    customers → products → addresses → orders → order_items
#    Chi tiết và số dòng trong docs/setup-guide.md mục 5
#    DB đã có đủ dữ liệu: bỏ qua bước nạp

# 7. Chạy MCP Server Tool 1–5 qua stdio; Dashboard vẫn chưa tích hợp
python -m mcp_server.server

# 8. Chạy Dashboard (terminal khác)
streamlit run dashboard/app.py
```

> 📖 Hướng dẫn cài đặt A-Z chi tiết: [docs/setup-guide.md](docs/setup-guide.md)

---

## 📁 Cấu trúc thư mục

```
mcp-slowquery-optimizer/
├── project-management/  # 📊 Quản lý dự án
│   ├── ROADMAP.md       #    ⭐ Nguồn sự thật: lịch, deadline, quyết định kỹ thuật
│   ├── TEAM.md          #    Ai làm gì, ai review file nào
│   ├── PROGRESS.md      #    Trạng thái hiện tại
│   ├── CONTRIBUTING.md
│   └── GIT-WORKFLOW.md
│
├── mcp_server/          # ⭐ MCP Server + tool + LLM + validation
│   ├── server.py
│   ├── tools/           #    6 tool (Vũ: 1–3 · Hải: 4 · Tường: 5 · Tình: 6)
│   ├── llm/             #    Agent, prompt, parser (Vũ)
│   ├── validation/      #    Validation Layer (Hải)
│   └── utils/
├── db/                  # 🗄️ Schema + MySQL config          (Hải)
├── data/
│   ├── queries/         #    30 query + ground_truth.json     (Tường)
│   ├── metrics/         #    Metrics, comparison.csv, charts  (Tường)
│   └── baseline/        #    greedy, rule-based, pt-query-digest (Tường)
├── security/            # 🛡️ AST whitelist, approval token, 20 injection (Tình)
├── dashboard/           # 🖥️ Streamlit 4 tab                 (Tình)
├── tests/               # 🧪 Unit tests                      (Cả nhóm)
├── docs/                # 📚 api-contract, architecture, setup-guide (Vũ)
├── reports/             # 📝 Báo cáo + slide                 (Vũ)
├── scripts/             # 🔧 Script setup + verify
└── README.md
```

---

## 🧪 Testing

Trên PowerShell, tạo thư mục tạm mới bằng chính tài khoản đang chạy để tránh lỗi quyền giữa user và sandbox:

```powershell
$pytestTemp = Join-Path $env:TEMP ("pytest-user-" + [guid]::NewGuid().ToString("N"))
.\venv\Scripts\python.exe -m pytest tests/ -q -p no:cacheprovider --basetemp="$pytestTemp"
.\venv\Scripts\python.exe scripts/verify_ground_truth.py --check
```

Đã xác nhận 125 tests pass và audit bằng chứng 30/30 pass. `--check` chỉ đối chiếu file, không đo lại DB. Giữ `data/outputs/` (gitignored) vì chứa bằng chứng raw. Chạy cả hai dòng tạo thư mục + pytest mỗi lần kiểm tra.

```bash
# Chạy toàn bộ test
pytest tests/ -v

# Test AST whitelist (47 tests)
pytest tests/test_ast_whitelist.py -v

# Đo lại một nhóm/query P95 (kết quả raw nằm trong data/outputs và không commit)
python scripts/measure_p95_baseline.py --group 1
python scripts/measure_p95_baseline.py --ids q01 --force --output data/outputs/q01_baseline_recheck.json
```

Luồng ground truth: `ground_truth_candidates.py` chứa ứng viên → `scripts/verify_ground_truth.py` thử index INVISIBLE và đo → chỉ phương án đạt mới lưu `ground_truth.json`. Script thử có thay đổi index tạm, chỉ chạy khi được cho phép trên lab; không phải Tool 6. Một số đáp án yêu cầu cả SQL rewrite/hint và index kèm theo. Không chạy hai benchmark đồng thời.

Các ví dụ chạy trực tiếp trong `python -m mcp_server.tools.explain`, `python -m mcp_server.tools.benchmark` và script `verify_setup.py` còn SQL `sales_data` cũ; hiện dùng pytest và các script đo ở trên để kiểm tra bộ 5 bảng.

---

## 📏 Chỉ số đánh giá (tóm tắt)

Định nghĩa đầy đủ và ngưỡng mục tiêu: [ROADMAP.md](project-management/ROADMAP.md) mục 2.4.

- **Precision / Recall (index)** so với ground truth dạng _tập đáp án chấp nhận được_ (khớp chính xác hoặc tương đương về hiệu năng)
- **Consistency Rate:** chạy lại 5 lần cùng prompt, cố định model + temperature thấp
- **False Positive Rate:** index thừa/trùng lặp
- **Metric rewrite:** kết quả tương đương (hash) + P95 giảm ≥ 20%
- **Trade-off ghi/đọc:** dung lượng index + INSERT throughput trước/sau
- **Baseline:** greedy + rule-based (đề xuất index); `pt-query-digest` (phát hiện query chậm)

---

## 🛡️ Bảo mật

Kiểm thử **20 kịch bản** prompt injection chia 4 kênh (slow log, schema comment, cấu trúc SQL, đầu ra/mã hóa). Báo cáo kết quả theo dạng _"chặn được các kịch bản đã thử ở các lớp X, Y, Z"_ kèm phần giới hạn, không tuyên bố an toàn tuyệt đối. Chi tiết: `security/injection_report.md`.

**Đã hoàn thành:** AST whitelist với **47 unit tests pass** — chặn DROP/DELETE/UPDATE, multi-statement, executable comment `/*!...*/`, SLEEP/BENCHMARK, INTO OUTFILE, mysql.\* schema.

---

## 📚 Tài liệu liên quan

| File                                                                     | Mô tả                                                        |
| ------------------------------------------------------------------------ | ------------------------------------------------------------ |
| [project-management/ROADMAP.md](project-management/ROADMAP.md)           | ⭐ Lịch, deadline, quyết định kỹ thuật, định nghĩa metric    |
| [project-management/TEAM.md](project-management/TEAM.md)                 | Phân công, quy tắc review                                    |
| [project-management/PROGRESS.md](project-management/PROGRESS.md)         | Tiến độ hiện tại                                             |
| [project-management/CONTRIBUTING.md](project-management/CONTRIBUTING.md) | Git flow, commit                                             |
| [project-management/GIT-WORKFLOW.md](project-management/GIT-WORKFLOW.md) | Hướng dẫn Git                                                |
| [docs/api-contract.md](docs/api-contract.md)                             | Input/output 6 tool                                          |
| [docs/architecture.md](docs/architecture.md)                             | Kiến trúc chi tiết (MCP host/client, luồng Dashboard → tool) |
| [docs/setup-guide.md](docs/setup-guide.md)                               | Hướng dẫn cài đặt từ A–Z                                     |

---

## 📞 Liên hệ

- **Nhóm trưởng:** Lý Lâm Vũ — 23050102@student.bdu.edu.vn
- **GVHD:** Dương Quang Sinh — dqsinh@bdu.edu.vn
