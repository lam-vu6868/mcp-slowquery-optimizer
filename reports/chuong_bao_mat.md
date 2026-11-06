# CHƯƠNG — BẢO MẬT

> **Người viết:** Tình · **Review:** Vũ, Hải · **Bản nháp 1** (06/11/2026) — chờ số liệu lớp quyền DB (`--db`) và thử nghiệm với LLM thật để chốt.
> Số liệu trong chương lấy từ: `pytest tests/` và `python -m security.injection_tests.run_tests` (kết quả gốc ở `security/logs/injection_results.json`).

## 1. Đặt vấn đề

Hệ thống cho một mô hình ngôn ngữ lớn (LLM) đọc dữ liệu vận hành của cơ sở dữ liệu (slow log, schema, thống kê) rồi đề xuất index. Điều này tạo ra hai rủi ro mà một công cụ tối ưu truyền thống không có:

1. **Prompt injection gián tiếp.** Dữ liệu mà LLM đọc (câu SQL trong slow log, comment của bảng/cột) có thể do kẻ tấn công cài vào. Nếu LLM coi đó là chỉ thị, nó có thể bị dẫn đi làm việc khác với mục đích ban đầu.
2. **Tác nhân tự động có quyền ghi.** Đề tài yêu cầu một tool áp dụng đề xuất (`apply_optimization`). Nếu LLM gọi được tool này mà không có người kiểm soát, một lần injection thành công có thể biến thành thay đổi thật trên CSDL.

Nguyên tắc thiết kế xuyên suốt chương: **không tin LLM**. Mọi biện pháp được đặt ở phía server sao cho *kể cả khi LLM đã bị thao túng hoàn toàn*, hành động nguy hiểm vẫn không xảy ra.

## 2. Mô hình đe dọa

**Tài sản cần bảo vệ:** dữ liệu và cấu trúc của schema thực nghiệm `shopdb`; tính sẵn sàng của MySQL; tính toàn vẹn của quyết định áp dụng index (chỉ index đã được người duyệt mới được tạo).

**Kẻ tấn công:** không truy cập trực tiếp được MCP Server, Dashboard hay file `.env`, nhưng có thể:

- chạy câu SQL để nó xuất hiện trong slow log / `performance_schema`;
- đặt comment hoặc tên bất thường cho bảng/cột;
- thông qua đó điều khiển nội dung LLM sinh ra (SQL gửi vào Tool 4/5, proposal, lời gọi tool).

**Mục tiêu tấn công:** (a) ghi/xóa dữ liệu hoặc schema; (b) làm treo, khóa CSDL; (c) đọc file hệ thống hoặc schema hệ thống; (d) áp dụng index không qua duyệt, hoặc áp dụng index khác với index đã duyệt.

**Ngoài phạm vi:** kẻ tấn công đã chiếm máy chủ chạy Dashboard/MCP Server, hoặc có quyền mở Dashboard (xem mục 9).

## 3. Kiến trúc phòng thủ nhiều lớp

| Lớp | Cơ chế | Chống mục tiêu |
| :-: | ------ | :------------: |
| L1 | Tài khoản `readonly_user` (SELECT, PROCESS) cho Tool 1–5 | a, d |
| L2 | Tài khoản `index_admin` (INDEX, ALTER, SELECT trên `shopdb`) chỉ Tool 6 dùng | a |
| L3 | Sanitize dữ liệu từ CSDL trước khi đưa cho LLM | tất cả (giảm xác suất LLM bị thao túng) |
| L4 | AST whitelist (`sqlglot`, fail-closed) cho mọi SQL từ bên ngoài | a, b, c |
| L4b | Proposal có cấu trúc — server tự sinh DDL | a, d |
| L5 | Tool 6 tách khỏi LLM + approval token một lần | d |
| L6 | Audit log chỉ ghi thêm | truy vết |

Hai lớp L1, L2 là kiểm soát của chính MySQL, không phụ thuộc mã nguồn nhóm viết. Lớp L3 là heuristic (giảm rủi ro), các lớp L4, L4b, L5 là kiểm tra cứng (quyết định chặn/cho qua một cách tất định).

