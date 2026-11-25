# 📊 TIẾN ĐỘ DỰ ÁN

> **Cập nhật lần cuối:** 25/11/2026 — thử khôi phục index hỗ trợ FK trên bảng nhỏ của validation lab; Vũ quản lý
> **Mốc đối chiếu hiện tại:** 25/11/2026; các bảng tuần bên dưới là lịch sử
> **Tổng tiến độ:** Chưa tính lại từ mốc ~27% ngày 19/10
>
> ⚠️ **File này chỉ ghi TRẠNG THÁI.** Deadline, người phụ trách và tiêu chí Done xem [ROADMAP.md](ROADMAP.md) (mục 4–5). Mục tiêu Precision/Recall/Consistency xem [ROADMAP.md](ROADMAP.md) mục 2.4.

**Chú thích:** ✅ Done | 🟡 Đang làm | ⬜ Chưa làm | 🔴 Trễ hạn | ⏸️ Tạm dừng

---

## 🎯 TỔNG QUAN CÁC GIAI ĐOẠN

|  #  | Giai đoạn                                            | Trạng thái  | Người chính      |          Deadline          |
| :-: | ---------------------------------------------------- | :---------: | ---------------- | :------------------------: |
|  0  | Setup môi trường                                     |   ✅ Done   | Vũ               |           28/09            |
| 0b  | Thiết kế (`api-contract.md`, `architecture.md`) | ✅ Contract v2 đã chốt; triển khai theo từng chặng | Vũ | 06/10 |
|  1  | CSDL 5 bảng, tổng 5M records                         |   ✅ Đã nạp/kiểm tra   | Hải              |           05/10            |
|  2  | 30 query + ground truth                              | 🟡 Đạt đo kiểm chứng; chờ review/ký | Tường | 06/10 (draft) · 20/10 (ký) |
|  3  | Tool 1–5 MCP                                         | 🟡 Đang làm | Vũ · Hải · Tường |           13/10            |
|  4  | Tích hợp LLM                                         | 🟡 Đang làm | Vũ               |           18/10            |
|  5  | Validation Layer                                     | 🟡 Đang làm | Hải              |           22/10            |
|  6  | Tool 6 + approval token + 20 injection               |     ⬜      | Tình             |           27/10            |
|  7  | Metrics + Baseline                                   |     ⬜      | Tường · Hải      |           03/11            |
|  8  | Dashboard 4 tab                                      |     ⬜      | Tình             |           10/11            |
|  9  | Báo cáo + Demo                                       |     ⬜      | Cả nhóm          |       17/11 · 01/12        |

---

## Thử recovery khôi phục index hỗ trợ FK ngày 25/11/2026

- Thêm nhánh `TrialIndex.restore_fk_support(snapshot)`: xác minh marker trial và FK hiện tại; chỉ dựng lại đúng một index hỗ trợ FK đơn giản, có định nghĩa khớp snapshot; xác minh lại trước khi dọn trial. `recover_interrupted_trials()` còn đối chiếu schema FK/index sau DROP; mọi sai lệch giữ `pending`/`recovery_failed`. Trường hợp ngắt sau `pending` nhưng trước CREATE được nhận diện là trial vắng và schema gốc còn nguyên.
- Test DB giả bao phủ thứ tự khôi phục→DROP→đối chiếu, ngắt trước CREATE, thử lại sau khôi phục, FK đổi, snapshot không hỗ trợ FK, trial không hỗ trợ FK bị mất và schema sai sau DROP. **268 tests pass**, Ruff pass cho Python đã sửa và `git diff --check` pass.
- Trên **validation lab 3309**, kiểm marker `mcp-validation-lab-v1` rồi tạo riêng hai bảng nhỏ có FK và một dòng; tạo trial INVISIBLE có marker. MySQL tự bỏ index FK ban đầu như q01. Recovery từ SQLite snapshot đã tạo lại index FK, dọn trial, đối chiếu schema khớp ban đầu và chuyển store sang `cleaned`. Lặp lại sau khi thêm điều kiện trial phải hỗ trợ chính FK bị mất, kết quả vẫn sạch. Bằng chứng `data/outputs/lab_only_fk_restore_e39cf25b.json` và `data/outputs/lab_only_fk_restore_4e258865.json` cùng SQLite tương ứng (gitignored). Dùng root lab cho phép thử DDL, nên lượt này chưa kiểm ranh giới quyền `readonly_user`/`index_admin` trên MySQL thật.
- Sau phép thử, hai bảng nhỏ đã dọn; lab vẫn có 2.450.000 dòng `order_items`, không còn bảng `mcp_fk_*`. Đã dừng container validation lab, giữ volume và bằng chứng. DB chính 3307 không được kết nối hoặc chạy DDL trong lượt này. **q01 vẫn bị chặn trước CREATE**, chưa thử luồng đo đầy đủ hay áp dụng index trên DB chính.

---

## Lưu metadata hỗ trợ FK trước trial ngày 25/11/2026

- `TrialIndex.fk_support_snapshot()` đọc FK phía tham chiếu và định nghĩa index đang hỗ trợ bằng `readonly_user`. `validate_saved_index()` gọi hàm này trước `begin_trial()`; store ghi snapshot cùng `trial_state=pending` trong một giao dịch SQLite, rồi mới cho phép `CREATE INDEX`. Mở lại SQLite vẫn đọc được snapshot; lỗi đọc metadata dừng khi state còn `new`, không chạy DDL.
- Test dùng DB giả và SQLite tạm: toàn bộ **261 tests pass**, Ruff pass. Không khởi động MySQL/Dashboard thật, không tạo/drop index trong lượt này. Snapshot chưa được dùng để tự khôi phục index; q01 vẫn bị chặn. Bước tiếp theo là thiết kế/thử khôi phục an toàn qua các điểm ngắt trên lab riêng trước khi mở lại q01.

---

## Chặn recovery dọn index duy nhất hỗ trợ FK ngày 25/11/2026

- Khi trial cũ là index duy nhất còn hỗ trợ một FK tham chiếu, `TrialIndex.recover_drop()` nay kiểm metadata và từ chối trước DDL. `recover_interrupted_trials()` giữ proposal `pending`, báo `recovery_failed`; backend không nhận validation mới. Test DB giả chứng minh không gọi admin DDL trong trường hợp này.
- Chưa mở lại q01. Thiết kế tiếp theo cần lưu định nghĩa index hỗ trợ FK trước khi tạo trial và chứng minh được cách khôi phục qua mọi điểm ngắt DDL trên lab riêng. Không dựng lại index chỉ theo tên FK. Trong lượt này không khởi động MySQL/Dashboard thật, không tạo/drop index.

