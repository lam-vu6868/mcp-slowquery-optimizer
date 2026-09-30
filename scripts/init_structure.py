#!/usr/bin/env python3
"""
scripts/init_structure.py
-------------------------
Việc script này làm:
  1. Ghi comment giải thích (chức năng, người phụ trách, lưu ý, việc cần làm)
     vào đầu mọi file đang RỖNG (0 byte) trong repo.
  2. Tạo các thư mục/file còn thiếu theo cấu trúc đã chốt (config/, store/, baseline/...).
  3. Bổ sung các dòng còn thiếu vào .gitignore.

An toàn:
  - KHÔNG bao giờ ghi đè file đã có nội dung (size > 0).
  - Chạy lại nhiều lần vẫn an toàn (idempotent).

Cách dùng (chạy từ thư mục gốc repo):
    python scripts/init_structure.py --dry-run     # xem trước, không ghi gì
    python scripts/init_structure.py               # thực thi
"""
import argparse
import sys
from pathlib import Path

# ----------------------------------------------------------------------------
# Bộ dựng comment
# ----------------------------------------------------------------------------


def _body(path, purpose, owner, review, notes=(), todo=(), refs=()):
    lines = [path, "-" * len(path), ""]
    lines.append("CHỨC NĂNG :")
    for p in ([purpose] if isinstance(purpose, str) else purpose):
        lines.append(f"    {p}")
    lines.append("")
    lines.append(f"PHỤ TRÁCH  : {owner}    |    REVIEW: {review}")
    if notes:
        lines.append("")
        lines.append("LƯU Ý:")
        lines += [f"    - {n}" for n in notes]
    if todo:
        lines.append("")
        lines.append("CẦN LÀM:")
        lines += [f"    [ ] {t}" for t in todo]
    if refs:
        lines.append("")
        lines.append("THAM KHẢO  : " + ", ".join(refs))
    lines.append("")
    lines.append("TRẠNG THÁI : KHUNG RỖNG — chưa cài đặt. Xóa dòng này khi bắt đầu code.")
    return lines


def render(style, path, purpose, owner, review, notes=(), todo=(), refs=()):
    body = _body(path, purpose, owner, review, notes, todo, refs)
    if style == "py":
        return '"""\n' + "\n".join(body) + '\n"""\n'
    if style == "hash":
        return "\n".join(("# " + l).rstrip() for l in body) + "\n"
    if style == "sh":
        return "#!/usr/bin/env bash\n" + "\n".join(("# " + l).rstrip() for l in body) + "\n"
    if style == "sql":
        return "\n".join(("-- " + l).rstrip() for l in body) + "\n"
    if style == "css":
        return "/*\n" + "\n".join(body) + "\n*/\n"
    raise ValueError(style)


def py(*a, **k):
    return render("py", *a, **k)


def hs(*a, **k):
    return render("hash", *a, **k)


def sh(*a, **k):
    return render("sh", *a, **k)


def sql(*a, **k):
    return render("sql", *a, **k)


def css(*a, **k):
    return render("css", *a, **k)


API = "docs/api-contract.md"
ROAD = "project-management/ROADMAP.md"

# ----------------------------------------------------------------------------
# 1) Nội dung điền vào các file RỖNG
# ----------------------------------------------------------------------------
FILL = {}

# ---- gốc repo ---------------------------------------------------------------
FILL["Makefile"] = hs(
    "Makefile",
    "Gom các lệnh hay dùng thành lối tắt (make up, make seed, make test...).",
    "Vũ", "Cả nhóm",
    notes=[
        "Makefile bắt buộc thụt lề bằng TAB, không dùng dấu cách.",
        "Windows không có sẵn make: dùng scripts/*.sh qua Git Bash, hoặc bỏ qua file này.",
    ],
    todo=[
        "up        : docker compose up -d",
        "down      : docker compose down",
        "seed      : python data/seed/seed_all.py",
        "server    : python -m mcp_server.server",
        "dashboard : streamlit run dashboard/app.py",
        "test      : pytest tests/ -v",
        "reset-db  : bash scripts/reset_db.sh",
    ],
    refs=["README.md"],
)

FILL["docker-compose.yml"] = hs(
    "docker-compose.yml",
    "Khởi động MySQL 8.0 cho thực nghiệm (kèm cấu hình slow log).",
    "Hải", "Vũ",
    notes=[
        "File đang RỖNG nên `docker compose up -d` sẽ báo lỗi cho đến khi có nội dung thật.",
        "Bắt buộc MySQL 8.0 (cần INVISIBLE INDEX cho Validation Layer).",
        "Mount db/conf/my.cnf vào /etc/mysql/conf.d/ và db/init.sql vào /docker-entrypoint-initdb.d/.",
        "Mật khẩu lấy từ .env (biến môi trường), KHÔNG ghi cứng trong file này.",
        "Cấu hình cần có: slow_query_log=ON, long_query_time=0.5, log_output=FILE,TABLE.",
        "Dùng volume có tên để dữ liệu 12M dòng không mất khi `docker compose down`.",
    ],
    todo=["Điền service mysql (image mysql:8.0, port, volume, env, healthcheck)."],
    refs=["db/conf/my.cnf", "db/init.sql", ".env.example"],
)

# ---- dashboard --------------------------------------------------------------
FILL["dashboard/app.py"] = py(
    "dashboard/app.py",
    "Điểm vào (entry point) của Dashboard Streamlit: trang chủ + cấu hình chung. "
    "4 tab nằm trong thư mục pages/.",
    "Tình", "Tường",
    notes=[
        "Chạy: streamlit run dashboard/app.py",
        "Phải có try/except khi chưa có dữ liệu (trước đây từng crash).",
        "Dashboard KHÔNG tự chạy DDL: chỉ gọi Tool 6 kèm approval token sau khi người bấm Approve.",
    ],
    todo=["Trang chủ: tổng quan (số query chậm, số đề xuất chờ duyệt, trạng thái hệ thống)."],
    refs=[API, "dashboard/pages/"],
)

FILL["dashboard/assets/style.css"] = css(
    "dashboard/assets/style.css",
    "CSS tùy chỉnh giao diện Dashboard (màu trạng thái Approved/Rejected/Pending, bảng, thẻ số liệu).",
    "Tình", "Tường",
    notes=["Nạp bằng st.markdown('<style>...</style>', unsafe_allow_html=True) trong app.py."],
)

