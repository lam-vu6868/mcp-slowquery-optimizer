# 🌿 GIT WORKFLOW — HƯỚNG DẪN CHO NHÓM

> **File này hướng dẫn:** Từ lúc nhận việc → tạo nhánh → code → push → tạo Pull Request → merge.
> **Dành cho:** Cả 4 thành viên (Vũ, Hải, Tình, Tường).
> **Người viết:** Vũ (nhóm trưởng)

---

## 🎯 TỔNG QUAN — 3 CẤP NHÁNH

```
┌─────────────────────────────────────────────────┐
│  main    = 🏠 Nhà mẫu (sản phẩm cuối, ổn định)  │
│            ↑ Chỉ merge khi đủ milestone         │
│                                                 │
│  dev     = 🏗️ Bãi tập kết (ráp code 4 người)   │
│            ↑ Nơi nhận PR từ nhánh cá nhân       │
│                                                 │
│  feat/.. = 🔨 Bàn riêng (code cá nhân)          │
│            ↑ Mỗi người tự tạo, tự push          │
└─────────────────────────────────────────────────┘
```

**Luồng đi:**

```
feat/...  ──PR──►  dev  ──PR──►  main
```

---

## 📖 CÁC KHÁI NIỆM CƠ BẢN

| Khái niệm             | Nghĩa dễ hiểu                               |
| --------------------- | ------------------------------------------- |
| **Branch**            | Nhánh — "bàn làm việc riêng" cho từng người |
| **Push**              | Đẩy code từ máy lên GitHub                  |
| **Pull**              | Kéo code từ GitHub về máy                   |
| **Pull Request (PR)** | Yêu cầu merge code từ nhánh A sang nhánh B  |
| **Review**            | Người khác đọc code của bạn để kiểm tra     |
| **Approve**           | "Đồng ý" — cho phép merge PR                |
| **Merge**             | Gộp code từ nhánh A sang nhánh B            |
| **Conflict**          | Xung đột code — 2 người sửa cùng 1 dòng     |

---

## 🚀 QUY TRÌNH 6 BƯỚC — TỪ NHẬN VIỆC ĐẾN HOÀN THÀNH

### BƯỚC 1 — LẤY CODE MỚI NHẤT VỀ

**Mục đích:** Đảm bảo máy bạn có code mới nhất từ `dev`.

```bash
# 1. Chuyển về nhánh dev
git checkout dev

# 2. Kéo code mới nhất từ GitHub
git pull origin dev
```

⚠️ **Luôn làm bước này TRƯỚC khi code** — tránh conflict không đáng có.

---

### BƯỚC 2 — TẠO NHÁNH CÁ NHÂN

**Mục đích:** Tạo "bàn làm việc riêng" cho task sắp làm.

```bash
# Tạo và chuyển sang nhánh mới
git checkout -b feat/<ten-ban>-<viec>
```

**Ví dụ theo phân công:**

| Thành viên | Lệnh tạo nhánh                       |
| ---------- | ------------------------------------ |
| Hải        | `git checkout -b feat/hai-seed-data` |
| Tình       | `git checkout -b feat/tinh-security` |
| Tường      | `git checkout -b feat/tuong-metrics` |
| Vũ         | `git checkout -b feat/vu-mcp-server` |

**Kiểm tra đang ở nhánh nào:**

```bash
git branch
```

→ Nhánh có dấu `*` là nhánh hiện tại.

---

### BƯỚC 3 — CODE + COMMIT

**Mục đích:** Viết code và lưu lại từng bước.

```bash
# 1. Xem file đã sửa
git status

# 2. Thêm file muốn commit
git add <file>          # Thêm 1 file
git add .               # Thêm TẤT CẢ file

# 3. Commit với message rõ ràng
git commit -m "feat(data): add seed_orders.py"
```

**Commit message theo convention:**

