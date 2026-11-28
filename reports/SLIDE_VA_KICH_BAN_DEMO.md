# DÀN Ý SLIDE BẢO VỆ & KỊCH BẢN DEMO

> **Tài liệu đi kèm:** [BAO_CAO_DO_AN.md](BAO_CAO_DO_AN.md) · **Thời lượng dự kiến:** 10 phút trình bày + 5 phút demo trực tiếp.

---

## Phần 1. Dàn ý 12 Slide Bảo vệ

1. **Slide 1 — Trang bìa:** Tên đề tài (*Tối ưu Slow Query và Chỉ mục CSDL bằng LLM qua kiến trúc MCP*), nhóm thực hiện, GVHD.
2. **Slide 2 — Bài toán & Động lực:** Sự cố slow query (ngữ cảnh Black Friday), hạn chế của tối ưu thủ công và rủi ro nếu cho LLM chạy DDL tự do (hallucination, Prompt Injection, lệch `query_cost`).
3. **Slide 3 — Kiến trúc tổng thể (Sơ đồ Mermaid):** MySQL 8.0 (`3307` chỉ đọc, 5M dòng) ↔ MCP Server (Tool 1–5) ↔ LLM Groq → Validation Layer trên Staging Lab (`3309`, INVISIBLE INDEX + SHA-256) → Dashboard 7 trang → Approval Token 1 lần → Tool 6 (`index_admin`).
4. **Slide 4 — Thiết kế 6 Tool MCP:** Bảng phân quyền Tool 1–5 (`readonly_user`, LLM thấy) vs Tool 6 (`index_admin`, LLM **không thấy**).
5. **Slide 5 — Bảo mật 6 lớp:** Tách quyền DB, sanitize + `untrusted: true`, AST whitelist (fail-closed `sqlglot`), đề xuất JSON có cấu trúc, HMAC Approval Token 1 lần + Audit log, bảo vệ khóa ngoại (FK).
6. **Slide 6 — Validation Layer bằng INVISIBLE INDEX:** Quy trình đo 3 warm-up + 20 lượt (tắt/bật `use_invisible_indexes`), kiểm tương đương SHA-256, đo trade-off ghi (Write Lab `3308`), tự rollback khi fail.
7. **Slide 7 — Bộ dữ liệu & 30 Query thực nghiệm:** Schema 5 bảng / 5M dòng (`shopdb.multitable-v1`), 5 nhóm lỗi × 6 query, 30/30 ground truth đạt kiểm chứng.
8. **Slide 8 — Kết quả nhóm Rewrite (12/12 đo thật trên Lab 3309):** **8/12 đạt (66,7%)**, vượt ngưỡng tối thiểu 60% (`q14` giảm 98,34%, `q17` giảm 95,04%, `q27` giảm 86,90%).
9. **Slide 9 — Bằng chứng giá trị Validation Layer (`q13`/`q15`/`q30`):**
   - `q13`, `q15`: `query_cost` giảm >50% nhưng P95 chậm >2× → không thể tin EXPLAIN cost.
   - `q30`: LLM rewrite làm lệch SHA-256 hash → Validation chặn lỗi sai dữ liệu.
10. **Slide 10 — So sánh LLM vs 2 Baseline (`Greedy` & `pt-query-digest`) + Chỉ số LLM & Trade-off `q07`:** Bảng so sánh `llm_groq_mcp` vs `greedy` (Precision 24,32%, Recall 38,89%, FPR 75,68% theo khớp chính xác; Rewrite 66,7% vs 0%); Consistency Rate 5 lần lặp (`q01` 60%, `q14` 80%, TB 70%); đối chứng `pt-query-digest` vs Tool 1; trade-off `q07` (P95 đọc giảm 49,7%, INSERT giảm 21,7%, index ~73 MB).
11. **Slide 11 — Kiểm thử Bảo mật (20 kịch bản Prompt Injection):** 20/20 bị chặn qua 8 lớp phòng thủ (kèm phát hiện & vá lỗi `EXPLAIN ANALYZE` ở C05 và bộ lọc tên bảng B05 trước Groq), nêu rõ giới hạn.
12. **Slide 12 — Demo trực tiếp & Kết luận:** 393 unit tests pass, Dashboard 7 trang hoàn chỉnh theo "Hành trình của 1 query", hướng phát triển.

---

## Phần 2. Kịch bản Demo trực tiếp (5–7 phút)

### Chuẩn bị trước giờ bảo vệ (2 phút)
1. Bật Docker container `mcp_mysql_db` (`3307`) và `mcp_validation_lab_db` (`3309`). *(Nếu demo Validation chính thức ở Trang 6 thì bật thêm `mcp_write_lab_db` cổng `3308`.)*
2. Chuẩn bị sẵn key Groq dự phòng (Free Tier có hạn mức 200.000 token/ngày).
3. Chạy Dashboard:
   ```powershell
   .\venv\Scripts\streamlit.exe run dashboard/app.py --server.address 127.0.0.1 --server.port 8501
   ```
4. Mở trình duyệt tại `http://127.0.0.1:8501`.

### Luồng trình diễn 7 Trang ("Hành trình của 1 query")
- **Phút 1 — Trang 1 (`1. Chọn query chậm`):**
  - Chọn **`q01`** (hoặc `q02`) trong bộ 30 query → bấm **▶ Chạy query này (đo ms)** trên DB chính `3307` (`readonly_user`) để hội đồng thấy thời gian chạy thật, số dòng quét và `EXPLAIN cost`.
