"""
data/metrics/metrics.py
-----------------------

CHỨC NĂNG :
    Tính chỉ số đánh giá LLM và baseline: Precision, Recall, False Positive Rate, Consistency Rate, tỉ lệ rewrite đạt.

PHỤ TRÁCH  : Tường    |    REVIEW: Hải

LƯU Ý:
    - Công thức và 3 mức 'khớp' (chính xác / tương đương / không khớp) định nghĩa ở ROADMAP mục 2.4. KHÔNG tự đổi.
    - Precision/Recall chỉ tính cho nhóm lỗi thiên về index (nhóm 1, 2, 4).
    - Rewrite (nhóm 3, 5): đạt khi kết quả tương đương (hash) VÀ P95 giảm >= 20%.
    - Không chỉnh ground truth cho vừa kết quả LLM.

CẦN LÀM:
    [ ] Đọc ground_truth.json + kết quả chạy ở data/outputs/runs/.
    [ ] Ghi kết quả vào comparison.csv.

THAM KHẢO  : project-management/ROADMAP.md, data/queries/ground_truth.json

TRẠNG THÁI : KHUNG RỖNG — chưa cài đặt. Xóa dòng này khi bắt đầu code.
"""