## 4. Tách quyền cơ sở dữ liệu (L1, L2)

`db/init.sql` tạo hai tài khoản. `readonly_user` chỉ có `SELECT` trên `shopdb` và `performance_schema` cùng quyền `PROCESS` để đọc thống kê câu lệnh. Mọi tool phân tích (Tool 1–5) đều kết nối bằng tài khoản này (`mcp_server/utils/db.py::get_conn`), nên kể cả khi một câu `DROP TABLE` lọt qua mọi lớp phần mềm, MySQL vẫn từ chối.

`index_admin` có `INDEX` (tạo/xóa index), `ALTER` (cần cho `ALTER TABLE … ALTER INDEX … VISIBLE`) và `SELECT`. Tài khoản này không có `DROP`, `DELETE`, `UPDATE`, `INSERT`. Chỉ Tool 6 dùng (`get_admin_conn`).

> *Ghi chú cho bản cuối:* quyền `ALTER` của MySQL rộng hơn mức cần (cho phép cả `ALTER TABLE … DROP COLUMN`). Rủi ro này được khống chế ở L4b: Tool 6 không nhận SQL tự do, chỉ chạy đúng hai dạng câu do server sinh. Nếu còn thời gian sẽ thử thu hẹp bằng cách bỏ `ALTER` và tạo index trực tiếp `VISIBLE` thay vì bật từ `INVISIBLE`.

## 5. Làm sạch dữ liệu đầu vào cho LLM (L3)

Mô-đun `mcp_server/utils/sanitize.py` xử lý mọi văn bản lấy từ CSDL trước khi trả cho LLM:

- **Bỏ comment SQL** (`strip_sql_comments`): xóa `/* … */`, `/*! … */`, `/*M! … */`, `-- …` và `# …` bằng một bộ quét ký tự có nhận biết chuỗi `'…'`, `"…"` và định danh `` `…` `` — nhờ vậy `'-- không phải comment'` trong chuỗi literal được giữ nguyên. Comment không đóng bị bỏ đến hết chuỗi (an toàn hơn giữ lại).
- **Chuẩn hóa Unicode** (`normalize_unicode`): NFKC (chữ full-width `ＤＲＯＰ` → `DROP`) và bỏ ký tự vô hình (zero-width, điều khiển hướng chữ bidi, soft hyphen). Đây là cách chống homoglyph và giấu chữ.
- **Phát hiện chỉ thị** (`detect_injection`): các mẫu "ignore/bỏ qua … instructions/hướng dẫn", nhãn vai trò `system:`/`assistant:`, câu DDL/DML, từ khóa phê duyệt (`approved`, `apply_optimization`), comment thực thi; đồng thời thử **giải mã base64** các chuỗi dài để tìm chỉ thị bị mã hóa.
- **Lọc comment schema** (`sanitize_comment`): comment có dấu hiệu chỉ thị bị thay hẳn bằng nhãn `[ĐÃ LỌC: nội dung giống chỉ thị]`; comment sạch được chuẩn hóa và cắt còn 200 ký tự.
- **Gắn nhãn** (`untrusted_field`): mọi giá trị trả cho LLM mang `"untrusted": true` cùng danh sách cờ, để prompt hệ thống yêu cầu LLM coi đó là dữ liệu.

Lớp này có giới hạn rõ ràng: phát hiện dựa trên mẫu nên có thể bị né bằng diễn đạt khác, và nó **không thể** xóa chỉ thị nằm trong chuỗi literal (kịch bản A5) vì đó là dữ liệu thật của câu truy vấn. Vì vậy L3 chỉ được coi là lớp giảm xác suất; quyết định chặn thuộc về các lớp sau.

## 6. AST whitelist (L4)

`security/ast_whitelist.py::check(sql)` trả về `(cho_phép, lý_do)` và được gọi trước khi chạy bất kỳ SQL nào nhận từ bên ngoài (Tool 4, Tool 5, `rewritten_sql`). Bộ quy tắc theo ROADMAP mục 2.2:

