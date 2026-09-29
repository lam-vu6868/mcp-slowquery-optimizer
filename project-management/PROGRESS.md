# 📊 TIẾN ĐỘ DỰ ÁN

> **Cập nhật lần cuối:** 29/09 — bởi Vũ (nhóm trưởng)
> **Tuần hiện tại:** Tuần 1/12 (cuối tuần)
> **Tổng tiến độ:** 🟩⬜⬜⬜⬜⬜⬜⬜⬜⬜ **~5%**
>
> ⚠️ **File này chỉ ghi TRẠNG THÁI.** Deadline, người phụ trách và tiêu chí Done xem [ROADMAP.md](ROADMAP.md) (mục 4–5). Mục tiêu Precision/Recall/Consistency xem [ROADMAP.md](ROADMAP.md) mục 2.4. Không ghi lại con số ở đây để tránh lệch.

**Chú thích:** ✅ Done | 🟡 Đang làm | ⬜ Chưa làm | 🔴 Trễ hạn | ⏸️ Tạm dừng

---

## 🎯 TỔNG QUAN CÁC GIAI ĐOẠN

|  #  | Giai đoạn                                            | Trạng thái  | Người chính      |          Deadline          |
| :-: | ---------------------------------------------------- | :---------: | ---------------- | :------------------------: |
|  0  | Setup môi trường                                     |   ✅ Done   | Vũ               |           28/09            |
| 0b  | Chốt thiết kế (`api-contract.md`, `architecture.md`) | 🟡 Đang làm | Vũ               |       03/10 · 06/10        |
|  1  | CSDL 12M records (phân bố lệch)                      | 🟡 Đang làm | Hải              |           05/10            |
|  2  | 30 query + ground truth                              | 🟡 Đang làm | Tường            | 06/10 (draft) · 20/10 (ký) |
|  3  | Tool 1–5 MCP                                         |     ⬜      | Vũ · Hải · Tường |           13/10            |
|  4  | Tích hợp LLM                                         |     ⬜      | Vũ               |           18/10            |
|  5  | Validation Layer                                     |     ⬜      | Hải              |           22/10            |
|  6  | Tool 6 + approval token + 20 injection               |     ⬜      | Tình             |           27/10            |
|  7  | Metrics + Baseline                                   |     ⬜      | Tường · Hải      |           03/11            |
|  8  | Dashboard 4 tab                                      |     ⬜      | Tình             |           10/11            |
|  9  | Báo cáo + Demo                                       |     ⬜      | Cả nhóm          |       17/11 · 01/12        |

> Cột Deadline chỉ để tiện nhìn, bản chuẩn ở ROADMAP mục 5.

---

## 📅 CẬP NHẬT THEO TUẦN

### 🗓️ Tuần 1 (23/09 – 29/09)

**Mục tiêu:** Setup môi trường + khung dự án

| Việc                      | Người   | Trạng thái | Ghi chú                       |
| ------------------------- | ------- | :--------: | ----------------------------- |
| Tạo repo GitHub           | Vũ      |     ✅     | Đã push `main` + `dev`        |
| Cấu trúc thư mục          | Vũ      |     ✅     | 70 file + 20 thư mục          |
| `docker-compose.yml`      | Vũ      |     ✅     | MySQL 8.0 chạy được           |
| MySQL + bật slow log      | Hải     |     ✅     | `long_query_time = 0.5`       |
| User `readonly_user`      | Hải     |     ✅     | Chỉ SELECT                    |
| Test quyền readonly       | Tình    |     ✅     | DDL bị chặn                   |
| Streamlit skeleton        | Tình    |     ✅     | `app.py` chạy được            |
| Draft 30 query            | Tường   |     🟡     | Nhóm 3/5 → chuyển sang tuần 2 |
| Chốt `api-contract.md`    | Cả nhóm |     🟡     | Đã có draft v1, cần review    |
| Bàn giao kiến thức 4 buổi | Cả nhóm |     🟡     | Xem Blockers                  |

**Checklist cuối tuần 1 (kiểm tra thật, không tick trước):**

