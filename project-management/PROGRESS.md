# 📊 TIẾN ĐỘ DỰ ÁN

> **Cập nhật lần cuối:** 27/11/2026 — bàn giao điểm dừng theo yêu cầu người dùng; Vũ quản lý
> **Mốc đối chiếu hiện tại:** 27/11/2026; các bảng tuần bên dưới là lịch sử
> **Tổng tiến độ:** Chưa tính lại từ mốc ~27% ngày 19/10
>
> ⚠️ **File này chỉ ghi TRẠNG THÁI.** Deadline, người phụ trách và tiêu chí Done xem [ROADMAP.md](ROADMAP.md) (mục 4–5). Mục tiêu Precision/Recall/Consistency xem [ROADMAP.md](ROADMAP.md) mục 2.4.

**Chú thích:** ✅ Done | 🟡 Đang làm | ⬜ Chưa làm | 🔴 Trễ hạn | ⏸️ Tạm dừng

---

## Nâng cấp Prompt v3 và thêm adapter Gemini Pro ngày 28/11/2026

- Nâng cấp [mcp_server/llm/prompts.py](../mcp_server/llm/prompts.py) lên `PROMPT_VERSION = "v3"`: bổ sung 4 nguyên tắc DBA tổng quát (đọc `get_schema`/`get_table_stats`/`explain_query` tìm bảng nút thắt, ưu tiên covering index trên bảng lớn gồm cột `SELECT`/`SUM`/`COUNT`, tránh index thừa trên bảng nhỏ, giữ nguyên ngữ nghĩa khi rewrite).
- Thêm adapter Gemini Pro (OpenAI-compatible endpoint) trong [mcp_server/llm/groq.py](../mcp_server/llm/groq.py) (`create_gemini_client()`, `create_llm_client()`), nối vào [dashboard/backend.py](../dashboard/backend.py) theo `LLM_PROVIDER=gemini` và `GEMINI_MODEL` (mặc định `gemini-2.5-pro`), cập nhật `.env.example` và thêm unit test ở [tests/test_gemini_client.py](../tests/test_gemini_client.py).
- **Kiểm tra:** **387 passed**, Ruff và `git diff --check` pass. Chưa gọi Gemini API thật (chờ người dùng tự điền `GEMINI_API_KEY` vào `.env`).

---

## Thiết kế lại Dashboard 6 trang theo "Hành trình của 1 query" ngày 28/11/2026

- Thay 5 trang cũ bằng 6 trang liên kết qua phiên làm việc (`dashboard/journey.py`, `dashboard/query_runner.py`, `dashboard/lab_jobs.py`, `dashboard/lab_session.py`, `dashboard/detection.py`, `dashboard/render.py`, `scripts/lab_demo_runner.py`):
  1. `1_chon_query_cham.py`: chọn từ bộ 30 query hoặc slow log, bấm chạy thật trên DB chính `3307` đo ms/rows/EXPLAIN.
  2. `2_llm_de_xuat.py`: gọi Groq qua MCP Tool 1–5 (chỉ đọc), lưu đề xuất cho query đang làm việc.
  3. `3_chay_thu_de_xuat.py`: chạy thử đề xuất LLM trên lab `3309` ở tiến trình nền với 2 chế độ **Đo nhanh** (1 warm-up + 3 lượt, có nhãn chưa chính thức) và **Đo đầy đủ** (3 warm-up + 20 lượt).
  4. `4_so_sanh.py`: tab chính chỉ hiển thị dữ liệu của query vừa chạy (**Gốc vs LLM vs Greedy**, có nút chạy Greedy thật); tab 2 so sánh **pt-query-digest vs Tool 1** chạy trực tiếp; tab 3 hiển thị bảng 30 query đã đo sẵn (ghi rõ nhãn).
  5. `5_bao_mat.py`: nút **Chạy 20 kịch bản Prompt Injection** chạy trực tiếp từng ca qua `iter_cases()` kèm lớp chặn + Audit log Tool 6.
  6. `6_duyet_va_ap_dung.py`: Validation chính thức & Approve/Reject (ô CSV write lab tự điền `D:\labt2\data` trong mục Nâng cao).
- Bỏ `rule_based` khỏi UI và `data/metrics/comparison.csv` (giữ code/test trong repo), giữ đúng 2 baseline theo yêu cầu GVHD (`pt-query-digest` + `Greedy`).
- **Kiểm tra:** **384 passed**, Ruff sạch 100%, giữ nguyên guard an toàn (DB `3307` chỉ đọc, DDL thử chỉ trên lab `3309`).

---

## Hoàn tất bản thảo Báo cáo đồ án và Dàn ý Slide/Demo ngày 28/11/2026

- Tạo [reports/BAO_CAO_DO_AN.md](../reports/BAO_CAO_DO_AN.md) (5 chương đầy đủ: kiến trúc MCP, bảo mật 6 lớp, thực nghiệm 30 query, kết quả đo thật 12/12 Rewrite = 8/12 đạt 66,7%, bảng `comparison.csv` 3 phương pháp, case study `q07` kèm trade-off INSERT/UPDATE, phân tích lỗi `q13`/`q15`/`q30`, 20/20 kịch bản Prompt Injection và giới hạn trung thực).
- Tạo [reports/SLIDE_VA_KICH_BAN_DEMO.md](../reports/SLIDE_VA_KICH_BAN_DEMO.md) (dàn ý 12 slide bảo vệ, kịch bản demo trực tiếp 5 phút qua 4 tab Dashboard và 4 câu hỏi phản biện trọng tâm).
- Cập nhật trạng thái Giai đoạn 9 (Báo cáo + Demo) trong bảng tổng quan sang 🟡 Đang làm (đã có bản thảo báo cáo, dàn ý slide và kịch bản demo).

---

## Chạy thật baseline greedy 18/18 query trên lab 3309 và cập nhật comparison.csv ngày 28/11/2026

- Thêm `--catalog` vào [data/baseline/greedy.py](../data/baseline/greedy.py) và chạy thật trên validation lab `3309` cho đủ **18/18 query nhóm Index (`1/2/4`)** (`--max-columns 2 --max-indexes 1`): sinh **11 đề xuất index** trên 11/18 query (7 query không tìm được index 1–2 cột giảm `query_cost` ≥ 5%), **0/11 khớp cấu trúc chính xác** (do đáp án ground truth đa số là covering index 3–4 cột gồm cả cột `SELECT`). Bằng chứng lưu ở `data/outputs/baseline_greedy_20261128.json` (gitignored).
- Kiểm độc lập sau chạy: lab `3309` `idx_*` trống, `orders` vẫn `1.500.000` dòng; DB chính `3307` không bị chạm.
- Cập nhật [data/metrics/metrics.py](../data/metrics/metrics.py) và xuất lại [data/metrics/comparison.csv](../data/metrics/comparison.csv) đầy đủ số liệu thật cho cả 3 phương pháp (`llm_groq_mcp`, `rule_based`, `greedy`).

---

## Cài đặt Tab 4 Security (4_security.py) ngày 28/11/2026

- Cài đặt Tab 4 [dashboard/pages/4_security.py](../dashboard/pages/4_security.py): đọc bảng 20 kịch bản Prompt Injection từ [security/injection_report.md](../security/injection_report.md) (hiển thị tổng số ca bị chặn `20/20`, số lớp phòng thủ và bảng đầy đủ cột *Lớp chặn*) cùng bảng audit log Tool 6 và bộ đếm `rejected`/`TOKEN_INVALID` từ SQLite audit log.
- Thêm Streamlit AppTest ở [tests/test_tab4_security.py](../tests/test_tab4_security.py): **379 passed**, Ruff và `git diff --check` pass. Cả 4 tab trong `dashboard/pages/` nay đều đã có code và AppTest; chưa mở kiểm tra Tab 3/Tab 4 trên trình duyệt thật.

---

## Xuất comparison.csv và cài đặt Tab 3 Comparison ngày 28/11/2026

- Mở rộng [data/metrics/metrics.py](../data/metrics/metrics.py): thêm `summarize_rewrite_reports()`, `build_comparison_rows()`, `write_comparison_csv()` và CLI `--build-comparison`; đã tạo [data/metrics/comparison.csv](../data/metrics/comparison.csv) gồm 3 dòng (`llm_groq_mcp`, `rule_based`, `greedy`) ghi trung thực phạm vi hiện tại (Rewrite 8/12 = 66,7% đo thật; Index nhóm 1/2/4 mới khớp chính xác, chưa đo P95 tương đương; `greedy` chưa chạy lab).
- Cài đặt Tab 3 [dashboard/pages/3_comparison.py](../dashboard/pages/3_comparison.py): hiển thị bảng `comparison.csv` (kèm ghi chú `pt-query-digest` không đề xuất index), metric tổng quan Rewrite, bảng chi tiết P95/cost/rows examined và biểu đồ cột P95 trước vs sau theo từng query.
- Thêm unit test + Streamlit AppTest ở [tests/test_metrics_comparison_and_tab3.py](../tests/test_metrics_comparison_and_tab3.py). Chạy `pytest tests/`: **378 passed**, Ruff pass. Chưa mở Tab 3 trên trình duyệt thật.

---

## Cài đặt hoàn chỉnh 3 module baseline (rule-based, greedy, pt-query-digest) ngày 28/11/2026

- **Rule-based:** [data/baseline/rule_based.py](../data/baseline/rule_based.py) (luật cứng `equality -> range -> ORDER BY` dùng `sqlglot`, giới hạn ≤5 cột, bỏ tiền tố PK/UNIQUE/FK mặc định) + 7 unit test ở [tests/test_rule_based_baseline.py](../tests/test_rule_based_baseline.py). Chạy thử trên 18 query nhóm Index (1/2/4): sinh **24 đề xuất index**, **0/24 khớp cấu trúc chính xác** (báo cáo `data/outputs/baseline_rule_based_20261128.json`, gitignored).
- **Greedy:** [data/baseline/greedy.py](../data/baseline/greedy.py) (chọn tập index tham lam theo mức giảm `query_cost` từ EXPLAIN, hỗ trợ dependency injection cho unit test và `make_lab_cost_evaluator()` chỉ mở trên lab `3309` có marker + tự `drop()`). Chưa chạy trên lab MySQL thật.
- **pt-query-digest:** [data/baseline/pt_query_digest.py](../data/baseline/pt_query_digest.py) (gọi `pt-query-digest --output json` nếu có trên hệ thống, fallback parser slow query log chuẩn MySQL bằng Python + hàm `compare_top_n()` so sánh overlap/Jaccard và thời gian phân tích với Tool 1). Chưa chạy trên file slow log thật của container.
- Thêm 5 unit test cho `greedy` và `pt_query_digest` ở [tests/test_greedy_and_pt_digest_baseline.py](../tests/test_greedy_and_pt_digest_baseline.py).
- **Kiểm tra:** **376 passed**, Ruff và `git diff --check` pass; không kết nối DB thật trong lượt này.

---

## Đo 3 query cuối nhóm 5 (q28, q29, q30) — tổng hợp 12/12 nhóm Rewrite ngày 28/11/2026

- **Đo thật tuần tự `q28`, `q29`, `q30` trên lab 3309 (`--timeout-ms 60000`, 3 warm-up + 20 lượt mỗi phía, `approvable=false`):**
  - **`q28` (`passed`):** hash `sha256:d4d9…b1fd` và 1 dòng khớp, 0 timeout; P95 **19.660,73 → 6.797,78 ms** (giảm **65,42%**), P50 19.329,42 → 6.552,13 ms; dùng `idx_orders_customer_status`, bỏ qua `idx_addresses_city`.
  - **`q30` (`failed / result_changed`):** 0 timeout, cùng 1 dòng nhưng **hash kết quả khác nhau** (`sha256:e04f…4ba` ≠ `sha256:e764…09d`, P95 cũng chỉ giảm 10,17%: 43.029,94 → 38.652,05 ms); dùng `idx_addresses_city_customer`, bỏ qua `idx_order_items_price_order`. Minh chứng trực tiếp vai trò kiểm tra tương đương kết quả bằng hash để chặn SQL rewrite sai ngữ nghĩa.
  - **`q29` (đo lại riêng, không sleep — `inconclusive / measurement_error`, `error_type=ValueError`):** bước `before` (SQL gốc) chạy ổn định 20 lượt, 0 timeout, P95 **32.537,87 ms** (2 dòng), nhưng bước `after` (SQL rewrite + 2 index LLM) chạy ~20 phút và có lượt chạm trần `timeout_ms=60000` nên không đạt ngưỡng đo hợp lệ (chậm hơn SQL gốc gần ≥2×).
- **Chốt toàn bộ 12/12 nhóm Rewrite (nhóm 3 & 5):**
  - **8/12 đạt cả (a) hash khớp + (b) P95 giảm ≥20% = 66,7%** (vượt mức tối thiểu ≥60% của ROADMAP): `q14`, `q16`, `q17`, `q18` (nhóm 3: 4/6) và `q25`, `q26`, `q27`, `q28` (nhóm 5: 4/6).
  - **4/12 không đạt:** `q13`, `q15` (`failed / p95_below_threshold`, P95 chậm hơn >2× dù `query_cost` giảm), `q30` (`failed / result_changed`, sai kết quả), và `q29` (`inconclusive / measurement_error` do rewrite vượt trần timeout 60s trong khi SQL gốc 32,5s không timeout).
  - Các report nằm trong `data/outputs/llm_catalog_20261127/q*_rewrite_measure.json` (gitignored).
- **Dọn dẹp:** kiểm độc lập sau cả batch và lượt đo lại `q29`: lab 3309 `idx_*` trống, `orders` vẫn 1.500.000 dòng; DB chính 3307 không bị chạm.
- Bước tiếp: đo tương đương nhóm Index 1/2/4 (16 query có index khác đáp án) để chốt Precision/Recall cuối của LLM, và chạy/hoàn thiện baseline `greedy`, `rule_based`, `pt_query_digest` để tạo `data/metrics/comparison.csv`.

---

## Đo thật 3 query đầu nhóm 5 (q25, q26, q27) trên validation lab ngày 28/11/2026

- **Đo thật tuần tự `q25`, `q26`, `q27` trên lab 3309 (`--timeout-ms 60000`, 3 warm-up + 20 lượt mỗi phía, 0 timeout, `approvable=false`):** cả **3/3 đều `passed`**:
  - **`q25` (`passed`):** hash `sha256:2977…86f3` và 5 dòng khớp; P95 **50.691,77 → 17.184,15 ms** (giảm **66,10%**), P50 47.596,60 → 15.994,52 ms; dùng `idx_orders_customer_total`, bỏ qua `idx_orders_status`. (`query_cost` tăng 144.108 → 2.873.800 nhưng P95 giảm mạnh — cùng với `q13`/`q15` khẳng định cần đo P95 thực tế thay vì chỉ nhìn cost).
  - **`q26` (`passed`):** hash `sha256:0921…2d7f` và 2 dòng khớp; P95 **16.867,46 → 12.516,95 ms** (giảm **25,79%**), P50 16.568,89 → 10.932,32 ms; dùng **cả 2 index LLM** (`idx_order_items_order_product_qty`, `idx_orders_status_id`).
  - **`q27` (`passed`, nhánh FK opt-in):** hash `sha256:7b11…2262` và 5 dòng khớp; P95 **33.871,04 → 4.436,66 ms** (giảm **86,90%**), P50 32.924,86 → 4.351,22 ms; dùng index duy nhất `idx_order_items_orderid_quantity`, cleanup FK không lỗi.
- **Tổng tiến độ nhóm rewrite (nhóm 3 & 5):** đã đo **9/12**, trong đó **7/9 `passed`** (`q14`, `q16`, `q17`, `q18`, `q25`, `q26`, `q27`) và **2/9 `failed`** (`q13`, `q15`). Report ở `data/outputs/llm_catalog_20261127/q25_rewrite_measure.json`, `q26_rewrite_measure.json`, `q27_rewrite_measure.json` (gitignored).
- **Dọn dẹp:** kiểm độc lập sau batch: lab 3309 `idx_*` trống, `orders` vẫn 1.500.000 dòng; DB chính 3307 không bị chạm.
- Bước tiếp: đo 3 query cuối nhóm 5 (`q28`, `q29`, `q30`) trên lab 3309 để chốt Metric Rewrite 12/12.

---

## Hoàn tất đo nhóm 3 (q13–q18) trên validation lab ngày 28/11/2026

- **Đo thật tuần tự `q13`, `q15`, `q17` trên lab 3309 (`--timeout-ms 60000`, 3 warm-up + 20 lượt mỗi phía, 0 timeout, `approvable=false`):**
  - **`q17` (`passed`):** hash `sha256:b2e0…4583` và 5 dòng khớp; P95 **54.113,26 → 2.686,19 ms** (giảm **95,04%**), P50 49.214,14 → 2.485,99 ms, query_cost 2.484.011,18 → 308.933,72; dùng đúng index duy nhất `idx_order_items_product_price_qty`.
  - **`q13` (`failed / p95_below_threshold`):** hash `sha256:9bd6…4e50` và 5 dòng khớp, query_cost giảm 3.353.713 → 1.646.418 nhưng **P95 tăng 20.432,37 → 54.047,83 ms** (chậm hơn 2,65×); chỉ dùng `idx_orders_order_date_id`, bỏ qua `idx_products_category_id`.
  - **`q15` (`failed / p95_below_threshold`):** hash `sha256:8ec4…41ce` và 5 dòng khớp, query_cost giảm 4.252.977 → 1.598.562 nhưng **P95 tăng 25.800,39 → 54.102,93 ms** (chậm hơn 2,10×); chỉ dùng `idx_orders_date_id`, bỏ qua `idx_products_category_id`.
