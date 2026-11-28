# DÀN Ý SLIDE BẢO VỆ & KỊCH BẢN DEMO

> **Tài liệu đi kèm:** [BAO_CAO_DO_AN.md](BAO_CAO_DO_AN.md) · **Thời lượng dự kiến:** 10 phút trình bày + 5 phút demo trực tiếp.

---

## Phần 1. Dàn ý 12 Slide Bảo vệ

1. **Slide 1 — Trang bìa:** Tên đề tài (*Tối ưu Slow Query và Chỉ mục CSDL bằng LLM qua kiến trúc MCP*), nhóm thực hiện, GVHD.
2. **Slide 2 — Bài toán & Động lực:** Sự cố slow query (ngữ cảnh Black Friday), hạn chế của tối ưu thủ công và rủi ro nếu cho LLM chạy DDL tự do (hallucination, Prompt Injection, lệch `query_cost`).
3. **Slide 3 — Kiến trúc tổng thể (Sơ đồ Mermaid):** MySQL 8.0 (5M dòng) ↔ MCP Server (Tool 1–5) ↔ LLM Groq → Validation Layer (INVISIBLE INDEX + SHA-256) → Dashboard 4 tab → Approval Token 1 lần → Tool 6 (`index_admin`).
4. **Slide 4 — Thiết kế 6 Tool MCP:** Bảng phân quyền Tool 1–5 (`readonly_user`, LLM thấy) vs Tool 6 (`index_admin`, LLM **không thấy**).
5. **Slide 5 — Bảo mật 6 lớp:** Tách quyền DB, sanitize + `untrusted: true`, AST whitelist (fail-closed `sqlglot`), đề xuất JSON có cấu trúc, HMAC Approval Token 1 lần + Audit log, bảo vệ khóa ngoại (FK).
6. **Slide 6 — Validation Layer bằng INVISIBLE INDEX:** Quy trình đo 3 warm-up + 20 lượt (tắt/bật `use_invisible_indexes`), kiểm tương đương SHA-256, đo trade-off ghi (Write Lab `3308`), tự rollback khi fail.
7. **Slide 7 — Bộ dữ liệu & 30 Query thực nghiệm:** Schema 5 bảng / 5M dòng (`shopdb.multitable-v1`), 5 nhóm lỗi × 6 query, 30/30 ground truth đạt kiểm chứng.
8. **Slide 8 — Kết quả nhóm Rewrite (12/12 đo thật trên Lab 3309):** **8/12 đạt (66,7%)**, vượt ngưỡng tối thiểu 60% (`q14` giảm 98,34%, `q17` giảm 95,04%, `q27` giảm 86,90%).
9. **Slide 9 — Bằng chứng giá trị Validation Layer (`q13`/`q15`/`q30`):**
   - `q13`, `q15`: `query_cost` giảm >50% nhưng P95 chậm >2× → không thể tin EXPLAIN cost.
   - `q30`: LLM rewrite làm lệch SHA-256 hash → Validation chặn lỗi sai dữ liệu.
10. **Slide 10 — So sánh LLM vs Baseline (`comparison.csv`) & Trade-off `q07`:** Bảng so sánh `llm_groq_mcp` vs `rule_based` vs `greedy`; trade-off `q07` (P95 đọc giảm 49,7%, INSERT giảm 21,7%, index ~73 MB).
11. **Slide 11 — Kiểm thử Bảo mật (20 kịch bản Prompt Injection):** 20/20 bị chặn qua 8 lớp phòng thủ (kèm phát hiện & vá lỗi `EXPLAIN ANALYZE` ở C05 và bộ lọc tên bảng B05 trước Groq), nêu rõ giới hạn.
12. **Slide 12 — Demo trực tiếp & Kết luận:** 379 unit tests pass, 4 tab Dashboard hoạt động, hướng phát triển.

---

## Phần 2. Kịch bản Demo trực tiếp (5 phút)

### Chuẩn bị trước giờ bảo vệ (2 phút)
1. Bật Docker container `mcp_mysql_db` (cổng `3307`). *(Nếu muốn bấm thử nút Validation/Approve thật thì bật thêm `mcp_validation_lab_db` cổng `3309` và `mcp_write_lab_db` cổng `3308`.)*
2. *(Tùy chọn)* Chạy nhanh 1–2 câu query mẫu trên `3307` để `performance_schema` có dữ liệu tươi; hoặc dùng trực tiếp nguồn `slow_log` (đã có sẵn 10 query lưu trên đĩa).
3. Chạy Dashboard:
   ```powershell
   .\venv\Scripts\streamlit.exe run dashboard/app.py --server.address 127.0.0.1 --server.port 8501
   ```
