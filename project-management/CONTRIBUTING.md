# 📜 QUY ĐỊNH CONTRIBUTE

> **File này quy định:** Cách làm việc nhóm, Git flow, ai sửa file nào.
> **Ai cũng phải đọc trước khi commit lần đầu.**
> **Người duy trì:** Vũ (nhóm trưởng)

---

## 🌿 1. GIT BRANCH

### Các nhánh chính

| Nhánh                    | Vai trò                                | Ai được push            |
| ------------------------ | -------------------------------------- | ----------------------- |
| `main`                   | Nhánh chính, **LUÔN chạy được**        | Chỉ Vũ (sau khi review) |
| `dev`                    | Nhánh phát triển, tích hợp các feature | Cả nhóm (qua PR)        |
| `feat/<ten>-<chuc-nang>` | Nhánh cá nhân                          | Người tạo nhánh         |

### Danh sách nhánh cá nhân

| Thành viên | Nhánh                |
| ---------- | -------------------- |
| **Vũ** ⭐  | `feat/vu-mcp-server` |
| **Hải**    | `feat/hai-seed-data` |
| **Tình**   | `feat/tinh-security` |
| **Tường**  | `feat/tuong-metrics` |

### Quy tắc đặt tên nhánh

```
feat/<ten-nguoi>-<chuc-nang-chinh>

Ví dụ:
✅ feat/vu-mcp-server
✅ feat/hai-validation-layer
✅ feat/tinh-dashboard
✅ feat/tuong-metrics-chart

❌ feature1
❌ test
❌ my-branch
❌ fix-loi
```

---

## 🔀 2. QUY TRÌNH LÀM VIỆC (5 BƯỚC)

### Bước 1 — Pull code mới nhất

```bash
# Chuyển về nhánh dev
git checkout dev

# Pull code mới nhất từ GitHub
git pull origin dev
```

⚠️ **Luôn pull trước khi làm việc mới.** Nếu không pull → sẽ conflict khi push.

### Bước 2 — Tạo nhánh cá nhân (nếu chưa có)

```bash
# Tạo nhánh mới
git checkout -b feat/vu-mcp-server

# Hoặc chuyển sang nhánh cũ đã có
git checkout feat/vu-mcp-server
```

### Bước 3 — Code + Commit

```bash
# Xem file đã sửa
git status

# Thêm file vào staging
git add <file>
# Hoặc thêm tất cả
git add .

# Commit với message theo convention
git commit -m "feat(mcp): add get_slow_queries tool"
```

### Bước 4 — Push lên GitHub

```bash
# Lần đầu push nhánh mới
git push -u origin feat/vu-mcp-server

# Các lần sau
git push
```

### Bước 5 — Tạo Pull Request

1. Vào GitHub repo → tab **Pull requests** → **New pull request**
2. Chọn:
   - **base:** `dev`
   - **compare:** `feat/vu-mcp-server`
3. Điền tiêu đề + mô tả
4. Gán **reviewer** (theo bảng bên dưới)
5. Chờ approve → **merge**

---

## ✍️ 3. COMMIT MESSAGE CONVENTION

### Format

```
<type>(<scope>): <mô tả ngắn>

Ví dụ:
feat(mcp): add get_slow_queries tool
fix(validation): correct P95 calculation
docs(readme): update setup guide
test(security): add 5 injection cases
refactor(server): split server.py into modules
chore(deps): update requirements.txt
```

### Bảng type

| Type       | Ý nghĩa                           | Ví dụ                               |
| ---------- | --------------------------------- | ----------------------------------- |
| `feat`     | Thêm tính năng mới                | `feat(mcp): add benchmark_query`    |
| `fix`      | Sửa bug                           | `fix(validation): hash compare sai` |
| `docs`     | Sửa tài liệu                      | `docs(readme): update setup`        |
| `test`     | Thêm/sửa test                     | `test(security): add payload #21`   |
| `refactor` | Tái cấu trúc (không đổi behavior) | `refactor(tools): split apply.py`   |
| `chore`    | Việc vặt (deps, config)           | `chore: update .gitignore`          |
| `perf`     | Tối ưu hiệu năng                  | `perf(seed): use LOAD DATA INFILE`  |
| `style`    | Format code                       | `style: format with black`          |