FILL["dashboard/pages/1_slow_queries.py"] = py(
    "dashboard/pages/1_slow_queries.py",
    "TAB 1 — Top slow query: bảng và biểu đồ latency, rows examined, số lần chạy.",
    "Tình", "Tường",
    notes=["Nguồn dữ liệu: Tool 1 get_slow_queries.", "SQL hiển thị là dữ liệu không tin cậy, chỉ hiển thị dạng text."],
    refs=[API],
)

FILL["dashboard/pages/2_proposals.py"] = py(
    "dashboard/pages/2_proposals.py",
    "TAB 2 — Đề xuất của LLM + trạng thái Validation + nút Approve / Reject.",
    "Tình", "Tường",
    notes=[
        "Nút Approve -> server sinh approval token (dùng 1 lần, hết hạn 10 phút) -> backend gọi Tool 6.",
        "Đề xuất loại 'rewrite' chỉ HIỂN THỊ, KHÔNG có nút Apply.",
        "Chỉ cho Approve khi validation_report.status == 'passed'.",
    ],
    refs=[API + " (Tool 6, mục 4)", "security/approval.py"],
)

FILL["dashboard/pages/3_comparison.py"] = py(
    "dashboard/pages/3_comparison.py",
    "TAB 3 — So sánh trước/sau: P95 latency, Query Cost, rows examined, dung lượng index, "
    "write overhead; kèm bảng so sánh LLM vs baseline.",
    "Tình", "Tường",
    notes=["Đọc data/metrics/comparison.csv và validation_report.", "Biểu đồ theo từng query, không chỉ trung bình."],
    refs=[ROAD + " (mục 2.3, 2.4)"],
)

FILL["dashboard/pages/4_security.py"] = py(
    "dashboard/pages/4_security.py",
    "TAB 4 — Bảo mật: kết quả 20 kịch bản injection, audit log Tool 6, số lần token bị từ chối.",
    "Tình", "Tường",
    notes=["Hiển thị 'lớp nào đã chặn' cho từng kịch bản, không chỉ pass/fail."],
    refs=["security/injection_report.md"],
)

# ---- data/metrics + queries + seed -----------------------------------------
FILL["data/metrics/comparison.csv"] = (
    "method,precision,recall,fpr,consistency_rate,rewrite_pass_rate,notes\n"
)  # CSV không dùng comment: dùng dòng tiêu đề, để pandas đọc được

FILL["data/metrics/metrics.py"] = py(
    "data/metrics/metrics.py",
    "Tính chỉ số đánh giá LLM và baseline: Precision, Recall, False Positive Rate, "
    "Consistency Rate, tỉ lệ rewrite đạt.",
    "Tường", "Hải",
    notes=[
        "Công thức và 3 mức 'khớp' (chính xác / tương đương / không khớp) định nghĩa ở ROADMAP mục 2.4. KHÔNG tự đổi.",
        "Precision/Recall chỉ tính cho nhóm lỗi thiên về index (nhóm 1, 2, 4).",
        "Rewrite (nhóm 3, 5): đạt khi kết quả tương đương (hash) VÀ P95 giảm >= 20%.",
        "Không chỉnh ground truth cho vừa kết quả LLM.",
    ],
    todo=[
        "Đọc ground_truth.json + kết quả chạy ở data/outputs/runs/.",
        "Ghi kết quả vào comparison.csv.",
    ],
    refs=[ROAD, "data/queries/ground_truth.json"],
)

FILL["data/queries/queries.py"] = py(
    "data/queries/queries.py",
    "Bộ 30 câu truy vấn chậm dùng để thực nghiệm: 5 nhóm lỗi x 6 câu.",
    "Tường", "Hải",
    notes=[
        "5 nhóm: (1) thiếu index, (2) sai thứ tự cột composite, (3) hàm bọc cột / non-sargable, "
        "(4) SELECT * + filesort, (5) subquery nên chuyển thành JOIN.",
        "Mỗi query có: id (q01..q30), group (1..5), sql, mô tả lỗi.",
        "BẮT BUỘC xác nhận từng query chạy > 0.5s trên dữ liệu thật (MySQL 8 tự tối ưu một số subquery IN).",
        "Nhóm 5: ưu tiên subquery correlated / NOT IN, tránh kiểu đã được semijoin tự động.",
        "Mỗi query nên có ORDER BY xác định để hash kết quả so sánh được.",
    ],
    todo=["Hoàn thành đủ 6 query mỗi nhóm.", "Chạy EXPLAIN gốc cho từng query và lưu lại."],
    refs=["data/queries/ground_truth.json", ROAD + " (mục 2.4, 2.6)"],
)

FILL["data/queries/ground_truth.json"] = (
    "{\n"
    '  "_readme": "Đáp án chuẩn cho 30 query. JSON không có comment nên ghi chú nằm ở đây; '
    'code đọc file phải BỎ QUA các khóa bắt đầu bằng dấu gạch dưới. '
    'Mỗi query có TẬP đáp án chấp nhận được (không chỉ 1 đáp án). '
    'Tường soạn, Hải verify bằng EXPLAIN + benchmark, GVHD ký. KHÔNG sửa cho vừa kết quả LLM.",\n'
    '  "_owner": "Tường",\n'
    '  "_reviewer": "Hải (verify) + GVHD (ký)",\n'
    '  "version": 1,\n'
    '  "signed_by_gvhd": false,\n'
    '  "signed_date": null,\n'
    '  "items": []\n'
    "}\n"
)