1. Chỉ một câu lệnh (chặn `;` nối lệnh).
2. Gốc cây cú pháp chỉ được là `SELECT` (kể cả `UNION`/`EXCEPT`/`INTERSECT`) hoặc `EXPLAIN` của một `SELECT`; `CREATE INDEX` chỉ hợp lệ với DDL do server sinh.
3. Chặn comment thực thi `/*! */`, `/*M! */`.
4. Chặn xuất/đọc file: `INTO OUTFILE`, `INTO DUMPFILE`, `LOAD_FILE()`.
5. Chặn khóa dòng: `FOR UPDATE`, `FOR SHARE`, `LOCK IN SHARE MODE` — kiểm trên **cây cú pháp** (node `Lock`), và chặn `SELECT … INTO` (node `Into`).
6. Chặn hàm nguy hiểm: `SLEEP`, `BENCHMARK`, `GET_LOCK`, `RELEASE_LOCK`, `SYS_EXEC`, `LOAD_FILE`.
7. Chỉ cho truy cập schema `shopdb` và `information_schema`; `mysql.*`, `performance_schema.*`, `sys.*` bị chặn (kể cả trong subquery, CTE, UNION).
8. Parse lỗi → từ chối (**fail-closed**).

Kiểm tra được thực hiện hai tầng: so khớp từ khóa trên chuỗi (cả bản gốc lẫn bản đã bỏ comment và gộp khoảng trắng), sau đó duyệt cây cú pháp của `sqlglot`. Tầng chuỗi bắt được những câu mà parser hiểu sai; tầng AST bắt được những cách viết mà so khớp chuỗi bỏ sót.

**Lỗ hổng phát hiện trong quá trình kiểm thử.** Lần chạy đầu bộ 20 kịch bản cho kết quả 19/20: câu `SELECT … FOR SHARE` (cú pháp MySQL 8) lọt qua vì bản đầu chỉ so khớp chuỗi `FOR UPDATE` và `LOCK IN SHARE MODE`. Thử thêm phát hiện `FOR/**/UPDATE`, `LOCK  IN  SHARE MODE` (nhiều khoảng trắng) và `SELECT … INTO @v` cũng lọt. Bản vá chuyển việc chặn khóa dòng sang kiểm tra node AST và chuẩn hóa chuỗi trước khi so từ khóa; 8 test hồi quy được thêm. Kinh nghiệm rút ra: danh sách đen dạng chuỗi luôn có khả năng sót, nên cần dựa vào cấu trúc cú pháp và giữ nguyên tắc fail-closed.

## 7. Con người trong vòng lặp: Tool 6 và approval token (L4b, L5)

### 7.1. Vì sao không dùng tham số `approved=True`

Thiết kế ban đầu cho Tool 6 nhận tham số `approved=True`. Tham số do bên gọi truyền vào, mà bên gọi chính là LLM — một LLM bị injection hoàn toàn có thể tự đặt `approved=True`. Phê duyệt vì vậy phải là thứ LLM **không thể tự tạo ra**.

### 7.2. Thiết kế

- **Tách tool:** server chỉ đăng ký Tool 1–5 cho LLM host. Tool 6 có cờ `LLM_EXPOSED = False` và chỉ backend Dashboard gọi.
- **Không có SQL tự do:** Tool 6 chỉ nhận `proposal_id` và `approval_token`. LLM chỉ được đề xuất dạng có cấu trúc `{table, columns[], index_name}`; server tự sinh DDL bằng `build_ddl()`. Tên bảng/cột phải khớp `^[A-Za-z_][A-Za-z0-9_]{0,63}$`, `index_name` khớp `^idx_[a-z0-9_]{1,50}$`, tối đa 5 cột, không trùng, chiều chỉ `ASC`/`DESC`; định danh được bọc backtick. DDL sinh ra còn phải qua AST whitelist và được đối chiếu với schema thật (bảng/cột tồn tại) trước khi chạy.
- **Approval token:** khi người dùng tick xác nhận và bấm *Approve* trên Dashboard, server sinh

  ```
  token = "v1.<nonce>.<expires_at>.<sig>"
  sig   = HMAC-SHA256(APPROVAL_SECRET, "v1|proposal_id|sha256(DDL)|nonce|expires_at")
  ```

  với `nonce` 16 byte ngẫu nhiên từ `secrets`, `expires_at` = thời điểm hiện tại + 600 giây. `APPROVAL_SECRET` chỉ nằm trong `.env` phía server; LLM không bao giờ thấy secret lẫn token. Token chỉ tồn tại trong biến cục bộ của lần bấm: không hiển thị, không lưu session, không ghi log.