### Bảng scope (phạm vi)

| Scope        | Khi nào dùng                       |
| ------------ | ---------------------------------- |
| `mcp`        | Liên quan `mcp_server/`            |
| `db`         | Liên quan `db/`                    |
| `data`       | Liên quan `data/`                  |
| `security`   | Liên quan `security/`              |
| `dashboard`  | Liên quan `dashboard/`             |
| `validation` | Liên quan `mcp_server/validation/` |
| `llm`        | Liên quan `mcp_server/llm/`        |
| `test`       | Liên quan `tests/`                 |
| `docs`       | Liên quan `docs/`                  |

### Commit message tốt vs xấu

| ❌ Xấu    | ✅ Tốt                                    |
| --------- | ----------------------------------------- |
| `update`  | `feat(mcp): add get_schema tool`          |
| `fix bug` | `fix(validation): correct rollback logic` |
| `abc`     | `docs(readme): add Vũ as team lead`       |
| `code`    | `feat(dashboard): add tab 4 security`     |
| `done`    | `test(security): 20/20 injection pass`    |

---

## 👤 4. AI SỬA FILE NÀO

### Nguyên tắc vàng

> **Muốn sửa file của người khác → tạo Pull Request.**
> **KHÔNG commit trực tiếp lên branch của người khác.**

### Bảng chi tiết

| Thư mục/File                       | Người CHÍNH      |  Người REVIEW   | Người KHÁC được sửa? |
| ---------------------------------- | ---------------- | :-------------: | :------------------: |
| `mcp_server/server.py`             | **Vũ** ⭐        |      Tình       |       ❌ Không       |
| `mcp_server/tools/slow_queries.py` | **Vũ**           |       Hải       |          ❌          |
| `mcp_server/tools/schema.py`       | **Vũ**           |       Hải       |          ❌          |
| `mcp_server/tools/stats.py`        | **Vũ**           |       Hải       |          ❌          |
| `mcp_server/tools/explain.py`      | **Hải**          |       Vũ        |          ❌          |
| `mcp_server/tools/benchmark.py`    | **Hải**          |       Vũ        |          ❌          |
| `mcp_server/tools/apply.py`        | **Vũ**           |   **Tình** ⚠️   |          ❌          |
| `mcp_server/llm/agent.py`          | **Vũ**           |      Tường      |          ❌          |
| `mcp_server/llm/prompts.py`        | **Vũ**           |      Tường      |          ❌          |
| `mcp_server/llm/parsers.py`        | **Vũ**           |      Tường      |          ❌          |
| `mcp_server/validation/`           | **Hải**          |       Vũ        |          ❌          |
| `mcp_server/utils/db.py`           | **Hải**          |       Vũ        |          ❌          |
| `mcp_server/utils/config.py`       | **Vũ**           |       Hải       |          ❌          |
| `db/schema.sql`                    | **Hải**          |      Tường      |          ❌          |
| `db/init.sql`                      | **Hải**          |      Tường      |          ❌          |
| `data/seed/`                       | **Hải**          |      Tường      |          ❌          |
| `data/queries/queries.py`          | **Tường**        |       Hải       |          ❌          |
| `data/queries/ground_truth.json`   | **Tường**        | **GVHD ký** ⚠️  |          ❌          |
| `data/metrics/`                    | **Tường**        |       Hải       |          ❌          |
| `security/ast_whitelist.py`        | **Tình**         |       Vũ        |          ❌          |
| `security/injection_tests/`        | **Tình**         |       Vũ        |          ❌          |
| `security/injection_report.md`     | **Tình**         |       Vũ        |          ❌          |
| `dashboard/app.py`                 | **Tình**         |      Tường      |          ❌          |
| `dashboard/pages/`                 | **Tình**         |      Tường      |          ❌          |
| `tests/`                           | **Ai cũng viết** | Người review PR |          ✅          |
| `docs/`                            | **Vũ**           |     Cả nhóm     |     ✅ (qua PR)      |
| `reports/`                         | **Vũ**           |     Cả nhóm     |     ✅ (qua PR)      |
| `README.md`, `PROGRESS.md`         | **Vũ**           |     Cả nhóm     |     ✅ (qua PR)      |
| `TEAM.md`, `ROADMAP.md`            | **Vũ**           |     Cả nhóm     |     ✅ (qua PR)      |
| `CONTRIBUTING.md`                  | **Vũ**           |     Cả nhóm     |     ✅ (qua PR)      |