FILL["data/seed/seed_all.py"] = py(
    "data/seed/seed_all.py",
    "Script tổng: chạy tuần tự seed toàn bộ dữ liệu thực nghiệm (users -> products -> orders -> order_items -> payments).",
    "Hải", "Tường",
    notes=[
        "12M orders + 20M order_items ước tính 2-6 giờ tùy máy, nên chạy nền/qua đêm.",
        "Hỗ trợ giảm quy mô: biến môi trường SEED_SCALE=5m (đề yêu cầu tối thiểu 5 triệu bản ghi).",
        "Dùng LOAD DATA INFILE (nhanh hơn INSERT nhiều lần); nên tạo index sau khi nạp xong.",
        "Phân bố PHẢI lệch (Zipf cho user/product, status lệch, đỉnh Black Friday), không random đều.",
        "File dữ liệu trung gian ghi vào data/generated/ (đã .gitignore), không commit.",
    ],
    todo=[
        "Thêm seed cho products, order_items, payments (hiện mới có seed_users, seed_orders).",
        "In tiến độ + tổng số dòng khi xong.",
    ],
    refs=["db/schema.sql", ROAD + " (mục 2.6)"],
)

FILL["data/seed/seed_orders.py"] = py(
    "data/seed/seed_orders.py",
    "Sinh 12M dòng bảng orders (created_at, status, user_id, total_amount...).",
    "Hải", "Tường",
    notes=[
        "status lệch (ví dụ ~85% completed), created_at có đỉnh theo mùa/Black Friday.",
        "user_id theo phân bố Zipf (một số user mua rất nhiều).",
        "Phải khớp cột trong db/schema.sql.",
    ],
    refs=["db/schema.sql", "data/seed/seed_all.py"],
)

FILL["data/seed/seed_users.py"] = py(
    "data/seed/seed_users.py",
    "Sinh 1M dòng bảng users.",
    "Hải", "Tường",
    notes=["Nên seed users TRƯỚC orders (orders tham chiếu user_id)."],
    refs=["db/schema.sql", "data/seed/seed_all.py"],
)

# ---- db / docs --------------------------------------------------------------
FILL["db/schema.sql"] = sql(
    "db/schema.sql",
    "Định nghĩa 5 bảng thực nghiệm: users, orders, order_items, products, payments.",
    "Hải", "Tường",
    notes=[
        "Chỉ tạo PRIMARY KEY và khóa ngoại cần thiết.",
        "CỐ Ý KHÔNG tạo các index mà 30 query cần: để LLM đề xuất, ground truth mới có ý nghĩa.",
        "Engine InnoDB, MySQL 8.0.",
        "orders phải có created_at và status (dùng cho case study Black Friday).",
    ],
    todo=["Viết CREATE TABLE cho 5 bảng."],
    refs=["db/init.sql", "data/seed/"],
)

FILL["docs/architecture.md"] = """# Kiến trúc hệ thống

> **Phụ trách:** Vũ · **Review:** cả nhóm · **Trạng thái:** KHUNG RỖNG, cần chốt cùng `api-contract.md`.
> Sơ đồ tổng quát xem `README.md`. File này bổ sung phần chi tiết còn thiếu.

## 1. Các thành phần và ranh giới process

_TODO: vẽ sơ đồ. Cần trả lời rõ:_

- **Ai là MCP host / client** (nơi chạy agent loop gọi Claude)? Chạy ở process nào?
- **Streamlit gọi tool bằng cách nào**: import Python trực tiếp, hay qua MCP client?
- **Ai gọi Validation Layer** và ai gọi Tool 6?

## 2. Luồng dữ liệu chính

_TODO: slow log -> Tool 1 -> LLM -> đề xuất -> Validation -> Dashboard -> Approve -> token -> Tool 6._

## 3. Mô hình tin cậy (trust boundaries)

| Nguồn dữ liệu | Tin cậy? | Xử lý |
| ------------- | :------: | ----- |
| SQL trong slow log | Không | Strip comment, gắn nhãn `untrusted` |
| Comment bảng/cột | Không | Lọc, gắn nhãn `untrusted` |
| Đầu ra của LLM | Không | Kiểm JSON Schema + AST whitelist |
| Approval token | Có (do server sinh) | Dùng 1 lần, hết hạn 10 phút, gắn hash DDL |

## 4. Tài khoản DB và quyền

| Tài khoản | Dùng bởi | Quyền |
| --------- | -------- | ----- |
| `readonly_user` | Tool 1-5, Validation (đọc) | SELECT (+ quyền cần cho EXPLAIN) |
| `index_admin` | Chỉ Tool 6 | CREATE/DROP INDEX, ALTER INDEX VISIBLE/INVISIBLE |

## 5. Validation Layer

_TODO: INVISIBLE INDEX, quy trình đo, rollback (xem ROADMAP mục 2.3)._

## 6. Nơi lưu trữ

_TODO: proposals, validation_reports, audit_log nằm ở đâu (SQLite riêng hoặc schema `optimizer_meta`)._

## 7. Quyết định thiết kế và lý do

_TODO: mỗi quyết định lớn ghi 1 dòng: quyết định gì, vì sao, phương án đã bỏ._
"""

FILL["docs/setup-guide.md"] = """# Hướng dẫn cài đặt từ A đến Z

> **Phụ trách:** Hải (phần DB/Docker), Vũ (phần Python/MCP), Tình (phần Dashboard) · **Trạng thái:** KHUNG RỖNG.
> Mục tiêu: người mới clone repo làm theo file này là chạy được, không cần hỏi.

## 1. Yêu cầu hệ thống

_TODO: Python 3.11+, Docker Desktop, Git, RAM/ổ đĩa tối thiểu cho 12M dòng._

## 2. Cài đặt môi trường

_TODO: venv, `pip install -r requirements.txt`, `pip install -e .`._

## 3. Cấu hình `.env`

_TODO: giải thích từng biến (API key, mật khẩu `readonly_user`, `index_admin`, `APPROVAL_SECRET`)._

## 4. Khởi động MySQL

_TODO: `docker compose up -d`, kiểm tra slow log bằng `scripts/verify_setup.py`._

## 5. Seed dữ liệu

_TODO: `python data/seed/seed_all.py`, thời gian dự kiến, cách giảm còn 5M._

## 6. Chạy MCP Server và Dashboard

_TODO._

## 7. Chạy test

_TODO._

## 8. Lỗi thường gặp

_TODO: mỗi lỗi 1 dòng: triệu chứng, nguyên nhân, cách sửa._
"""

# ---- mcp_server -------------------------------------------------------------
FILL["mcp_server/__init__.py"] = py(
    "mcp_server/__init__.py", "Đánh dấu thư mục là Python package.", "Vũ", "Hải")

