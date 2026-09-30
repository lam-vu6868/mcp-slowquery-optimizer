-- db/schema.sql
-- -------------
--
-- CHỨC NĂNG :
--     Định nghĩa 1 bảng thực nghiệm duy nhất: sales_data (dữ liệu 5 triệu dòng).
--
-- PHỤ TRÁCH  : Hải    |    REVIEW: Tường
--
-- LƯU Ý:
--     - Chỉ tạo PRIMARY KEY (id tự tăng).
--     - CỐ Ý KHÔNG tạo các index mà 30 query cần: để LLM đề xuất, ground truth mới có ý nghĩa.
--     - Engine InnoDB, MySQL 8.0, charset utf8mb4.
--     - sales_data đã chứa order_date, order_priority, region, country... (đáp ứng case study Black Friday và đủ 5 nhóm slow query).
--
-- THAM KHẢO  : db/init.sql, data/seed/
--

GO

USE shopdb;

DROP TABLE IF EXISTS sales_data;

CREATE TABLE sales_data (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    region VARCHAR(100) NOT NULL,
    country VARCHAR(100) NOT NULL,
    item_type VARCHAR(100) NOT NULL,
    sales_channel VARCHAR(50) NOT NULL,
    order_priority VARCHAR(10) NOT NULL,
    order_date_raw VARCHAR(50),
    order_date DATE,
    order_id BIGINT NOT NULL,
    ship_date_raw VARCHAR(50),
    ship_date DATE,
    units_sold INT NOT NULL,
    unit_price DECIMAL(10, 2) NOT NULL,
    unit_cost DECIMAL(10, 2) NOT NULL,
    total_revenue DECIMAL(15, 2) NOT NULL,
    total_cost DECIMAL(15, 2) NOT NULL,
    total_profit DECIMAL(15, 2) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- LƯU Ý: CỐ Ý KHÔNG tạo các index (ngoài PRIMARY KEY id)
-- để LLM đề xuất index trong quá trình chạy thực nghiệm.