- [x] `docker compose up -d` chạy không lỗi
- [x] `SHOW VARIABLES LIKE 'slow_query_log'` → ON
- [x] `readonly_user` không chạy được `DROP TABLE`
- [x] Streamlit `app.py` mở được
- [ ] Draft 30 query đủ 5 nhóm → **còn thiếu nhóm 4, 5**
- [ ] `api-contract.md` đã chốt → **đang review**
- [ ] Tất cả thành viên hiểu phân công mới → **cần xác nhận ở standup**

**Vấn đề gặp phải:**

- ⚠️ MySQL trong Docker chậm khi seed → chuyển sang `LOAD DATA INFILE`
- ⚠️ Streamlit crash khi không có data → thêm try/except

**Thay đổi lớn cuối tuần 1:** cập nhật ROADMAP v2 (tách baseline đúng bản chất, approval token, INVISIBLE INDEX, định nghĩa metric, cân lại phân công). Chi tiết ở [ROADMAP.md](ROADMAP.md) mục 0.

---

### 🗓️ Tuần 2 (30/09 – 06/10)

| Việc                                  | Người        | Trạng thái | Ghi chú                        |
| ------------------------------------- | ------------ | :--------: | ------------------------------ |
| Chuyển `log_output` sang `FILE,TABLE` | Hải          |     ⬜     |                                |
| Seed 1M users                         | Hải          |     ⬜     | Phân bố Zipf                   |
| Seed 12M orders                       | Hải          |     ⬜     | Status lệch, đỉnh Black Friday |
| Seed 20M order_items                  | Hải          |     ⬜     |                                |
| Verify phân bố dữ liệu                | Tường        |     ⬜     |                                |
| Hoàn thành draft 30 query (6/nhóm)    | Tường        |     ⬜     |                                |
| Chốt `api-contract.md`                | Vũ + cả nhóm |     ⬜     | Hạn 03/10                      |
| Chốt `architecture.md`                | Vũ           |     ⬜     | Hạn 06/10                      |
| Khung 6 tool rỗng                     | Vũ           |     ⬜     |                                |
| Draft AST whitelist v1 + test đơn vị  | Tình         |     ⬜     |                                |
| Xin API key + đặt ngân sách token     | Vũ           |     ⬜     | Hạn 01/10                      |

_(Cập nhật khi tuần 2 bắt đầu)_

---

## 🚨 BLOCKERS

| #   | Vấn đề                                                                                        | Người xử lý   | Trạng thái   | Hạn   |
| --- | --------------------------------------------------------------------------------------------- | ------------- | ------------ | ----- |
| 1   | MySQL trong Docker chậm khi seed                                                              | Hải (Vũ pair) | 🟡 Đang fix  | 30/09 |
| 2   | Chưa có API key Anthropic                                                                     | Vũ            | 🔴 Chưa có   | 01/10 |
| 3   | Bàn giao MCP: Tình → Vũ                                                                       | Tình, Vũ      | 🟡           | 30/09 |
| 4   | Bàn giao MySQL: Vũ → Hải                                                                      | Vũ, Hải       | 🟡           | 30/09 |
| 5   | Bàn giao Security (`sqlglot`): Vũ → Tình, **kèm code mẫu có test**                            | Vũ, Tình      | 🟡           | 30/09 |
| 6   | Bàn giao EXPLAIN/metrics: Tình → Tường                                                        | Tình, Tường   | 🟡           | 30/09 |
| 7   | Chưa xác nhận cả 30 query thực sự > 0.5s (MySQL 8 tự tối ưu một số subquery)                  | Tường, Hải    | ⬜ Chưa kiểm | 13/10 |
| 8   | Chưa kiểm chứng case study `(created_at, status)` vs `(status, created_at)` bằng số liệu thật | Tường, Hải    | ⬜ Chưa kiểm | 13/10 |

---

## 📈 CHỈ SỐ THEO DÕI

Mục tiêu chuẩn xem [ROADMAP.md](ROADMAP.md) mục 2.4. Cột "Hiện tại" là chỗ duy nhất cần cập nhật ở đây.

