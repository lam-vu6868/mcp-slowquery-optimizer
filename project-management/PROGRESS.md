# 📊 TIẾN ĐỘ DỰ ÁN

> **Cập nhật lần cuối:** 28/09/2025 — bởi Vũ (nhóm trưởng)
> **Tuần hiện tại:** Tuần 1/12
> **Tổng tiến độ:** 🟩⬜⬜⬜⬜⬜⬜⬜⬜⬜ **5%**

---

## 🎯 TỔNG QUAN 10 GIAI ĐOẠN

|  #  | Giai đoạn               |   Trạng thái    | Deadline | Người chính |
| :-: | ----------------------- | :-------------: | :------: | ----------- |
|  0  | Setup môi trường        |   ✅ **Done**   |  28/09   | Vũ          |
|  1  | CSDL 12M records        | 🟡 **Đang làm** |  05/10   | Hải         |
|  2  | 30 query + ground truth |   ⬜ Chưa làm   |  08/10   | Tường       |
|  3  | 6 Tool MCP              |   ⬜ Chưa làm   |  15/10   | Vũ + Hải    |
|  4  | Tích hợp LLM            |   ⬜ Chưa làm   |  18/10   | Vũ          |
|  5  | Validation Layer        |   ⬜ Chưa làm   |  22/10   | Hải         |
|  6  | 20 Prompt Injection     |   ⬜ Chưa làm   |  25/10   | Tình        |
|  7  | Metrics + Baseline      |   ⬜ Chưa làm   |  29/10   | Tường       |
|  8  | Dashboard Streamlit     |   ⬜ Chưa làm   |  02/11   | Tình        |
|  9  | Báo cáo + Demo          |   ⬜ Chưa làm   |  09/11   | Cả nhóm     |

**Chú thích:** ✅ Done | 🟡 Đang làm | ⬜ Chưa làm | 🔴 Trễ hạn | ⏸️ Tạm dừng

---

## 👥 PHÂN CÔNG NHANH

| Thành viên | Vai trò                      | Phụ trách chính                          |
| ---------- | ---------------------------- | ---------------------------------------- |
| **Vũ** ⭐  | 🧠 Team Lead + MCP Architect | MCP Server core, LLM, báo cáo, điều phối |
| **Hải**    | 🗄️ DB Engineer + Backend     | CSDL, 6 tool backend, Validation Layer   |
| **Tình**   | 🛡️ Security + Frontend       | AST whitelist, 20 injection, Dashboard   |
| **Tường**  | 📊 Data Analyst + Metrics    | Ground truth, metrics, biểu đồ           |

> Chi tiết xem [TEAM.md](TEAM.md)

---

## 📅 CẬP NHẬT THEO TUẦN

### 🗓️ Tuần 1 (23/09 – 29/09/2025)

**Mục tiêu:** Setup xong môi trường + khung dự án

| Việc                         | Người làm | Trạng thái | Ghi chú                    |
| ---------------------------- | --------- | :--------: | -------------------------- |
| Tạo repo GitHub              | Vũ        |     ✅     | Đã push lên `main` + `dev` |
| Tạo cấu trúc thư mục         | Vũ        |     ✅     | 70 file + 20 thư mục       |
| Viết `docker-compose.yml`    | Vũ        |     ✅     | MySQL 8.0 chạy được        |
| Cài đặt MySQL + bật slow log | Hải       |     ✅     | `long_query_time = 0.5`    |
| Tạo user `readonly_user`     | Hải       |     ✅     | Chỉ có quyền SELECT        |
| Draft 30 query theo 5 nhóm   | Tường     |     🟡     | Đang viết nhóm 3/5         |
| Setup Streamlit skeleton     | Tình      |     ✅     | `app.py` chạy được         |
| Test quyền readonly user     | Tình      |     ✅     | DDL bị chặn thành công     |

**Vấn đề gặp phải:**

- ⚠️ MySQL trong Docker bị chậm khi seed → chuyển sang `LOAD DATA INFILE`
- ⚠️ Streamlit crash khi không có data → thêm try/except

**Kế hoạch tuần 2:** Seed xong 12M orders, hoàn thành draft 30 query

---