### Reviewer mapping

| Người tạo PR | Reviewer mặc định |
| ------------ | ----------------- |
| Vũ           | Tình hoặc Hải     |
| Hải          | Vũ                |
| Tình         | Vũ                |
| Tường        | Hải               |

⚠️ **Không tự review PR của mình.** Phải có người khác approve.

---

## 🚫 5. KHÔNG ĐƯỢC COMMIT

| ❌ Không commit                      | Lý do                               |
| ------------------------------------ | ----------------------------------- |
| `.env`, `.env.local`                 | Chứa API key, mật khẩu → lộ bảo mật |
| File CSV > 10MB                      | GitHub giới hạn 100MB/file          |
| File DB (`*.sql`, `*.sql.gz`) > 50MB | Quá nặng                            |
| `__pycache__/`, `*.pyc`              | File tạm, tự sinh                   |
| `.venv/`, `venv/`                    | Môi trường ảo, ai cũng tự tạo được  |
| `data/outputs/`                      | Kết quả tạm                         |
| `~$*.docx`, `~$*.pptx`               | File lock của Office                |
| `.DS_Store`, `Thumbs.db`             | File hệ thống                       |
| `mysql-data/`                        | Volume Docker                       |

→ **Đã có `.gitignore` xử lý tự động.** Nhưng nếu bạn vô tình `git add` → cẩn thận.

### Nếu lỡ commit file lớn

```bash
# Xóa khỏi Git nhưng giữ file local
git rm --cached path/to/large-file.csv

# Thêm vào .gitignore
echo "path/to/large-file.csv" >> .gitignore

# Commit
git add .gitignore
git commit -m "chore: remove large file from git"
```

---

## 🆘 6. KHI BỊ CONFLICT

### Bước 1 — Bình tĩnh, KHÔNG force push

```bash
# Không bao giờ chạy lệnh này!
git push --force
```

### Bước 2 — Pull code mới nhất

```bash
git checkout dev
git pull origin dev

git checkout feat/vu-mcp-server
git rebase dev
```

### Bước 3 — Fix conflict

Git sẽ báo file nào conflict:

```bash
# Mở file, tìm dấu:
<<<<<<< HEAD
Code của bạn
=======
Code mới từ dev
>>>>>>> dev
```

Chọn giữ code nào (hoặc kết hợp cả 2), xóa dấu `<<<`, `===`, `>>>`.

### Bước 4 — Continue rebase

```bash
git add <file-đã-fix>
git rebase --continue
```

### Bước 5 — Push lại

```bash
git push --force-with-lease
```

⚠️ Chỉ dùng `--force-with-lease` (an toàn hơn `--force`).

### Nếu bí quá

```bash
# Hủy rebase, quay về trạng thái trước
git rebase --abort
```

→ **Nhắn Vũ (nhóm trưởng) ngay.** Đừng tự phá.

---

## ✅ 7. CHECKLIST TRƯỚC KHI MỞ PULL REQUEST