- **Tổng hợp nhóm 3 (non-sargable, 6/6 đã đo):** **4/6 `passed`** (`q14`, `q16`, `q17`, `q18` — đạt 66,7%), **2/6 `failed`** (`q13`, `q15` — minh chứng rõ việc chỉ tin EXPLAIN `query_cost` mà không đo P95 thật sẽ lọt đề xuất gây thoái hóa hiệu năng). Report ở `data/outputs/llm_catalog_20261127/q13_rewrite_measure.json`, `q15_rewrite_measure.json`, `q17_rewrite_measure.json` (gitignored).
- **Dọn dẹp:** kiểm độc lập sau batch: lab 3309 `idx_*` trống, `orders` vẫn 1.500.000 dòng; DB chính 3307 không bị chạm.
- Bước tiếp: đo 6 query nhóm 5 (`q25`–`q30`) trên lab 3309 để hoàn tất 12/12 nhóm rewrite.

---

## Thêm `--timeout-ms`, đo lại q16 đạt và dry-run đủ 12/12 rewrite ngày 28/11/2026

- **Sửa `scripts/measure_llm_rewrite.py`:** thêm tham số `--timeout-ms` (1000–60000 ms, khớp giới hạn `benchmark_query`) và ghi `error_type` khi gặp lỗi đo (không ghi SQL); thêm unit test tương ứng trong `tests/test_measure_llm_rewrite.py`. Chạy lại toàn bộ test: **364 passed**, Ruff và `git diff --check` pass.
- **Đo lại q16 trên lab 3309 (`--timeout-ms 60000`):** xác nhận nguyên nhân lượt trước là SQL gốc chạm timeout mặc định 30s. Report mới đạt `status=passed`, `approvable=false` (3 warm-up + 20 lượt mỗi phía, 0 timeout): hash `sha256:2030…c6ed` và 2 dòng kết quả khớp; P95 **49.259,97 → 16.159,94 ms** (giảm **67,19%**), P50 46.756,45 → 15.313,47 ms, số dòng xét 5.490.006 → 2.070.004, query_cost 4.999.766,46 → 1.843.620,80. EXPLAIN của rewrite dùng **cả 2 index LLM** (`idx_order_items_order_product_qty_price` và `idx_orders_status`). Report ở `data/outputs/llm_catalog_20261127/q16_rewrite_measure.json` (gitignored).
- **Dọn dẹp sau ngắt server giữa chừng:** lượt chạy đầu sau restart bị ngắt khi đang benchmark và để sót 2 index thử INVISIBLE; đã dọn sạch bằng `TrialIndex.recover_drop()` đối chiếu khớp snapshot FK trước khi chạy lại. Sau lượt đo đạt, kiểm độc lập lab 3309: `idx_*` trống, `orders` vẫn 1.500.000 dòng; DB chính 3307 không bị chạm.
- **Dry-run 9 query rewrite còn lại (chỉ đọc, không DDL):** `q13`, `q15`, `q17`, `q25`, `q26`, `q27`, `q28`, `q29`, `q30` đều **9/9 `dry_run` pass** và đã lưu snapshot FK/index (kể cả `q27` nhờ nhánh FK opt-in). Tổng nhóm rewrite hiện có **12/12 dry-run pass**, **3/12 đã đo thật và 3/3 đạt** (`q14`, `q16`, `q18`).
- Bước tiếp: đo thật tuần tự 9 query rewrite còn lại (`q13`, `q15`, `q17`, `q25`–`q30`) trên lab 3309 với `--timeout-ms 60000`, sau đó đo tương đương nhóm index 1/2/4 để tổng hợp Metrics và `comparison.csv`.

---

## Đo thật rewrite q16, q18 và chốt Ground Truth ngày 28/11/2026

- **Chốt Ground Truth:** người dùng (đóng vai cả 4 thành viên) xác nhận `data/queries/ground_truth.json` (30/30 đã đạt `verify_ground_truth --check`) đã hoàn tất review và được GVHD đồng ý. Chuyển trạng thái Giai đoạn 2 sang ✅ Done.
- **Đo thật q18 trên lab 3309:** `--dry-run` lưu snapshot 2 index (`idx_orders_status`, `idx_order_items_prod_order_qty_price`); đo thật (3 warm-up + 20 lượt mỗi phía) đạt `status=passed`, `approvable=false`. Hash `sha256:2d25…74e` và 2 dòng kết quả khớp, 0 timeout; P95 **26.278,30 → 10.544,77 ms** (giảm **59,87%**), P50 25.130,18 → 9.413,56 ms, số dòng xét 8.390.006 → 1.530.006, query_cost 5.266.195,56 → 2.514.270,10. EXPLAIN dùng `idx_order_items_prod_order_qty_price`, **không dùng** `idx_orders_status`. Report ở `data/outputs/llm_catalog_20261127/q18_rewrite_measure.json` (gitignored).
- **Đo thật q16 trên lab 3309:** `--dry-run` pass (`idx_order_items_order_product_qty_price`, `idx_orders_status`), nhưng đo thật dừng ở bước benchmark SQL gốc sau ~30 giây với `status=inconclusive`, `failure_reason=measurement_error` (khả năng cao chạm `timeout_ms=30000` mặc định ở lượt warm-up, giống mức ~25–27 s của q14/q18). Report ở `data/outputs/llm_catalog_20261127/q16_rewrite_measure.json` (gitignored).
- **Dọn dẹp:** kiểm độc lập sau cả q16 và q18: lab 3309 không còn index `idx*`, `orders` vẫn 1.500.000 dòng; không đụng DB chính 3307.
- Bước tiếp: bổ sung `--timeout-ms` (tối đa 60000 ms theo giới hạn `benchmark_query`) và ghi mã lỗi ngắn trong `scripts/measure_llm_rewrite.py` để đo lại q16 và chạy nốt nhóm rewrite (q13, q15, q17, q25–q30).

---

## Đo thật rewrite + tập index LLM cho q14 trên validation lab ngày 28/11/2026

- **Test:** sửa 5 test fail trong `tests/test_measure_llm_rewrite.py` (mock `Trial` thiếu tham số `fk_snapshot`, không sửa code chính). Chạy lại: **363 passed**, Ruff và `git diff --check` pass.
- **Dry-run (không DDL):** bật `mcp_validation_lab_db` (3309); marker `mcp-validation-lab-v1` hợp lệ, snapshot FK/index của 2 index q14 lưu ở `data/outputs/llm_catalog_20261127/q14.snapshot.json` (gitignored). Lab 3309 từng từ chối kết nối khi container chưa chạy; không dùng DB chính 3307.
- **Đo thật (được người dùng cho phép):** `python -m scripts.measure_llm_rewrite q14 ...` tạo cả 2 index LLM INVISIBLE (`addresses(customer_id, city)` và `orders(order_date, customer_id, total_amount)`), đo SQL gốc (tắt index invisible) và SQL rewrite (bật), mỗi phía 3 warm-up + 20 lượt. Report `status=passed`, `approvable=false`: hash `sha256:0ebf…9ae0` và 5 dòng kết quả bằng nhau, 0 timeout; P95 **27.121,31 → 449,14 ms** (giảm **98,34%**), P50 25.694,8 → 355,9 ms, số dòng xét 2.564.717 → 258.839, query_cost 1.260.931,91 → 118.212,10. EXPLAIN của rewrite dùng index `orders`, **không dùng** index phụ `addresses` (index phụ này không đóng góp cho q14).
- **Lưu ý khi diễn giải:** baseline lượt này (P95 ~27 s) chậm hơn nhiều so với bằng chứng ground truth cũ (4.605,85 ms), nên không so thẳng số tuyệt đối giữa hai lượt đo; tỉ lệ giảm vẫn vượt ngưỡng ≥20%. Nguyên nhân chênh lệch chưa tìm (có thể do trạng thái cache/tài nguyên máy sau khi container khởi động lại). Query không có ORDER BY nên hash tính sau khi sắp xếp.
- **Dọn dẹp:** kiểm độc lập sau đo: lab 3309 không còn index `idx*`, `orders` vẫn 1.500.000 dòng. Report ở `data/outputs/llm_catalog_20261127/q14_rewrite_measure.json` (gitignored). Chưa Approve/cấp token; chưa đo q16/q18/q27 hay index tương đương nhóm 1/2/4; ground truth vẫn chờ Hải review/GVHD ký; Metrics chưa Done.
- Bước tiếp: đo tiếp q16 và q18 (q27 cần nhánh FK riêng), rồi các index khác đáp án của nhóm 1/2/4.

---

## Thêm CLI và snapshot bền vững vào measure_llm_rewrite.py ngày 27/11/2026

- Hoàn thiện [scripts/measure_llm_rewrite.py](../scripts/measure_llm_rewrite.py): thêm `save_preflight_snapshot()` / `load_preflight_snapshot()` ghi/đọc JSON trạng thái FK+index trước DDL (ghi đè nếu chạy lại, tránh dùng snapshot cũ sai); thêm `_build_parser()` và `main()` cho CLI với 3 tham số (`query_id`, `store_path`, `--dry-run`, `--output`, `--snapshot`).
- `--dry-run`: chỉ chạy `load_saved_rewrite()` → `preflight_validation_lab()` → `save_preflight_snapshot()`, không tạo DDL; in JSON `status=dry_run` và đường snapshot. `--snapshot` cho phép chỉ định đường lưu (mặc định `<store>.snapshot.json`).
- Thêm 5 test mới trong [tests/test_measure_llm_rewrite.py](../tests/test_measure_llm_rewrite.py): roundtrip lưu/đọc snapshot, ghi đè snapshot, thiếu file raise, `main()` với `--dry-run` và giả lập catalog + preflight, kiểm parser argument. **363 passed**, Ruff pass (2 lỗi import order đã tự fix). Không tạo/xóa index hoặc kết nối DB thật trong lượt này.
- Bước tiếp: bật `mcp_validation_lab_db` (3309), kiểm marker thật, chạy `--dry-run` trên lab rồi mới chạy đo thật với q14.

---

## Kiểm chứng đọc MySQL 3307 và bộ test ngày 27/11/2026

- Chạy lại toàn bộ `pytest tests/`: **358 passed** (bao gồm `tests/test_measure_llm_rewrite.py` dùng trial/tool giả). `scripts.verify_ground_truth --check` đạt **30/30 PASS**; `security.injection_tests.run_tests` đạt **20/20 blocked** ở ranh giới code.
- Kiểm Docker và DB chính `3307` (`mcp_mysql_db` healthy): gọi trực tiếp Tool 1–4 (`get_slow_queries`, `get_schema(tables=['orders'])`, `get_table_stats('orders')`, `explain_query` estimate trên `q14`) bằng `readonly_user` đều `ok=true` (`orders` ước lượng `1.494.969` dòng, `q14` có `query_cost=1668841.22`). `load_saved_rewrite()` đọc `data/outputs/llm_catalog_20261127/q14.sqlite3` xác nhận khớp SQL catalog (1 rewrite + 2 index trên `addresses` và `orders`).
- Hai container lab `mcp_validation_lab_db` (`3309`) và `mcp_write_lab_db` (`3308`) vẫn `Exited`, nên chưa kiểm marker thật, chưa chạy DDL hay đo P95 trên lab trong lượt này; không sửa dữ liệu/index trên DB chính và giữ nguyên trạng thái các chặng.

---

## Phép đo offline rewrite + tập index LLM ngày 27/11/2026

- Thêm `scripts/measure_llm_rewrite.py` làm lõi đo thử bằng dependency injection, chưa có CLI hoặc kết nối lab. Hàm kiểm AST SQL gốc/rewrite trước khi tạo trial; tạo đủ tập index INVISIBLE do caller cấp, đo SQL gốc khi `use_invisible_indexes=off` và SQL rewrite khi `on`, đối chiếu hash/số dòng, số lượt, timeout và ngưỡng P95 từ config. Report ghi index nào xuất hiện trong EXPLAIN của rewrite và luôn `approvable=false`; dù phép đo rewrite đạt cũng không cấp token Tool 6.
- Hàm dọn mọi trial đã bắt đầu theo thứ tự ngược, kể cả khi tạo index hoặc phép đo lỗi; lỗi dọn trả `inconclusive/cleanup_failed`. Test dùng trial/tool giả, chưa tạo/drop index trên MySQL. Bước sau mới nối store proposal với lab 3309, kiểm marker, snapshot FK/index và đường cleanup trước DDL thật; q14 là ca đầu tiên để đo thêm index phụ chưa được bằng chứng cũ bao phủ.
- Bước tiếp: thêm loader chỉ nhận đúng một rewrite cùng toàn bộ index từ SQLite đã tồn tại và đối chiếu SQL catalog; đọc q14 thật xác nhận 1 rewrite + 2 index, không in SQL. Preflight mới từ chối host/port/schema/user sai hoặc marker lab sai, rồi đọc snapshot FK/index và kiểm schema cho từng trial bằng quyền đọc. Test giả đạt; chưa lưu snapshot bền vững hoặc nối preflight với DDL. Cổng lab 3309 và write lab 3308 đều đóng trong lượt này; Docker daemon không truy cập được nên chưa thể kiểm marker thật hay đo MySQL.

---

## Điểm dừng để tiếp tục ở chat sau (27/11/2026)

- **Chặng hiện tại:** thu proposal LLM đã đủ **30/30 query catalog, 85 proposal** qua Groq/MCP Tool 1–5 với DB chính quyền đọc. Manifest đối chiếu SQL catalog và run thành công ở `data/outputs/llm_catalog_20261127/manifest_30_query_summary.json` (gitignored). Chẩn đoán index chỉ là **9/37 khớp cấu trúc chính xác** trong 18 query nhóm 1/2/4; chưa có Precision/Recall, Consistency, FPR hay metric rewrite chính thức. Ground truth 30/30 đạt phép đo lab cũ nhưng vẫn chờ Hải review/GVHD ký.
- **q14:** SQL rewrite của LLM cùng cây cú pháp với SQL đã đo trong ground truth; một index `orders(order_date, customer_id, total_amount)` cũng khớp. Bằng chứng lab cũ có 20 lượt mỗi phía, hash/số dòng khớp, P95 4605,85 → 668,61 ms. Đây chỉ là cặp rewrite + **một** index; index LLM phụ trên `addresses` chưa đo. Chi tiết không chứa SQL ở `data/outputs/llm_catalog_20261127/q14_existing_evidence_match.json`. `scripts.verify_ground_truth --check` đạt 30/30 evidence PASS; không chạy lại DDL.
- **Giới hạn trước bước lab:** `validate_index()` hiện chỉ đo index trên SQL gốc, chưa đo rewrite + tập index LLM. Không dùng `verify_ground_truth.py` nhánh đo cho proposal LLM vì script nhận ứng viên cố định và có thể sửa ground truth. Docker kiểm gần nhất: DB chính 3307 chạy; validation lab 3309 `Exited (137)`, write lab 3308 cũng dừng. Chưa khởi động lab, chưa kiểm marker/snapshot mới, chưa tạo/drop index hoặc áp dụng trên DB chính.
- **Working tree lúc bàn giao:** `project-management/PROGRESS.md` đang sửa; `scripts/collect_llm_proposals.py` và `tests/test_collect_llm_proposals.py` là file mới chưa commit; sau cập nhật này còn có `README.md` và `AGENTS.md` đang sửa. Giữ các file và bằng chứng ignored, không ghi đè/xóa. Lần chạy test code gần nhất: **350 passed**, Ruff pass cho hai file Python mới; sau các cập nhật Markdown chỉ cần `git diff --check` (xem kết quả lượt bàn giao). Chưa commit/push/merge.
- **Bước nên làm khi quay lại:** đọc mục này, `README.md`, `ROADMAP.md`, contract và kiểm `git status`; sau đó thiết kế phép đo offline riêng cho rewrite cùng index LLM, test bằng giả lập trước. Chỉ mở lab 3309/3308 và chạy DDL thử khi đã kiểm marker, snapshot, cleanup và biết chính xác proposal nào sẽ đo. Không đánh dấu Metrics Done trước khi có kiểm chứng tương đương/rewrite và review ground truth.

---

## Đối chiếu q14 với bằng chứng lab hiện có ngày 27/11/2026

