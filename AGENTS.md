# Hướng dẫn làm việc trong MCP Slow Query Optimizer

Áp dụng cho repository này. Đây là quy tắc và bản đồ để bắt đầu cuộc chat mới, không thay thế yêu cầu mới nhất của người dùng.

## Giao tiếp và phạm vi

- Trao đổi bằng tiếng Việt, giải thích ngắn gọn cho người đang học dự án. Khi mô tả luồng, nêu dữ liệu đến từ đâu, hàm nào xử lý, kiểm tra gì và trả về gì.
- Nếu người dùng chỉ hỏi kiến thức hoặc xin ví dụ, trả lời trong chat. Chỉ sửa file khi người dùng yêu cầu tạo hoặc sửa code/tài liệu.
- Làm đúng chặng được yêu cầu; không tự triển khai toàn bộ roadmap. Ưu tiên thay đổi nhỏ, rõ ràng, dùng lại cấu trúc và helper hiện có.
- Khi sửa file mã nguồn, **giữ comment/docstring đầu file của nhóm** (chức năng, phụ trách, lưu ý, tham khảo). Chỉ bỏ hoặc cập nhật dòng `TRẠNG THÁI : KHUNG RỖNG` khi file đã có mã thực thi; không xóa cả phần đầu trang để thay bằng mô tả ngắn.
- Không sửa phần việc của thành viên khác ngoài phạm vi yêu cầu; xem người phụ trách và reviewer trong `project-management/TEAM.md` và `project-management/CONTRIBUTING.md`.

## Đọc tài liệu và xác định trạng thái

- Bắt đầu từ `README.md`, `project-management/ROADMAP.md`, `project-management/PROGRESS.md`; sau đó đọc phần liên quan trong `docs/api-contract.md`, `docs/architecture.md` và file code/test sẽ đụng tới.
- `ROADMAP.md` là nguồn cho mốc và quyết định kỹ thuật; `api-contract.md` quy định input/output của 6 tool. Nếu đổi contract, nêu rõ ảnh hưởng tới caller và tài liệu.
- `PROGRESS.md` và `README.md` có thể cũ. Kiểm tra `git status`, code và test thực tế trước khi nói một tính năng đã hoàn thành. File chỉ chứa docstring `KHUNG RỖNG` chưa phải tính năng.
- Đối chiếu mọi kết luận từ Graphify hoặc tài liệu với code hiện tại. Nếu có `graphify-out/`, kiểm tra độ mới trước khi dùng; không tạo graph chỉ để thay cho việc đọc vài file liên quan.

## Bản đồ dự án

- Python 3.11+, MySQL 8.0 qua Docker (cổng host 3307), MCP server và Dashboard Streamlit.
- `mcp_server/tools/`: Tool 1–6; `mcp_server/server.py`: điểm đăng ký tool; `mcp_server/utils/`: config, kết nối DB, logging, sanitize.
- `security/`: AST whitelist, approval token, kiểm thử prompt injection; `mcp_server/validation/`: kiểm chứng index; `mcp_server/llm/`: agent và parser.
- `data/queries/`: 30 query và ground truth; `data/metrics/`, `data/baseline/`: đánh giá; `dashboard/`: giao diện; `tests/`: kiểm thử.
- Chạy Python từ thư mục gốc, ưu tiên `venv/Scripts/python.exe` trên Windows nếu có. Không sửa thư viện trong `venv/` hoặc ghi dữ liệu tạm vào Git.

## Ranh giới an toàn của dự án

- Tool 1–5 dùng `get_conn()` với `readonly_user`; chỉ Tool 6 dùng `get_admin_conn()` với `index_admin`. LLM chỉ được thấy Tool 1–5.
- SQL nhận từ bên ngoài phải qua `security/ast_whitelist.py` trước khi chạy. SQL/comment lấy từ DB để đưa cho LLM là dữ liệu không tin cậy: làm sạch phù hợp và gắn `untrusted: true` theo contract.
- Tool 6 chỉ nhận proposal và approval token một lần từ backend Dashboard; không nhận SQL tự do hoặc tự áp dụng đề xuất rewrite. Validation phải đạt trước khi index được duyệt áp dụng.
- Không in, gửi vào tool hoặc commit `.env`, API key, mật khẩu, token hay dữ liệu nhạy cảm. Không reset DB, xóa volume, tạo/drop index thật chỉ để thử khi chưa rõ tác động; dùng test giả lập cho logic và báo rõ phần chưa thử với MySQL.
- Giữ giới hạn số dòng, timeout và xử lý lỗi ở ranh giới DB. Không biến một test đơn vị pass thành tuyên bố toàn hệ thống chạy được.

## Cách triển khai và kiểm tra

1. Đọc đầu file đích, caller, test, config và contract liên quan; liệt kê những chỗ thay đổi có thể ảnh hưởng.
2. Viết phần nhỏ nhất hoàn chỉnh, thêm test có ý nghĩa cho logic mới hoặc bug được sửa. Không thêm tầng hay dependency khi code hiện có đã đủ.
3. Chạy test phù hợp; trên PowerShell dùng thư mục tạm mới do chính tài khoản đang chạy tạo (tránh lỗi ACL khi dùng chung thư mục pytest giữa sandbox và user):

   ```powershell
   $pytestTemp = Join-Path $env:TEMP ("pytest-user-" + [guid]::NewGuid().ToString("N"))
   .\venv\Scripts\python.exe -m pytest tests/ -q -p no:cacheprovider --basetemp="$pytestTemp"
   ```

   Chạy cả hai dòng mỗi lần test. Chạy Ruff cho các file Python đã sửa nếu có trong venv. Với tài liệu thuần túy, kiểm tra nội dung và `git diff --check` là đủ.