---

## Kiểm chứng Validation trên lab 5M dòng ngày 25/11/2026

- Chỉ dùng hai lab tách biệt: validation lab cổng 3309 có đủ 5 bảng/tổng 5.000.000 dòng (customers 500.000, addresses 500.000, products 50.000, orders 1.500.000, order_items 2.450.000); write lab cổng 3308 giữ 0 dòng. DB chính cổng 3307 chỉ kiểm bằng truy vấn đọc, không chạy DDL hoặc nạp dữ liệu trong lượt này.
- q01: index thử `order_items(product_id, quantity, unit_price)` đã đo xong nhưng MySQL tự bỏ index `fk_order_items_product` hỗ trợ khóa ngoại; lần dọn đầu bị lỗi 1553. Đã xác minh định nghĩa/marker index thử, tạo lại index hỗ trợ FK trên **validation lab**, rồi dọn index thử và xác nhận FK còn nguyên. Report `passed` cũ trong SQLite lab chỉ là bằng chứng sự cố, **không đủ điều kiện duyệt**. Bằng chứng: `data/outputs/lab_only_full5m_q01_cleanup_incident_20261125.json` (gitignored).
- Đã thêm chặn trước DDL cho proposal có tiền tố cột trùng FK tham chiếu. q01 chạy lại trả `inconclusive/foreign_key_support_risk` và không tạo index; `ProposalStore` giữ nguyên lý do này. Bằng chứng: `data/outputs/lab_only_full5m_q01_guard_20261125.json`. Cần thiết kế cách giữ index hỗ trợ FK trước khi hỗ trợ lại trường hợp này.
- q05 với SQL gốc và index thử `order_items(unit_price, product_id, quantity)` trả `passed`, `evidence_complete=true`, hash/số dòng khớp, 20/20 lượt đo mỗi bên, không timeout; P95 **2872,51 → 1051,51 ms** (giảm **63,39%**), index khoảng **91.963.392 byte**, INSERT throughput thay đổi **−16,19%** trên write lab. Index thử đã dọn sau report; report lab không dùng để cấp approval token. Bằng chứng: `data/outputs/lab_only_full5m_q05_20261125.json` và SQLite cùng tên (gitignored).
- Kiểm lại sau cùng: validation lab vẫn đủ 5M dòng, write lab 0 dòng, DB chính đủ 5M dòng; `fk_order_items_product` VISIBLE ở cả ba, không còn index thử q01/q05 trên hai lab. **257 tests pass**, Ruff pass cho Python đã sửa, `git diff --check` pass. Validation Layer vẫn **Đang làm**: mới thử q05 và nhánh chặn q01 trên lab 5M, chưa kiểm đủ 30 proposal, chưa nối Tool 6/Dashboard end-to-end.
- Đã dừng đúng hai container `write_lab_db` và `validation_lab_db` sau phép đo; volume và file bằng chứng được giữ nguyên. Lần dừng đầu bị hệ thống duyệt tự động từ chối do hạn mức tạm thời, lần thử lại sau 14:38 đã thực thi thành công.

---

## Thử recovery từ chối marker sai trên validation lab ngày 25/11/2026

- Chỉ chạy trên `validation_lab_db` cổng 3309, có marker riêng và 200.000 dòng `orders`. Tạo SQLite lab `data/outputs/lab_only_recovery_wrong_marker_20261125.sqlite3` với trial `pending`, rồi tạo index `INVISIBLE` trùng tên/định nghĩa nhưng mang marker khác `mcp_trial:<proposal_id>`.
- `dashboard.backend.initialize_backend()` từ chối khởi động; index marker lạ vẫn còn nguyên và SQLite vẫn `pending`, không có report. Sau khi xác minh marker đúng là của phép thử này, dọn thủ công index đó **chỉ trên lab**, gọi khởi tạo lại: trial chuyển `cleaned`, report `inconclusive/interrupted`. Bằng chứng ở `data/outputs/lab_only_recovery_wrong_marker_20261125.json` (gitignored).
- Kiểm sau cùng: index thử không còn ở validation lab hoặc DB chính; lab vẫn 200.000 dòng, DB chính cổng 3307 vẫn 1.500.000 dòng `orders`. Đã dừng container lab, giữ volume và bằng chứng. Lượt kiểm đầu báo fail giả do chuỗi tiếng Việt trong lệnh thử qua console Windows khác bảng mã; kiểm lại bằng loại lỗi và proposal ID ASCII cho kết quả đúng, không sửa code recovery.
- Đây là kiểm chứng nhánh từ chối an toàn trên lab mẫu; chưa kiểm toàn bộ bộ 5M. Validation Layer vẫn **Đang làm**.

---

## Thử recovery sau gián đoạn trên validation lab ngày 25/11/2026

- Chỉ khởi động lại `validation_lab_db` cổng 3309, xác nhận marker `mcp-validation-lab-v1`, 200.000 dòng `orders` và index thử chưa tồn tại. DB chính cổng 3307 được kiểm bằng tài khoản đọc, có 1.500.000 dòng `orders`.
- Trong tiến trình thứ nhất, tạo proposal/index thử `INVISIBLE` với marker `mcp_trial:<proposal_id>` và ghi `trial_state=pending` vào SQLite lab `data/outputs/lab_only_recovery_20261125.sqlite3`; cố ý kết thúc tiến trình trước khi lưu report để mô phỏng lần Validation bị ngắt. Trong tiến trình thứ hai, `dashboard.backend.initialize_backend()` gọi recovery: dọn đúng index thử, chuyển trạng thái sang `cleaned`, lưu report `inconclusive` với `failure_reason=interrupted`. Gọi khởi tạo lần nữa không còn trial pending; không chạy DDL lặp lại.
- Xác nhận sau recovery: index thử không còn trên validation lab hoặc DB chính; lab vẫn 200.000 dòng, DB chính vẫn 1.500.000 dòng. Bằng chứng `data/outputs/lab_only_recovery_20261125.json` và SQLite lab được giữ (gitignored); container lab đã dừng, volume không xóa.
- Đây là **mô phỏng gián đoạn giữa hai tiến trình**, có tạo/drop index thật chỉ trên lab. Chưa chứng minh xử lý mọi kiểu crash hoặc kết quả trên bộ 5M; Validation Layer vẫn **Đang làm**.