Trước khi bấm "Create pull request", tự kiểm tra:

- [ ] Code chạy được ở máy mình (`python -m mcp_server.server` hoặc `streamlit run dashboard/app.py`)
- [ ] Không commit file `.env`
- [ ] Không commit file > 10MB
- [ ] Commit message rõ ràng, theo convention
- [ ] Đã pull code mới nhất từ `dev` và rebase
- [ ] Update `README.md` nếu có thay đổi setup
- [ ] Update `PROGRESS.md` nếu hoàn thành việc
- [ ] Đã chạy `pytest tests/` (nếu có test)
- [ ] Đã gán ít nhất 1 reviewer

---

## 📝 8. TEMPLATE PULL REQUEST

Khi tạo PR, copy template này:

```markdown
## 📋 Mô tả

<!-- Mô tả ngắn gọn PR này làm gì -->

## 🎯 Loại thay đổi

- [ ] Feature mới
- [ ] Bug fix
- [ ] Documentation
- [ ] Test
- [ ] Refactor
- [ ] Khác: ...

## 🔗 Liên quan

- Issue: #
- Giai đoạn: Tuần X

## 🧪 Đã test

- [ ] Chạy local OK
- [ ] Chạy `pytest tests/` OK
- [ ] Test thủ công các case liên quan

## 📸 Screenshot (nếu có UI)

<!-- Paste screenshot -->

## ⚠️ Lưu ý cho reviewer

<!-- Có gì cần chú ý đặc biệt khi review? -->
```

---

## 🗣️ 9. KÊNH LIÊN LẠC

| Kênh                     | Mục đích                 | Tần suất            |
| ------------------------ | ------------------------ | ------------------- |
| **Discord/Zoom**         | Daily standup 21h        | Hàng ngày (15 phút) |
| **Zalo/Messenger nhóm**  | Chat nhanh, hỏi đáp      | Liên tục            |
| **GitHub Issues**        | Báo bug, đề xuất feature | Khi cần             |
| **GitHub Pull Requests** | Review code              | Khi code xong       |
| **Email GVHD**           | Weekly report            | Chủ nhật hàng tuần  |

### Ai báo cáo gì cho ai?

| Việc           | Người báo cáo   | Người nhận |
| -------------- | --------------- | ---------- |
| Bug MCP Server | Người phát hiện | Vũ         |
| Bug DB         | Người phát hiện | Hải        |
| Bug Security   | Người phát hiện | Tình       |
| Bug Metrics    | Người phát hiện | Tường      |
| Tiến độ tuần   | Vũ              | GVHD       |

---

## 🎓 10. QUY TẮC ỨNG XỬ

### Khi review code người khác

| ✅ Nên                                | ❌ Không nên        |
| ------------------------------------- | ------------------- |
| "Đoạn này có thể viết gọn hơn không?" | "Code dở quá"       |
| "Anh nghĩ nên thêm try/except ở đây"  | "Sai bét"           |
| "Test case này chưa cover"            | "Test như ..."      |
| Comment cụ thể dòng nào               | Comment chung chung |

### Khi nhận review

| ✅ Nên                   | ❌ Không nên              |
| ------------------------ | ------------------------- |
| Cảm ơn feedback          | Cãi lại                   |
| Giải thích nếu chưa hiểu | Im lặng                   |
| Sửa + commit lại         | Force push để xóa lịch sử |
| Hỏi lại nếu không đồng ý | Tự ý merge                |

### Nguyên tắc vàng

> **"Code của bạn không phải là bạn."**
> **Review code, không review con người.**

---

## 📊 11. BẢNG TÓM TẮT NHANH