FILL["mcp_server/server.py"] = py(
    "mcp_server/server.py",
    "Điểm vào (entry point) của MCP Server: đăng ký 6 tool và phục vụ yêu cầu từ LLM host.",
    "Vũ", "Hải",
    notes=[
        "Chạy: python -m mcp_server.server",
        "Tool 6 (apply_optimization) KHÔNG được cấp cho LLM host: chỉ Tool 1-5.",
        "Tool 6 chỉ gọi được từ backend Dashboard, kèm approval token.",
        "Mọi SQL nhận từ bên ngoài phải qua security/ast_whitelist.py trước khi chạy.",
        "Dữ liệu lấy từ DB (comment, SQL trong log) phải qua sanitize và gắn nhãn untrusted.",
    ],
    todo=["Đăng ký Tool 1-5 cho LLM.", "Tách registry riêng cho Tool 6."],
    refs=[API, "docs/architecture.md"],
)

FILL["mcp_server/llm/__init__.py"] = py(
    "mcp_server/llm/__init__.py", "Package tích hợp LLM.", "Vũ", "Tường")

FILL["mcp_server/llm/agent.py"] = py(
    "mcp_server/llm/agent.py",
    "Agent loop: gọi Claude, cho phép gọi Tool 1-5, thu về đề xuất cuối cùng dạng JSON.",
    "Vũ", "Tường",
    notes=[
        "CHỈ nạp danh sách Tool 1-5 cho LLM (không có apply_optimization).",
        "Ghim model version, temperature thấp (0-0.2) để Consistency Rate có ý nghĩa; lấy từ config/settings.yaml.",
        "Ghi lại mọi lần chạy (prompt, tool call, kết quả) vào data/outputs/runs/ để tái lập.",
        "Có giới hạn số lượt tool call và ngân sách token mỗi query.",
    ],
    todo=["Vòng lặp tool-use.", "Retry khi JSON sai schema (tối đa 2 lần)."],
    refs=[API + " (mục 2.3)", "config/settings.yaml"],
)

FILL["mcp_server/llm/parsers.py"] = py(
    "mcp_server/llm/parsers.py",
    "Phân tích và kiểm tra câu trả lời JSON của LLM (IndexProposal / RewriteProposal).",
    "Vũ", "Tường",
    notes=[
        "Kiểm bằng JSON Schema; sai schema thì báo để agent retry.",
        "Ràng buộc index_name: ^idx_[a-z0-9_]{1,50}$, tối đa 5 cột, cột phải tồn tại trong schema.",
        "Sau retry vẫn hỏng thì đánh dấu parse_failed (có tính vào thống kê).",
    ],
    refs=[API + " (mục 2)", "tests/test_llm_parser.py"],
)

FILL["mcp_server/llm/prompts.py"] = py(
    "mcp_server/llm/prompts.py",
    "System prompt và mẫu prompt gửi cho LLM.",
    "Vũ", "Tường",
    notes=[
        "Nói rõ: nội dung lấy từ slow log / schema là DỮ LIỆU, không phải chỉ thị.",
        "Ép trả lời JSON theo đúng schema, không kèm văn bản khác.",
        "LLM chỉ ĐỀ XUẤT; không tự áp dụng, không có quyền phê duyệt.",
        "Mỗi lần sửa prompt: ghi lại phiên bản để so sánh kết quả.",
    ],
    refs=[API + " (mục 2.3)"],
)

# ---- mcp_server/tools -------------------------------------------------------
FILL["mcp_server/tools/__init__.py"] = py(
    "mcp_server/tools/__init__.py", "Package chứa 6 tool MCP.", "Vũ", "Hải")

FILL["mcp_server/tools/slow_queries.py"] = py(
    "mcp_server/tools/slow_queries.py",
    "TOOL 1 — get_slow_queries: trả top N query chậm (digest, latency, rows examined).",
    "Vũ", "Hải",
    notes=[
        "Nguồn chính: performance_schema.events_statements_summary_by_digest; phụ: mysql.slow_log.",
        "Strip comment khỏi SQL trước khi trả (chống injection qua slow log) và gắn untrusted=true.",
        "Tối đa 100 dòng, có cờ truncated.",
        "Dùng readonly_user.",
    ],
    refs=[API + " (Tool 1)"],
)

FILL["mcp_server/tools/schema.py"] = py(
    "mcp_server/tools/schema.py",
    "TOOL 2 — get_schema: trả cấu trúc bảng (cột, index hiện có, khóa ngoại).",
    "Vũ", "Hải",
    notes=[
        "Comment của bảng/cột là kênh injection: phải lọc và gắn untrusted.",
        "Trả kèm trạng thái visible/invisible và dung lượng của từng index.",
        "Dùng readonly_user.",
    ],
    refs=[API + " (Tool 2)"],
)

FILL["mcp_server/tools/stats.py"] = py(
    "mcp_server/tools/stats.py",
    "TOOL 3 — get_table_stats: số dòng, cardinality, phân bố giá trị từng cột.",
    "Vũ", "Hải",
    notes=[
        "Dùng số ước lượng/sample, KHÔNG COUNT(*) toàn bảng mỗi lần gọi.",
        "top_values chỉ trả cho cột có cardinality thấp (<= 50).",
        "Dùng readonly_user.",
    ],
    refs=[API + " (Tool 3)"],
)

FILL["mcp_server/tools/explain.py"] = py(
    "mcp_server/tools/explain.py",
    "TOOL 4 — explain_query: chạy EXPLAIN FORMAT=JSON (estimate) hoặc EXPLAIN ANALYZE (analyze).",
    "Hải", "Vũ",
    notes=[
        "SQL phải qua AST whitelist trước khi chạy.",
        "EXPLAIN ANALYZE CÓ chạy query thật: luôn đặt MAX_EXECUTION_TIME.",
        "use_invisible_indexes chỉ dành cho Validation Layer, LLM không được đặt true.",
        "Dùng readonly_user.",
    ],
    refs=[API + " (Tool 4)"],
)