---

## Thử backend Validation trên lab riêng ngày 25/11/2026

- Khởi động hai service riêng từ `docker-compose.write-lab.yml`: write lab cổng 3308 có marker `mcp-write-lab-v1`, validation lab cổng 3309 có marker `mcp-validation-lab-v1`. Nạp 200.000 dòng đầu `orders.csv` vào validation lab; write lab giữ bảng `orders` rỗng. DB chính cổng 3307 không nhận DDL/INSERT từ lượt này.
- Gọi `dashboard.backend.initialize_backend()` rồi `validate_proposal()` trên SQLite lab riêng `data/outputs/lab_only_backend_validation_20261125_110918.sqlite3`, với proposal thử `orders(status ASC, order_date ASC)` và SQL SELECT mẫu ngoài 30 query catalog. Report trong `data/outputs/lab_only_backend_validation_20261125_110918.json` trả `passed`, `evidence_complete=true`, hash/số dòng khớp, 20/20 lượt mỗi bên, không timeout; P95 **63,70 → 10,53 ms** (giảm **83,47%**), EXPLAIN chọn index thử. Dung lượng ước lượng **6.832.128 byte** từ `innodb_index_stats_pages`; INSERT throughput thay đổi **−22,31%** trên write lab.
- Sau report, đã dọn index thử bằng marker và xác nhận nó không còn trên validation lab; write lab vẫn 0 dòng, validation lab 200.000 dòng, DB chính vẫn 1.500.000 dòng `orders` và không có index thử. Đã dừng hai container lab, **giữ nguyên volume và file bằng chứng**. SQLite lab còn report `passed` nhưng index đã dọn: chỉ là bằng chứng lab, tuyệt đối không dùng để cấp approval token.
- Đây là kiểm chứng đường backend mới trên mẫu 200.000 dòng, chưa phải validation bộ 5M hoặc kiểm recovery DDL khi tiến trình thật bị ngắt. Chặng Validation Layer vẫn **Đang làm**.

---

## Nối đường gọi Validation với store runtime ngày 25/11/2026

- `dashboard.backend.validate_proposal()` nhận đúng `ProposalStore` do `initialize_backend()` trả về và chuyển tiếp cùng `proposal_id`, `write_csv_dir` cho `validate_saved_index()`. `dashboard/app.py` giữ store đã recovery trong `proposal_store` để caller giao diện sau này dùng lại, tránh mở một SQLite khác.
- Test giả xác nhận thứ tự recovery trước validation, dùng cùng đối tượng/path và chuyển đủ tham số. Giao diện hiện chưa có thao tác kích hoạt Validation; không chạy MySQL hoặc tạo/drop index trong lượt này.

---

## Nối recovery khi Dashboard khởi động ngày 25/11/2026

- `dashboard/app.py` mở store runtime `data/outputs/proposals.sqlite3` qua `dashboard/backend.py` và gọi `recover_interrupted_trials()` trước khi tiếp tục. Streamlit cache kết quả khởi tạo để không lặp recovery ở mỗi lần rerun; nếu có trial `recovery_failed`, Dashboard dừng, không nhận việc mới.
- Hàm recovery chỉ xét proposal có `trial_state=pending`; `TrialIndex.recover_drop()` chỉ dọn index còn INVISIBLE với marker và định nghĩa đúng proposal. Dọn thành công hoặc index đã vắng thì lưu report `inconclusive/interrupted`; lỗi để lại `pending` cho lần kiểm tra sau. Caller validation runtime phải dùng cùng đường dẫn store, còn store lab riêng không tự được quét.
- 4 test mới dùng store/trial/Streamlit giả; chưa khởi động Dashboard với MySQL thật hoặc tạo/drop index để thử. Các chặng Tool 6, Dashboard 4 tab và Validation trên bộ 5M vẫn chưa Done.

---

## Chốt thiết kế contract v2 ngày 25/11/2026

- Theo ủy quyền của người dùng thay nhóm review, đã đối chiếu contract với registry Tool 1–5, parser LLM, Validation Layer, proposal store, helper DDL và test hiện có; chốt giao diện v2 làm mốc cho caller. Đây không phải chữ ký riêng của từng thành viên hoặc GVHD.
- Đồng bộ tình trạng `mysql.slow_log` đã thử với quyền đọc riêng trên lab; giữ rõ Tool 6/approval token/Dashboard là thiết kế chưa triển khai. Report Validation từ lab đã dọn index không được dùng để cấp token trên DB khác hoặc khi index thử không còn.
- Kiểm tra lại: working tree sạch trước khi sửa tài liệu; 249 unit tests pass và audit bằng chứng ground truth 30/30 pass. Không chạy lại MySQL/Dashboard thật trong lượt chốt contract. Validation Layer, LLM metric 30 query, Tool 6 và Dashboard vẫn theo trạng thái riêng ở bảng trên.

---

## Kiểm chứng ngày 21/11/2026