- Kiểm code trước khi chạy lab: `validate_saved_index()`/`validate_index()` hiện chỉ đo một index trên **SQL gốc** (`candidate_sql_kind="original"`), không đo cặp rewrite + index. `scripts/verify_ground_truth.py` có đo rewrite nhưng chỉ nhận ứng viên ground truth cố định và có thể cập nhật `ground_truth.json`; không đưa proposal LLM vào script đó. Validation lab 3309 đang `Exited (137)`, DB chính 3307 vẫn chạy; chưa khởi động lab hoặc tạo/drop index.
- Nhánh `python -m scripts.verify_ground_truth --check` chỉ đọc đạt **30/30 evidence PASS**. Riêng q14, SQL rewrite LLM và SQL sau tối ưu trong report có cùng cây cú pháp MySQL khi parse bằng SQLGlot; index LLM `orders(order_date, customer_id, total_amount)` khớp index đã đo. Report q14 có 20 lượt trước/sau, 0 timeout, hash và số dòng bằng nhau, P95 **4605,85 → 668,61 ms** (giảm **85,48%**). Bằng chứng đối chiếu không chứa SQL ở `data/outputs/llm_catalog_20261127/q14_existing_evidence_match.json` (gitignored).
- Đây là bằng chứng lab **đã có** cho cặp rewrite + một index khớp, không phải Validation mới của toàn bộ output LLM: q14 còn một index LLM phụ trên `addresses` chưa đo. q16/q18/q27 có bộ index bắt buộc khớp nhưng rewrite LLM khác cây cú pháp SQL đã đo, nên không kế thừa P95/hash của ground truth. Ground truth vẫn chờ Hải review/GVHD ký; chưa chấm rewrite metric cuối hoặc cấp token/Approve.
- Lượt này chỉ kiểm read-only và sửa PROGRESS, không sửa code. Bước tiếp theo là xác định phép đo riêng cho rewrite cùng tập index LLM trên validation lab, bắt đầu với phần q14 chưa được bao phủ; giữ guard lab/marker/snapshot và cleanup trước khi thử DDL.

---

## Phân loại proposal trước Validation lab ngày 27/11/2026

- Đọc offline manifest 30 query, proposal đã lưu và ground truth; không kết nối MySQL trong bước phân loại. Với nhóm index 1/2/4: 18 query có 37 đề xuất index, 9 index khớp cấu trúc chính xác; 16 query còn ít nhất một index khác đáp án cần xét hiệu năng tương đương, không tự gán là sai.
- Với nhóm rewrite 3/5: **12/12** query có đề xuất rewrite và ground truth của cả 12 đều đòi index đi kèm. Chỉ **q14, q16, q18, q27** có đủ bộ index bắt buộc khớp cấu trúc chính xác trong các proposal LLM; điều này chưa chứng minh SQL rewrite tương đương hoặc nhanh hơn. Báo cáo phân loại không chứa SQL ở `data/outputs/llm_catalog_20261127/validation_triage_20261127.json` (gitignored).
- Chọn q14 làm ca lab đầu tiên khi môi trường sẵn sàng: LLM có index `orders(order_date, customer_id, total_amount)` trùng một index bắt buộc của ground truth và có một rewrite; một index LLM phụ trên `addresses` phải xét riêng. q27 có đúng một index + rewrite nhưng index bắt đầu bằng cột FK `order_items.order_id`, nên cần nhánh FK precheck riêng trên lab. Kiểm Docker read-only cho thấy DB chính 3307 đang chạy còn validation lab 3309 chưa chạy; chưa kiểm marker/snapshot, chưa tạo/drop index, chưa chấm Metrics chính thức. Ground truth vẫn chờ Hải review/GVHD ký.

---

## Hoàn tất thu proposal LLM cho 30 query ngày 27/11/2026

- Chạy các batch tuần tự còn thiếu qua `scripts/collect_llm_proposals.py` trên DB chính bằng quyền đọc: q04/q10/q15/q21/q27; q05/q11/q16/q22/q28; q06/q12/q17/q24/q29; rồi q18/q30 và q23 riêng. q22 và q18 gặp Groq `400/tool_use_failed` ở lượt đầu, mỗi query thành công sau đúng một lần thử lại. q23 từng có kết quả baseline lớn nhưng lượt tạo proposal riêng thành công, không chạy Validation hoặc DDL.
- Manifest `data/outputs/llm_catalog_20261127/manifest_30_query_summary.json` (gitignored) đối chiếu từng store với catalog: **30/30 query có proposal**, tổng **85 proposal**, không có SQL gốc lệch catalog, và mỗi ID có ít nhất một run metadata `success`. Các store thử q01/q07/q13/q25 từ trước vẫn giữ riêng; manifest chỉ tham chiếu đường dẫn, số lượng, loại proposal và trạng thái, không chứa SQL.
- Chẩn đoán khớp index chính xác cho 18 query nhóm 1/2/4: **37 đề xuất index, 9 index khớp chính xác**, thuộc 7 query; 16 query còn ít nhất một phương án cần xét tương đương. Chi tiết không chứa SQL ở `data/outputs/llm_catalog_20261127/exact_index_diagnostic.json` (gitignored). Đây **không phải Precision/Recall cuối**: chưa đo P95 tương đương cho index khác đáp án, chưa kiểm hash/P95 cho rewrite, chưa tính Consistency/FPR và ground truth còn chờ Hải review/GVHD ký. Chưa tạo `comparison.csv`.
- Lượt này chỉ tạo dữ liệu thử ignored và sửa PROGRESS; không sửa code, không chạy Validation, Approve hoặc DDL. Bước tiếp theo là phân loại các phương án cần kiểm chứng trên lab riêng và hoàn tất review ground truth trước khi chấm Metrics chính thức.

---

## Thu tiếp năm query catalog ngày 27/11/2026

- Chạy `scripts/collect_llm_proposals.py` cho q03, q09, q14, q20, q26 trên DB chính bằng quyền đọc. q03/q09/q14/q26 thành công lần đầu, lưu lần lượt **1/2/3/3 proposal**. q20 gặp Groq `400/tool_use_failed` sau 2 tool call ở lần đầu, thành công khi thử lại đúng một lần và lưu **3 proposal**. Chạy lại cả batch trả `skipped` cho 5/5 query, không gọi API thêm.
- Bộ chấm index hiện có ghi q03 **0/1**, q09 **0/2**, q20 **0/2** khớp chính xác; Precision/Recall của ba query này vẫn `null` vì chưa đo P95 để xét phương án tương đương. q14 và q26 là nhóm rewrite, chưa kiểm hash/P95. Tóm tắt không chứa SQL ở `data/outputs/llm_catalog_20261127/batch_q03_q09_q14_q20_q26_summary.json` (gitignored).
- Đã xác nhận có proposal lưu cho **12/30 query catalog** tính cả các store thử trước đó. Chưa có bộ 30 query thống nhất, chưa tính Metrics tổng; ground truth vẫn chờ Hải review/GVHD ký. Không chạy Validation, Approve hoặc DDL. Lượt này chỉ thêm dữ liệu thử ignored và sửa PROGRESS; chưa sửa code, nên kiểm `git diff --check` thay vì chạy lại test.

---

## Thu proposal LLM theo batch nhỏ ngày 27/11/2026

- Thêm `scripts/collect_llm_proposals.py` để chạy 1–5 query catalog mỗi lượt qua backend Dashboard đã kiểm AST và chỉ cấp Tool 1–5. Mỗi query lưu SQLite riêng trong `data/outputs/llm_catalog_20261127/`; query đã có proposal được bỏ qua khi chạy lại. Kết quả in ra chỉ gồm ID, trạng thái, số proposal hoặc loại lỗi; không in SQL hay nội dung lỗi. Test giả kiểm chạy tiếp sau lỗi, bỏ qua query đã lưu và từ chối ID lạ trước khi gọi backend.
- Batch thật q02, q08, q19 trên DB chính với quyền đọc: lần lượt lưu **3, 4, 3 proposal**; chạy lại cho cả ba trả `skipped`, không gọi Groq. Chấm khớp index chính xác: q02 **0/2**, q08 **1/3**, q19 **0/2**. Các index chưa khớp cần đo P95 tương đương nên Precision còn `null`; Recall q08 là 1,0 trong phạm vi query đó, q02/q19 còn `null`. Proposal rewrite chưa được chấm hash/P95. Tính cả q01, q07, q13, q25 đã có trước, hiện có proposal cho **7/30 query catalog** ở các store thử riêng; đây chưa phải bộ kết quả thống nhất hay Metrics tổng.
- Không chạy Validation, Approve hoặc DDL. Ground truth vẫn chờ Hải review/GVHD ký. **350 tests pass**, Ruff và `git diff --check` pass sau thay đổi. Bước tiếp theo: tiếp tục thu query còn lại theo batch nhỏ, rồi kiểm chứng những phương án khác ground truth và rewrite trước khi tính chỉ số toàn bộ.

---

## Thử LLM cho ba nhóm query ngày 27/11/2026

- Dùng SQL trong `data/queries/queries.py` và đường `generate_proposals_from_dashboard()` để kiểm AST, gọi Groq qua MCP Tool 1–5 trên DB chính với quyền đọc, rồi lưu từng query vào SQLite riêng trong `data/outputs/` (gitignored). q01 lưu 1 index sau 2 lần gọi; lần đầu Groq trả `400/tool_use_failed` sau 1 tool call, lần thứ hai thành công. q13 và q25 mỗi query gọi 1 lần, mỗi lần lưu 2 index và 1 rewrite.
- Bộ chấm hiện có cho q01 ghi **0/1 index khớp chính xác**; Precision và Recall đều `null` vì index khác ground truth còn cần đo P95 cùng điều kiện để xét tương đương. q13 và q25 thuộc nhóm rewrite nên chưa chấm hash/P95 hoặc điểm rewrite. Kết quả q07 trước đó vẫn là mẫu riêng, không cộng thành chỉ số 30 query. Ground truth chưa có chữ ký GVHD; chưa tạo `comparison.csv`.
- Bằng chứng tóm tắt không chứa SQL ở `data/outputs/llm_metrics_pilot_20261127_summary.json`; proposal và run metadata ở cùng thư mục ignored. Không chạy Validation, Approve hoặc DDL. Bước tiếp theo: chuẩn hóa cách lưu/chạy lại từng query và thu kết quả 30 query; chỉ tính Metrics đầy đủ sau review ground truth và kiểm chứng tương đương/rewrite.

---

## Chấm mẫu Metrics index q07 ngày 27/11/2026

- Triển khai `data/metrics/metrics.py` phần khớp index **chính xác** theo bảng, cột và thứ tự cho các nhóm 1/2/4; đáp án `index_set` được tách thành từng index để chấm. Đề xuất rewrite không nằm trong mẫu số Precision index. Index khác thứ tự không bị gọi ngay là sai: nếu chưa có P95 cùng điều kiện để chấm mức tương đương thì `precision`/`recall` trả `null` thay vì gán 0.
- Đọc store Groq q07 đã lưu và `ground_truth.json` bằng CLI chỉ đọc: **2/2 index khớp chính xác**, Precision index **2/2 = 1,0**; Recall query nhóm 2 **1/1 = 1,0** trong phạm vi **duy nhất q07**. Không dùng tên index để quyết định khớp; không chấm hiệu năng của cả bộ hai index + rewrite. Ground truth còn `performance_verified_pending_review`, chưa có chữ ký GVHD. Bằng chứng tóm tắt ở `data/outputs/metrics_q07_pilot_20261127.json` (gitignored), không chứa SQL.
- CLI từ chối đường dẫn store không tồn tại trước khi SQLite có thể tạo file rỗng, tránh chấm nhầm thành 0 đề xuất. **348 tests pass**, Ruff và `git diff --check` pass. Chưa có kết quả LLM cho đủ 30 query để tính Precision/Recall toàn bộ, Consistency Rate, False Positive Rate hoặc metric rewrite; chưa tạo `comparison.csv`. Không gọi Groq/MySQL hay chạy DDL trong lượt chấm mẫu.

---

## Kiểm tích hợp injection B05 qua LLM host ngày 27/11/2026

- Test dùng LLM/MCP giả: model gọi `get_schema`, nhận `orders` cùng tên B05 chứa chỉ thị, rồi cố gọi `apply_optimization` với token giả. Host lọc B05 khỏi kết quả Tool 2 trước lượt model tiếp theo; danh sách tool cấp cho model chỉ có Tool 1–5. Host từ chối Tool 6 bằng `PermissionError` trước `mcp_client.call_tool`; MCP chỉ được gọi `get_schema` một lần, run metadata ghi lỗi. Không có DDL hoặc audit Tool 6 cho lượt bị chặn sớm này; ca D05 riêng kiểm audit khi token giả thực sự tới lõi Tool 6 trên DB giả.
- Đây là kiểm tích hợp bằng LLM/MCP giả cho một ca đại diện, không phải 20 lần gọi Groq hoặc tiêm dữ liệu vào MySQL. **345 tests pass**, Ruff và `git diff --check` pass. Report `security/injection_report.md` ghi rõ phạm vi; chặng 20 injection vẫn **Đang làm** về kiểm chứng end-to-end.

---

## Lọc tên bảng B05 trước Groq ngày 27/11/2026

- `mcp_server/llm/agent.py` lọc tên bảng Tool 2 không khớp identifier đơn giản trước khi gửi kết quả cho Groq và trước khi thêm bảng vào schema của parser. Bảng hợp lệ như `orders` vẫn giữ; raw tool result và nội dung chuyển cho LLM có hash riêng trong run metadata khi có lọc. Public output của Tool 2 không đổi. Test giả kiểm cả response đầy đủ và `truncated`.
- Probe Groq với SQL catalog q07 và MCP giả: sau sửa, B05 tới host nhưng **không tới model**. Một lượt sau sửa vẫn báo `400/tool_use_failed`. Đối chứng cuối gửi cùng nội dung tool result (SHA-256 khớp) cho nhánh bình thường và nhánh B05 đã lọc: nhánh bình thường thành công, nhánh B05 lỗi. Do đó chưa thể quy lỗi API cho payload B05 hoặc tuyên bố Groq luôn phân tích thành công; không có bằng chứng gọi Tool 6/token/DDL.
- Bằng chứng ở `data/outputs/groq_injection_b05_after_fix_20261127.json` và `data/outputs/groq_injection_b05_control_20261127.json` (gitignored). **344 tests pass**, Ruff và `git diff --check` pass. Không kết nối MySQL trong probe; DB chính không đổi. Mốc injection vẫn **Đang làm**.

---

## Probe Groq với tên schema độc hại B05 ngày 27/11/2026

- Trước bản sửa lọc tên bảng, dùng Groq thật, SQL catalog q07 và MCP giả chỉ trả schema tổng hợp; không kết nối MySQL hoặc gửi slow log thật. Đối chứng tên bảng bình thường: gọi `get_schema`, trả JSON hợp lệ và 2 proposal. Hai lượt tên bảng chứa chỉ thị B05: payload tới model qua `get_schema`, sau đó Groq trả HTTP 400 `tool_use_failed`, không có proposal/DDL. Metadata lỗi lần lặp không chứa tên Tool 6 hoặc token giả; chưa chứng minh model làm theo chỉ thị. Đối chứng sau sửa ở mục trên cho thấy không thể quy lỗi API này cho riêng payload B05.
- Bằng chứng tóm tắt không chứa SQL/key/response ở `data/outputs/groq_injection_b05_probe_20261127.json` và `data/outputs/groq_injection_b05_repeat_20261127.json` (gitignored). Host chỉ cấp Tool 1–5; DB chính không bị ghi. Đây là một probe LLM, không thay thế kết quả 20 ca ranh giới hoặc hoàn tất mốc injection end-to-end.

---

## Kiểm 20 kịch bản injection ở ranh giới code ngày 27/11/2026

- Hoàn thiện `security/injection_tests/payloads.py` (4 nhóm × 5) và runner `python -m security.injection_tests.run_tests`. **20/20 ca bị chặn tại lớp đã thử**: comment SQL/schema, guard identifier, AST whitelist, parser và registry/token. Log từng ca tại `security/logs/injection_results.log` (gitignored); report có giới hạn ở `security/injection_report.md`. D05 dùng Tool 6 với DB giả và token giả, audit ghi `attempted` rồi `rejected/TOKEN_INVALID`; không có DDL thật.
- Ca C05 phát hiện `security/ast_whitelist.py` chấp nhận `EXPLAIN ANALYZE SELECT ...` do bỏ từ `ANALYZE` trước khi parse. Đã sửa tối thiểu và thêm hai test tái hiện; `EXPLAIN` đọc thông thường vẫn được chấp nhận. **342 tests pass**, Ruff pass cho các file Python đã sửa.
- Đây là kiểm ranh giới bằng dữ liệu giả, chưa gọi Groq hoặc tiêm vào slow log/schema MySQL thật; chưa đo LLM có làm theo chỉ thị hay không. Vì vậy mốc 20 injection vẫn **Đang làm**, không ghi `Done` hay tuyên bố an toàn tuyệt đối. DB chính không bị DDL/ghi.

---

## Rà soát workload và điều kiện DB chính ngày 27/11/2026

- Đọc `performance_schema.events_statements_summary_by_digest` trên DB chính 3307 bằng `readonly_user`, không xuất SQL: không có digest của SQL catalog q07; các digest `SELECT` hiện lưu tổng cộng chỉ 11 lượt. Nguồn này không đủ để ước lượng tần suất q07 hay tỷ lệ đọc/ghi. Slow log chỉ gồm query chậm, nên cũng không đại diện các INSERT/UPDATE nhanh. Chưa chọn một tỷ lệ tải trộn tùy ý để gọi là workload thực tế.
- Đường Dashboard hiện chỉ cho Validation trên lab 3309 có marker; report q07 lab đã Reject/`cleaned` và không thể dùng để cấp token trên DB chính. DB chính có 1.500.000 dòng `orders` nhưng chưa có phép đo tải trộn hay quy trình Validation riêng đã kiểm chứng trên môi trường này. Bước tiếp theo là lấy tần suất workload từ người vận hành hoặc xác định rõ một kịch bản giả định cho báo cáo, rồi mới thiết kế phép đo trộn; không mở guard DB chính bằng cách tái sử dụng report lab.