4. Báo rõ đã sửa gì, test nào pass, phần nào chưa chạy với MySQL/Dashboard thật. Chỉ cập nhật trạng thái Done trong tài liệu sau khi phần cần thiết đã được kiểm chứng.
- Theo `project-management/CONTRIBUTING.md`: không push thẳng `main`, không commit bí mật; PR vào `dev` và để đúng người review. Không tự push hoặc merge khi người dùng chưa yêu cầu.

## Điểm bàn giao để kiểm tra lại khi mở chat mới

- Cập nhật bàn giao 21/11/2026: dataset `shopdb.multitable-v1` gồm 5 bảng/tổng 5M dòng, đã thay bộ `sales_data`. Xem số dòng từng bảng ở `PROGRESS.md` và schema ở `db/schema.sql`.
- `data/queries/ground_truth.json`: 30/30 phương án đạt đo kiểm chứng (3 warm-up +20 lượt; hash/số dòng khớp, không timeout, P95 giảm ≥20%), còn chờ Hải review/GVHD ký. Không coi đây là tối ưu toàn cục hoặc đã đo đủ trade-off ghi/đọc.
- `ground_truth_candidates.py` chứa phương án thử; `scripts/verify_ground_truth.py` là script offline lab có tạo/drop index tạm, không phải MCP Tool 6. Chỉ chạy nhánh đo khi đã được cho phép và hiểu tác động; không chạy song song benchmark. Nhánh `--check` chỉ đọc bằng chứng, không kết nối DB.
- Bằng chứng raw trong `data/outputs/` (gitignored), gồm baseline `p95_baseline_multitable_raw.json` và `ground_truth_validation/report.json` cùng file từng lượt. Không xóa bằng chứng; `--check` cần các file này. Kết quả đã xác nhận: audit 30/30 pass, 125 unit tests pass (người dùng cũng đã chạy).
- Sau batch, `gt_trial_*` đã dọn, index ban đầu đã khôi phục; `idx_gt_q01_cover` vẫn INVISIBLE, `fk_order_items_product` vẫn VISIBLE. Không tự drop/recreate chỉ để test.
- Bàn giao 22/11/2026: Tool 1 đọc `performance_schema` (nhánh `mysql.slow_log` chưa có do thiếu quyền SELECT riêng); Tool 2 đọc schema; Tool 3 lấy thống kê bằng mẫu PK giới hạn. `server.py` dùng MCP SDK 2.x, đăng ký Tool 1–5 qua stdio; Tool 4–5 chỉ lộ wrapper giới hạn cho LLM, Tool 6 không được đăng ký.
- Đã thử client MCP gọi cả 5 tool trên MySQL thật, đều `ok=true`; 150 unit tests pass, Ruff pass cho `server.py`/test mới và Tool 3. Chưa có LLM host, Validation Layer, Tool 6, Dashboard end-to-end. Contract v2 còn DRAFT chờ nhóm review; chặng Tool 1–5 MCP chưa đánh dấu Done vì Tool 1 còn thiếu nguồn slow log và chưa kiểm chứng toàn bộ tiêu chí roadmap.
- Bước code kế tiếp: đọc `mcp_server/llm/agent.py`, `parsers.py`, `prompts.py`, contract và caller rồi tích hợp LLM host chỉ thấy Tool 1–5; test bằng LLM giả trước khi dùng API thật. Hãy kiểm tra `git status` và thay đổi hiện có trước khi sửa, không ghi đè phần chưa commit. `PROGRESS.md` là trạng thái mới nhất sau mỗi lần kiểm chứng.

## Công cụ và lời nhắn mở đầu

- Chọn công cụ theo việc: Ponytail cho thay đổi gọn; Agent Skills cho quy trình phù hợp; Context7 khi API thư viện có thể đã đổi; Playwright khi cần kiểm tra UI đang chạy bằng dữ liệu thử; Graphify khi cần truy vết nhiều quan hệ code. Không commit snapshot/log tạm của Playwright hoặc `graphify-out/` khi chỉ dùng cục bộ.
- Khi người dùng nhắn **“Tiếp tục dự án theo AGENTS.md”**: đọc tài liệu ở trên, kiểm tra working tree và code/test của chặng đang làm, rồi báo ngắn gọn trạng thái đã xác minh cùng bước kế tiếp. Chỉ sửa file nếu yêu cầu hiện tại là triển khai hoặc sửa đổi.

Gợi ý mở chat mới:

```text
Tiếp tục dự án theo AGENTS.md. Đọc README.md, ROADMAP/PROGRESS và contract liên quan;
kiểm tra git status, code và test thực tế rồi cho tôi biết chặng hiện tại và bước tiếp theo.
```

Nếu muốn tiếp tục viết code ngay, thêm: `Triển khai bước LLM host trong mcp_server/llm/agent.py theo chặng hiện tại.`