FILL["mcp_server/tools/benchmark.py"] = py(
    "mcp_server/tools/benchmark.py",
    "TOOL 5 — benchmark_query: đo P50/P95 latency và hash kết quả.",
    "Tường", "Hải",
    notes=[
        "Warm-up 3 lần (bỏ), đo >= 20 lần, ghi rõ cache_state.",
        "Có timeout mỗi lần chạy.",
        "Query không có ORDER BY xác định: sort kết quả trước khi hash và đặt deterministic_order=false.",
        "SQL phải qua AST whitelist. Dùng readonly_user.",
    ],
    refs=[API + " (Tool 5)", ROAD + " (mục 2.3)"],
)

FILL["mcp_server/tools/apply.py"] = py(
    "mcp_server/tools/apply.py",
    "TOOL 6 — apply_optimization: áp dụng THẬT một đề xuất index đã được người duyệt.",
    "Tình", "Vũ + Hải (BẮT BUỘC cả hai)",
    notes=[
        "KHÔNG được cấp cho LLM. Chỉ backend Dashboard gọi.",
        "Input CHỈ gồm proposal_id + approval_token. TUYỆT ĐỐI không nhận SQL tự do.",
        "Kiểm token: đúng chữ ký, chưa hết hạn, chưa dùng, khớp hash DDL của proposal.",
        "Proposal loại 'rewrite' luôn bị từ chối (FORBIDDEN).",
        "Chỉ cho apply khi validation_report.status == 'passed'.",
        "Dùng tài khoản index_admin (chỉ CREATE/DROP INDEX, ALTER INDEX).",
        "Mọi lần gọi (kể cả bị từ chối) đều ghi audit_log.",
    ],
    refs=[API + " (Tool 6)", "security/approval.py"],
)

# ---- mcp_server/utils -------------------------------------------------------
FILL["mcp_server/utils/__init__.py"] = py(
    "mcp_server/utils/__init__.py", "Package tiện ích dùng chung.", "Vũ", "Hải")

FILL["mcp_server/utils/config.py"] = py(
    "mcp_server/utils/config.py",
    "Đọc cấu hình từ config/settings.yaml và biến môi trường (.env).",
    "Vũ", "Hải",
    notes=["Bí mật (API key, mật khẩu DB, APPROVAL_SECRET) chỉ lấy từ .env, không ghi trong yaml.",
           "Không in giá trị bí mật ra log."],
    refs=["config/settings.yaml", ".env.example"],
)

FILL["mcp_server/utils/db.py"] = py(
    "mcp_server/utils/db.py",
    "Kết nối MySQL. Cung cấp 2 kết nối tách biệt: readonly_user và index_admin.",
    "Hải", "Vũ",
    notes=["Tool 1-5 chỉ dùng kết nối readonly.", "index_admin chỉ Tool 6 được dùng.",
           "Đặt MAX_EXECUTION_TIME cho session phân tích."],
    refs=["db/init.sql"],
)

FILL["mcp_server/utils/logger.py"] = py(
    "mcp_server/utils/logger.py",
    "Cấu hình logging thống nhất cho toàn dự án.",
    "Vũ", "Hải",
    notes=["Không log bí mật (API key, token, mật khẩu).", "Audit log của Tool 6 tách riêng khỏi log thường."],
)

# ---- mcp_server/validation --------------------------------------------------
FILL["mcp_server/validation/__init__.py"] = py(
    "mcp_server/validation/__init__.py", "Package Validation Layer.", "Hải", "Vũ")

FILL["mcp_server/validation/validator.py"] = py(
    "mcp_server/validation/validator.py",
    "Validation Layer chính: kiểm chứng đề xuất TRƯỚC khi cho người duyệt.",
    "Hải", "Vũ",
    notes=[
        "Quy trình: tạo index INVISIBLE -> đo 'trước' (không bật cờ) -> đo 'sau' "
        "(SET SESSION optimizer_switch='use_invisible_indexes=on') -> so sánh -> ghi validation_report.",
        "Pass khi: kết quả tương đương (hash) VÀ P95 giảm >= 20% VÀ không lỗi/timeout.",
        "Fail: DROP INDEX (rollback), đánh dấu rejected_by_validation.",
        "Đo thêm write overhead (INSERT throughput) và dung lượng index.",
        "Ngưỡng lấy từ config/settings.yaml.",
    ],
    refs=[API + " (mục 4)", ROAD + " (mục 2.3)"],
)

FILL["mcp_server/validation/hash_compare.py"] = py(
    "mcp_server/validation/hash_compare.py",
    "Băm tập kết quả query trước/sau để kiểm tra tính tương đương.",
    "Hải", "Vũ",
    notes=["Cần thứ tự xác định: có ORDER BY xác định, hoặc sort mọi cột trước khi hash.",
           "Chú ý NULL, kiểu số thực, và độ chính xác thập phân khi băm."],
)

FILL["mcp_server/validation/rollback.py"] = py(
    "mcp_server/validation/rollback.py",
    "Hoàn tác thay đổi khi validation thất bại hoặc khi cần gỡ index đã áp dụng.",
    "Hải", "Vũ",
    notes=["Rollback = DROP INDEX (hoặc chuyển lại INVISIBLE).", "Phải chạy được cả khi validation bị ngắt giữa chừng."],
)

# ---- scripts ----------------------------------------------------------------
FILL["scripts/reset_db.sh"] = sh(
    "scripts/reset_db.sh",
    "Xóa và tạo lại CSDL thực nghiệm (dùng khi cần làm lại từ đầu).",
    "Hải", "Vũ",
    notes=["NGUY HIỂM: xóa toàn bộ dữ liệu. Nên yêu cầu người dùng gõ 'yes' xác nhận.",
           "Chạy bằng Git Bash trên Windows."],
    todo=["docker compose down -v", "docker compose up -d", "chạy db/schema.sql"],
)

FILL["scripts/setup.sh"] = sh(
    "scripts/setup.sh",
    "Cài đặt môi trường một lần: venv, thư viện, .env, khởi động MySQL.",
    "Vũ", "Hải",
    todo=["Tạo .venv và pip install -r requirements.txt", "pip install -e .",
          "cp .env.example .env nếu chưa có", "docker compose up -d"],
    refs=["docs/setup-guide.md"],
)