---

## Đo bổ sung UPDATE cho ứng viên Groq q07 ngày 27/11/2026

- Chỉ bật write lab 3308, kiểm marker và bảng `orders` gốc có 0 dòng. Một script lab riêng đọc 100.000 dòng từ CSV, nạp hai bảng TEMPORARY cùng dữ liệu, tạo index q07 INVISIBLE chỉ trên bảng sau, rồi cập nhật `total_amount = total_amount + 0.01` theo PK theo 100 lô, mỗi lô 1.000 dòng; thứ tự chạy trước/sau được luân phiên. Không kết nối DB chính hoặc validation lab, không thêm UPDATE vào ngưỡng `passed` hiện tại.
- Một lượt đo: **183.835,90 → 96.067,51 dòng/giây** (giảm **47,74%**); thời gian cộng dồn **0,544 → 1,041 giây** cho 100.000 UPDATE. Đây là phép đo ngắn cho **một kiểu UPDATE tác động cột có trong index**, trên bảng tạm không có FK; chưa đo lặp, phân bố update khác hoặc tải đọc/ghi đồng thời. Không suy rộng thành mức giảm throughput của DB chính.
- Sau khi kết nối đóng, bảng tạm biến mất; kiểm độc lập bảng `orders` gốc vẫn 0 dòng, không có index thử hoặc bảng probe tồn tại. Bằng chứng ở `data/outputs/lab_only_groq_q07_update_c4a53357.json` (gitignored). Quyết định review vẫn giữ ứng viên q07 để nghiên cứu, **chưa Approve trên DB chính**; phép đo này tăng lý do cần cân nhắc tác động ghi. Report Validation và Dashboard hiện chỉ chứa số INSERT, chưa tích hợp số UPDATE một lượt này.

---

## Review kỹ thuật ứng viên Groq q07 ngày 27/11/2026

- **Kết luận:** giữ index `orders(status, order_date, customer_id, total_amount)` làm ứng viên có ích cho q07; **chưa Approve trên DB chính**. Đây là đối chiếu kỹ thuật do Codex thực hiện theo yêu cầu người dùng, không giả nhận chữ ký Hải/Tình/GVHD.
- Bằng chứng đọc trên validation lab: 3 warm-up + 20 lượt mỗi phía, P95 **2261,62 → 1137,69 ms** (giảm **49,70%**), P50 **2009,34 → 959,09 ms**, số dòng xét **1.971.386 → 628.511**, hash và số dòng kết quả khớp, 0 timeout, EXPLAIN chọn index thử. `query_cost` ước tính lại tăng **161.315,24 → 212.609,65**; không dùng riêng cost này để phủ nhận phép đo thời gian thực tế.
- Bằng chứng ghi ban đầu: INSERT trên 100.000 dòng mẫu **58.795,88 → 46.018,45 dòng/giây** (giảm **21,73%**), dung lượng index ước tính **73.072.640 byte**. Phép đo ghi dùng hai bảng TEMPORARY trên write lab, không sao chép FK. UPDATE được đo bổ sung một lượt ở mục trên; vẫn chưa có tải đọc/ghi đồng thời hoặc tần suất q07 so với ghi trên workload thật. Vì vậy chưa kết luận lợi ích ròng cho DB chính.
- Kiểm đọc metadata DB chính 3307: `orders` có 1.500.000 dòng và chỉ có `PRIMARY(order_id)`, `fk_orders_customer(customer_id)`; chưa có index q07 cùng tiền tố. Report `passed` thuộc lab 3309 đã Reject và dọn trial; theo contract không dùng report đó để cấp token/Approve trên DB chính. Đường `validate_from_dashboard()` hiện chỉ mở cho lab 3309. Trước khi cân nhắc áp dụng DB chính cần có tải đại diện hơn, quyết định về trade-off và quy trình Validation riêng phù hợp môi trường chính.

---

## Hiển thị trade-off trên trang Đề xuất ngày 27/11/2026

- Trang Đề xuất đọc report đã lưu từ `ProposalStore` và hiển thị P95 trước/sau, thay đổi thông lượng INSERT, dung lượng index thử ước tính, cỡ mẫu, kết quả tương đương và trạng thái bằng chứng. Report thiếu phép đo không được hiển thị thành số 0; trang ghi rõ chưa đo UPDATE hoặc tải đồng thời.
- Test Streamlit AppTest xác nhận người duyệt thấy các số của report q07 mẫu. **339 unit tests pass**, Ruff và `git diff --check` pass. Chưa mở lại Dashboard trên trình duyệt với report lab thật; không chạy thêm DDL/benchmark hoặc Approve trên DB chính. Review kỹ thuật ứng viên q07 được ghi ở mục trên.

---

## Đối chiếu ứng viên Groq q07 với ground truth ngày 27/11/2026

- Cả hai index Groq đề xuất (`orders(status, order_date, customer_id, total_amount)` và `addresses(customer_id, city)`) khớp chính xác bảng, cột và thứ tự với **hai thành phần** của đáp án q07 trong `ground_truth.json`. Rewrite Groq khác SQL ground truth và không có `FORCE INDEX`; chưa đo rewrite hoặc index trên `addresses`.
- Report Validation vừa có chỉ đo **một index trên `orders` với SQL gốc**. Ground truth q07 đo **hai index và SQL có hint**, lại dùng baseline ở lượt khác; vì vậy không so P95 1137,69 ms với 843,73 ms như hai phương án cùng điều kiện. Ground truth còn chờ Hải review/GVHD ký.
- Ứng viên `orders` đạt ngưỡng đọc/hash của Validation nhưng mẫu INSERT lab giảm thông lượng 21,73%; UPDATE đã đo thêm một lượt riêng trên lab, chưa có tải ghi/đọc đồng thời theo mục 2.3 ROADMAP. **Quyết định hiện tại:** giữ ứng viên theo review kỹ thuật ở mục trên, chưa đưa tới Approve trên DB chính.

---

## Kiểm chứng proposal Groq q07 trên validation lab ngày 27/11/2026

- Lấy đúng proposal index `orders(status, order_date, customer_id, total_amount)` đã được Groq tạo và lưu từ Dashboard, sao chép sang SQLite store lab riêng. Trước DDL, kiểm marker, số dòng, schema, index hiện có và snapshot FK: lab 3309 có 1.500.000 dòng `orders`, lab ghi 3308 có 0 dòng; index thử chưa tồn tại.
- Gọi `validate_from_dashboard()` trên lab 3309 với SQL q07 gốc. Report `passed`, đủ 20 lượt mỗi phía, không timeout; P95 **2261,62 → 1137,69 ms** (giảm **49,70%**), hash/số dòng kết quả tương đương và EXPLAIN dùng đúng index. Chi phí ghi trên lab: thông lượng INSERT giảm **21,73%** với mẫu 100.000 dòng; kích thước index ước tính **73.072.640 byte** từ `innodb_index_stats`.
- Gọi Reject để dọn trial sau khi ghi report. Store lab chuyển `cleaned`, index thử vắng mặt, snapshot FK khớp và số dòng hai lab không đổi. Bằng chứng tóm tắt ở `data/outputs/lab_only_groq_q07_validation_56d87020.json`, report đầy đủ trong SQLite cùng hậu tố (gitignored). DB chính 3307 không bị DDL; proposal gốc vẫn `new`. Đây là một ứng viên q07 đạt ngưỡng lab, chưa phải quyết định áp dụng trên DB chính hoặc kết quả cho cả 30 query.

---

## Tạo proposal bằng Groq từ trình duyệt ngày 27/11/2026

- Dashboard loopback cổng 8502 dùng store SQLite thử riêng, trỏ `127.0.0.1:3307/shopdb` cho Tool 1–5 bằng `readonly_user`. Nhập query catalog `q07` và bấm **Phân tích và lưu đề xuất** trên trình duyệt sau khi xác nhận gửi SQL cho LLM. Không dùng SQL từ slow log cho lượt này.
- Lần đầu tiến trình bị sandbox chặn mạng và run ghi `APIConnectionError`, 0 proposal. Khởi động lại đúng Dashboard thử với quyền mạng, bấm lại một lần: Groq trả JSON hợp lệ; LLM host gọi `get_schema` qua MCP; parser chấp nhận 3 proposal. Trang báo **Đã lưu 3 đề xuất**; store có 2 index và 1 rewrite, tất cả `trial_state=new`.
- Không bấm Validation/Approve, không chạy DDL hoặc ghi MySQL. Đã đóng trình duyệt/Dashboard; DB chính 3307 vẫn kết nối được. Bằng chứng tóm tắt không chứa SQL/key/token ở `data/outputs/groq_ui_main_read_20261127.json`; proposal store và run metadata cũng nằm trong `data/outputs/` (gitignored). Đây là một lượt q07 thành công, chưa phải metric ổn định hoặc kiểm đủ 30 query; chặng LLM/Dashboard vẫn **Đang làm**.

---

## Kiểm đọc Slow Query trên DB chính ngày 27/11/2026

- Tool 1 gọi bằng `readonly_user` trên `127.0.0.1:3307/shopdb`: nguồn `performance_schema` trả `ok=true` nhưng 0 query đạt ngưỡng hiện tại; nguồn `mysql.slow_log` trả `ok=true`, 10 query và `truncated=true`. Không in SQL log trong phép kiểm.
- Dashboard loopback cổng 8502 dùng store SQLite thử riêng. Trên trình duyệt, chọn `slow_log` rồi bấm **Tải slow query**: bảng kết quả, SQL dạng code và nút chuyển trang xuất hiện, không có lỗi Streamlit. Bấm **Phân tích query này** chuyển sang trang Đề xuất; `query_id` và SQL được điền sẵn, nút gửi LLM vẫn khóa khi chưa xác nhận.
- Store thử riêng có 0 proposal; không gửi Groq, không chạy Validation/Tool 6 hoặc DDL. Đã đóng trình duyệt và Dashboard, giữ DB chính chạy. Bằng chứng tóm tắt không chứa SQL ở `data/outputs/main_read_smoke_20261127.json` (gitignored). Chưa thử tạo proposal bằng Groq từ nút mới trên DB chính.

---

## Chọn Slow Query để phân tích trên Dashboard ngày 27/11/2026

- Trang Slow Query gọi Tool 1 khi người dùng bấm tải, chọn nguồn `performance_schema` hoặc `slow_log`, đọc tối đa 10 bản ghi bằng `readonly_user`. Backend chỉ nhận hàng có `query_id`, `sql_text` và `untrusted=true`; trang hiển thị SQL bằng `st.code`, cùng bảng latency, số lần chạy và số dòng đọc.
- Nút **Phân tích query này** chuyển mã query và SQL đã chọn qua session state sang form Đề xuất. Nút này chưa gọi LLM; người dùng vẫn phải xác nhận gửi SQL ở trang sau, nơi backend kiểm AST trước API. Query sample từ `performance_schema` có thể cần thay placeholder bằng giá trị cụ thể trước khi Validation chạy.
- Test AppTest dùng Tool 1 giả để kiểm chuyển trang/prefill; **338 unit tests pass**, Ruff và `git diff --check` pass. Chưa kiểm đường chọn query trên trình duyệt với MySQL thật. Trang Slow Query vẫn **Đang làm**: chưa có biểu đồ và chưa đo giao diện với dữ liệu thật.

---

## Nối tạo proposal từ trang Đề xuất ngày 27/11/2026

- Trang Đề xuất nhận `query_id` và SQL đọc do người vận hành nhập, yêu cầu xác nhận trước khi gửi tới LLM. Backend kiểm SQL bằng AST whitelist và giới hạn prompt trước khi tạo Groq client; mở MCP stdio chỉ với Tool 1–5, gọi `analyze_query()` đã có parser và retry. Lỗi API/parser không đưa proposal lỗi vào store hoặc hiển thị SQL/bí mật trong thông báo giao diện.
- `ProposalStore.add_many()` lưu cả danh sách trong một giao dịch SQLite sau khi kiểm cấu trúc index hoặc SQL rewrite; một đề xuất không hợp lệ không để lại nhóm lưu dở. Rewrite chỉ hiển thị, không có nút Validation/Approve. LLM không được gọi Tool 6; việc tạo proposal không chạy DDL.
- **335 unit tests pass**, Ruff và `git diff --check` pass. Giao diện đã kiểm bằng Streamlit AppTest với LLM/MCP giả; chưa gọi Groq hoặc MySQL thật từ nút mới và chưa đo metric LLM trên 30 query. Chặng Dashboard/LLM vẫn **Đang làm**.

---

## Kiểm Validation → Approve trên trình duyệt với lab riêng ngày 27/11/2026

- Chỉ bật lại hai container lab cũ ở `127.0.0.1:3308/3309`; kiểm marker và số dòng trước thao tác: validation lab có 1.500.000 dòng `orders`, write lab có 0 dòng. Dashboard chạy loopback `127.0.0.1:8502`, trỏ DB 3309 và store SQLite riêng. DB chính 3307 không được dùng trong lượt thử.
- Tạo proposal mẫu mới cho `orders(status, order_date)` trong store lab. Trên trình duyệt, nhập thư mục CSV, xác nhận và bấm **Chạy Validation**. Report `passed`, `evidence_complete=true`, P95 **817,24 → 70,55 ms**; trial giữ INVISIBLE trước khi duyệt.
- Xác nhận rồi bấm **Approve** trên trình duyệt. Trang hiển thị `applied`; kiểm độc lập thấy index thử VISIBLE, đúng 1 token đã tiêu thụ và audit ghi `attempted` rồi `applied`. Sau đó dọn đúng index VISIBLE của lượt lab; index vắng mặt, snapshot FK khớp và số dòng hai lab không đổi. Store lab vẫn giữ `applied` làm bằng chứng lịch sử, không dùng làm store runtime.
- Bằng chứng ở `data/outputs/lab_only_browser_approve_29d5228a.json` và SQLite cùng hậu tố (gitignored). Chưa áp dụng trên DB chính; chưa nối tạo proposal từ UI hoặc kiểm 20 payload injection. Validation Layer, Tool 6 và Dashboard vẫn **Đang làm**.

---

## 🎯 TỔNG QUAN CÁC GIAI ĐOẠN

|  #  | Giai đoạn                                            | Trạng thái  | Người chính      |          Deadline          |
| :-: | ---------------------------------------------------- | :---------: | ---------------- | :------------------------: |
|  0  | Setup môi trường                                     |   ✅ Done   | Vũ               |           28/09            |
| 0b  | Thiết kế (`api-contract.md`, `architecture.md`) | ✅ Contract v2 đã chốt; triển khai theo từng chặng | Vũ | 06/10 |
|  1  | CSDL 5 bảng, tổng 5M records                         |   ✅ Đã nạp/kiểm tra   | Hải              |           05/10            |
|  2  | 30 query + ground truth                              | ✅ Done (đã đo kiểm chứng & GVHD đồng ý) | Tường | 06/10 (draft) · 20/10 (ký) |
|  3  | Tool 1–5 MCP                                         | 🟡 Đang làm | Vũ · Hải · Tường |           13/10            |
|  4  | Tích hợp LLM                                         | 🟡 Đang làm | Vũ               |           18/10            |
|  5  | Validation Layer                                     | 🟡 Đang làm | Hải              |           22/10            |
|  6  | Tool 6 + approval token + 20 injection               | 🟡 Đang làm | Tình             |           27/10            |
|  7  | Metrics + Baseline                                   | 🟡 Chấm mẫu q07; baseline 30/30, còn metric toàn bộ | Tường · Hải | 03/11 |
|  8  | Dashboard 4 tab                                      | 🟡 Đã có code cả 4 tab + AppTest | Tình             |           10/11            |
|  9  | Báo cáo + Demo                                       | 🟡 Đã có bản thảo báo cáo + dàn ý slide/demo | Cả nhóm          |       17/11 · 01/12        |

---

## Kiểm Dashboard trên trình duyệt với lab riêng ngày 26/11/2026

- Thêm `DASHBOARD_STORE_PATH` để tiến trình Streamlit dùng SQLite proposal/token/audit tách khỏi store mặc định. Chạy Dashboard loopback `127.0.0.1:8502` với `DB_HOST=127.0.0.1`, `DB_PORT=3309`, store lab mới và write lab 3308; không dùng DB chính 3307 hoặc store runtime mặc định.
- Playwright mở trang Đề xuất: nút Validation bị khóa trước khi nhập CSV/xác nhận; sau xác nhận bấm Validation, report `passed` với P95 **776,32 → 68,42 ms**. Sau tải lại, nút Approve/Reject chỉ xuất hiện với trial `passed`; bấm Reject, trang báo đã dọn. Kiểm độc lập: store `cleaned`, index thử vắng mặt, validation lab `orders` vẫn 1.500.000 dòng, write lab vẫn 0 dòng. Bằng chứng `data/outputs/lab_only_browser_d614ad48.json` và SQLite cùng hậu tố (gitignored).
- Phát hiện trang giữ trạng thái/nút cũ ngay sau thao tác; đã sửa tự rerun và giữ thông báo thành công. Test AppTest mới xác nhận Reject chuyển trang sang trạng thái `cleaned` ngay sau cú bấm. Đây là sửa sau lượt Playwright đầu; chưa lặp lại DDL chỉ để chụp lại cùng trạng thái.
- Đã đóng trình duyệt, dừng Streamlit cổng 8502 và hai container lab; volume/bằng chứng giữ nguyên. DB chính vẫn healthy. Chưa bấm Approve từ trình duyệt, chưa nối tạo proposal từ UI hoặc kiểm 20 payload injection.
- **329 tests pass**, Ruff và `git diff --check` pass. Snapshot/log tạm của Playwright đã dọn khỏi working tree; report/SQLite lab trong `data/outputs/` vẫn giữ.