| Prefix   | Dùng khi       | Ví dụ                             |
| -------- | -------------- | --------------------------------- |
| `feat:`  | Thêm tính năng | `feat(mcp): add get_schema tool`  |
| `fix:`   | Sửa bug        | `fix(validation): correct P95`    |
| `docs:`  | Sửa tài liệu   | `docs(readme): update setup`      |
| `test:`  | Thêm test      | `test(security): add payload #21` |
| `chore:` | Việc vặt       | `chore: update .gitignore`        |

---

### BƯỚC 4 — PUSH LÊN GITHUB

**Mục đích:** Đưa code từ máy lên GitHub để cả nhóm thấy.

```bash
# Lần đầu push nhánh mới (dùng -u)
git push -u origin feat/hai-seed-data

# Các lần sau (không cần -u)
git push
```

**Giải thích `-u`:**

- `-u` = viết tắt của `--set-upstream`
- "Đăng ký cặp nhánh local ↔ remote"
- Dùng **1 lần đầu** → các lần sau chỉ cần `git push`

---

### BƯỚC 5 — TẠO PULL REQUEST TRÊN GITHUB

**Mục đích:** Yêu cầu merge code từ nhánh cá nhân vào `dev`.

**Làm trên GitHub web:**

1. Vào repo: https://github.com/lam-vu6868/mcp-slowquery-optimizer
2. Tab **Pull requests** → **New pull request**
3. Chọn:
   - **base:** `dev` ← nhánh nhận
   - **compare:** `feat/hai-seed-data` ← nhánh gửi
4. Điền tiêu đề + mô tả:

```markdown
## 📋 Mô tả

Thêm script seed 1M users.

## 🎯 Loại

- [x] Feature mới
- [ ] Bug fix
- [ ] Documentation

## 🧪 Đã test

- [x] Chạy local OK
- [x] COUNT(\*) users = 1,000,000
```

5. Gán reviewer: **Vũ**
6. Bấm **Create pull request**

---

### BƯỚC 6 — CHỜ REVIEW + MERGE

**Luồng review:**

```
1. Reviewer đọc code (Files changed)
2. Reviewer bấm "Review changes"
3. Reviewer chọn "Approve" → Submit review
4. Author bấm "Merge pull request"
5. Bấm "Confirm merge"
```

⚠️ **KHÔNG bấm "Delete branch"** — giữ nhánh lại để dùng tiếp.

---

## 🎬 VÍ DỤ THỰC TẾ — HẢI LÀM SEED DATA

**Task:** Hải được giao viết script seed 1M users.

### Bước 1: Kéo code mới nhất

```bash
git checkout dev
git pull origin dev
```

### Bước 2: Tạo nhánh

```bash
git checkout -b feat/hai-seed-data
```

### Bước 3: Code + commit

```bash
# Viết file data/seed/seed_users.py
notepad data/seed/seed_users.py

# Commit
git add data/seed/seed_users.py
git commit -m "feat(data): add seed_users.py for 1M users"
```

### Bước 4: Push

```bash
git push -u origin feat/hai-seed-data
```

### Bước 5: Tạo PR trên GitHub

- base: `dev`
- compare: `feat/hai-seed-data`
- Title: `feat: seed 1M users`
- Reviewer: Vũ

### Bước 6: Chờ Vũ approve → Merge

→ Xong! Code Hải đã vào `dev`.

---

## 🔧 CÁC LỆNH GIT HAY DÙNG

| Lệnh                      | Công dụng                            |
| ------------------------- | ------------------------------------ |
| `git status`              | Xem file đã sửa                      |
| `git branch`              | Xem đang ở nhánh nào                 |
| `git branch -a`           | Xem tất cả nhánh (cả local + remote) |
| `git checkout <nhánh>`    | Chuyển nhánh                         |
| `git checkout -b <nhánh>` | Tạo nhánh mới                        |
| `git add .`               | Thêm tất cả file vào staging         |
| `git commit -m "..."`     | Commit                               |
| `git push`                | Đẩy lên GitHub                       |
| `git pull`                | Kéo code mới về                      |
| `git log --oneline -5`    | Xem 5 commit gần nhất                |
| `git diff`                | Xem thay đổi chưa add                |