| Chỉ số                                             | Hiện tại |
| -------------------------------------------------- | :------: |
| Số dòng bảng `orders`                              |    0     |
| Số query trong slow log                            |    0     |
| Query xác nhận > 0.5s (trên 30)                    |   0/30   |
| Tool MCP hoàn thành                                |   0/6    |
| Injection test pass                                |   0/20   |
| Ground truth có chữ ký GVHD                        |   Chưa   |
| Precision / Recall (index)                         |    —     |
| Consistency Rate                                   |    —     |
| False Positive Rate                                |    —     |
| Rewrite đạt (kết quả tương đương + P95 giảm ≥ 20%) |    —     |

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

---

## 🔄 GHI CHÚ ĐỔI PHÂN CÔNG

**Đổi vai (28/09):**

| Vai trò                   | Người cũ | Người mới |
| ------------------------- | -------- | --------- |
| Team Lead + MCP Architect | Tình     | **Vũ**    |
| DB Engineer               | Hải      | Hải       |
| Security + Frontend       | Vũ       | **Tình**  |
| Data Analyst + Metrics    | Tường    | Tường     |

**Điều chỉnh việc (29/09, theo ROADMAP v2):** Tool 6 → Tình · Tool 5 + baseline → Tường · Hải verify ground truth cùng Tường. Lý do và chi tiết ở [TEAM.md](TEAM.md).

**Rủi ro cần theo dõi:**

- ⚠️ Vũ vừa Lead vừa MCP Architect → Tình hỗ trợ MCP 2 tuần đầu; nếu quá tải, báo ngay trong standup
- ⚠️ Hải đang trên đường găng (seed → validation) mà mới quen MySQL → Vũ pair seed tuần 2
- ⚠️ Tình mới làm AST whitelist → Vũ giao code mẫu kèm test
- ⚠️ Tường mới làm EXPLAIN nhưng giữ ground truth → Hải verify chéo

---

## 📌 CÁCH CẬP NHẬT FILE NÀY

| Khi nào             | Cập nhật gì                                           | Ai làm    |
| ------------------- | ----------------------------------------------------- | --------- |
| Sau standup tối     | Đổi trạng thái việc đã xong                           | Vũ        |
| Gặp blocker mới     | Thêm dòng vào "Blockers"                              | Người gặp |
| Chủ nhật            | Thêm bảng "Tuần N+1", cập nhật % và "Chỉ số theo dõi" | Vũ        |
| Đổi phân công/scope | Ghi vào "Nhật ký thay đổi" **và** sửa ROADMAP         | Vũ        |
| Cuối tháng          | Review tổng tiến độ                                   | Cả nhóm   |

Ai cũng có thể đề xuất sửa qua Pull Request.

---

## ✅ CHECKLIST REVIEW CUỐI TUẦN (Vũ)

| Mục                                                | Trạng thái |
| -------------------------------------------------- | :--------: |
| Cập nhật bảng "Tuần N"                             |     ⬜     |
| Thêm bảng "Tuần N+1"                               |     ⬜     |
| Cập nhật % tổng tiến độ                            |     ⬜     |
| Kiểm tra Blockers                                  |     ⬜     |
| Cập nhật "Chỉ số theo dõi"                         |     ⬜     |
| Gửi weekly report GVHD                             |     ⬜     |
| Đối chiếu với ROADMAP mục 5, có việc nào trễ không |     ⬜     |

---

## 📞 LIÊN HỆ NHANH

| Vấn đề                                           | Liên hệ         |
| ------------------------------------------------ | --------------- |
| Điều phối, deadline, kế hoạch                    | Vũ              |
| MCP protocol, LLM API, Tool 1–3                  | Vũ              |
| MySQL, Docker, seed, Validation Layer, Tool 4    | Hải             |
| AST, injection, Tool 6, Dashboard                | Tình            |
| Ground truth, metrics, Tool 5, baseline, biểu đồ | Tường           |
| Không biết hỏi ai                                | Nhóm chat chung |