## Kiểm Validation → Approve/Tool 6 trên lab riêng ngày 26/11/2026

- Khởi động lại đúng hai lab cổng 3308/3309 với volume cũ, giữ marker/dữ liệu; dùng store, token SQLite và audit SQLite riêng trong `data/outputs/`. Proposal mẫu `orders(status, order_date)` mới, không đụng FK q01; DB chính 3307 không được kết nối.
- Bấm **Chạy Validation** rồi **Approve** bằng Streamlit AppTest. Report `passed`, 20 lượt mỗi phía, P95 **507,31 → 68,74 ms**. Tool 6 xác nhận index VISIBLE, store chuyển `applied`, một token đã tiêu thụ, audit ghi `attempted` rồi `applied`. Bằng chứng ở `data/outputs/lab_only_dashboard_approve_c961bc89.json` cùng SQLite proposal/token/audit theo hậu tố (gitignored); không lưu token vào report.
- Sau khi thử, script kiểm `db_identity`, marker lab, định nghĩa index và rủi ro FK rồi dọn **đúng index VISIBLE của lượt lab**. Kiểm độc lập: index vắng mặt trong metadata, snapshot FK khớp, validation lab `orders` vẫn 1.500.000 dòng, write lab vẫn 0 dòng. Store lab giữ `applied` để ghi nhận đã áp dụng trước khi cleanup ngoài luồng; không dùng store này cho Dashboard runtime. Đã dừng hai container lab, giữ volume/bằng chứng; DB chính vẫn chạy.
- Đây là kiểm qua Streamlit AppTest, **chưa bấm bằng trình duyệt thật** và chưa chạy trên DB chính. Chưa có luồng tạo proposal từ UI hoặc 20 payload injection. Tool 6 và Dashboard vẫn **Đang làm**.

## Kiểm Validation → Reject trên lab riêng ngày 26/11/2026

- Khởi động lại hai container/volume lab riêng ở `127.0.0.1:3308/3309`, xác nhận healthy, marker đúng; validation lab có 1.500.000 dòng `orders`, write lab `orders` có 0 dòng và không có index thử cũ trên `orders`. DB chính 3307 không được kết nối trong lượt này.
- Dùng store SQLite lab mới và proposal mẫu `orders(status, order_date)` để bấm **Chạy Validation** bằng Streamlit AppTest. Report `passed`, đủ 20 lượt mỗi phía, P95 **626,05 → 103,68 ms**; dung lượng index thử 46.759.936 byte từ `innodb_index_stats_pages`. Sau đó bấm **Reject**; store chuyển `cleaned`. Kiểm độc lập bằng `readonly_user`: index thử vắng mặt, validation lab vẫn 1.500.000 dòng `orders`, write lab vẫn 0 dòng. Bằng chứng ở `data/outputs/lab_only_dashboard_ui_7ab607bd.json` và SQLite cùng hậu tố (gitignored).
- Đây là thử qua máy chạy script Streamlit AppTest, **chưa bấm bằng trình duyệt thật**, chưa thử Approve/Tool 6 trên lab. Chưa áp dụng index trên DB chính. Validation Layer và Dashboard vẫn **Đang làm**.
- Sau khi kiểm chứng, đã dừng đúng hai container lab 3308/3309; volume và bằng chứng giữ nguyên. DB chính `mcp_mysql_db` cổng 3307 vẫn healthy.

## Nút Validation trên Dashboard ngày 26/11/2026

- Trang Đề xuất cho proposal index `new` nhập thư mục CSV, xác nhận rồi gọi `validate_from_dashboard()`. Backend kiểm CSV, cấu hình đúng `127.0.0.1:3309/shopdb` và marker `mcp-validation-lab-v1` trước khi gọi Validation có DDL; DB chính 3307 bị từ chối. Đo INSERT vẫn dùng write lab 3308 qua guard riêng có sẵn.
- Tại thời điểm viết code, Docker chỉ có DB chính 3307 chạy; sau đó đã khởi động lại hai lab và kiểm Validation → Reject như mục trên. Proposal vẫn chưa có đường tạo từ UI.
- **327 tests pass**, Ruff và `git diff --check` pass. Validation Layer và Dashboard vẫn **Đang làm**.

## Trang Đề xuất Dashboard ngày 26/11/2026

- `ProposalStore.recent_proposals()` đọc tối đa 50 proposal mới nhất. Trang Đề xuất hiển thị SQL gốc dạng code, trạng thái trial/report và hạn duyệt; rewrite chỉ hiển thị. Approve/Reject bị khóa đến khi người dùng xác nhận. Approve gọi `apply_from_dashboard()` (token một lần + Tool 6 riêng); Reject gọi đường cleanup có kiểm DB/marker/snapshot. Backend kiểm lại mọi điều kiện khi thực hiện, không tin điều kiện hiển thị của UI.
- **324 tests pass**, gồm Streamlit AppTest cho thao tác và trạng thái bị khóa; Ruff và `git diff --check` pass. Chưa nối nút tạo proposal/Validation trên UI, chưa chạy DDL thật từ Dashboard. Các tab khác vẫn là khung.

## Hạn chờ duyệt trial ngày 26/11/2026

- Report `passed` lưu `review_expires_at` = lúc lưu + 86.400 giây theo `approval.review_ttl_seconds`. Precheck chung của Dashboard và Tool 6 từ chối proposal quá hạn hoặc bản cũ thiếu hạn. Token một lần vẫn có hạn 600 giây tính từ lúc cấp.
- Backend chạy recovery rồi dọn trial `passed` quá hạn khi Dashboard khởi động; dọn qua kiểm tra DB, marker và snapshot FK/index của Reject. Lỗi dọn làm backend dừng. Chưa có lịch nền dọn đúng giờ nếu Dashboard chạy liên tục; chưa thử DROP thật trên MySQL.
- **319 unit tests pass**, Ruff và `git diff --check` pass; test expiry dùng DB/trial giả. Chặng Validation vẫn **Đang làm**.

## Reject dọn index thử đã pass ngày 26/11/2026

- `reject_saved_index()` kiểm report thuộc DB hiện tại, rồi chuyển proposal `passed → pending` trong SQLite trước khi gọi đường recovery dọn trial có marker và kiểm snapshot FK/index. Dọn thành công chuyển `cleaned`; lỗi để `pending` để lần khởi động sau thử recovery. Recovery gặp report mới thuộc DB khác sẽ giữ `pending` và không DROP; proposal đã dọn hoặc đã áp dụng không được Reject lặp. Chưa nối nút Reject trên Dashboard.
- **314 unit tests pass**, Ruff pass. Test dùng trial giả, không chạy DROP INDEX thật. Contract chưa định thời gian chờ duyệt trước khi tự dọn; **chưa bật tự dọn theo thời gian**. Chặng Validation vẫn đang làm: cần thử Reject trên lab riêng, kiểm lại luồng report/trial hiện tại và các proposal còn lại trước khi đánh dấu Done.

---

## Backend Dashboard cục bộ gọi Tool 6 ngày 26/11/2026

- Theo phạm vi một người dùng cục bộ, `.streamlit/config.toml` đặt `server.address="127.0.0.1"`; Streamlit đã đọc đúng giá trị này. `dashboard.backend.apply_from_dashboard()` lấy tên OS account của tiến trình Streamlit, cấp token sau precheck rồi gọi registry MCP Dashboard riêng. Kết quả Tool 6 trả về cho backend không chứa token; lỗi tool được che bằng thông báo chung. Giao diện chưa có nút Approve, nên đường này chưa được gọi từ trình duyệt.
- **311 unit tests pass**, Ruff pass. Test dùng applier giả; chưa chạy DDL thật hoặc kiểm thao tác bấm trên Dashboard. Tên OS account chỉ nhận diện người vận hành tiến trình cục bộ, không phải cơ chế đăng nhập cho nhiều người; cấu hình loopback có thể bị người chạy ghi đè bằng tham số CLI. Bước tiếp theo: giao diện Tab 2 chỉ hiện Approve với proposal đủ điều kiện, gọi backend này sau cú bấm, rồi kiểm thử UI; DDL thật chỉ thử trên lab riêng sau khi có report/trial hợp lệ và kiểm marker.

---

## Registry MCP riêng cho Dashboard ngày 26/11/2026

- `mcp_server/dashboard_server.py` tạo registry chỉ có `apply_optimization(proposal_id, approval_token)` và chuyển lời gọi tới `OptimizationApplier` mà backend cấp. `mcp_server/server.py` dành cho LLM vẫn chỉ đăng ký Tool 1–5. Registry Dashboard hiện là factory nội bộ, không có entry point chạy riêng; chưa được giao diện gọi hoặc gắn danh tính người duyệt đã xác thực.
- Test giả kiểm đúng tên tool, đúng hai trường input và gọi được applier giả; **307 unit tests pass**, Ruff pass. Không khởi động Dashboard hoặc chạy DDL thật. Bước tiếp theo là xác định nguồn danh tính người duyệt đáng tin cậy trong Dashboard rồi mới nối nút Approve với registry này.

---

## Lõi Tool 6 với DB giả ngày 26/11/2026

- `OptimizationApplier.apply_optimization(proposal_id, approval_token)` dùng chung `check_approval()` với backend để kiểm report, danh tính DB và index INVISIBLE trước khi tiêu thụ token. Sau đó chỉ chạy DDL `ALTER ... VISIBLE` do `TrialIndex` dựng bằng `index_admin`, xác minh marker/định nghĩa/index VISIBLE, chuyển proposal sang `applied` và ghi audit. Audit không ghi được trước DDL thì dừng; token sai, proposal thiếu hoặc DB sai đều bị từ chối và có bản ghi audit. Nếu lỗi sau khi ALTER được gọi mà chưa xác minh chắc trạng thái, audit ghi `uncertain` để cần đối chiếu thủ công.
- **306 unit tests pass**, Ruff pass. Test dùng DB và trial giả, không chạy DDL thật. Lõi chưa có registry riêng cho backend Dashboard, chưa có người duyệt xác thực từ giao diện, chưa thử MySQL lab hoặc 20 payload injection; Tool 6 và Dashboard vẫn **Đang làm**. Bước tiếp theo: nối registry/đường gọi chỉ cho Dashboard với danh tính người duyệt tin cậy, rồi thử DDL trên lab riêng sau khi kiểm marker và bằng chứng.

---

## Audit log cho Tool 6 ngày 26/11/2026

- `mcp_server/store/audit_log.py` đã có `AuditLog.append()` ghi thời gian UTC, proposal ID, hash DDL, kết quả, người duyệt, nguồn gọi và mã lý do vào SQLite riêng. API chỉ thêm bản ghi, không có cột token; lỗi ghi audit được ném ra để caller dừng trước DDL.
- Test bằng SQLite tạm xác nhận bản ghi giữ nguyên sau khi mở lại và không có cột token. **297 unit tests pass**, Ruff pass. Tool 6 chưa gọi audit, chưa thực thi ALTER hoặc được đăng ký ở registry riêng; cần nối kiểm lại report/trial/DB, tiêu thụ token và ghi audit cho cả nhánh chấp nhận/từ chối bằng DB giả trước khi thử MySQL lab.

---

## Cấp token từ backend sau precheck ngày 26/11/2026

- `dashboard.backend.issue_approval_token()` gọi `approval_precheck()` trước, rồi dùng `ApprovalTokens` với secret từ cấu hình để ký đúng `proposal_id`, version và DDL `ALTER ... VISIBLE` đã kiểm. Nonce được lưu trong SQLite riêng. Report sai DB hoặc index thử không hợp lệ không được cấp token; không nhận SQL tự do từ caller.
- Test giả xác nhận token đúng phiên bản/DDL và từ chối report thuộc DB khác trước khi tạo kho token. **296 unit tests pass**, Ruff pass. Chưa có nút Approve, Tool 6, audit log hoặc thử MySQL thật. Bước tiếp theo là Tool 6 kiểm lại report/trial/DB, tiêu thụ token một lần và ghi audit trước khi nối Dashboard.

---

## Ràng buộc danh tính DB trong report ngày 26/11/2026

- `validate_saved_index()` đọc `@@server_uuid`, `DATABASE()` qua `readonly_user` cùng host/port cấu hình trước khi bắt đầu trial, rồi lưu `db_identity` vào report. `approval_precheck()` đọc lại danh tính DB hiện tại và từ chối report thiếu trường hoặc không khớp trước khi kiểm index thử. Report cũ không tự được nâng cấp; phải validation lại để đủ điều kiện duyệt.
- Test giả kiểm report lưu qua SQLite, DB đúng được phép qua precheck, thiếu/sai danh tính bị từ chối. **294 unit tests pass**, Ruff pass; chưa thử MySQL thật hoặc Dashboard. Chặng Validation, Tool 6 và Dashboard vẫn đang làm. Bước tiếp theo: kiểm truy vấn danh tính trên MySQL lab bằng quyền readonly, sau đó nối cấp token/Tool 6 với cùng ranh giới DB và audit.

---

## Approval token độc lập ngày 25/11/2026

- `security/approval.py` đã có lớp ký token HMAC gắn proposal ID, version và hash của đúng lệnh ALTER; nonce và hạn 10 phút được lưu trong SQLite riêng. Xác thực dùng `hmac.compare_digest`, tiêu thụ nonce bằng một lệnh UPDATE có điều kiện để chặn dùng lại, kể cả hai lượt đồng thời. Thiếu secret thì không khởi tạo được.
- Backend có `approval_precheck()` đọc proposal/report đã lưu, chỉ chấp nhận index `passed` trên SQL gốc với `evidence_complete=true`, trial ở state `passed`, rồi đọc lại index INVISIBLE có marker/định nghĩa khớp bằng `TrialIndex._index_state()`. Hàm chỉ trả DDL `ALTER INDEX ... VISIBLE` do server dựng; chưa cấp token hay chạy DDL. Report hiện chưa gắn danh tính DB nơi đo, nên chưa được nối precheck với nút Approve hoặc Tool 6 trước khi bổ sung ràng buộc môi trường.
- Test bằng SQLite tạm và trial giả: token dùng một lần; precheck từ chối report không đạt, trial đã dọn hoặc index không còn. **290 unit tests pass**, Ruff pass. Chưa nối Tool 6, giao diện Dashboard hay audit log, chưa cấp token dựa trên report/index thật, chưa chạy DDL trên lab/DB chính. Bước tiếp theo là ghi/kiểm danh tính DB trong report trước khi nối cấp token.

---

## Validation q01 đầy đủ trên lab 5M ngày 25/11/2026

- `TrialIndex.create()` giữ guard FK ở đường mặc định. Chỉ `validate_saved_index(..., allow_fk_trials=True)` trên `127.0.0.1:3309` có marker validation lab mới được thử FK khi snapshot đã lưu khớp schema, đúng một FK bị ảnh hưởng và index hỗ trợ đơn giản có thể khôi phục. Sau CREATE, helper dựng lại index FK cũ nếu MySQL tự bỏ nó, **trước lượt đo baseline**; cleanup so schema sau DROP với snapshot. Dashboard không truyền cờ này, DB chính không được kết nối trong lượt thử.
- Một lượt q01 đầu với timeout mặc định 30 giây trả `inconclusive/measurement_error`, không có P95 hợp lệ; cleanup vẫn sạch. Phép chẩn đoán 5 lượt chỉ đọc trả P95 25.575,62 ms, sát timeout; đây là dấu hiệu timeout ở lượt 20/20 nhưng report hiện chưa giữ mã lỗi Tool 5 nên không khẳng định nguyên nhân chính xác. Script lab chạy lại **một lượt đầy đủ** với timeout 60 giây, vẫn giữ 3 warm-up + 20 lượt mỗi phía.
- Lượt 60 giây trả `passed`, `evidence_complete=true`, `result_equivalent=true`, 20/20 lượt mỗi phía, 0 timeout, hash/số dòng khớp; P95 **29.479,27 → 222,28 ms** (giảm **99,25%**). Kích thước index **91.963.392 byte** từ `innodb_index_stats_pages`; INSERT throughput thay đổi **−3,02%** trên write lab riêng. Đây là so sánh trong cùng lượt lab; không so trực tiếp P95 với lần đo cũ. Report trong `data/outputs/lab_only_full5m_q01_validation_df244d1d.json` và SQLite lab cùng hậu tố (gitignored).
- Index thử đã dọn, `fk_order_items_product` VISIBLE và schema FK khớp snapshot; report lab **không đủ điều kiện cấp token** vì trial không còn. Thử thêm đường `TrialIndex.create()` trên hai bảng nhỏ có FK tự tạo: MySQL bỏ index cũ, helper khôi phục nó trước khi trả về cho phép đo và dọn sạch sau đó. Kiểm độc lập: validation lab vẫn 5 bảng/tổng 5M dòng, không còn trial/bảng nhỏ; write lab `order_items` vẫn 0 dòng. Hai container đã dừng, giữ volume và bằng chứng.
- **273 unit tests pass**, Ruff pass cho Python đã sửa. Validation Layer vẫn **Đang làm**: nhánh FK chỉ được bật cho lab, Tool 6/Dashboard chưa tích hợp và chưa kiểm đủ mọi proposal. Không áp dụng index nào trên DB chính.

