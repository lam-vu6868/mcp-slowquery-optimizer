# Kịch bản video demo (5–10 phút) + video dự phòng

> **Phụ trách:** Tình · **Hạn:** 01/12 · Quay bằng OBS, 1080p, có thu tiếng.
> Video **chính** quay với dữ liệu thật (MySQL 5M dòng + LLM + Validation Layer). Video **dự phòng** quay bằng dữ liệu demo (`scripts/seed_demo_dashboard.py`) phòng khi máy/mạng hôm bảo vệ có sự cố — phải nói rõ trên màn hình là dữ liệu demo.

## Chuẩn bị trước khi quay

- [ ] `docker compose up -d`, MySQL có đủ 5M dòng, slow log bật (`python scripts/verify_setup.py`)
- [ ] `.env` có `APPROVAL_SECRET` thật (tạo bằng `python -c "import secrets; print(secrets.token_hex(32))"`), `ANTHROPIC_API_KEY`
- [ ] Xóa các index thí nghiệm cũ để demo bắt đầu từ trạng thái "chậm" (`bash scripts/reset_db.sh`)
- [ ] `python scripts/test_queries.py` để slow log có dữ liệu
- [ ] `python -m security.injection_tests.run_tests --db` → 20/20, có lớp L1
- [ ] Đóng thông báo, ẩn bookmark, phóng chữ terminal ≥ 16pt, ẩn `.env` khỏi màn hình
- [ ] Chạy thử toàn bộ kịch bản 1 lần không quay

## Kịch bản

| # | Thời lượng | Màn hình | Lời thoại / thao tác |
|:-:|:---------:|----------|----------------------|
| 1 | 0:00–0:40 | Slide tiêu đề → sơ đồ kiến trúc | Giới thiệu bài toán: query chậm trên bảng 5M dòng; LLM đề xuất index qua 6 tool MCP; **con người duyệt** trước khi áp dụng. |
| 2 | 0:40–1:30 | Dashboard trang chủ | Chỉ 5 thẻ số liệu và trạng thái hệ thống (MySQL, APPROVAL_SECRET, Tool 1). Nhấn mạnh: LLM chỉ có Tool 1–5. |
| 3 | 1:30–2:30 | Tab 1 Slow query | Biểu đồ P95 / rows examined. Mở 1 query (vd q07), chỉ nhãn "dữ liệu không tin cậy". |
| 4 | 2:30–3:30 | Terminal: chạy LLM agent cho q07 | Cho thấy LLM gọi `get_slow_queries` → `get_schema` → `get_table_stats` → `explain_query` → trả JSON proposal **có cấu trúc** (không có câu `CREATE INDEX`). |
| 5 | 3:30–4:30 | Tab 2 Đề xuất | Proposal q07 sau Validation: P95 trước/sau, hash tương đương ✅, dung lượng index, write overhead. Chỉ "DDL do server sinh". Chỉ proposal rewrite: **không có nút Apply**. |
| 6 | 4:30–5:30 | Tab 2 → Approve | Nhập tên người duyệt, tick xác nhận, bấm **Approve & Apply** → thông báo thành công + audit id. Quay sang terminal MySQL: `SHOW INDEX FROM sales_data` thấy index mới `VISIBLE`. Chạy lại q07: nhanh hơn. |
| 7 | 5:30–6:30 | Tab 3 So sánh | Biểu đồ P95/Query cost/rows trước–sau theo từng query; bảng LLM vs greedy vs rule-based. |
| 8 | 6:30–8:00 | Tab 4 Bảo mật | 20/20 kịch bản, biểu đồ theo lớp. Mở A2 (`/*!50000 DROP TABLE */`): lớp chặn Sanitize + AST. Mở D5 (đổi proposal sau khi duyệt): token không khớp hash DDL. Kể chuyện tìm ra lỗ hổng `FOR SHARE` khi test và đã vá. |
| 9 | 8:00–8:45 | Terminal | **Demo tấn công trực tiếp:** gọi Tool 6 với token giả `"approved"` → `TOKEN_INVALID`; dùng lại token cũ → `REUSED`. Mở tab Audit log: cả hai lần bị từ chối đều có dòng ghi. |
| 10 | 8:45–9:30 | Slide kết luận | Kết quả chính + **giới hạn** (chưa đo phản ứng LLM thật với injection, chưa có đăng nhập Dashboard…). |

Lệnh cho cảnh 9 (chuẩn bị sẵn trong file, đừng gõ tay khi quay):

```python
# demo_attack.py — chạy: python demo_attack.py <proposal_id_đã_áp_dụng_hoặc_validated>
import asyncio, json, sys
from mcp_server.tools.apply import apply_optimization
pid = sys.argv[1]
for tok in ["approved", "v1." + "0" * 32 + ".9999999999.Zm9yZ2Vk"]:
    print(tok[:20], "→", json.loads(asyncio.run(apply_optimization(pid, tok, source="demo_attack")))["error"])
```

## Video dự phòng (quay bằng dữ liệu demo)

```bash
python scripts/seed_demo_dashboard.py
META_DB_PATH=data/meta/demo.sqlite3 streamlit run dashboard/app.py          # bash
$env:META_DB_PATH="data/meta/demo.sqlite3"; streamlit run dashboard/app.py   # PowerShell
```

Quay cảnh 2, 5, 7, 8, 9 (bỏ 4 và phần MySQL của cảnh 6). Banner vàng "dữ liệu demo" phải hiện trong khung hình. Không cắt banner.

## Sau khi quay

- [ ] Xuất MP4 H.264, kiểm tra tiếng
- [ ] Lưu ≥ 2 nơi (Drive nhóm + USB) theo cam kết backup
- [ ] Gửi link cho Vũ để chèn vào slide