### 🗓️ Tuần 2 (30/09 – 06/10/2025)

**Mục tiêu:** Có CSDL 12M records + draft 30 query

| Việc                   | Người làm | Trạng thái | Ghi chú |
| ---------------------- | --------- | :--------: | ------- |
| Seed 1M users          | Hải       |     ⬜     |         |
| Seed 12M orders        | Hải       |     ⬜     |         |
| Seed 20M order_items   | Hải       |     ⬜     |         |
| Verify phân bố dữ liệu | Tường     |     ⬜     |         |
| Hoàn thành 30 query    | Tường     |     ⬜     |         |
| Viết khung 6 tool rỗng | Vũ        |     ⬜     |         |
| Draft AST whitelist    | Tình      |     ⬜     |         |

_(Sẽ cập nhật khi tuần 2 bắt đầu)_

---

## 🚨 BLOCKERS (Vấn đề đang chặn)

| #   | Vấn đề                                | Người xử lý | Trạng thái  | Deadline |
| --- | ------------------------------------- | ----------- | ----------- | -------- |
| 1   | MySQL trong Docker chậm khi seed      | Hải         | 🟡 Đang fix | 30/09    |
| 2   | Chưa có API key Anthropic             | Vũ          | 🔴 Chưa có  | 01/10    |
| 3   | Bàn giao kiến thức MCP cũ → Vũ        | Cả nhóm     | 🟡 Đang làm | 30/09    |
| 4   | Bàn giao kiến thức MySQL cũ → Hải     | Cả nhóm     | 🟡 Đang làm | 30/09    |
| 5   | Bàn giao kiến thức Security cũ → Tình | Cả nhóm     | 🟡 Đang làm | 30/09    |
| 6   | Bàn giao kiến thức Metrics cũ → Tường | Cả nhóm     | 🟡 Đang làm | 30/09    |

---

## 📈 METRICS THEO DÕI

| Chỉ số                  | Hiện tại | Mục tiêu   |
| ----------------------- | -------- | ---------- |
| Số dòng bảng `orders`   | 0        | 12,000,000 |
| Số query chậm trong log | 0        | ≥ 30       |
| Số tool MCP hoàn thành  | 0/6      | 6/6        |
| Số injection test pass  | 0/20     | 20/20      |
| Precision của LLM       | —        | ≥ 70%      |
| Recall của LLM          | —        | ≥ 70%      |

---

## 📝 NHẬT KÝ THAY ĐỔI

| Ngày  | Người   | Việc đã làm                                                      |
| ----- | ------- | ---------------------------------------------------------------- |
| 23/09 | Vũ      | Tạo repo, push cấu trúc ban đầu                                  |
| 24/09 | Hải     | Setup MySQL + bật slow log                                       |
| 25/09 | Vũ      | Viết `docker-compose.yml`                                        |
| 26/09 | Tường   | Bắt đầu draft 30 query                                           |
| 27/09 | Tình    | Test readonly user, DDL bị chặn OK                               |
| 28/09 | Cả nhóm | Standup: review tuần 1, chốt kế hoạch tuần 2                     |
| 28/09 | Cả nhóm | **Đổi phân công**: Vũ=Lead, Hải=DB, Tình=Security, Tường=Metrics |

---

## 🔄 GHI CHÚ VỀ ĐỔI PHÂN CÔNG (28/09)

**Lý do đổi:** Cân bằng lại workload + phát huy thế mạnh từng người.

**Bảng mapping cũ → mới:**

| Vai trò                      | Người CŨ | Người MỚI         |
| ---------------------------- | -------- | ----------------- |
| 🧠 Team Lead + MCP Architect | Tình     | **Vũ** ⭐         |
| 🗄️ DB Engineer + Backend     | Hải      | Hải (không đổi)   |
| 🛡️ Security + Frontend       | Vũ       | **Tình**          |
| 📊 Data Analyst + Metrics    | Tường    | Tường (không đổi) |

**Kế hoạch bàn giao (tuần 1-2):**