### 7.3. Kiểm tra token

`verify_token` kiểm theo thứ tự: định dạng → chữ ký (`hmac.compare_digest`, chống timing attack) → hạn dùng → chưa dùng. "Chưa dùng" được bảo đảm bằng cách `INSERT` nonce vào bảng `used_tokens` có khóa chính là nonce: lần dùng thứ hai vi phạm khóa chính, và vì thao tác này nguyên tử nên hai yêu cầu song song cũng không thể cùng dùng một token. Token chỉ bị "đốt" khi đã qua các bước trước, nên một yêu cầu sai không làm mất token hợp lệ.

Vì chữ ký gắn với cả `proposal_id` lẫn hash của DDL, các tấn công sau đều thất bại với cùng một kiểm tra: token giả, token bị sửa hạn, token của proposal khác, và **sửa proposal sau khi đã duyệt** (người duyệt index A, kẻ tấn công đổi proposal sang index B — DDL B có hash khác nên chữ ký không khớp).

Secret rỗng, còn giá trị mẫu `CHANGE_ME…` hoặc ngắn hơn 32 ký tự → hệ thống từ chối cả sinh lẫn kiểm token (fail-closed), Dashboard khóa nút Approve và hiện hướng dẫn tạo secret.

### 7.4. Luồng Tool 6

```
proposal_id hợp lệ? ─▶ proposal tồn tại? ─▶ loại rewrite? → FORBIDDEN
   ─▶ đã pass validation? (validated / apply_failed) ─▶ build_ddl + AST
   ─▶ verify_token (đốt) ─▶ bảng/cột có thật? index trùng tên khác cột?
   ─▶ chưa có index: CREATE INDEX · có index INVISIBLE: ALTER INDEX … VISIBLE · đã VISIBLE: không làm gì
   ─▶ cập nhật trạng thái + ghi audit
```

Proposal loại `rewrite` luôn bị từ chối (`FORBIDDEN`) — viết lại câu truy vấn chỉ được đề xuất và hiển thị, không có đường áp dụng vào CSDL. Khi chạy DDL lỗi (ví dụ mất kết nối), proposal chuyển `apply_failed` và có thể duyệt lại với **token mới** (token cũ đã bị đốt).

## 8. Audit log (L6)

Mỗi lần gọi Tool 6 — kể cả bị từ chối ở bước kiểm tra đầu vào — ghi một dòng vào bảng `audit_log` (SQLite meta, tách khỏi `shopdb`): thời điểm, hành động, `proposal_id`, hash DDL, kết quả, mã lỗi, người duyệt, nguồn gọi. Việc cấp token và từ chối đề xuất trên Dashboard cũng được ghi. Bảng có trigger chặn `UPDATE` và `DELETE` (chỉ ghi thêm), và hàm ghi log không có tham số nào nhận token nên token không thể vô tình lọt vào log. Tab 4 của Dashboard hiển thị audit log và số lần token bị từ chối.

## 9. Kiểm thử và kết quả

### 9.1. Kiểm thử đơn vị