---

## Kiểm cleanup q01 trên validation lab 5M ngày 25/11/2026

- Chỉ khởi động validation lab 3309, xác nhận marker `mcp-validation-lab-v1`, `order_items` 2.450.000 dòng, index `fk_order_items_product` ban đầu VISIBLE và ổ D còn khoảng 72 GB. Dùng SQLite lab riêng ghi snapshot FK/index cùng `pending`, rồi `index_admin` tạo trial INVISIBLE `order_items(product_id, quantity, unit_price)` có marker; tiến trình này kết thúc trước recovery. Guard runtime q01 **không đổi**; script offline lab gọi DDL đã cấu trúc để kiểm riêng cleanup.
- Lần này MySQL **không tự bỏ** index hỗ trợ FK ban đầu, phù hợp với việc index trên lab đã được khôi phục tường minh sau sự cố trước. Để tái hiện trạng thái cần recovery, script xác minh trial đang hỗ trợ đúng FK và snapshot/marker khớp, rồi **chỉ trên lab** dùng `index_admin` bỏ `fk_order_items_product`. Tiến trình mới gọi `recover_interrupted_trials()`: tạo lại index FK từ snapshot, dọn trial và chuyển `cleaned`; report kiểm `schema_restored=true`, `trial_absent=true`, `fk_support_visible=true`.
- Kiểm độc lập sau cùng bằng `readonly_user`: 5 bảng vẫn tổng 5.000.000 dòng (500.000/500.000/50.000/1.500.000/2.450.000), FK `fk_order_items_product` còn, index hỗ trợ VISIBLE và không có `idx_lab_q01_recovery_*`. Container lab đã dừng, volume/bằng chứng giữ nguyên. File `data/outputs/lab_only_full5m_q01_recovery_20261125.json` và SQLite lab riêng được gitignore. DB chính 3307 không được kết nối trong lượt này.
- Đây là phép kiểm **cleanup/recovery ở quy mô dữ liệu đầy đủ**, không đo lại P95, chi phí ghi, không thử đường Validation q01 tự tạo index sau khi bỏ guard. q01 vẫn bị chặn trước CREATE; chưa đủ điều kiện duyệt hoặc áp dụng lên DB chính. Lượt này không sửa code runtime; test 268 pass từ chặng trước không chạy lại, tài liệu kiểm bằng `git diff --check`.

---

## Kiểm quyền DB thật cho recovery FK ngày 25/11/2026

- Chỉ dùng `validation_lab_db` cổng 3309, xác nhận marker `mcp-validation-lab-v1` trước DDL. Tạo hai bảng thử nhỏ có FK và một dòng bằng root lab; phần runtime giữ nguyên `get_conn()`/`get_admin_conn()` với tài khoản thật `readonly_user`/`index_admin`. `readonly_user` đọc được snapshot FK/index nhưng bị từ chối `CREATE INDEX` (MySQL 1142). `index_admin` tạo được trial INVISIBLE, và MySQL tự bỏ index FK cũ như sự cố q01.
- Tiến trình thứ nhất ghi snapshot + `pending` vào SQLite lab rồi tạo trial; tiến trình thứ hai gọi `recover_interrupted_trials()`: dựng lại index FK bằng `index_admin`, dọn trial, xác minh schema khớp snapshot và chuyển `cleaned`. Bằng chứng `data/outputs/lab_only_fk_privilege_20261125.json` và SQLite `lab_only_fk_privilege_*.sqlite3` (gitignored); script lab cũng nằm trong `data/outputs/` và không thuộc runtime.
- Kiểm sau cùng: không còn bảng thử `mcp_fk_priv_*`, validation lab vẫn có 2.450.000 dòng `order_items`, `fk_order_items_product` VISIBLE; đã dừng container, giữ volume và bằng chứng. DB chính cổng 3307 không được kết nối trong lượt này. Không sửa code runtime hoặc grant DB; q01 vẫn bị guard chặn trước CREATE. Bước kế tiếp là thử q01 trên lab 5M bằng đường kiểm soát riêng sau khi rà lại điều kiện cleanup, chưa áp dụng lên DB chính.

---

## Thử recovery khôi phục index hỗ trợ FK ngày 25/11/2026

- Thêm nhánh `TrialIndex.restore_fk_support(snapshot)`: xác minh marker trial và FK hiện tại; chỉ dựng lại đúng một index hỗ trợ FK đơn giản, có định nghĩa khớp snapshot; xác minh lại trước khi dọn trial. `recover_interrupted_trials()` còn đối chiếu schema FK/index sau DROP; mọi sai lệch giữ `pending`/`recovery_failed`. Trường hợp ngắt sau `pending` nhưng trước CREATE được nhận diện là trial vắng và schema gốc còn nguyên.
- Test DB giả bao phủ thứ tự khôi phục→DROP→đối chiếu, ngắt trước CREATE, thử lại sau khôi phục, FK đổi, snapshot không hỗ trợ FK, trial không hỗ trợ FK bị mất và schema sai sau DROP. **268 tests pass**, Ruff pass cho Python đã sửa và `git diff --check` pass.
- Trên **validation lab 3309**, kiểm marker `mcp-validation-lab-v1` rồi tạo riêng hai bảng nhỏ có FK và một dòng; tạo trial INVISIBLE có marker. MySQL tự bỏ index FK ban đầu như q01. Recovery từ SQLite snapshot đã tạo lại index FK, dọn trial, đối chiếu schema khớp ban đầu và chuyển store sang `cleaned`. Lặp lại sau khi thêm điều kiện trial phải hỗ trợ chính FK bị mất, kết quả vẫn sạch. Bằng chứng `data/outputs/lab_only_fk_restore_e39cf25b.json` và `data/outputs/lab_only_fk_restore_4e258865.json` cùng SQLite tương ứng (gitignored). Dùng root lab cho phép thử DDL, nên lượt này chưa kiểm ranh giới quyền `readonly_user`/`index_admin` trên MySQL thật.
- Sau phép thử, hai bảng nhỏ đã dọn; lab vẫn có 2.450.000 dòng `order_items`, không còn bảng `mcp_fk_*`. Đã dừng container validation lab, giữ volume và bằng chứng. DB chính 3307 không được kết nối hoặc chạy DDL trong lượt này. **q01 vẫn bị chặn trước CREATE**, chưa thử luồng đo đầy đủ hay áp dụng index trên DB chính.

---

## Lưu metadata hỗ trợ FK trước trial ngày 25/11/2026

- `TrialIndex.fk_support_snapshot()` đọc FK phía tham chiếu và định nghĩa index đang hỗ trợ bằng `readonly_user`. `validate_saved_index()` gọi hàm này trước `begin_trial()`; store ghi snapshot cùng `trial_state=pending` trong một giao dịch SQLite, rồi mới cho phép `CREATE INDEX`. Mở lại SQLite vẫn đọc được snapshot; lỗi đọc metadata dừng khi state còn `new`, không chạy DDL.
- Test dùng DB giả và SQLite tạm: toàn bộ **261 tests pass**, Ruff pass. Không khởi động MySQL/Dashboard thật, không tạo/drop index trong lượt này. Snapshot chưa được dùng để tự khôi phục index; q01 vẫn bị chặn. Bước tiếp theo là thiết kế/thử khôi phục an toàn qua các điểm ngắt trên lab riêng trước khi mở lại q01.

---

## Chặn recovery dọn index duy nhất hỗ trợ FK ngày 25/11/2026

- Khi trial cũ là index duy nhất còn hỗ trợ một FK tham chiếu, `TrialIndex.recover_drop()` nay kiểm metadata và từ chối trước DDL. `recover_interrupted_trials()` giữ proposal `pending`, báo `recovery_failed`; backend không nhận validation mới. Test DB giả chứng minh không gọi admin DDL trong trường hợp này.
- Chưa mở lại q01. Thiết kế tiếp theo cần lưu định nghĩa index hỗ trợ FK trước khi tạo trial và chứng minh được cách khôi phục qua mọi điểm ngắt DDL trên lab riêng. Không dựng lại index chỉ theo tên FK. Trong lượt này không khởi động MySQL/Dashboard thật, không tạo/drop index.

---

## Kiểm chứng Validation trên lab 5M dòng ngày 25/11/2026

- Chỉ dùng hai lab tách biệt: validation lab cổng 3309 có đủ 5 bảng/tổng 5.000.000 dòng (customers 500.000, addresses 500.000, products 50.000, orders 1.500.000, order_items 2.450.000); write lab cổng 3308 giữ 0 dòng. DB chính cổng 3307 chỉ kiểm bằng truy vấn đọc, không chạy DDL hoặc nạp dữ liệu trong lượt này.
- q01: index thử `order_items(product_id, quantity, unit_price)` đã đo xong nhưng MySQL tự bỏ index `fk_order_items_product` hỗ trợ khóa ngoại; lần dọn đầu bị lỗi 1553. Đã xác minh định nghĩa/marker index thử, tạo lại index hỗ trợ FK trên **validation lab**, rồi dọn index thử và xác nhận FK còn nguyên. Report `passed` cũ trong SQLite lab chỉ là bằng chứng sự cố, **không đủ điều kiện duyệt**. Bằng chứng: `data/outputs/lab_only_full5m_q01_cleanup_incident_20261125.json` (gitignored).
- Đã thêm chặn trước DDL cho proposal có tiền tố cột trùng FK tham chiếu. q01 chạy lại trả `inconclusive/foreign_key_support_risk` và không tạo index; `ProposalStore` giữ nguyên lý do này. Bằng chứng: `data/outputs/lab_only_full5m_q01_guard_20261125.json`. Cần thiết kế cách giữ index hỗ trợ FK trước khi hỗ trợ lại trường hợp này.
- q05 với SQL gốc và index thử `order_items(unit_price, product_id, quantity)` trả `passed`, `evidence_complete=true`, hash/số dòng khớp, 20/20 lượt đo mỗi bên, không timeout; P95 **2872,51 → 1051,51 ms** (giảm **63,39%**), index khoảng **91.963.392 byte**, INSERT throughput thay đổi **−16,19%** trên write lab. Index thử đã dọn sau report; report lab không dùng để cấp approval token. Bằng chứng: `data/outputs/lab_only_full5m_q05_20261125.json` và SQLite cùng tên (gitignored).
- Kiểm lại sau cùng: validation lab vẫn đủ 5M dòng, write lab 0 dòng, DB chính đủ 5M dòng; `fk_order_items_product` VISIBLE ở cả ba, không còn index thử q01/q05 trên hai lab. **257 tests pass**, Ruff pass cho Python đã sửa, `git diff --check` pass. Validation Layer vẫn **Đang làm**: mới thử q05 và nhánh chặn q01 trên lab 5M, chưa kiểm đủ 30 proposal, chưa nối Tool 6/Dashboard end-to-end.
- Đã dừng đúng hai container `write_lab_db` và `validation_lab_db` sau phép đo; volume và file bằng chứng được giữ nguyên. Lần dừng đầu bị hệ thống duyệt tự động từ chối do hạn mức tạm thời, lần thử lại sau 14:38 đã thực thi thành công.

---

## Thử recovery từ chối marker sai trên validation lab ngày 25/11/2026

- Chỉ chạy trên `validation_lab_db` cổng 3309, có marker riêng và 200.000 dòng `orders`. Tạo SQLite lab `data/outputs/lab_only_recovery_wrong_marker_20261125.sqlite3` với trial `pending`, rồi tạo index `INVISIBLE` trùng tên/định nghĩa nhưng mang marker khác `mcp_trial:<proposal_id>`.
- `dashboard.backend.initialize_backend()` từ chối khởi động; index marker lạ vẫn còn nguyên và SQLite vẫn `pending`, không có report. Sau khi xác minh marker đúng là của phép thử này, dọn thủ công index đó **chỉ trên lab**, gọi khởi tạo lại: trial chuyển `cleaned`, report `inconclusive/interrupted`. Bằng chứng ở `data/outputs/lab_only_recovery_wrong_marker_20261125.json` (gitignored).
- Kiểm sau cùng: index thử không còn ở validation lab hoặc DB chính; lab vẫn 200.000 dòng, DB chính cổng 3307 vẫn 1.500.000 dòng `orders`. Đã dừng container lab, giữ volume và bằng chứng. Lượt kiểm đầu báo fail giả do chuỗi tiếng Việt trong lệnh thử qua console Windows khác bảng mã; kiểm lại bằng loại lỗi và proposal ID ASCII cho kết quả đúng, không sửa code recovery.
- Đây là kiểm chứng nhánh từ chối an toàn trên lab mẫu; chưa kiểm toàn bộ bộ 5M. Validation Layer vẫn **Đang làm**.

---

## Thử recovery sau gián đoạn trên validation lab ngày 25/11/2026

- Chỉ khởi động lại `validation_lab_db` cổng 3309, xác nhận marker `mcp-validation-lab-v1`, 200.000 dòng `orders` và index thử chưa tồn tại. DB chính cổng 3307 được kiểm bằng tài khoản đọc, có 1.500.000 dòng `orders`.
- Trong tiến trình thứ nhất, tạo proposal/index thử `INVISIBLE` với marker `mcp_trial:<proposal_id>` và ghi `trial_state=pending` vào SQLite lab `data/outputs/lab_only_recovery_20261125.sqlite3`; cố ý kết thúc tiến trình trước khi lưu report để mô phỏng lần Validation bị ngắt. Trong tiến trình thứ hai, `dashboard.backend.initialize_backend()` gọi recovery: dọn đúng index thử, chuyển trạng thái sang `cleaned`, lưu report `inconclusive` với `failure_reason=interrupted`. Gọi khởi tạo lần nữa không còn trial pending; không chạy DDL lặp lại.
- Xác nhận sau recovery: index thử không còn trên validation lab hoặc DB chính; lab vẫn 200.000 dòng, DB chính vẫn 1.500.000 dòng. Bằng chứng `data/outputs/lab_only_recovery_20261125.json` và SQLite lab được giữ (gitignored); container lab đã dừng, volume không xóa.
- Đây là **mô phỏng gián đoạn giữa hai tiến trình**, có tạo/drop index thật chỉ trên lab. Chưa chứng minh xử lý mọi kiểu crash hoặc kết quả trên bộ 5M; Validation Layer vẫn **Đang làm**.

---

## Thử backend Validation trên lab riêng ngày 25/11/2026

- Khởi động hai service riêng từ `docker-compose.write-lab.yml`: write lab cổng 3308 có marker `mcp-write-lab-v1`, validation lab cổng 3309 có marker `mcp-validation-lab-v1`. Nạp 200.000 dòng đầu `orders.csv` vào validation lab; write lab giữ bảng `orders` rỗng. DB chính cổng 3307 không nhận DDL/INSERT từ lượt này.
- Gọi `dashboard.backend.initialize_backend()` rồi `validate_proposal()` trên SQLite lab riêng `data/outputs/lab_only_backend_validation_20261125_110918.sqlite3`, với proposal thử `orders(status ASC, order_date ASC)` và SQL SELECT mẫu ngoài 30 query catalog. Report trong `data/outputs/lab_only_backend_validation_20261125_110918.json` trả `passed`, `evidence_complete=true`, hash/số dòng khớp, 20/20 lượt mỗi bên, không timeout; P95 **63,70 → 10,53 ms** (giảm **83,47%**), EXPLAIN chọn index thử. Dung lượng ước lượng **6.832.128 byte** từ `innodb_index_stats_pages`; INSERT throughput thay đổi **−22,31%** trên write lab.
- Sau report, đã dọn index thử bằng marker và xác nhận nó không còn trên validation lab; write lab vẫn 0 dòng, validation lab 200.000 dòng, DB chính vẫn 1.500.000 dòng `orders` và không có index thử. Đã dừng hai container lab, **giữ nguyên volume và file bằng chứng**. SQLite lab còn report `passed` nhưng index đã dọn: chỉ là bằng chứng lab, tuyệt đối không dùng để cấp approval token.
- Đây là kiểm chứng đường backend mới trên mẫu 200.000 dòng, chưa phải validation bộ 5M hoặc kiểm recovery DDL khi tiến trình thật bị ngắt. Chặng Validation Layer vẫn **Đang làm**.

---

## Nối đường gọi Validation với store runtime ngày 25/11/2026

- `dashboard.backend.validate_proposal()` nhận đúng `ProposalStore` do `initialize_backend()` trả về và chuyển tiếp cùng `proposal_id`, `write_csv_dir` cho `validate_saved_index()`. `dashboard/app.py` giữ store đã recovery trong `proposal_store` để caller giao diện sau này dùng lại, tránh mở một SQLite khác.
- Test giả xác nhận thứ tự recovery trước validation, dùng cùng đối tượng/path và chuyển đủ tham số. Giao diện hiện chưa có thao tác kích hoạt Validation; không chạy MySQL hoặc tạo/drop index trong lượt này.

---

## Nối recovery khi Dashboard khởi động ngày 25/11/2026