| Buổi | Người dạy | Người học | Nội dung                                       |
| :--: | --------- | --------- | ---------------------------------------------- |
|  1   | Tình (cũ) | Vũ (mới)  | MCP protocol, cách viết tool, kiến trúc server |
|  2   | Vũ (cũ)   | Hải       | MySQL setup, seed data, LOAD DATA INFILE       |
|  3   | Vũ (cũ)   | Tình      | AST whitelist (sqlglot), prompt injection      |
|  4   | Tình (cũ) | Tường     | EXPLAIN, cách đo metrics, ground truth         |

**Rủi ro cần theo dõi:**

- ⚠️ Vũ vừa làm Lead vừa làm MCP Architect → cần Tình hỗ trợ MCP 2 tuần đầu
- ⚠️ Hải chưa quen MySQL → cần Vũ hỗ trợ seed 1 tuần đầu
- ⚠️ Tình chưa quen AST whitelist → cần Vũ bàn giao code mẫu
- ⚠️ Tường chưa quen EXPLAIN → cần Hải + Vũ hỗ trợ

---

## 📌 CÁCH CẬP NHẬT FILE NÀY

1. **Cuối mỗi ngày (sau standup):** Đổi 🟡 → ✅ khi xong việc
2. **Chủ nhật hàng tuần:** Thêm bảng "Tuần N" mới
3. **Khi gặp vấn đề:** Thêm vào mục "Blockers"
4. **Cuối cùng:** Cập nhật % tổng tiến độ ở đầu file

**Ai cập nhật:** **Vũ** (nhóm trưởng) — nhưng ai cũng có thể đề xuất sửa qua Pull Request.

---

## 🎯 QUY TẮC CẬP NHẬT PROGRESS

| Khi nào             | Cập nhật gì                           | Ai làm    |
| ------------------- | ------------------------------------- | --------- |
| Sau standup tối     | Đổi trạng thái việc đã xong (🟡 → ✅) | Vũ        |
| Khi gặp blocker mới | Thêm dòng vào mục "Blockers"          | Người gặp |
| Chủ nhật            | Thêm section "Tuần N+1"               | Vũ        |
| Cuối tháng          | Review tổng tiến độ                   | Cả nhóm   |
| Khi đổi phân công   | Ghi chú vào "Nhật ký thay đổi"        | Vũ        |

---

## 📞 LIÊN HỆ NHANH THEO VAI TRÒ

| Vấn đề                        | Liên hệ                  |
| ----------------------------- | ------------------------ |
| Điều phối, deadline, kế hoạch | **Vũ** (Lead)            |
| MCP protocol, LLM API         | **Vũ** (MCP Architect)   |
| MySQL, Docker, seed data      | **Hải** (DB Engineer)    |
| Validation Layer, baseline    | **Hải** (Backend)        |
| Bảo mật, injection, dashboard | **Tình** (Security)      |
| Metrics, số liệu, biểu đồ     | **Tường** (Data Analyst) |
| Không biết hỏi ai             | **Nhóm chat chung**      |

---

## 🎯 MỤC TIÊU CUỐI TUẦN 1 (REVIEW)

Trước Chủ nhật 29/09, nhóm phải đạt:

- [ ] `docker compose up -d` chạy không lỗi
- [ ] `SHOW VARIABLES LIKE 'slow_query_log'` → ON
- [ ] `readonly_user` không thể chạy `DROP TABLE`
- [ ] Streamlit `app.py` mở được trên browser
- [ ] Draft 30 query (chưa cần chạy) — đủ 5 nhóm
- [ ] Chốt `docs/api-contract.md` (input/output 6 tool)
- [ ] Tất cả thành viên hiểu phân công mới

---

## ✅ CHECKLIST REVIEW CUỐI TUẦN

**Cuối mỗi tuần, Vũ cập nhật các mục sau:**

| Mục                                             | Trạng thái |
| ----------------------------------------------- | :--------: |
| Cập nhật bảng "Tuần N" với trạng thái từng việc |     ⬜     |
| Thêm bảng "Tuần N+1" kế hoạch                   |     ⬜     |
| Cập nhật % tổng tiến độ ở đầu file              |     ⬜     |
| Kiểm tra Blockers — cái nào đã fix              |     ⬜     |
| Cập nhật Metrics theo dõi                       |     ⬜     |
| Gửi weekly report cho GVHD                      |     ⬜     |