| Việc           | Lệnh/Người                          |
| -------------- | ----------------------------------- |
| Pull code mới  | `git checkout dev && git pull`      |
| Tạo branch mới | `git checkout -b feat/<ten>-<viec>` |
| Commit         | `git commit -m "type(scope): msg"`  |
| Push           | `git push`                          |
| Tạo PR         | GitHub → New pull request           |
| Review PR      | Người được gán                      |
| Merge          | Vũ (sau khi approve)                |
| Bị conflict    | Rebase, không force push            |
| Cần hỏi        | Nhóm chat chung                     |

---

## 🎯 12. COMMIT ĐẦU TIÊN CỦA BẠN

Nếu bạn mới vào nhóm, làm theo các bước sau:

```bash
# 1. Clone repo
git clone https://github.com/<username>/mcp-slowquery-optimizer.git
cd mcp-slowquery-optimizer

# 2. Cấu hình Git (lần đầu)
git config user.name "Tên của bạn"
git config user.email "email@example.com"

# 3. Chuyển sang nhánh dev
git checkout dev

# 4. Tạo nhánh cá nhân
git checkout -b feat/<ten-nguoi>-<viec>

# Ví dụ:
# Hải: git checkout -b feat/hai-seed-data
# Tình: git checkout -b feat/tinh-security
# Tường: git checkout -b feat/tuong-metrics

# 5. Sửa file theo phân công

# 6. Commit
git add .
git commit -m "feat(data): add seed_users.py for 1M users"

# 7. Push
git push -u origin feat/hai-seed-data

# 8. Tạo Pull Request trên GitHub
```

---

## 📌 13. CÁC LỆNH GIT HAY DÙNG

| Lệnh                      | Công dụng                           |
| ------------------------- | ----------------------------------- |
| `git status`              | Xem file đã sửa                     |
| `git log --oneline -10`   | Xem 10 commit gần nhất              |
| `git diff`                | Xem thay đổi chưa add               |
| `git diff --staged`       | Xem thay đổi đã add                 |
| `git stash`               | Tạm cất thay đổi                    |
| `git stash pop`           | Lấy lại thay đổi                    |
| `git branch -a`           | Xem tất cả branch                   |
| `git checkout <branch>`   | Chuyển branch                       |
| `git reset --soft HEAD~1` | Hủy commit gần nhất (giữ file)      |
| `git reset --hard HEAD~1` | Hủy commit + xóa file (⚠️ cẩn thận) |

---

## 🎯 14. 5 NGUYÊN TẮC VÀNG

1. **Luôn pull trước khi code** — tránh conflict không đáng có
2. **Commit nhỏ, thường xuyên** — dễ revert khi sai
3. **Không push thẳng `main`** — mọi thứ qua PR
4. **Không commit file rác** — xem mục 5
5. **Bí thì hỏi** — không tự phá, không force push

---

## 📞 15. KHI KHẨN CẤP

| Tình huống                | Hành động                                            |
| ------------------------- | ---------------------------------------------------- |
| Lỡ commit API key         | Xóa key trên Anthropic Console + rotate key mới NGAY |
| Lỡ push code lỗi lên main | Báo Vũ, revert commit                                |
| Bị conflict nặng          | `git rebase --abort`, nhắn Vũ                        |
| Mất code chưa commit      | `git reflog`, tìm lại                                |
| Không push được           | Kiểm tra quyền GitHub, nhắn Vũ                       |

---

## ✅ ĐỌC XONG = ĐÃ HIỂU

Bằng việc đọc hết file này, bạn đồng ý:

- [ ] Làm việc theo Git flow đã quy định
- [ ] Commit message theo convention
- [ ] Không sửa file người khác mà không báo
- [ ] Không commit file rác
- [ ] Tôn trọng đồng đội trong review

**Chữ ký nhóm:** Vũ – Hải – Tình – Tường

---

## 📅 CẬP NHẬT LẦN CUỐI

- **Ngày:** 28/09/2025
- **Người cập nhật:** Vũ
- **Thay đổi:** Đổi vai trò Vũ = Lead, Tình = Security, cập nhật bảng ai sửa file nào