- `dashboard/app.py` mở store runtime `data/outputs/proposals.sqlite3` qua `dashboard/backend.py` và gọi `recover_interrupted_trials()` trước khi tiếp tục. Streamlit cache kết quả khởi tạo để không lặp recovery ở mỗi lần rerun; nếu có trial `recovery_failed`, Dashboard dừng, không nhận việc mới.
- Hàm recovery chỉ xét proposal có `trial_state=pending`; `TrialIndex.recover_drop()` chỉ dọn index còn INVISIBLE với marker và định nghĩa đúng proposal. Dọn thành công hoặc index đã vắng thì lưu report `inconclusive/interrupted`; lỗi để lại `pending` cho lần kiểm tra sau. Caller validation runtime phải dùng cùng đường dẫn store, còn store lab riêng không tự được quét.
- 4 test mới dùng store/trial/Streamlit giả; chưa khởi động Dashboard với MySQL thật hoặc tạo/drop index để thử. Các chặng Tool 6, Dashboard 4 tab và Validation trên bộ 5M vẫn chưa Done.

---

## Chốt thiết kế contract v2 ngày 25/11/2026

- Theo ủy quyền của người dùng thay nhóm review, đã đối chiếu contract với registry Tool 1–5, parser LLM, Validation Layer, proposal store, helper DDL và test hiện có; chốt giao diện v2 làm mốc cho caller. Đây không phải chữ ký riêng của từng thành viên hoặc GVHD.
- Đồng bộ tình trạng `mysql.slow_log` đã thử với quyền đọc riêng trên lab; giữ rõ Tool 6/approval token/Dashboard là thiết kế chưa triển khai. Report Validation từ lab đã dọn index không được dùng để cấp token trên DB khác hoặc khi index thử không còn.
- Kiểm tra lại: working tree sạch trước khi sửa tài liệu; 249 unit tests pass và audit bằng chứng ground truth 30/30 pass. Không chạy lại MySQL/Dashboard thật trong lượt chốt contract. Validation Layer, LLM metric 30 query, Tool 6 và Dashboard vẫn theo trạng thái riêng ở bảng trên.

---

## Kiểm chứng ngày 21/11/2026

- Dataset `shopdb.multitable-v1`: customers 500.000, addresses 500.000, products 50.000, orders 1.500.000, order_items 2.450.000; tổng 5.000.000 dòng. Bộ `sales_data` cũ đã được thay thế.
- Baseline hiện tại: `data/outputs/p95_baseline_multitable_raw.json`, 30/30 valid, SQL khớp `data/queries/queries.py`. Lỗi q23 ngày 19/10 thuộc bộ cũ, không phải blocker của bộ hiện tại.
- `data/queries/ground_truth.json`: 30/30 có phương án đạt kiểm chứng. Đủ 3 warm-up + 20 lượt đo, không timeout, hash/số dòng khớp và P95 giảm ≥20%; một số trường hợp dùng lại baseline đã đo, một số đo lại trước tối ưu. Không gọi đây là kết quả đo đồng thời hoặc tối ưu toàn cục.
- q07–q12: đã đo đối chứng hoán đổi thứ tự cùng tập cột, giữ cùng SQL ngoài tên index thử. Các đáp án có `rewritten_sql`, `requires_rewrite` hoặc `required_indexes` cần dùng đủ SQL/hint và index.
- Index `gt_trial_*` đã dọn, cấu hình index ban đầu đã khôi phục. `idx_gt_q01_cover` còn INVISIBLE như trước batch; `fk_order_items_product` vẫn VISIBLE.
- Kiểm tra bằng chứng `scripts/verify_ground_truth.py --check`: 30/30 pass. Toàn bộ unit tests: 125 pass, người dùng cũng đã xác nhận trên PowerShell với thư mục tạm riêng.
- Trạng thái: `performance_verified_pending_review`, reviewer Hải, `gvhd_signature=null`. Script lab không thay thế Hải review hoặc Validation Layer/Human-in-the-loop của hệ thống.
- Chưa đo đầy đủ index size/chi phí ghi, metric LLM và baseline truyền thống. Chưa xác nhận luồng MCP–LLM–Dashboard end-to-end. Trạng thái `server.py` và Tool 1–3 xem cập nhật ngày 22/11 bên dưới.
- Dữ liệu giả có phân bố khá đều và tương quan city/status; cần nêu giới hạn này trong báo cáo, chưa coi là mô phỏng đủ tải Black Friday.