| Bộ test | Số test | Nội dung |
| ------- | :-----: | -------- |
| `test_ast_whitelist.py` | 55 | Câu được phép, từng quy tắc chặn, parse lỗi, 8 test hồi quy cách né |
| `test_approval_token.py` | 28 | Token hợp lệ, TTL, sai chữ ký, sửa hạn, khác DDL, khác proposal, sai secret, hết hạn, dùng lại, secret chưa cấu hình, audit chỉ ghi thêm |
| `test_apply_tool.py` | 38 | Hợp đồng Tool 6 (không có tham số `sql`/`approved`), `build_ddl` với 9 dạng proposal độc hại, luồng thành công, mọi mã lỗi, mọi lần gọi đều có audit, token không xuất hiện trong audit |
| `test_sanitize.py` | 29 | Bỏ comment nhưng giữ chuỗi literal, Unicode, phát hiện chỉ thị (Anh/Việt, base64) |
| `test_injection_suite.py` | 22 | Chạy 20 kịch bản trong CI |
| **Tổng phần bảo mật** | **172** | Tất cả pass (Tool 6 dùng DB giả) |

### 9.2. Bộ 20 kịch bản injection

Bốn nhóm × năm kịch bản, tổng 39 vector tính cả biến thể: (A) chỉ thị trong slow log, (B) comment và tên bất thường trong schema, (C) cấu trúc SQL nguy hiểm, (D) đầu ra, mã hóa và token. Mỗi kịch bản khai trước các lớp *phải* chặn; kịch bản chỉ được tính là chặn khi **mọi** lớp đã khai đều chặn. Chi tiết từng kịch bản ở `security/injection_report.md`.

**Kết quả:** chặn **20/20** kịch bản (sau bản vá ở mục 6). Theo lớp: Sanitize 9 lần, AST whitelist 13 lần (26 câu SQL độc hại), proposal có cấu trúc 2 lần (4 proposal độc hại), approval token / tách Tool 6 9 lần. Mọi kịch bản đi qua Tool 6 đều sinh đúng một dòng audit log và không có câu DDL nào được chạy. Mọi kịch bản nhắm vào ghi/đổi CSDL đều có ít nhất hai lớp độc lập cùng chặn.

## 10. Giới hạn

Kết quả trên **không** chứng minh hệ thống an toàn tuyệt đối. Những điểm chưa kiểm chứng hoặc còn rủi ro:

1. Chưa đo phản ứng của LLM thật trước 20 vector (agent LLM chưa hoàn thiện). Kết quả hiện tại khẳng định "dù LLM bị lừa, server vẫn chặn được hành động", không khẳng định LLM không bị lừa.
2. Lớp quyền MySQL (L1, L2) chưa kiểm tự động trong CI; cần chạy `run_tests --db` trên máy nhóm. Tool 6 mới kiểm với DB giả, cần test tích hợp trên MySQL 8.
3. Sanitize dựa trên mẫu, có thể bị né bằng ngôn ngữ hoặc kiểu mã hóa khác.
4. AST dựa trên parser `sqlglot` chứ không phải parser MySQL; đã tìm và vá 4 cách né, có thể còn cách khác.
5. Whitelist vẫn cho đọc `information_schema` và biến hệ thống như `@@version` (rò rỉ thông tin mức thấp, chấp nhận trong phạm vi đề tài).
6. Dashboard chưa có xác thực người dùng; tên người duyệt trong audit là tự khai. Token chống LLM tự duyệt, không chống người có quyền mở Dashboard.
7. `APPROVAL_SECRET` nằm cùng máy với Dashboard và server; chiếm được máy là ký được token.

## 11. Tiểu kết

Chương này trình bày cách hệ thống cho phép LLM tham gia tối ưu CSDL mà không trao cho LLM quyền thay đổi CSDL. Ba ý chính: (1) tách quyền ở chính MySQL, (2) chặn cứng mọi SQL từ bên ngoài bằng AST whitelist fail-closed và chỉ cho LLM gửi đề xuất có cấu trúc, (3) thay tham số `approved` bằng approval token HMAC một lần do con người kích hoạt, gắn với đúng DDL đã duyệt, kèm audit log chỉ ghi thêm. Bộ 20 kịch bản injection bị chặn hoàn toàn ở phía server, và chính quá trình kiểm thử đã phát hiện và vá 4 cách né AST whitelist — minh chứng cho giá trị của việc kiểm thử có hệ thống thay vì tuyên bố an toàn.