# ---- security ---------------------------------------------------------------
FILL["security/ast_whitelist.py"] = py(
    "security/ast_whitelist.py",
    "AST whitelist (sqlglot, dialect mysql): kiểm mọi SQL từ bên ngoài trước khi chạy.",
    "Tình", "Vũ",
    notes=[
        "Fail-closed: parse lỗi thì TỪ CHỐI.",
        "Chỉ 1 statement mỗi lần (chặn nối lệnh bằng dấu ;).",
        "Chỉ cho SELECT và EXPLAIN.",
        "Từ chối comment thực thi /*! ... */ và /*M! ... */.",
        "Từ chối INTO OUTFILE/DUMPFILE, LOAD_FILE, FOR UPDATE, LOCK IN SHARE MODE.",
        "Từ chối hàm nguy hiểm: SLEEP, BENCHMARK, GET_LOCK, RELEASE_LOCK.",
        "Từ chối truy cập schema hệ thống ngoài danh sách cho phép.",
        "DDL duy nhất được phép là CREATE INDEX do SERVER tự sinh ở Tool 6, không đi qua đường của LLM.",
        "Mỗi quy tắc phải có ít nhất 1 test trong tests/test_ast_whitelist.py.",
    ],
    refs=[ROAD + " (mục 2.2)", "tests/test_ast_whitelist.py"],
)

FILL["security/injection_report.md"] = """# Báo cáo kiểm thử Prompt Injection

> **Phụ trách:** Tình · **Review:** Vũ · **Trạng thái:** KHUNG RỖNG.
> Cách báo cáo: "chặn được N/20 kịch bản đã thử ở các lớp X, Y, Z" kèm phần giới hạn. Không tuyên bố an toàn tuyệt đối.

## 1. Phạm vi và phương pháp

_TODO: mô hình đe dọa, 4 kênh tấn công (A slow log, B schema, C cấu trúc SQL, D đầu ra/mã hóa)._

## 2. Kết quả từng kịch bản

| # | Nhóm | Kịch bản | Lớp chặn | Ghi audit log? | LLM bị ảnh hưởng? | Kết quả |
|:-:| :--: | -------- | -------- | :------------: | :---------------: | :-----: |
| 1 | A | _TODO_ | | | | |

## 3. Tổng hợp theo lớp phòng thủ

_TODO: mỗi lớp (readonly account, sanitize, AST, token, index_admin) chặn được bao nhiêu kịch bản._

## 4. Giới hạn và rủi ro còn lại

_TODO: nêu trung thực những gì chưa kiểm chứng được._

## 5. Kết luận

_TODO._
"""

FILL["security/injection_tests/payloads.py"] = py(
    "security/injection_tests/payloads.py",
    "Danh sách 20 kịch bản tấn công Prompt Injection (dữ liệu, không chứa logic test).",
    "Tình", "Vũ",
    notes=[
        "Chia 4 nhóm x 5 kịch bản: A) comment trong slow log, B) comment schema/tên bảng-cột, "
        "C) cấu trúc SQL (multi-statement, INTO OUTFILE, SLEEP...), D) đầu ra tool / mã hóa / giả token.",
        "Mỗi payload có: id, group, mô tả, nội dung, lớp phòng thủ dự kiến sẽ chặn.",
        "Nên có payload dùng /*!50000 DROP TABLE x */ và payload LLM cố truyền approval token giả cho Tool 6.",
    ],
    refs=["security/injection_tests/run_tests.py", ROAD + " (mục 6)"],
)

FILL["security/injection_tests/run_tests.py"] = py(
    "security/injection_tests/run_tests.py",
    "Chạy tự động 20 payload qua hệ thống và ghi kết quả (lớp nào chặn, có audit log không).",
    "Tình", "Vũ",
    notes=["Kết quả ghi ra security/logs/ và đưa vào security/injection_report.md.",
           "Chạy được bằng: python -m security.injection_tests.run_tests"],
    refs=["security/injection_tests/payloads.py"],
)

# ---- tests ------------------------------------------------------------------
FILL["tests/__init__.py"] = py("tests/__init__.py", "Đánh dấu tests là package.", "Cả nhóm", "Người review PR")

FILL["tests/test_ast_whitelist.py"] = py(
    "tests/test_ast_whitelist.py",
    "Test AST whitelist: mỗi quy tắc chặn có ít nhất 1 test.",
    "Tình", "Vũ",
    notes=["Cần cả test 'được phép' (SELECT hợp lệ) lẫn test 'bị chặn'.",
           "Phải có test cho: multi-statement, /*!...*/, INTO OUTFILE, SLEEP, FOR UPDATE, parse lỗi."],
    refs=["security/ast_whitelist.py"],
)

FILL["tests/test_llm_parser.py"] = py(
    "tests/test_llm_parser.py",
    "Test parser JSON của LLM: schema đúng/sai, index_name không hợp lệ, cột không tồn tại.",
    "Vũ", "Tường",
    refs=["mcp_server/llm/parsers.py"],
)

FILL["tests/test_mcp_tools.py"] = py(
    "tests/test_mcp_tools.py",
    "Test 6 tool: input hợp lệ/không hợp lệ, định dạng output theo api-contract.",
    "Cả nhóm (mỗi người test tool của mình)", "Người review PR",
    refs=[API],
)

FILL["tests/test_validation.py"] = py(
    "tests/test_validation.py",
    "Test Validation Layer: hash tương đương, rollback khi fail, ngưỡng P95.",
    "Hải", "Vũ",
    refs=["mcp_server/validation/"],
)

# ----------------------------------------------------------------------------
# 2) File/thư mục còn THIẾU (chỉ tạo khi chưa tồn tại)
# ----------------------------------------------------------------------------
NEW_DIRS = [
    "mcp_server/store",
    "mcp_server/llm/schemas",
    "data/baseline",
    "data/outputs/runs",
    "data/generated",
    "config",
]

NEW_FILES = {}

NEW_FILES["security/__init__.py"] = py(
    "security/__init__.py", "Package bảo mật (cần cho pip install -e .).", "Tình", "Vũ")