Lệnh kiểm tra không chạy lại DB và cách chạy pytest trên Windows xem [setup-guide](../docs/setup-guide.md#7-kiểm-tra-test-và-bằng-chứng).

---

## Kiểm chứng ngày 22/11/2026

- Tool 1 `get_slow_queries` đã đọc được digest thật qua `performance_schema` bằng `readonly_user`; hiện không có digest đạt ngưỡng trung bình 500 ms. Chưa đăng ký vào MCP.
- Tool 2 `get_schema` đã trả cấu trúc của đủ 5 bảng từ `information_schema` qua `readonly_user`: cột, index visible/invisible và khóa ngoại. Comment cột được thay bằng nhãn dữ liệu không tin cậy. Kích thước từng index trả `null` vì tài khoản đọc không có quyền truy cập `mysql.innodb_index_stats` (lỗi 1142); contract đã ghi rõ. Chưa đăng ký vào MCP.
- 135 unit tests pass; Ruff pass. `server.py` và Tool 3 vẫn là khung, nên chặng Tool 1–5 MCP chưa Done.

### Đồng bộ contract v2 trong ngày 22/11/2026

- `docs/api-contract.md` v2 là bản DRAFT chờ nhóm review; `docs/architecture.md` vẫn giữ để mô tả luồng và được cập nhật theo contract. `ROADMAP.md` ghi rõ các điểm kỹ thuật đang chờ review.
- Tool 1 bổ sung `source=performance_schema` trong kết quả. Tool 2 ghi rõ `size_bytes=null` nếu không đo được dung lượng từng index. Tool 4–5 có wrapper giới hạn tham số cho LLM; Tool 5 trả `MEASUREMENT_INVALID` khi số lượt đo chưa đủ hoặc thiếu hash bắt buộc.
- 139 unit tests pass sau thay đổi. `server.py`, Tool 3, LLM agent, Validation Layer, Tool 6 và Dashboard vẫn là khung; wrapper Tool 4–5 chưa đăng ký MCP. Chưa chạy lại đo thực nghiệm MySQL hoặc Dashboard trong lần đồng bộ này.
- Ruff toàn bộ file Python đã sửa còn 13 lỗi định dạng/quy tắc có sẵn ở Tool 4–5; không thay logic của hai tool chỉ để sửa style trong lượt đồng bộ contract này.

### Tool 3 trong ngày 22/11/2026

- `get_table_stats` đã triển khai độc lập theo contract v2: ước lượng từ `information_schema.TABLES`, 10 cửa sổ PK tối đa 100 dòng/cửa sổ, gộp theo PK và tính thống kê trên mẫu. Không dùng `COUNT(*)` hay `ORDER BY RAND()` toàn bảng. Chỉ trả top values của cột phân loại cho phép; cắt ký tự điều khiển/độ dài và gắn `untrusted: true`.
- 9 test mới pass; toàn bộ 148 test pass, Ruff pass ở `stats.py` và test mới. Gọi read-only trên MySQL thật cho `orders(status, order_date)` và `addresses(city)` đều `ok=true`, mỗi bảng thu được mẫu 1.000 dòng. Số dòng từ `TABLE_ROWS` là ước lượng, không phải đếm chính xác.
- Chưa đăng ký Tool 3 vào MCP; `server.py` vẫn là khung. Chặng Tool 1–5 MCP tiếp tục ở trạng thái Đang làm.

### Registry MCP trong ngày 22/11/2026

- `server.py` dùng MCP SDK 2.x (`MCPServer`) để đăng ký Tool 1–3 và hai wrapper LLM của Tool 4–5, cùng tên public `explain_query` và `benchmark_query`. Tool 6 và hàm Tool 4–5 đầy đủ tham số không nằm trong registry LLM.
- Test registry kiểm tra đúng 5 tên và schema Tool 4–5 chỉ có `sql`. Đã thử client/server qua stdio thật: liệt kê đúng 5 tool, input sai của Tool 1 nhận `INVALID_INPUT`; sau đó gọi cả 5 tool bằng input đọc giới hạn trên MySQL thật, tất cả trả `ok=true`. Toàn bộ 150 test pass; Ruff pass cho `server.py` và test mới. Chưa thử host LLM, Dashboard hoặc Tool 6.

---

## Validation Layer ngày 24/11/2026

- Đã có bước đánh giá report thuần Python: chỉ pass khi đo đủ số lượt từ `config/settings.yaml` (hiện 20/20), không timeout, hash/số dòng khớp, P95 giảm ít nhất ngưỡng config (hiện 20%), EXPLAIN chọn index mới và có bằng chứng dung lượng/chi phí ghi trên lab riêng. Report thiếu hoặc dùng SQL viết lại trả `inconclusive`; sai kết quả hoặc chậm trả `failed`.
- `validate_index()` gọi Tool 4/5 nội bộ với index INVISIBLE tắt/bật, ghép Query Cost và số đo, dọn index thử khi fail/lỗi. Helper `TrialIndex` sinh DDL từ proposal có cấu trúc, kiểm tra schema hiện tại, dùng `index_admin` chỉ cho CREATE/DROP, dùng `readonly_user` cho metadata. Chưa đăng ký helper thành MCP tool.
- `ProposalStore` lưu proposal/report bất biến trong SQLite riêng; `validate_saved_index()` lấy SQL gốc từ store, ghi `trial_state=pending` trước DDL, đo rồi lưu report. Index thử gắn `mcp_trial:<proposal_id>` trong `INDEX_COMMENT`; `recover_interrupted_trials()` chỉ dọn index có đúng marker, định nghĩa cột và trạng thái INVISIBLE, rồi ghi report `inconclusive` nếu lần thử bị ngắt. Lỗi dọn giữ trạng thái `pending` để thử lại/kiểm tra.
- Test dùng DB/Tool giả: chưa tạo/drop index trên MySQL thật, chưa đo INSERT trên clone riêng, chưa nối hàm recovery vào điểm khởi động backend, chưa tích hợp Dashboard/Tool 6. Do đó **chưa Done**, chưa có report thật đủ điều kiện phê duyệt.
- Kiểm tra sau bước recovery: 237 unit tests pass, Ruff pass trên các file Python đã sửa, `git diff --check` pass.

### Write lab và phép đo INSERT ngày 24/11/2026

- `docker-compose.write-lab.yml` tạo MySQL riêng tại `127.0.0.1:3308`, volume riêng và marker trong `db/write_lab_marker.sql`; đã khởi động và kiểm marker thật. DB chính vẫn ở cổng 3307. Mật khẩu lab nằm trong `.env.write-lab` cục bộ, đã gitignore.
- `write_overhead.py` tạo hai bảng TEMPORARY từ schema cùng bảng, preload cùng 100.000 dòng đầu từ CSV, thêm index INVISIBLE vào một bảng, rồi đo INSERT cùng 100.000 dòng tiếp theo vào cả hai. Hàm kiểm marker, schema/header và dùng đúng số dòng từ config. `validate_saved_index()` có đường gọi phép đo này qua `write_csv_dir`; report kiểm tốc độ trước/sau, số dòng và tỷ lệ phần trăm nhất quán.
- Đã đo thật **một phương án mẫu**, `orders(status ASC, order_date ASC)`, bằng script offline; bằng chứng ở `data/outputs/write_overhead_orders_status_date_20261124.json` (gitignored). Lượt lưu: trước 56.422,54 dòng/giây (1,772 s), sau 46.501,17 dòng/giây (2,150 s), thay đổi throughput **−17,58%**. Một lượt thăm dò trước đó cho −19,21%; chưa dùng các lượt này làm kết luận tổng quát.
- Lab chỉ sao chép schema và dùng 200.000 dòng mẫu đầu CSV, không nạp toàn bộ 5M; bảng tạm không sao chép FOREIGN KEY. Sau phép đo, lab `orders` vẫn 0 dòng và không còn bảng scratch; DB chính `orders` vẫn 1.500.000 dòng. Chưa đo đủ mọi bảng/phương án, chưa chạy Validation end-to-end tạo index thật trên DB chính, chưa có số dung lượng index cho proposal này.
- Sau khi lưu bằng chứng, đã dừng rồi xóa riêng container/network/volume `mcp-write-lab_write_lab_data` theo yêu cầu người dùng; `docker volume inspect` xác nhận volume không còn. File bằng chứng trong `data/outputs/` vẫn giữ; container DB chính vẫn `running/healthy`. Lần chạy write lab sau sẽ tạo volume mới và khởi tạo schema/marker lại.
- Toàn bộ 242 unit tests pass sau thay đổi; Ruff và `git diff --check` được chạy cho file đã sửa.

### Rà lại Validation Layer ngày 25/11/2026

- Sửa kiểm chứng EXPLAIN cho JOIN: Tool 4 vẫn trả `key_used` của bảng đầu tiên, còn Validation Layer đọc `raw_plan` để xác nhận index mới nằm trên đúng bảng của proposal, kể cả bảng ở vị trí sau. Alias dùng lại cho bảng khác trả `inconclusive`. `ProposalStore.save_report()` kiểm lại bằng SQL gốc và tên bảng đã lưu; caller lưu report cần giữ `after.raw_plan`.
- Khôi phục `docker-compose.write-lab.yml` mà setup guide tham chiếu; `docker compose ... config --quiet` hợp lệ. Không khởi tạo lại volume lab đã xóa theo yêu cầu người dùng.
- Toàn bộ **244 unit tests pass**; Ruff cho Python đã sửa và `git diff --check` pass. Lần EXPLAIN q07 đầu tiên bị từ chối kết nối (WinError 10061); thử lại khi cổng 3307 sẵn sàng thì `ok=true`. Plan thật có `orders` alias `o` không chọn index và `addresses` alias `a` dùng `fk_addresses_customer`; helper xác nhận index thuộc `addresses`, không gán nhầm cho `orders`. Đây là kiểm chứng chỉ đọc với index sẵn có, chưa tạo/drop index thật hoặc chạy validation end-to-end; chặng vẫn **Đang làm**.

### Thử end-to-end trên hai lab riêng ngày 25/11/2026

- Dựng `write_lab_db` cổng 3308 và `validation_lab_db` cổng 3309, mỗi service có marker/volume riêng; nạp 200.000 dòng `orders` từ CSV vào validation lab. DB chính cổng 3307 vẫn có đúng 1.500.000 dòng `orders`. Proposal thử là `orders(status ASC, order_date ASC)` trên SQL gốc chỉ đọc, không thuộc 30 query catalog; mục tiêu là kiểm luồng, không chấm ground truth.
- Lần thử dùng chung một DB cho index đọc và đo INSERT trả `inconclusive/measurement_error`: phép đo INSERT đúng ra phải chạy trên DB riêng có bảng gốc chưa mang index đề xuất. Sau khi tách hai service, lượt đo đọc/hash/INSERT thành công nhưng `INDEX_LENGTH` chưa cập nhật, nên code mặc định trả `inconclusive/write_evidence_incomplete` và tự dọn index. Bằng chứng ở `data/outputs/validation_lab_20261125_095725.json`.
- Lượt kiểm chứng lab dùng root **chỉ ở validation lab** chạy `ANALYZE TABLE orders` trước và sau khi tạo index để làm mới thống kê, không đổi quyền `index_admin` hoặc code mặc định. Report SQLite/JSON `passed`, 20 lượt mỗi bên, P95 **72,53 → 19,38 ms** (giảm 73,28%), hash/số dòng khớp, EXPLAIN chọn index đề xuất, dung lượng tăng ước lượng **6.832.128 byte**, INSERT throughput thay đổi **−20,27%**. Bằng chứng ở `data/outputs/validation_lab_20261125_100015.json`; index thử đã dọn bằng marker sau khi ghi report. Report này **chỉ là lab evidence**, không được dùng để cấp approval token vì index đã dọn và dữ liệu chỉ là mẫu 200.000 dòng.
- MySQL [yêu cầu `SELECT` và `INSERT` cho `ANALYZE TABLE`](https://dev.mysql.com/doc/refman/8.0/en/analyze-table.html). Do đó chưa có cách làm mới thống kê dung lượng với quyền `index_admin` hiện tại trên DB chính; không nới quyền chỉ để ép report `passed`. Validation Layer vẫn **Đang làm** cho đường runtime chung và chưa nối Dashboard/Tool 6.
- Đã xác nhận main `orders` vẫn 1.500.000 dòng; cả hai lab đều không còn index thử. Sau khi lưu JSON/SQLite bằng chứng (gitignored), đã `docker compose -p mcp-write-lab ... down -v`: xóa đúng hai container, hai volume và network lab; không xóa volume DB chính. SQLite lab còn report `passed` nhưng index lab đã dọn và volume đã xóa, nên **không dùng SQLite này làm nguồn phê duyệt runtime**.

### Sửa nguồn đo dung lượng ngày 25/11/2026

- Lab 200.000 dòng cho thấy `TABLES.INDEX_LENGTH` đứng yên sau `CREATE INDEX` và `INNODB_TABLESPACES.ALLOCATED_SIZE` tăng 4.194.304 byte ở lượt đầu, nhưng bằng 0 khi tạo lại index và InnoDB tái dùng chỗ trống. Không dùng mức tăng file làm bằng chứng duy nhất cho mọi lượt.
- `TrialIndex.size_delta()` giờ ưu tiên số trang `size` của đúng index trong `mysql.innodb_index_stats` nhân `@@innodb_page_size`. `index_admin` cần `SELECT` riêng trên bảng stats; `db/init.sql` đã thêm grant cho volume tạo mới, **DB chính đang tồn tại chưa được cấp grant này**. Thiếu quyền 1142/hàng stats thì thử chênh lệch `INDEX_LENGTH`, rồi tăng trưởng `ALLOCATED_SIZE` của file riêng; không có số dương vẫn `inconclusive`. Report có `index_size_source` đúng nguồn; callback đo dung lượng nội bộ đổi từ số nguyên sang object `{index_size_bytes, index_size_source}`.
- Trên validation lab, đã cấp grant hẹp cho `index_admin` và xác nhận **hai lượt tạo/xóa cùng index** đều đọc 417 trang = 6.832.128 byte mà không chạy `ANALYZE TABLE`. Lượt `validate_saved_index()` bằng code mặc định trả `passed`: P95 **67,54 → 15,16 ms**, 20 lượt mỗi bên, hash/số dòng khớp, EXPLAIN chọn index, INSERT throughput **−17,32%**. Bằng chứng `data/outputs/validation_lab_20261125_102218.json` (gitignored); index thử đã dọn. Đây vẫn là mẫu lab, không phải bằng chứng áp dụng trên DB chính hoặc 30 query catalog.
- Toàn bộ **249 unit tests pass**, Ruff pass cho Python đã sửa, `git diff --check` pass. DB chính `orders` vẫn 1.500.000 dòng và kết nối được sau khi dọn; hai volume/container `mcp-size-lab` đã xóa, bằng chứng trong `data/outputs/` vẫn giữ. Chặng Validation Layer vẫn chưa Done vì chưa kiểm trên 5M lab, chưa nối recovery vào backend và chưa tích hợp Dashboard/Tool 6.

## Kiểm chứng ngày 24/11/2026 — LLM host

- `agent.py` có vòng gọi Tool 1–5, retry JSON và hash run; `parsers.py` kiểm JSON Schema cùng schema Tool 2. Adapter `llm/groq.py` đổi messages/tool calls sang Groq; model thử nghiệm ghim `openai/gpt-oss-120b` trong `config/settings.yaml`.
- LLM giả + MCP giả/registry/stdio: 207 test toàn bộ pass, Ruff pass cho file Python đã sửa. Một lần thử Groq API thật với **tool mẫu** nhận `tool_use`, gửi kết quả mẫu rồi nhận phản hồi cuối; không gọi MySQL.
- Groq đã nhận schema Tool 1–5 thật; Tool 2 đọc schema MySQL qua `readonly_user`. Với q07: hai lượt prompt v1 `parse_failed` vì `columns[0]` sai kiểu; prompt v2 thêm ví dụ cấu trúc cột. Một lượt v2 lỗi HTTP 400 sau Tool 2, một lượt v2 parse thành công với 2 index (`orders(status, order_date, customer_id, total_amount)` và `addresses(customer_id, city)`) cùng 1 rewrite. Tập cột index trùng đáp án q07, nhưng chưa đối chiếu hướng cột/rewrite đầy đủ, chưa chạy Validation Layer hoặc đo hiệu năng. Không dùng 4 lượt này để tính metric ổn định vì prompt version khác nhau.
- Chưa chạy đủ 30 query/metric LLM; Validation Layer và Tool 6 vẫn chưa triển khai.

### Kiểm tra lại q07 ngày 24/11/2026

- Bốn lượt mới qua Python host → Groq → MCP → MySQL với `readonly_user` đều trả JSON hợp lệ, mỗi lượt có 3 proposal; ba lượt gọi Tool 2, một lượt gọi thêm Tool 3. Không tạo/drop index hoặc sửa dữ liệu MySQL.
- HTTP 400 cũ không tái hiện. Bản ghi cũ chỉ có `BadRequestError`, không có mã/body lỗi nên chưa xác định nguyên nhân. `agent.py` nay ghi HTTP status, loại/mã lỗi API và dấu hiệu `failed_generation` khi có, nhưng không ghi nội dung phản hồi hoặc SQL.
- Toàn bộ 208 unit tests pass; Ruff pass cho `agent.py` và test mới. Bốn lượt này chưa đủ để tính độ ổn định, Precision/Recall hoặc kiểm chứng hiệu năng proposal; chưa chạy Validation Layer hay đủ 30 query.

### Tool 1 đọc slow log ngày 24/11/2026

- `get_slow_queries` có tham số `source="slow_log"` tùy chọn; mặc định vẫn đọc `performance_schema`. Nhánh mới chỉ dùng `get_conn()`/`readonly_user`, giới hạn 5 giây, `limit+1` dòng và SQL tối đa 8.000 byte, bỏ comment rồi gắn `untrusted: true`. Mỗi dòng log là một lần chạy, nên `p95_latency_ms=null` và `digest=null`; chi tiết ở contract v2 DRAFT.
- Test giả kiểm tra kết quả, giới hạn và lỗi thiếu quyền. Trước khi cấp quyền, MySQL trả `FORBIDDEN`. Người dùng đã cấp `SELECT` riêng trên `mysql.slow_log` cho `readonly_user` tại lab; gọi trực tiếp và qua MCP stdio với `source="slow_log", limit=1` đều `ok=true`, trả 1 bản ghi thật có `untrusted=true`, `p95_latency_ms=null`. Nguồn mặc định `performance_schema` vẫn `ok=true`, hiện không có digest đạt ngưỡng 500 ms. Không in SQL log trong lần kiểm tra. Chặng Tool 1–5 MCP vẫn Đang làm vì chưa kiểm chứng toàn bộ tiêu chí roadmap.
- Toàn bộ 211 unit tests pass; Ruff pass cho file Python đã sửa. Không chạy lại `db/init.sql`, không sửa index hoặc dữ liệu lab.

### Kiểm chứng Tool 1–5 qua MCP stdio ngày 24/11/2026

- Registry trả đúng 5 tên Tool 1–5, không có Tool 6; schema của Tool 4–5 chỉ nhận `sql`, Tool 1 có tham số `source` tùy chọn. Gọi Tool 1 ở cả `performance_schema` (0 digest đạt 500 ms) và `slow_log` (1 bản ghi thật), Tool 2 với `orders`, Tool 3 với `orders.status`, Tool 4 EXPLAIN và Tool 5 benchmark một truy vấn PK đọc một dòng: tất cả trả `ok=true` với envelope `ok/data/error/meta` đúng tên tool.
- Tool 4 dùng `mode=estimate`; Tool 5 đo 5 lượt theo wrapper LLM. SQL đọc từ log không được in trong lần kiểm tra. Toàn bộ 211 unit tests và Ruff pass. Đây là kiểm chứng kỹ thuật cho Tool 1–5; contract v2 vẫn DRAFT chờ review, Tool 6/Validation/Dashboard chưa triển khai, nên giai đoạn Tool 1–5 giữ trạng thái Đang làm chờ chốt review.

---

## 📅 CẬP NHẬT THEO TUẦN

Các kết quả và lỗi dưới đây được giữ theo thời điểm thực hiện; trạng thái hiện tại xem cập nhật 24/11 ở trên.

### 🗓️ Tuần 1 (23/09 – 29/09) — ✅ DONE

| Việc                                 | Người | Trạng thái | Ghi chú                     |
| ------------------------------------ | ----- | :--------: | --------------------------- |
| Tạo repo GitHub                      | Vũ    |     ✅     | Đã push `main` + `dev`      |
| Cấu trúc thư mục                     | Vũ    |     ✅     | 70 file + 20 thư mục        |
| `docker-compose.yml`                 | Hải   |     ✅     | MySQL 8.0 chạy được         |
| MySQL + bật slow log                 | Hải   |     ✅     | `long_query_time = 0.5`     |
| User `readonly_user` + `index_admin` | Hải   |     ✅     | Quyền đúng, đã verify       |
| Test quyền readonly                  | Tình  |     ✅     | DDL bị chặn                 |
| Streamlit skeleton                   | Tình  |     ✅     | `app.py` chạy được          |
| ROADMAP v2 + 4 file .md              | Vũ    |     ✅     | Trong `project-management/` |

---

### 🗓️ Tuần 2 (30/09 – 06/10) — ✅ DONE

| Việc                              | Người        | Trạng thái | Ghi chú                       |
| --------------------------------- | ------------ | :--------: | ----------------------------- |
| Import dataset sales_data 5M dòng | Hải          |     ✅     | Từ CSV, có `_raw` cho ngày    |
| Verify 5M dòng + fix NULL date    | Hải          |     ✅     | `order_date`, `ship_date` OK  |
| Chốt `api-contract.md`            | Vũ + cả nhóm |     ✅     | 6 tool, có IndexProposal      |
| Chốt `architecture.md`            | Vũ           |     ✅     | Có Mermaid, 6 lớp bảo mật     |
| `docs/setup-guide.md`             | Hải          |     ✅     | Có hướng dẫn từ A-Z           |
| utils/config.py, db.py, logger.py | Vũ + Hải     |     ✅     | Đã verify import + kết nối DB |
| 30 query + ground_truth.json      | Tường        |     ✅     | 30/30 query pass (> 0.5s)     |
| `scripts/verify_setup.py`         | Vũ           |     ✅     | Verify setup chạy được        |

**Done tuần 2:** CSDL 5M dòng OK · slow log có query · contract + architecture đã chốt · 30 query pass.

---

### 🗓️ Tuần 3 (07/10 – 13/10) — 🟡 ĐANG LÀM

| Việc                              | Người       | Trạng thái | Ghi chú                                |
| --------------------------------- | ----------- | :--------: | -------------------------------------- |
| **AST whitelist + 47 unit tests** | Tình        |     ✅     | 47/47 test pass                        |
| **Tool 4 `explain_query`**        | Hải         |     ✅     | 7/7 test pass                          |
| **Tool 5 `benchmark_query`**      | Tường       |     ✅     | 7/7 test pass                          |
| Tool 1 `get_slow_queries`         | Vũ          |     🟡     | Có code + 11 unit tests; chờ thử MySQL và đăng ký MCP |
| Tool 2 `get_schema`               | Vũ          |     ⬜     | Sau Tool 1                             |
| Tool 3 `get_table_stats`          | Vũ          |     ⬜     | Sau Tool 2                             |
| `mcp_server/server.py`            | Vũ          |     ⬜     | Đăng ký 5 tool — sau khi xong Tool 1-3 |
| Đo P95 cho ground truth           | Hải         |     ✅     | Đã đo 30/30: 29 valid, q23 timeout     |
| Nháp chương "Cơ sở lý thuyết"     | Vũ          |     ⬜     | Song song                              |

**Checklist cuối tuần 3:**

- [x] `security/ast_whitelist.py` (47 tests)
- [x] `mcp_server/tools/explain.py` (7 tests)
- [x] `mcp_server/tools/benchmark.py` (7 tests)
- [ ] `mcp_server/tools/slow_queries.py` — có code và unit tests; chưa thử MySQL thật/đăng ký MCP
- [ ] `mcp_server/tools/schema.py`
- [ ] `mcp_server/tools/stats.py`
- [ ] `mcp_server/server.py`

**Vấn đề gặp phải:**

- ⚠️ `readonly_user` không có quyền `RELOAD` → không dùng được `FLUSH STATUS`
  → Fix: Tool 5 bỏ `FLUSH STATUS`, tính chênh lệch tổng `Handler_read*` trước/sau từng lượt.
- ⚠️ `fetchall()` giữ toàn bộ kết quả lớn trong RAM và số đếm Handler bị cộng dồn
  → Fix: Hải sửa Tool 5 dùng `SSDictCursor` đọc theo lô; hash chạy riêng và sort trên SQLite tạm.
- ⚠️ q23 trả khoảng 1.250.007 dòng, 4/20 lượt timeout ở lần xác nhận
  → Giữ `INVALID`; không dùng P95 của 16 lượt thành công, không tăng timeout quá 60000 ms.
- ⚠️ `sqlglot` version mới không có `exp.Explain`
  → Fix: Tool 4 + AST whitelist xử lý EXPLAIN riêng bằng regex.
- ⚠️ Lỗi import `mcp_server` khi chạy file trực tiếp
  → Fix: Dùng `python -m mcp_server.tools.<tool>` hoặc script test ở root.

---

## 🚨 BLOCKERS

| #   | Vấn đề                                                                 | Người xử lý | Trạng thái       | Hạn   |
| --- | ---------------------------------------------------------------------- | ----------- | ---------------- | ----- |
| 1   | Xác nhận 30 query thực sự > 0.5s trên máy nhóm                         | Tường + Hải | ✅ Đã xác nhận   | 13/10 |
| 2   | Chọn LLM provider (Claude/Qwen/Fireworks) — vì Claude trả phí          | Vũ          | 🟡 Đang cân nhắc | 14/10 |
| 3   | Chữ ký GVHD cho ground_truth.json                                      | Tường       | ⬜ Chưa ký       | 20/10 |
| 4   | Case study dataset mới: q07, status/order_date và bộ index đi kèm | Tường + Hải | 🟡 Đã đo lab; chờ Hải review, chưa tái hiện tải Black Friday | 13/10 |

---

## 📈 CHỈ SỐ THEO DÕI

| Chỉ số                                             |       Hiện tại        |
| -------------------------------------------------- | :-------------------: |
| Tổng số dòng 5 bảng hiện tại                        |       5.000.000       |
| Số query trong slow log hiện tại                   | Chưa đếm lại          |
| Query xác nhận > 0.5s (trên 30)                    |       **30/30**       |
| Tool có triển khai và đã kiểm thử độc lập           | Tool 4–5; Tool 1 có unit tests, chờ tích hợp |
| Đăng ký tool vào MCP                               | `server.py` còn khung |
| Injection test pass                                | 47/47 (unit test AST) |
| Ground truth có chữ ký GVHD                        |         Chưa          |
| Precision / Recall (index)                         |           —           |
| Consistency Rate                                   |           —           |
| False Positive Rate                                |           —           |
| Đáp án lab đạt hash + P95 giảm ≥20%                 | 30/30, chờ duyệt      |
| Unit tests toàn bộ                                 | 125 pass              |
| Audit file bằng chứng                             | 30/30 pass            |
| Rewrite do LLM đề xuất đạt yêu cầu                 | Chưa đo               |

---

## 📝 NHẬT KÝ THAY ĐỔI

| Ngày  | Người   | Việc đã làm                                                            |
| ----- | ------- | ---------------------------------------------------------------------- |
| 23/09 | Vũ      | Tạo repo, push cấu trúc ban đầu                                        |
| 24/09 | Hải     | Setup MySQL + bật slow log                                             |
| 25/09 | Vũ      | Viết `docker-compose.yml`                                              |
| 26/09 | Tường   | Bắt đầu draft 30 query                                                 |
| 27/09 | Tình    | Test readonly user, DDL bị chặn OK                                     |
| 28/09 | Cả nhóm | Standup: đổi phân công (Vũ=Lead, Hải=DB, Tình=Security, Tường=Metrics) |
| 29/09 | Vũ      | ROADMAP v2, TEAM, PROGRESS, `api-contract.md` draft v1                 |
| 05/10 | Hải     | Import dataset sales_data 5M dòng, fix NULL date                       |
| 06/10 | Vũ      | Chốt api-contract + architecture + setup-guide                         |
| 07/10 | Tình    | AST whitelist + 47 unit tests pass                                     |
| 07/10 | Hải     | Tool 4 `explain_query` (7 tests pass)                                  |
| 07/10 | Tường   | Tool 5 `benchmark_query` bản đầu (7 tests pass)                        |
| 19/10 | Hải     | Sửa Tool 5 theo cơ chế streaming, hash riêng; test 7/7 pass            |
| 19/10 | Hải     | Đo P95 đủ 30 query: 29 valid, q23 timeout và giữ trạng thái INVALID    |
| 28/10 | Codex   | Tool 1 có code + 11 unit tests; toàn bộ 58 tests pass, Ruff pass; chưa thử MySQL thật hoặc đăng ký MCP |
| 21/11 | Người dùng + Codex | Chuyển lab sang 5 bảng/tổng 5M dòng; baseline 30/30 valid, 30 đáp án đạt P95/hash và chờ Hải review/GVHD ký; audit 30/30, unit tests 125 pass; dọn index thử và đồng bộ tài liệu |

---

## 📌 CÁCH CẬP NHẬT FILE NÀY

| Khi nào             | Cập nhật gì                                           | Ai làm    |
| ------------------- | ----------------------------------------------------- | --------- |
| Sau standup tối     | Đổi trạng thái việc đã xong                           | Vũ        |
| Gặp blocker mới     | Thêm dòng vào "Blockers"                              | Người gặp |
| Chủ nhật            | Thêm bảng "Tuần N+1", cập nhật % và "Chỉ số theo dõi" | Vũ        |
| Đổi phân công/scope | Ghi vào "Nhật ký thay đổi" **và** sửa ROADMAP         | Vũ        |

---

## 📞 LIÊN HỆ NHANH

| Vấn đề                                           | Liên hệ |
| ------------------------------------------------ | ------- |
| Điều phối, deadline, kế hoạch                    | Vũ      |
| MCP protocol, LLM API, Tool 1–3                  | Vũ      |
| MySQL, Docker, seed, Validation Layer, Tool 4    | Hải     |
| AST, injection, Tool 6, Dashboard                | Tình    |
| Ground truth, metrics, Tool 5, baseline, biểu đồ | Tường   |