- Dataset `shopdb.multitable-v1`: customers 500.000, addresses 500.000, products 50.000, orders 1.500.000, order_items 2.450.000; tổng 5.000.000 dòng. Bộ `sales_data` cũ đã được thay thế.
- Baseline hiện tại: `data/outputs/p95_baseline_multitable_raw.json`, 30/30 valid, SQL khớp `data/queries/queries.py`. Lỗi q23 ngày 19/10 thuộc bộ cũ, không phải blocker của bộ hiện tại.
- `data/queries/ground_truth.json`: 30/30 có phương án đạt kiểm chứng. Đủ 3 warm-up + 20 lượt đo, không timeout, hash/số dòng khớp và P95 giảm ≥20%; một số trường hợp dùng lại baseline đã đo, một số đo lại trước tối ưu. Không gọi đây là kết quả đo đồng thời hoặc tối ưu toàn cục.
- q07–q12: đã đo đối chứng hoán đổi thứ tự cùng tập cột, giữ cùng SQL ngoài tên index thử. Các đáp án có `rewritten_sql`, `requires_rewrite` hoặc `required_indexes` cần dùng đủ SQL/hint và index.
- Index `gt_trial_*` đã dọn, cấu hình index ban đầu đã khôi phục. `idx_gt_q01_cover` còn INVISIBLE như trước batch; `fk_order_items_product` vẫn VISIBLE.
- Kiểm tra bằng chứng `scripts/verify_ground_truth.py --check`: 30/30 pass. Toàn bộ unit tests: 125 pass, người dùng cũng đã xác nhận trên PowerShell với thư mục tạm riêng.
- Trạng thái: `performance_verified_pending_review`, reviewer Hải, `gvhd_signature=null`. Script lab không thay thế Hải review hoặc Validation Layer/Human-in-the-loop của hệ thống.
- Chưa đo đầy đủ index size/chi phí ghi, metric LLM và baseline truyền thống. Chưa xác nhận luồng MCP–LLM–Dashboard end-to-end. Trạng thái `server.py` và Tool 1–3 xem cập nhật ngày 22/11 bên dưới.
- Dữ liệu giả có phân bố khá đều và tương quan city/status; cần nêu giới hạn này trong báo cáo, chưa coi là mô phỏng đủ tải Black Friday.