---

## 🆘 XỬ LÝ CONFLICT

### Khi nào conflict xảy ra?

Khi **2 người sửa cùng 1 dòng** trong cùng file.

### Cách nhận biết:

Khi pull hoặc merge, Git báo:

```
CONFLICT (content): Merge conflict in data/seed/seed_users.py
```

### Cách fix:

**Bước 1:** Mở file bị conflict → tìm dấu:

```python
<<<<<<< HEAD
Code CỦA BẠN
=======
Code TỪ NGƯỜI KHÁC
>>>>>>> dev
```

**Bước 2:** Chọn giữ code nào:

- Giữ code của bạn → xóa phần `=======` đến `>>>>>>>`
- Giữ code người khác → xóa phần `<<<<<<<` đến `=======`
- Giữ cả 2 → kết hợp

**Bước 3:** Xóa tất cả dấu `<<<`, `===`, `>>>`.

**Bước 4:**

```bash
git add <file-đã-fix>
git commit -m "fix: resolve conflict in seed_users.py"
git push
```

### Nếu bí quá:

```bash
# Hủy merge, quay về trạng thái trước
git merge --abort

# Nhắn Vũ ngay
```

---

## 🚫 NHỮNG ĐIỀU KHÔNG ĐƯỢC LÀM

| ❌ Không                            | Lý do                            |
| ----------------------------------- | -------------------------------- |
| Push thẳng lên `main`               | Bị branch protection chặn        |
| Push thẳng lên `dev`                | Phải qua PR + review             |
| `git push --force` lên `main`/`dev` | Xóa lịch sử, mất code người khác |
| Tự approve PR của mình              | GitHub chặn                      |
| Merge khi CI chưa pass              | Code có thể lỗi                  |
| Commit file `.env`                  | Lộ API key                       |
| Commit file > 10MB                  | GitHub từ chối                   |

---

## ✅ CHECKLIST TRƯỚC KHI PUSH

- [ ] Đang ở **đúng nhánh** (`git branch`)
- [ ] Đã **pull code mới** từ `dev`
- [ ] Không commit file `.env`
- [ ] Không commit file > 10MB
- [ ] Commit message **rõ ràng**, theo convention
- [ ] Code chạy được ở máy mình

---

## ✅ CHECKLIST TRƯỚC KHI TẠO PR

- [ ] Đã push nhánh lên GitHub
- [ ] base = `dev`, compare = `feat/...`
- [ ] Title rõ ràng
- [ ] Description đủ thông tin
- [ ] Gán reviewer đúng (Vũ)
- [ ] CI pass (không thấy dấu đỏ)

---

## 📞 KHI BÍ — HỎI AI?

| Vấn đề                | Hỏi ai               |
| --------------------- | -------------------- |
| Git conflict          | **Vũ** (nhóm trưởng) |
| Quên lệnh Git         | Đọc lại file này     |
| Không push được       | **Vũ**               |
| Token hết hạn         | **Vũ**               |
| Không biết cần làm gì | **Vũ**               |

---

## 🎯 5 NGUYÊN TẮC VÀNG

1. **Luôn pull trước khi code** — tránh conflict
2. **Không push thẳng `main`** — mọi thứ qua PR
3. **Commit nhỏ, thường xuyên** — dễ revert
4. **Bí thì hỏi** — không tự phá
5. **Không force push** — mất code người khác

---

## 📚 TÀI LIỆU THAM KHẢO

- [Atlassian Git Tutorial](https://www.atlassian.com/git/tutorials)
- [GitHub Docs](https://docs.github.com/)
- [Learn Git Branching](https://learngitbranching.js.org/) — học qua game

---

**Cập nhật lần cuối:** 28/09/2025 — bởi Vũ
