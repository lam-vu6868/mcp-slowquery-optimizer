# 📊 TIẾN ĐỘ DỰ ÁN

> **Cập nhật lần cuối:** 07/10/2026 — bởi Vũ (nhóm trưởng)
> **Tuần hiện tại:** Tuần 3/12
> **Tổng tiến độ:** 🟩🟩🟩⬜⬜⬜⬜⬜⬜⬜ **~27%**
>
> ⚠️ **File này chỉ ghi TRẠNG THÁI.** Deadline, người phụ trách và tiêu chí Done xem [ROADMAP.md](ROADMAP.md) (mục 4–5). Mục tiêu Precision/Recall/Consistency xem [ROADMAP.md](ROADMAP.md) mục 2.4.

**Chú thích:** ✅ Done | 🟡 Đang làm | ⬜ Chưa làm | 🔴 Trễ hạn | ⏸️ Tạm dừng

---

## 🎯 TỔNG QUAN CÁC GIAI ĐOẠN

|  #  | Giai đoạn                                            | Trạng thái  | Người chính      |          Deadline          |
| :-: | ---------------------------------------------------- | :---------: | ---------------- | :------------------------: |
|  0  | Setup môi trường                                     |   ✅ Done   | Vũ               |           28/09            |
| 0b  | Chốt thiết kế (`api-contract.md`, `architecture.md`) |   ✅ Done   | Vũ               |           06/10            |
|  1  | CSDL 5M records (dataset sales_data)                 |   ✅ Done   | Hải              |           05/10            |
|  2  | 30 query + ground truth                              |   ✅ Done   | Tường            | 06/10 (draft) · 20/10 (ký) |
|  3  | Tool 1–5 MCP                                         | 🟡 Đang làm | Vũ · Hải · Tường |           13/10            |
|  4  | Tích hợp LLM                                         |     ⬜      | Vũ               |           18/10            |
|  5  | Validation Layer                                     |     ⬜      | Hải              |           22/10            |
|  6  | Tool 6 + approval token + 20 injection               |     ⬜      | Tình             |           27/10            |
|  7  | Metrics + Baseline                                   |     ⬜      | Tường · Hải      |           03/11            |
|  8  | Dashboard 4 tab                                      |     ⬜      | Tình             |           10/11            |
|  9  | Báo cáo + Demo                                       |     ⬜      | Cả nhóm          |       17/11 · 01/12        |

---

## 📅 CẬP NHẬT THEO TUẦN

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
| Tool 1 `get_slow_queries`         | Vũ          |     ⬜     | Đang làm — ưu tiên tiếp theo           |
| Tool 2 `get_schema`               | Vũ          |     ⬜     | Sau Tool 1                             |
| Tool 3 `get_table_stats`          | Vũ          |     ⬜     | Sau Tool 2                             |
| `mcp_server/server.py`            | Vũ          |     ⬜     | Đăng ký 5 tool — sau khi xong Tool 1-3 |
| Đo P95 cho ground truth           | Tường + Hải |     ⬜     | Sau khi Tool 5 xong                    |
| Nháp chương "Cơ sở lý thuyết"     | Vũ          |     ⬜     | Song song                              |

**Checklist cuối tuần 3:**

- [x] `security/ast_whitelist.py` (47 tests)
- [x] `mcp_server/tools/explain.py` (7 tests)
- [x] `mcp_server/tools/benchmark.py` (7 tests)
- [ ] `mcp_server/tools/slow_queries.py`
- [ ] `mcp_server/tools/schema.py`
- [ ] `mcp_server/tools/stats.py`
- [ ] `mcp_server/server.py`

**Vấn đề gặp phải:**

- ⚠️ `readonly_user` không có quyền `RELOAD` → không dùng được `FLUSH STATUS`
  → Fix: Tool 5 bỏ `FLUSH STATUS`, dùng `Handler_read_rnd_next` cho `rows_examined`.
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
| 4   | Kiểm chứng case study `(region, order_date)` vs `(order_date, region)` | Tường + Hải | ⬜ Chưa đo       | 13/10 |

---

## 📈 CHỈ SỐ THEO DÕI

| Chỉ số                                             |       Hiện tại        |
| -------------------------------------------------- | :-------------------: |
| Số dòng bảng `sales_data`                          |       4,999,999       |
| Số query trong slow log                            |          ~30          |
| Query xác nhận > 0.5s (trên 30)                    |       **30/30**       |
| Tool MCP hoàn thành                                |        **2/6**        |
| Injection test pass                                | 47/47 (unit test AST) |
| Ground truth có chữ ký GVHD                        |         Chưa          |
| Precision / Recall (index)                         |           —           |
| Consistency Rate                                   |           —           |
| False Positive Rate                                |           —           |
| Rewrite đạt (kết quả tương đương + P95 giảm ≥ 20%) |           —           |

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
| 07/10 | Tường   | Tool 5 `benchmark_query` (7 tests pass)                                |

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