4. Mở trình duyệt tại `http://127.0.0.1:8501`.

### Luồng trình diễn 4 Tab
- **Phút 1 — Trang chủ & Tab 1 (`1_slow_queries`):**
  - Chọn nguồn `slow_log` → bấm **Tải slow query** → cho hội đồng thấy 10 slow query thật từ MySQL `3307` (cùng số lần chạy, latency, `rows_examined`).
  - Chọn 1 query → bấm **Phân tích query này** (chuyển tự động SQL sang Tab 2, chưa gọi LLM ngay để đảm bảo người dùng xác nhận).
- **Phút 2 — Tab 2 (`2_proposals`):**
  - Cho thấy hộp kiểm xác nhận trước khi gửi LLM, các proposal dạng cấu trúc (index vs rewrite — nhấn mạnh **rewrite chỉ hiển thị, không có nút Approve**).
  - Giải thích cơ chế Validation Layer (tạo INVISIBLE INDEX trên lab, đo P95/hash/write overhead) → chỉ khi `passed` mới hiện nút **Approve** sinh token 1 lần gọi Tool 6.
- **Phút 3 — Tab 3 (`3_comparison`):**
  - Trình bày bảng `comparison.csv` (LLM vs `rule_based` vs `greedy`) và ghi chú `pt-query-digest` không đề xuất index.
  - Chỉ vào 4 metric Rewrite (**8/12 = 66,7%**) và **biểu đồ cột P95 trước vs sau** theo từng query (nhấn mạnh `q14` giảm 98% và `q13`/`q15` chậm đi nên bị chặn).
- **Phút 4 — Tab 4 (`4_security`):**
  - Cho thấy bảng **20/20 kịch bản Prompt Injection** với cột **Lớp chặn** (8 lớp phòng thủ) và bảng **Audit log Tool 6** (ghi nhận `applied` / `rejected` / `TOKEN_INVALID`).
- **Phút 5 — Chốt bằng chứng kiểm thử:**
  - Nêu bộ test tự động **379 passed** (bao gồm 47+ test AST whitelist, token HMAC, Validation, 3 baseline và AppTest Dashboard).

---

## Phần 3. Câu hỏi hội đồng hay hỏi & Cách trả lời ngắn gọn

1. **Hỏi: Tại sao không để LLM chạy thẳng `CREATE INDEX` luôn cho nhanh?**  
   *Trả lời:* Qua thực nghiệm thật của nhóm, LLM vẫn có ca làm query **chậm hơn 2 lần** (`q13`, `q15`) hoặc **viết lại SQL sai kết quả** (`q30`). Do đó bắt buộc phải có Validation Layer đo P95 + hash thật và Human-in-the-loop duyệt bằng token 1 lần.
2. **Hỏi: Nếu hacker chèn prompt độc vào SQL trong slow log thì LLM có gọi Tool 6 xóa dữ liệu không?**  
   *Trả lời:* Không. Thứ nhất, comment SQL bị cắt bỏ và gắn `untrusted: true` trước khi tới LLM. Thứ hai, quan trọng nhất là **LLM chỉ được cấp danh sách Tool 1–5 (tài khoản `readonly_user`), hoàn toàn không thấy Tool 6**; ngay cả khi cố gọi với token giả (ca D05), lõi Tool 6 vẫn từ chối (`TOKEN_INVALID`) và ghi audit log.
3. **Hỏi: Tại sao `rule_based` và `greedy` đạt 0% khớp chính xác?**  
   *Trả lời:* Trên schema 5 bảng thực tế, đa số đáp án ground truth là **covering index 3–4 cột** (gồm cả cột nằm trong `SELECT` như `total_amount`, `quantity`, `unit_price`). Luật cứng E-R-S và `greedy` 2 cột chỉ nhìn `WHERE/JOIN/ORDER BY` nên không tự tạo được covering index, và hoàn toàn không biết rewrite SQL nhóm 3 & 5. Nhóm cũng ghi rõ mới chấm khớp chính xác, chưa đo P95 tương đương cho nhóm Index 1/2/4.
4. **Hỏi: Tại sao dùng `INVISIBLE INDEX` thay vì hypothetical index?**  
   *Trả lời:* PostgreSQL có `HypoPG`, còn MySQL 8.0 không có hypothetical index nên nhóm dùng `INVISIBLE INDEX` + `SET SESSION optimizer_switch='use_invisible_indexes=on'` trên lab riêng (`3309`) để đo P95 thực tế mà không ảnh hưởng session khác.