NEW_FILES["security/approval.py"] = py(
    "security/approval.py",
    "Sinh và kiểm tra APPROVAL TOKEN cho Tool 6 (thay cho tham số approved=True).",
    "Tình", "Vũ + Hải (BẮT BUỘC cả hai)",
    notes=[
        "token = HMAC(APPROVAL_SECRET, sha256(ddl) + nonce + expires_at).",
        "Hết hạn 10 phút, dùng MỘT LẦN, gắn với hash của đúng DDL đã duyệt.",
        "APPROVAL_SECRET chỉ ở .env phía server; LLM không bao giờ thấy.",
        "So sánh chữ ký bằng hmac.compare_digest (chống timing attack).",
    ],
    todo=["issue_token(proposal_id, ddl) -> str", "verify_token(token, proposal_id, ddl) -> bool",
          "Lưu token đã dùng để chống dùng lại."],
    refs=[API + " (Tool 6)", "tests/test_approval_token.py"],
)

NEW_FILES["mcp_server/store/__init__.py"] = py(
    "mcp_server/store/__init__.py", "Package lưu trữ proposals, validation_reports, audit_log.", "Hải", "Vũ")

NEW_FILES["mcp_server/store/proposals.py"] = py(
    "mcp_server/store/proposals.py",
    "Lưu và truy xuất đề xuất (proposal) cùng validation_report.",
    "Hải", "Vũ",
    notes=["Dùng SQLite riêng hoặc schema optimizer_meta, TÁCH khỏi schema thực nghiệm mà LLM/readonly_user đọc được."],
    refs=[API],
)

NEW_FILES["mcp_server/store/audit_log.py"] = py(
    "mcp_server/store/audit_log.py",
    "Ghi nhật ký mọi lần gọi Tool 6 (kể cả bị từ chối): thời gian, proposal_id, hash DDL, kết quả.",
    "Hải", "Tình",
    notes=["Chỉ ghi thêm (append-only), không sửa/xóa.", "Không ghi token vào log."],
)

NEW_FILES["mcp_server/utils/sanitize.py"] = py(
    "mcp_server/utils/sanitize.py",
    "Làm sạch dữ liệu lấy từ DB trước khi đưa cho LLM (chống injection gián tiếp).",
    "Vũ", "Tình",
    notes=["Cắt mọi comment trong SQL lấy từ slow log.", "Lọc comment bảng/cột; gắn nhãn untrusted.",
           "Chuẩn hóa Unicode để chống homoglyph."],
    refs=[ROAD + " (mục 2.2)", "tests/test_sanitize.py"],
)

NEW_FILES["data/baseline/__init__.py"] = py(
    "data/baseline/__init__.py", "Package baseline so sánh với LLM.", "Tường", "Hải")

NEW_FILES["data/baseline/greedy.py"] = py(
    "data/baseline/greedy.py",
    "Baseline 1 (đề xuất index): thuật toán greedy chọn index theo giảm cost từ EXPLAIN.",
    "Tường", "Hải", refs=[ROAD + " (mục 2.5)"])

NEW_FILES["data/baseline/rule_based.py"] = py(
    "data/baseline/rule_based.py",
    "Baseline 2 (đề xuất index): luật cứng equality -> range -> ORDER BY.",
    "Tường", "Hải", refs=[ROAD + " (mục 2.5)"])

NEW_FILES["data/baseline/pt_query_digest.py"] = py(
    "data/baseline/pt_query_digest.py",
    "Chạy pt-query-digest trên slow log file để so sánh khâu PHÁT HIỆN/xếp hạng query chậm.",
    "Tường", "Hải",
    notes=["pt-query-digest KHÔNG đề xuất index: không đưa vào bảng Precision/Recall.",
           "Cần log_output có FILE để có file slow log."],
    refs=[ROAD + " (mục 2.5)"],
)

NEW_FILES["tests/test_approval_token.py"] = py(
    "tests/test_approval_token.py",
    "Test approval token: sai chữ ký, hết hạn, dùng lại, khác DDL, thiếu token.",
    "Tình", "Vũ", refs=["security/approval.py"],
) + "\nimport pytest\n\npytestmark = pytest.mark.skip(reason=\"TODO: chưa cài đặt security/approval.py\")\n"

NEW_FILES["tests/test_sanitize.py"] = py(
    "tests/test_sanitize.py",
    "Test sanitize: strip comment, lọc comment schema, chuẩn hóa Unicode.",
    "Vũ", "Tình", refs=["mcp_server/utils/sanitize.py"],
) + "\nimport pytest\n\npytestmark = pytest.mark.skip(reason=\"TODO: chưa cài đặt sanitize.py\")\n"

NEW_FILES["config/settings.yaml"] = """# config/settings.yaml
# ---------------------
# Cấu hình không bí mật của dự án. Bí mật (API key, mật khẩu, APPROVAL_SECRET) để trong .env.
# Phụ trách: Vũ | Review: Hải
# Mọi ngưỡng dùng trong thực nghiệm PHẢI lấy từ file này để báo cáo ghi lại được.

llm:
  model: "claude-sonnet-5-5"     # GHIM phiên bản; đổi model = phải chạy lại thực nghiệm
  temperature: 0.0               # thấp để Consistency Rate có ý nghĩa
  max_tokens: 2000
  max_tool_calls_per_query: 8
  json_retry: 2                  # số lần retry khi JSON sai schema
  consistency_runs: 5            # chạy lại cùng 1 prompt bao nhiêu lần

db:
  slow_query_threshold_s: 0.5
  max_execution_time_ms: 30000

validation:
  warmup_runs: 3
  measured_runs: 20
  min_p95_improvement_pct: 20    # dưới ngưỡng này thì đề xuất bị coi là fail
  require_result_equivalence: true
  write_overhead_rows: 100000    # số dòng INSERT khi đo trade-off ghi

approval:
  token_ttl_seconds: 600
  single_use: true

limits:
  max_rows_returned: 100
  max_index_columns: 5
"""

NEW_FILES["pyproject.toml"] = """# pyproject.toml — cho phép `pip install -e .` để import mcp_server/security từ mọi nơi
# (Dashboard, tests, scripts). Thư viện phụ thuộc vẫn ở requirements.txt.
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "mcp-slowquery-optimizer"
version = "0.1.0"
requires-python = ">=3.11"

[tool.setuptools.packages.find]
include = ["mcp_server*", "security*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
"""