- **Phút 2 — Trang 2 (`2. LLM đề xuất`):**
  - Tick xác nhận → bấm **Phân tích bằng LLM** (Groq gọi MCP Tool 1–5 chỉ đọc) → nhận đề xuất JSON có cấu trúc (ví dụ `order_items(product_id, quantity, unit_price)` cho `q01`).
- **Phút 3 — Trang 3 (`3. Chạy thử đề xuất`):**
  - Chọn **Thử siêu nhanh (1 lượt trước + 1 lượt sau)** (~1 phút, chỉ để minh họa) → tick xác nhận tạo `INVISIBLE INDEX` tạm trên lab `3309` → bấm **▶ Chạy thử** để thấy giảm ~92% thời gian chạy, hash khớp 100%, rồi index tạm tự xóa sạch.
- **Phút 4 — Trang 4 (`4. So sánh với Baseline`):**
  - **Tab 1:** Bấm **▶ Chạy baseline Greedy** cho chính `q01` → chứng minh Greedy (tối đa 2 cột theo `EXPLAIN cost`) không tìm được covering index 3 cột như LLM.
  - **Tab 2:** Bấm **▶ So sánh `pt-query-digest` vs Tool 1** (chọn nguồn `slow_log`) → giải thích `pt-query-digest` chỉ dừng ở phát hiện, còn hệ thống đi trọn vòng tối ưu + kiểm chứng.
- **Phút 5 — Trang 5 (`5. Bảo mật`) & Trang 6 (`6. Duyệt & áp dụng`):**
  - **Trang 5:** Bấm **▶ Chạy 20 kịch bản Prompt Injection ngay** → thanh tiến độ chạy trực tiếp 20/20 ca bị chặn qua 8 lớp phòng thủ + xem Audit log Tool 6.
  - **Trang 6:** Trình bày cơ chế Validation chính thức (3 warm-up + 20 lượt + đo trade-off INSERT/dung lượng trên Write Lab `3308`), thời hạn duyệt 24h, Approval Token 1 lần (10 phút) cho Tool 6, và nhấn mạnh **rewrite không có nút Apply**.
- **Phút 6 — Trang 7 (`7. Đánh giá LLM & Tổng kết 30 query`):**
  - Chiếu 4 thẻ chỉ số tiếng Việt (**Precision, Recall, False Positive Rate, Consistency Rate 5 lần = 70%**), bảng so sánh LLM vs Greedy và biểu đồ cột P95 của 12 query Rewrite (**8/12 = 66,7%**). Chốt **393 unit tests passed**.

---

## Phần 3. Câu hỏi hội đồng hay hỏi & Cách trả lời ngắn gọn

1. **Hỏi: Tại sao không để LLM chạy thẳng `CREATE INDEX` luôn cho nhanh?**  
   *Trả lời:* Qua thực nghiệm thật của nhóm, LLM vẫn có ca làm query **chậm hơn 2 lần** (`q13`, `q15`) hoặc **viết lại SQL sai kết quả** (`q30`). Do đó bắt buộc phải có Validation Layer đo P95 + hash thật và Human-in-the-loop duyệt bằng token 1 lần.
2. **Hỏi: Nếu hacker chèn prompt độc vào SQL trong slow log thì LLM có gọi Tool 6 xóa dữ liệu không?**  
   *Trả lời:* Không. Comment SQL bị cắt bỏ và gắn `untrusted: true` trước khi tới LLM. Quan trọng nhất là **LLM chỉ được cấp danh sách Tool 1–5 (tài khoản `readonly_user`), hoàn toàn không thấy Tool 6**; ngay cả khi cố gọi với token giả (ca D05), lõi Tool 6 vẫn từ chối (`TOKEN_INVALID`) và ghi audit log.
3. **Hỏi: Tại sao cần DB phụ `3309` mà không thử thẳng trên DB chính `3307`?**  
   *Trả lời:* Trong thực tế không ai chạy `CREATE INDEX` + benchmark 20 lượt trên DB Production vì ngốn CPU/I/O và có thể làm chậm hệ thống đang phục vụ khách hàng. DB `3309` đóng vai trò môi trường Staging/Replica để thử nghiệm an toàn trước khi duyệt áp dụng.
4. **Hỏi: Tại sao `greedy` đạt 0% khớp chính xác?**  
   *Trả lời:* Trên schema 5 bảng thực tế, đa số đáp án ground truth là **covering index 3–4 cột** (gồm cả cột nằm trong `SELECT` như `total_amount`, `quantity`, `unit_price`). Thuật toán `greedy` 2 cột chỉ dựa vào `EXPLAIN cost` nên không tự tạo được covering index 3–4 cột và không biết rewrite SQL nhóm 3 & 5.
5. **Hỏi: Tại sao dùng `INVISIBLE INDEX` thay vì hypothetical index?**  
   *Trả lời:* PostgreSQL có `HypoPG`, còn MySQL 8.0 không có hypothetical index nên nhóm dùng `INVISIBLE INDEX` + `SET SESSION optimizer_switch='use_invisible_indexes=on'` trên lab riêng (`3309`) để đo P95 thực tế mà không ảnh hưởng session khác.
