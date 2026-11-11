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
3. Chạy test phù hợp; trên máy Windows hiện tại: `.\venv\Scripts\python.exe -m pytest tests/ -q -p no:cacheprovider`. Chạy Ruff cho các file Python đã sửa nếu có trong venv. Với tài liệu thuần túy, kiểm tra nội dung và `git diff --check` là đủ.
4. Báo rõ đã sửa gì, test nào pass, phần nào chưa chạy với MySQL/Dashboard thật. Chỉ cập nhật trạng thái Done trong tài liệu sau khi phần cần thiết đã được kiểm chứng.
- Theo `project-management/CONTRIBUTING.md`: không push thẳng `main`, không commit bí mật; PR vào `dev` và để đúng người review. Không tự push hoặc merge khi người dùng chưa yêu cầu.

## Điểm bàn giao để kiểm tra lại khi mở chat mới

- Tại thời điểm tạo file này (28/10/2026), `PROGRESS.md` vẫn cập nhật lần cuối 19/10/2026. Không dùng ngày đó làm bằng chứng cho trạng thái hiện tại.
- Working tree đang có thay đổi chưa commit cho Tool 1 ở `mcp_server/tools/slow_queries.py`, `mcp_server/utils/sanitize.py` và `tests/test_slow_queries.py`. Đã chạy 58 test pass và Ruff pass; **chưa thử Tool 1 với MySQL thật** vì Docker daemon không chạy. Hãy kiểm tra lại `git status` và test trước khi tiếp tục.
- Tool 1 hiện dùng `performance_schema`; nguồn phụ `mysql.slow_log` chưa triển khai vì `readonly_user` chưa có quyền đọc bảng đó. `server.py` vẫn là khung rỗng, nên Tool 1 chưa được đăng ký vào MCP. Tool 2 và Tool 3 vẫn là khung rỗng. Không tự suy ra các phần này đã hoàn tất khi có cuộc chat mới.

## Công cụ và lời nhắn mở đầu

- Chọn công cụ theo việc: Ponytail cho thay đổi gọn; Agent Skills cho quy trình phù hợp; Context7 khi API thư viện có thể đã đổi; Playwright khi cần kiểm tra UI đang chạy bằng dữ liệu thử; Graphify khi cần truy vết nhiều quan hệ code. Không commit snapshot/log tạm của Playwright hoặc `graphify-out/` khi chỉ dùng cục bộ.
- Khi người dùng nhắn **“Tiếp tục dự án theo AGENTS.md”**: đọc tài liệu ở trên, kiểm tra working tree và code/test của chặng đang làm, rồi báo ngắn gọn trạng thái đã xác minh cùng bước kế tiếp. Chỉ sửa file nếu yêu cầu hiện tại là triển khai hoặc sửa đổi.

Gợi ý mở chat mới:

```text
Tiếp tục dự án theo AGENTS.md. Đọc README.md, ROADMAP/PROGRESS và contract liên quan;
kiểm tra git status, code và test thực tế rồi cho tôi biết chặng hiện tại và bước tiếp theo.
```