NEW_FILES[".github/CODEOWNERS"] = """# .github/CODEOWNERS
# Thay các @..._GITHUB bằng GitHub username thật của từng người rồi bật
# "Require review from Code Owners" trong Settings > Branches.
# Quy tắc chi tiết: project-management/TEAM.md

# Mặc định: Vũ (Lead) review
*                                   @VU_GITHUB

/mcp_server/server.py               @VU_GITHUB
/mcp_server/tools/slow_queries.py   @VU_GITHUB
/mcp_server/tools/schema.py         @VU_GITHUB
/mcp_server/tools/stats.py          @VU_GITHUB
/mcp_server/llm/                    @VU_GITHUB
/mcp_server/utils/sanitize.py       @VU_GITHUB
/config/                            @VU_GITHUB
/docs/                              @VU_GITHUB
/reports/                           @VU_GITHUB

/mcp_server/tools/explain.py        @HAI_GITHUB
/mcp_server/validation/             @HAI_GITHUB
/mcp_server/store/                  @HAI_GITHUB
/mcp_server/utils/db.py             @HAI_GITHUB
/db/                                @HAI_GITHUB
/data/seed/                         @HAI_GITHUB

# Bảo mật: cần Tình VÀ Vũ (và Hải với apply/approval)
/security/                          @TINH_GITHUB @VU_GITHUB
/mcp_server/tools/apply.py          @TINH_GITHUB @VU_GITHUB @HAI_GITHUB
/dashboard/                         @TINH_GITHUB

/mcp_server/tools/benchmark.py      @TUONG_GITHUB
/data/queries/                      @TUONG_GITHUB @HAI_GITHUB
/data/metrics/                      @TUONG_GITHUB
/data/baseline/                     @TUONG_GITHUB
"""

NEW_FILES[".github/pull_request_template.md"] = """## Mô tả
<!-- PR này làm gì? Liên kết đến việc trong ROADMAP nếu có -->

## Loại thay đổi
- [ ] Tính năng mới
- [ ] Sửa lỗi
- [ ] Tài liệu
- [ ] Refactor

## Checklist
- [ ] Đã chạy `pytest tests/ -v` và pass
- [ ] Không commit bí mật (`.env`, API key, mật khẩu, token)
- [ ] Nếu đổi input/output tool: đã cập nhật `docs/api-contract.md` và báo cả nhóm
- [ ] Nếu đụng `security/` hoặc `apply.py`: đã có 2 người review
- [ ] Đã cập nhật `PROGRESS.md` nếu xong một việc
"""

GITIGNORE_LINES = [
    ".env",
    ".venv/",
    "__pycache__/",
    "*.pyc",
    "data/generated/",
    "data/outputs/*.csv",
    "security/logs/*.log",
    "logs/",
    "structure.txt",
]

# ----------------------------------------------------------------------------
# Thực thi
# ----------------------------------------------------------------------------


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="chỉ in ra, không ghi")
    ap.add_argument("--root", default=".", help="thư mục gốc repo (mặc định: thư mục hiện tại)")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    if not (root / "README.md").exists() and not (root / "mcp_server").exists():
        print(f"[!] {root} không giống thư mục gốc repo. Hãy chạy từ thư mục gốc hoặc dùng --root.")
        sys.exit(1)

    dry = args.dry_run
    tag = "[DRY-RUN] " if dry else ""
    counts = {"filled": 0, "created": 0, "skipped_nonempty": 0, "skipped_missing": 0, "dirs": 0}

    print(f"{tag}Thư mục gốc: {root}\n")

    # 1) điền comment vào file rỗng
    print("== 1. Ghi comment vào file rỗng ==")
    for rel, content in FILL.items():
        p = root / rel
        if not p.exists():
            print(f"  [bỏ qua - không tồn tại] {rel}")
            counts["skipped_missing"] += 1
            continue
        if p.stat().st_size > 0:
            print(f"  [giữ nguyên - đã có nội dung] {rel}")
            counts["skipped_nonempty"] += 1
            continue
        print(f"  [ghi comment] {rel}")
        if not dry:
            p.write_text(content, encoding="utf-8", newline="\n")
        counts["filled"] += 1

    # 2) tạo thư mục và file còn thiếu
    print("\n== 2. Tạo thư mục / file còn thiếu ==")
    for d in NEW_DIRS:
        p = root / d
        if not p.exists():
            print(f"  [tạo thư mục] {d}/")
            if not dry:
                p.mkdir(parents=True, exist_ok=True)
                (p / ".gitkeep").touch()
            counts["dirs"] += 1
    for rel, content in NEW_FILES.items():
        p = root / rel
        if p.exists():
            print(f"  [đã có, giữ nguyên] {rel}")
            counts["skipped_nonempty"] += 1
            continue
        print(f"  [tạo file] {rel}")
        if not dry:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8", newline="\n")
        counts["created"] += 1

    # 3) .gitignore
    print("\n== 3. Kiểm tra .gitignore ==")
    gi = root / ".gitignore"
    existing = gi.read_text(encoding="utf-8").splitlines() if gi.exists() else []
    have = {l.strip() for l in existing}
    missing = [l for l in GITIGNORE_LINES if l not in have]
    if missing:
        print("  [thêm vào .gitignore] " + ", ".join(missing))
        if not dry:
            with gi.open("a", encoding="utf-8", newline="\n") as f:
                if existing and existing[-1].strip():
                    f.write("\n")
                f.write("\n# --- thêm bởi init_structure.py ---\n")
                f.write("\n".join(missing) + "\n")
    else:
        print("  .gitignore đã đủ.")

    print("\n== Tổng kết ==")
    print(f"  Đã ghi comment   : {counts['filled']} file")
    print(f"  Đã tạo mới       : {counts['created']} file, {counts['dirs']} thư mục")
    print(f"  Giữ nguyên       : {counts['skipped_nonempty']} file (đã có nội dung)")
    print(f"  Không tồn tại    : {counts['skipped_missing']} file (bỏ qua)")
    if dry:
        print("\nĐây chỉ là chạy thử. Bỏ --dry-run để thực thi.")
    else:
        print("\nXong. Kiểm tra bằng `git status` / `git diff` trước khi commit.")


if __name__ == "__main__":
    main()