Lệnh kiểm tra không chạy lại DB và cách chạy pytest trên Windows xem [setup-guide](../docs/setup-guide.md#7-kiểm-tra-test-và-bằng-chứng).

---

## Kiểm chứng ngày 22/11/2026

- Tool 1 `get_slow_queries` đã đọc được digest thật qua `performance_schema` bằng `readonly_user`; hiện không có digest đạt ngưỡng trung bình 500 ms. Chưa đăng ký vào MCP.
- Tool 2 `get_schema` đã trả cấu trúc của đủ 5 bảng từ `information_schema` qua `readonly_user`: cột, index visible/invisible và khóa ngoại. Comment cột được thay bằng nhãn dữ liệu không tin cậy. Kích thước từng index trả `null` vì tài khoản đọc không có quyền truy cập `mysql.innodb_index_stats` (lỗi 1142); contract đã ghi rõ. Chưa đăng ký vào MCP.
- 135 unit tests pass; Ruff pass. `server.py` và Tool 3 vẫn là khung, nên chặng Tool 1–5 MCP chưa Done.

### Đồng bộ contract v2 trong ngày 22/11/2026

- `docs/api-contract.md` v2 là bản DRAFT chờ nhóm review; `docs/architecture.md` vẫn giữ để mô tả luồng và được cập nhật theo contract. `ROADMAP.md` ghi rõ các điểm kỹ thuật đang chờ review.
- Tool 1 bổ sung `source=performance_schema` trong kết quả. Tool 2 ghi rõ `size_bytes=null` nếu không đo được dung lượng từng index. Tool 4–5 có wrapper giới hạn tham số cho LLM; Tool 5 trả `MEASUREMENT_INVALID` khi số lượt đo chưa đủ hoặc thiếu hash bắt buộc.
- 139 unit tests pass sau thay đổi. `server.py`, Tool 3, LLM agent, Validation Layer, Tool 6 và Dashboard vẫn là khung; wrapper Tool 4–5 chưa đăng ký MCP. Chưa chạy lại đo thực nghiệm MySQL hoặc Dashboard trong lần đồng bộ này.
- Ruff toàn bộ file Python đã sửa còn 13 lỗi định dạng/quy tắc có sẵn ở Tool 4–5; không thay logic của hai tool chỉ để sửa style trong lượt đồng bộ contract này.

### Tool 3 trong ngày 22/11/2026

- `get_table_stats` đã triển khai độc lập theo contract v2: ước lượng từ `information_schema.TABLES`, 10 cửa sổ PK tối đa 100 dòng/cửa sổ, gộp theo PK và tính thống kê trên mẫu. Không dùng `COUNT(*)` hay `ORDER BY RAND()` toàn bảng. Chỉ trả top values của cột phân loại cho phép; cắt ký tự điều khiển/độ dài và gắn `untrusted: true`.
- 9 test mới pass; toàn bộ 148 test pass, Ruff pass ở `stats.py` và test mới. Gọi read-only trên MySQL thật cho `orders(status, order_date)` và `addresses(city)` đều `ok=true`, mỗi bảng thu được mẫu 1.000 dòng. Số dòng từ `TABLE_ROWS` là ước lượng, không phải đếm chính xác.
- Chưa đăng ký Tool 3 vào MCP; `server.py` vẫn là khung. Chặng Tool 1–5 MCP tiếp tục ở trạng thái Đang làm.

### Registry MCP trong ngày 22/11/2026

- `server.py` dùng MCP SDK 2.x (`MCPServer`) để đăng ký Tool 1–3 và hai wrapper LLM của Tool 4–5, cùng tên public `explain_query` và `benchmark_query`. Tool 6 và hàm Tool 4–5 đầy đủ tham số không nằm trong registry LLM.
- Test registry kiểm tra đúng 5 tên và schema Tool 4–5 chỉ có `sql`. Đã thử client/server qua stdio thật: liệt kê đúng 5 tool, input sai của Tool 1 nhận `INVALID_INPUT`; sau đó gọi cả 5 tool bằng input đọc giới hạn trên MySQL thật, tất cả trả `ok=true`. Toàn bộ 150 test pass; Ruff pass cho `server.py` và test mới. Chưa thử host LLM, Dashboard hoặc Tool 6.

---

## Validation Layer ngày 24/11/2026

- Đã có bước đánh giá report thuần Python: chỉ pass khi đo đủ số lượt từ `config/settings.yaml` (hiện 20/20), không timeout, hash/số dòng khớp, P95 giảm ít nhất ngưỡng config (hiện 20%), EXPLAIN chọn index mới và có bằng chứng dung lượng/chi phí ghi trên lab riêng. Report thiếu hoặc dùng SQL viết lại trả `inconclusive`; sai kết quả hoặc chậm trả `failed`.
- `validate_index()` gọi Tool 4/5 nội bộ với index INVISIBLE tắt/bật, ghép Query Cost và số đo, dọn index thử khi fail/lỗi. Helper `TrialIndex` sinh DDL từ proposal có cấu trúc, kiểm tra schema hiện tại, dùng `index_admin` chỉ cho CREATE/DROP, dùng `readonly_user` cho metadata. Chưa đăng ký helper thành MCP tool.
- `ProposalStore` lưu proposal/report bất biến trong SQLite riêng; `validate_saved_index()` lấy SQL gốc từ store, ghi `trial_state=pending` trước DDL, đo rồi lưu report. Index thử gắn `mcp_trial:<proposal_id>` trong `INDEX_COMMENT`; `recover_interrupted_trials()` chỉ dọn index có đúng marker, định nghĩa cột và trạng thái INVISIBLE, rồi ghi report `inconclusive` nếu lần thử bị ngắt. Lỗi dọn giữ trạng thái `pending` để thử lại/kiểm tra.
- Test dùng DB/Tool giả: chưa tạo/drop index trên MySQL thật, chưa đo INSERT trên clone riêng, chưa nối hàm recovery vào điểm khởi động backend, chưa tích hợp Dashboard/Tool 6. Do đó **chưa Done**, chưa có report thật đủ điều kiện phê duyệt.
- Kiểm tra sau bước recovery: 237 unit tests pass, Ruff pass trên các file Python đã sửa, `git diff --check` pass.

### Write lab và phép đo INSERT ngày 24/11/2026

- `docker-compose.write-lab.yml` tạo MySQL riêng tại `127.0.0.1:3308`, volume riêng và marker trong `db/write_lab_marker.sql`; đã khởi động và kiểm marker thật. DB chính vẫn ở cổng 3307. Mật khẩu lab nằm trong `.env.write-lab` cục bộ, đã gitignore.
- `write_overhead.py` tạo hai bảng TEMPORARY từ schema cùng bảng, preload cùng 100.000 dòng đầu từ CSV, thêm index INVISIBLE vào một bảng, rồi đo INSERT cùng 100.000 dòng tiếp theo vào cả hai. Hàm kiểm marker, schema/header và dùng đúng số dòng từ config. `validate_saved_index()` có đường gọi phép đo này qua `write_csv_dir`; report kiểm tốc độ trước/sau, số dòng và tỷ lệ phần trăm nhất quán.
- Đã đo thật **một phương án mẫu**, `orders(status ASC, order_date ASC)`, bằng script offline; bằng chứng ở `data/outputs/write_overhead_orders_status_date_20261124.json` (gitignored). Lượt lưu: trước 56.422,54 dòng/giây (1,772 s), sau 46.501,17 dòng/giây (2,150 s), thay đổi throughput **−17,58%**. Một lượt thăm dò trước đó cho −19,21%; chưa dùng các lượt này làm kết luận tổng quát.
- Lab chỉ sao chép schema và dùng 200.000 dòng mẫu đầu CSV, không nạp toàn bộ 5M; bảng tạm không sao chép FOREIGN KEY. Sau phép đo, lab `orders` vẫn 0 dòng và không còn bảng scratch; DB chính `orders` vẫn 1.500.000 dòng. Chưa đo đủ mọi bảng/phương án, chưa chạy Validation end-to-end tạo index thật trên DB chính, chưa có số dung lượng index cho proposal này.
- Sau khi lưu bằng chứng, đã dừng rồi xóa riêng container/network/volume `mcp-write-lab_write_lab_data` theo yêu cầu người dùng; `docker volume inspect` xác nhận volume không còn. File bằng chứng trong `data/outputs/` vẫn giữ; container DB chính vẫn `running/healthy`. Lần chạy write lab sau sẽ tạo volume mới và khởi tạo schema/marker lại.
- Toàn bộ 242 unit tests pass sau thay đổi; Ruff và `git diff --check` được chạy cho file đã sửa.

### Rà lại Validation Layer ngày 25/11/2026

- Sửa kiểm chứng EXPLAIN cho JOIN: Tool 4 vẫn trả `key_used` của bảng đầu tiên, còn Validation Layer đọc `raw_plan` để xác nhận index mới nằm trên đúng bảng của proposal, kể cả bảng ở vị trí sau. Alias dùng lại cho bảng khác trả `inconclusive`. `ProposalStore.save_report()` kiểm lại bằng SQL gốc và tên bảng đã lưu; caller lưu report cần giữ `after.raw_plan`.
- Khôi phục `docker-compose.write-lab.yml` mà setup guide tham chiếu; `docker compose ... config --quiet` hợp lệ. Không khởi tạo lại volume lab đã xóa theo yêu cầu người dùng.
- Toàn bộ **244 unit tests pass**; Ruff cho Python đã sửa và `git diff --check` pass. Lần EXPLAIN q07 đầu tiên bị từ chối kết nối (WinError 10061); thử lại khi cổng 3307 sẵn sàng thì `ok=true`. Plan thật có `orders` alias `o` không chọn index và `addresses` alias `a` dùng `fk_addresses_customer`; helper xác nhận index thuộc `addresses`, không gán nhầm cho `orders`. Đây là kiểm chứng chỉ đọc với index sẵn có, chưa tạo/drop index thật hoặc chạy validation end-to-end; chặng vẫn **Đang làm**.

### Thử end-to-end trên hai lab riêng ngày 25/11/2026

- Dựng `write_lab_db` cổng 3308 và `validation_lab_db` cổng 3309, mỗi service có marker/volume riêng; nạp 200.000 dòng `orders` từ CSV vào validation lab. DB chính cổng 3307 vẫn có đúng 1.500.000 dòng `orders`. Proposal thử là `orders(status ASC, order_date ASC)` trên SQL gốc chỉ đọc, không thuộc 30 query catalog; mục tiêu là kiểm luồng, không chấm ground truth.
- Lần thử dùng chung một DB cho index đọc và đo INSERT trả `inconclusive/measurement_error`: phép đo INSERT đúng ra phải chạy trên DB riêng có bảng gốc chưa mang index đề xuất. Sau khi tách hai service, lượt đo đọc/hash/INSERT thành công nhưng `INDEX_LENGTH` chưa cập nhật, nên code mặc định trả `inconclusive/write_evidence_incomplete` và tự dọn index. Bằng chứng ở `data/outputs/validation_lab_20261125_095725.json`.
- Lượt kiểm chứng lab dùng root **chỉ ở validation lab** chạy `ANALYZE TABLE orders` trước và sau khi tạo index để làm mới thống kê, không đổi quyền `index_admin` hoặc code mặc định. Report SQLite/JSON `passed`, 20 lượt mỗi bên, P95 **72,53 → 19,38 ms** (giảm 73,28%), hash/số dòng khớp, EXPLAIN chọn index đề xuất, dung lượng tăng ước lượng **6.832.128 byte**, INSERT throughput thay đổi **−20,27%**. Bằng chứng ở `data/outputs/validation_lab_20261125_100015.json`; index thử đã dọn bằng marker sau khi ghi report. Report này **chỉ là lab evidence**, không được dùng để cấp approval token vì index đã dọn và dữ liệu chỉ là mẫu 200.000 dòng.
- MySQL [yêu cầu `SELECT` và `INSERT` cho `ANALYZE TABLE`](https://dev.mysql.com/doc/refman/8.0/en/analyze-table.html). Do đó chưa có cách làm mới thống kê dung lượng với quyền `index_admin` hiện tại trên DB chính; không nới quyền chỉ để ép report `passed`. Validation Layer vẫn **Đang làm** cho đường runtime chung và chưa nối Dashboard/Tool 6.
- Đã xác nhận main `orders` vẫn 1.500.000 dòng; cả hai lab đều không còn index thử. Sau khi lưu JSON/SQLite bằng chứng (gitignored), đã `docker compose -p mcp-write-lab ... down -v`: xóa đúng hai container, hai volume và network lab; không xóa volume DB chính. SQLite lab còn report `passed` nhưng index lab đã dọn và volume đã xóa, nên **không dùng SQLite này làm nguồn phê duyệt runtime**.

### Sửa nguồn đo dung lượng ngày 25/11/2026

- Lab 200.000 dòng cho thấy `TABLES.INDEX_LENGTH` đứng yên sau `CREATE INDEX` và `INNODB_TABLESPACES.ALLOCATED_SIZE` tăng 4.194.304 byte ở lượt đầu, nhưng bằng 0 khi tạo lại index và InnoDB tái dùng chỗ trống. Không dùng mức tăng file làm bằng chứng duy nhất cho mọi lượt.
- `TrialIndex.size_delta()` giờ ưu tiên số trang `size` của đúng index trong `mysql.innodb_index_stats` nhân `@@innodb_page_size`. `index_admin` cần `SELECT` riêng trên bảng stats; `db/init.sql` đã thêm grant cho volume tạo mới, **DB chính đang tồn tại chưa được cấp grant này**. Thiếu quyền 1142/hàng stats thì thử chênh lệch `INDEX_LENGTH`, rồi tăng trưởng `ALLOCATED_SIZE` của file riêng; không có số dương vẫn `inconclusive`. Report có `index_size_source` đúng nguồn; callback đo dung lượng nội bộ đổi từ số nguyên sang object `{index_size_bytes, index_size_source}`.
- Trên validation lab, đã cấp grant hẹp cho `index_admin` và xác nhận **hai lượt tạo/xóa cùng index** đều đọc 417 trang = 6.832.128 byte mà không chạy `ANALYZE TABLE`. Lượt `validate_saved_index()` bằng code mặc định trả `passed`: P95 **67,54 → 15,16 ms**, 20 lượt mỗi bên, hash/số dòng khớp, EXPLAIN chọn index, INSERT throughput **−17,32%**. Bằng chứng `data/outputs/validation_lab_20261125_102218.json` (gitignored); index thử đã dọn. Đây vẫn là mẫu lab, không phải bằng chứng áp dụng trên DB chính hoặc 30 query catalog.
- Toàn bộ **249 unit tests pass**, Ruff pass cho Python đã sửa, `git diff --check` pass. DB chính `orders` vẫn 1.500.000 dòng và kết nối được sau khi dọn; hai volume/container `mcp-size-lab` đã xóa, bằng chứng trong `data/outputs/` vẫn giữ. Chặng Validation Layer vẫn chưa Done vì chưa kiểm trên 5M lab, chưa nối recovery vào backend và chưa tích hợp Dashboard/Tool 6.

## Kiểm chứng ngày 24/11/2026 — LLM host

- `agent.py` có vòng gọi Tool 1–5, retry JSON và hash run; `parsers.py` kiểm JSON Schema cùng schema Tool 2. Adapter `llm/groq.py` đổi messages/tool calls sang Groq; model thử nghiệm ghim `openai/gpt-oss-120b` trong `config/settings.yaml`.
- LLM giả + MCP giả/registry/stdio: 207 test toàn bộ pass, Ruff pass cho file Python đã sửa. Một lần thử Groq API thật với **tool mẫu** nhận `tool_use`, gửi kết quả mẫu rồi nhận phản hồi cuối; không gọi MySQL.
- Groq đã nhận schema Tool 1–5 thật; Tool 2 đọc schema MySQL qua `readonly_user`. Với q07: hai lượt prompt v1 `parse_failed` vì `columns[0]` sai kiểu; prompt v2 thêm ví dụ cấu trúc cột. Một lượt v2 lỗi HTTP 400 sau Tool 2, một lượt v2 parse thành công với 2 index (`orders(status, order_date, customer_id, total_amount)` và `addresses(customer_id, city)`) cùng 1 rewrite. Tập cột index trùng đáp án q07, nhưng chưa đối chiếu hướng cột/rewrite đầy đủ, chưa chạy Validation Layer hoặc đo hiệu năng. Không dùng 4 lượt này để tính metric ổn định vì prompt version khác nhau.
- Chưa chạy đủ 30 query/metric LLM; Validation Layer và Tool 6 vẫn chưa triển khai.

### Kiểm tra lại q07 ngày 24/11/2026

- Bốn lượt mới qua Python host → Groq → MCP → MySQL với `readonly_user` đều trả JSON hợp lệ, mỗi lượt có 3 proposal; ba lượt gọi Tool 2, một lượt gọi thêm Tool 3. Không tạo/drop index hoặc sửa dữ liệu MySQL.
- HTTP 400 cũ không tái hiện. Bản ghi cũ chỉ có `BadRequestError`, không có mã/body lỗi nên chưa xác định nguyên nhân. `agent.py` nay ghi HTTP status, loại/mã lỗi API và dấu hiệu `failed_generation` khi có, nhưng không ghi nội dung phản hồi hoặc SQL.
- Toàn bộ 208 unit tests pass; Ruff pass cho `agent.py` và test mới. Bốn lượt này chưa đủ để tính độ ổn định, Precision/Recall hoặc kiểm chứng hiệu năng proposal; chưa chạy Validation Layer hay đủ 30 query.

### Tool 1 đọc slow log ngày 24/11/2026

- `get_slow_queries` có tham số `source="slow_log"` tùy chọn; mặc định vẫn đọc `performance_schema`. Nhánh mới chỉ dùng `get_conn()`/`readonly_user`, giới hạn 5 giây, `limit+1` dòng và SQL tối đa 8.000 byte, bỏ comment rồi gắn `untrusted: true`. Mỗi dòng log là một lần chạy, nên `p95_latency_ms=null` và `digest=null`; chi tiết ở contract v2 DRAFT.
- Test giả kiểm tra kết quả, giới hạn và lỗi thiếu quyền. Trước khi cấp quyền, MySQL trả `FORBIDDEN`. Người dùng đã cấp `SELECT` riêng trên `mysql.slow_log` cho `readonly_user` tại lab; gọi trực tiếp và qua MCP stdio với `source="slow_log", limit=1` đều `ok=true`, trả 1 bản ghi thật có `untrusted=true`, `p95_latency_ms=null`. Nguồn mặc định `performance_schema` vẫn `ok=true`, hiện không có digest đạt ngưỡng 500 ms. Không in SQL log trong lần kiểm tra. Chặng Tool 1–5 MCP vẫn Đang làm vì chưa kiểm chứng toàn bộ tiêu chí roadmap.
- Toàn bộ 211 unit tests pass; Ruff pass cho file Python đã sửa. Không chạy lại `db/init.sql`, không sửa index hoặc dữ liệu lab.

### Kiểm chứng Tool 1–5 qua MCP stdio ngày 24/11/2026

- Registry trả đúng 5 tên Tool 1–5, không có Tool 6; schema của Tool 4–5 chỉ nhận `sql`, Tool 1 có tham số `source` tùy chọn. Gọi Tool 1 ở cả `performance_schema` (0 digest đạt 500 ms) và `slow_log` (1 bản ghi thật), Tool 2 với `orders`, Tool 3 với `orders.status`, Tool 4 EXPLAIN và Tool 5 benchmark một truy vấn PK đọc một dòng: tất cả trả `ok=true` với envelope `ok/data/error/meta` đúng tên tool.
- Tool 4 dùng `mode=estimate`; Tool 5 đo 5 lượt theo wrapper LLM. SQL đọc từ log không được in trong lần kiểm tra. Toàn bộ 211 unit tests và Ruff pass. Đây là kiểm chứng kỹ thuật cho Tool 1–5; contract v2 vẫn DRAFT chờ review, Tool 6/Validation/Dashboard chưa triển khai, nên giai đoạn Tool 1–5 giữ trạng thái Đang làm chờ chốt review.

---

## 📅 CẬP NHẬT THEO TUẦN

Các kết quả và lỗi dưới đây được giữ theo thời điểm thực hiện; trạng thái hiện tại xem cập nhật 24/11 ở trên.

### 🗓️ Tuần 1 (23/09 – 29/09) — ✅ DONE

| Việc                                 | Người | Trạng thái | Ghi chú                     |
| ------------------------------------ | ----- | :--------: | --------------------------- |
| Tạo repo GitHub                      | Vũ    |     ✅     | Đã push `main` + `dev`      |
| Cấu trúc thư mục                     | Vũ    |     ✅     | 70 file + 20 thư mục        |
| `docker-compose.yml`                 | Hải   |     ✅     | MySQL 8.0 chạy được         |
| MySQL + bật slow log                 | Hải   |     ✅     | `long_query_time = 0.5`     |
| User `readonly_user` + `index_admin` | Hải   |     ✅     | Quyền đúng, đã verify       |
| Test quyền readonly                  | Tình  |     ✅     | DDL bị chặn                 |
| Streamlit skeleton                   | Tình  |     ✅     | `app.py` chạy được          |
| ROADMAP v2 + 4 file .md              | Vũ    |     ✅     | Trong `project-management/` |

---

### 🗓️ Tuần 2 (30/09 – 06/10) — ✅ DONE

| Việc                              | Người        | Trạng thái | Ghi chú                       |
| --------------------------------- | ------------ | :--------: | ----------------------------- |
| Import dataset sales_data 5M dòng | Hải          |     ✅     | Từ CSV, có `_raw` cho ngày    |
| Verify 5M dòng + fix NULL date    | Hải          |     ✅     | `order_date`, `ship_date` OK  |
| Chốt `api-contract.md`            | Vũ + cả nhóm |     ✅     | 6 tool, có IndexProposal      |
| Chốt `architecture.md`            | Vũ           |     ✅     | Có Mermaid, 6 lớp bảo mật     |
| `docs/setup-guide.md`             | Hải          |     ✅     | Có hướng dẫn từ A-Z           |
| utils/config.py, db.py, logger.py | Vũ + Hải     |     ✅     | Đã verify import + kết nối DB |
| 30 query + ground_truth.json      | Tường        |     ✅     | 30/30 query pass (> 0.5s)     |
| `scripts/verify_setup.py`         | Vũ           |     ✅     | Verify setup chạy được        |

**Done tuần 2:** CSDL 5M dòng OK · slow log có query · contract + architecture đã chốt · 30 query pass.

---

### 🗓️ Tuần 3 (07/10 – 13/10) — 🟡 ĐANG LÀM

| Việc                              | Người       | Trạng thái | Ghi chú                                |
| --------------------------------- | ----------- | :--------: | -------------------------------------- |
| **AST whitelist + 47 unit tests** | Tình        |     ✅     | 47/47 test pass                        |
| **Tool 4 `explain_query`**        | Hải         |     ✅     | 7/7 test pass                          |
| **Tool 5 `benchmark_query`**      | Tường       |     ✅     | 7/7 test pass                          |
| Tool 1 `get_slow_queries`         | Vũ          |     🟡     | Có code + 11 unit tests; chờ thử MySQL và đăng ký MCP |
| Tool 2 `get_schema`               | Vũ          |     ⬜     | Sau Tool 1                             |
| Tool 3 `get_table_stats`          | Vũ          |     ⬜     | Sau Tool 2                             |
| `mcp_server/server.py`            | Vũ          |     ⬜     | Đăng ký 5 tool — sau khi xong Tool 1-3 |
| Đo P95 cho ground truth           | Hải         |     ✅     | Đã đo 30/30: 29 valid, q23 timeout     |
| Nháp chương "Cơ sở lý thuyết"     | Vũ          |     ⬜     | Song song                              |

**Checklist cuối tuần 3:**

- [x] `security/ast_whitelist.py` (47 tests)
- [x] `mcp_server/tools/explain.py` (7 tests)
- [x] `mcp_server/tools/benchmark.py` (7 tests)
- [ ] `mcp_server/tools/slow_queries.py` — có code và unit tests; chưa thử MySQL thật/đăng ký MCP
- [ ] `mcp_server/tools/schema.py`
- [ ] `mcp_server/tools/stats.py`
- [ ] `mcp_server/server.py`

**Vấn đề gặp phải:**

- ⚠️ `readonly_user` không có quyền `RELOAD` → không dùng được `FLUSH STATUS`
  → Fix: Tool 5 bỏ `FLUSH STATUS`, tính chênh lệch tổng `Handler_read*` trước/sau từng lượt.
- ⚠️ `fetchall()` giữ toàn bộ kết quả lớn trong RAM và số đếm Handler bị cộng dồn
  → Fix: Hải sửa Tool 5 dùng `SSDictCursor` đọc theo lô; hash chạy riêng và sort trên SQLite tạm.
- ⚠️ q23 trả khoảng 1.250.007 dòng, 4/20 lượt timeout ở lần xác nhận
  → Giữ `INVALID`; không dùng P95 của 16 lượt thành công, không tăng timeout quá 60000 ms.
- ⚠️ `sqlglot` version mới không có `exp.Explain`
  → Fix: Tool 4 + AST whitelist xử lý EXPLAIN riêng bằng regex.
- ⚠️ Lỗi import `mcp_server` khi chạy file trực tiếp
  → Fix: Dùng `python -m mcp_server.tools.<tool>` hoặc script test ở root.

---

## 🚨 BLOCKERS

| #   | Vấn đề                                                                 | Người xử lý | Trạng thái       | Hạn   |
| --- | ---------------------------------------------------------------------- | ----------- | ---------------- | ----- |
| 1   | Xác nhận 30 query thực sự > 0.5s trên máy nhóm                         | Tường + Hải | ✅ Đã xác nhận   | 13/10 |
| 2   | Chọn LLM provider (Claude/Qwen/Fireworks) — vì Claude trả phí          | Vũ          | 🟡 Đang cân nhắc | 14/10 |
| 3   | Chữ ký GVHD cho ground_truth.json                                      | Tường       | ⬜ Chưa ký       | 20/10 |
| 4   | Case study dataset mới: q07, status/order_date và bộ index đi kèm | Tường + Hải | 🟡 Đã đo lab; chờ Hải review, chưa tái hiện tải Black Friday | 13/10 |

---

## 📈 CHỈ SỐ THEO DÕI

| Chỉ số                                             |       Hiện tại        |
| -------------------------------------------------- | :-------------------: |
| Tổng số dòng 5 bảng hiện tại                        |       5.000.000       |
| Số query trong slow log hiện tại                   | Chưa đếm lại          |
| Query xác nhận > 0.5s (trên 30)                    |       **30/30**       |
| Tool có triển khai và đã kiểm thử độc lập           | Tool 4–5; Tool 1 có unit tests, chờ tích hợp |
| Đăng ký tool vào MCP                               | `server.py` còn khung |
| Injection test pass                                | 47/47 (unit test AST) |
| Ground truth có chữ ký GVHD                        |         Chưa          |
| Precision / Recall (index)                         |           —           |
| Consistency Rate                                   |           —           |
| False Positive Rate                                |           —           |
| Đáp án lab đạt hash + P95 giảm ≥20%                 | 30/30, chờ duyệt      |
| Unit tests toàn bộ                                 | 125 pass              |
| Audit file bằng chứng                             | 30/30 pass            |
| Rewrite do LLM đề xuất đạt yêu cầu                 | Chưa đo               |

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
| 05/10 | Hải     | Import dataset sales_data 5M dòng, fix NULL date                       |
| 06/10 | Vũ      | Chốt api-contract + architecture + setup-guide                         |
| 07/10 | Tình    | AST whitelist + 47 unit tests pass                                     |
| 07/10 | Hải     | Tool 4 `explain_query` (7 tests pass)                                  |
| 07/10 | Tường   | Tool 5 `benchmark_query` bản đầu (7 tests pass)                        |
| 19/10 | Hải     | Sửa Tool 5 theo cơ chế streaming, hash riêng; test 7/7 pass            |
| 19/10 | Hải     | Đo P95 đủ 30 query: 29 valid, q23 timeout và giữ trạng thái INVALID    |
| 28/10 | Codex   | Tool 1 có code + 11 unit tests; toàn bộ 58 tests pass, Ruff pass; chưa thử MySQL thật hoặc đăng ký MCP |
| 21/11 | Người dùng + Codex | Chuyển lab sang 5 bảng/tổng 5M dòng; baseline 30/30 valid, 30 đáp án đạt P95/hash và chờ Hải review/GVHD ký; audit 30/30, unit tests 125 pass; dọn index thử và đồng bộ tài liệu |

---

## 📌 CÁCH CẬP NHẬT FILE NÀY

| Khi nào             | Cập nhật gì                                           | Ai làm    |
| ------------------- | ----------------------------------------------------- | --------- |
| Sau standup tối     | Đổi trạng thái việc đã xong                           | Vũ        |
| Gặp blocker mới     | Thêm dòng vào "Blockers"                              | Người gặp |
| Chủ nhật            | Thêm bảng "Tuần N+1", cập nhật % và "Chỉ số theo dõi" | Vũ        |
| Đổi phân công/scope | Ghi vào "Nhật ký thay đổi" **và** sửa ROADMAP         | Vũ        |

---

## 📞 LIÊN HỆ NHANH

| Vấn đề                                           | Liên hệ |
| ------------------------------------------------ | ------- |
| Điều phối, deadline, kế hoạch                    | Vũ      |
| MCP protocol, LLM API, Tool 1–3                  | Vũ      |
| MySQL, Docker, seed, Validation Layer, Tool 4    | Hải     |
| AST, injection, Tool 6, Dashboard                | Tình    |
| Ground truth, metrics, Tool 5, baseline, biểu đồ | Tường   |
