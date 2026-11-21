-- db/schema.sql
-- -------------
--
-- CHỨC NĂNG :
--     Định nghĩa 5 bảng bán hàng: customers, addresses, products, orders, order_items.
--     Bộ CSV hiện tại có tổng cộng 5 triệu dòng.
--
-- PHỤ TRÁCH  : Hải    |    REVIEW: Tường
--
-- LƯU Ý:
--     - Chỉ tạo index bắt buộc cho PRIMARY KEY, UNIQUE và FOREIGN KEY.
--     - Các index tối ưu bổ sung do LLM đề xuất và phải được kiểm chứng.
--     - Engine InnoDB, MySQL 8.0, charset utf8mb4.
--     - VARCHAR không tự mã hóa; dữ liệu cần được mã hóa trước khi nạp nếu có yêu cầu.
--     - Chạy khi khởi tạo DB mới; không xóa bảng hoặc dữ liệu đã tồn tại.
--
-- THAM KHẢO  : db/init.sql, data/seed/
--

USE shopdb;

CREATE TABLE customers (
    customer_id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    full_name VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL,
    phone VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_customers_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE products (
    product_id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    product_name VARCHAR(200) NOT NULL,
    category VARCHAR(100),
    price DECIMAL(12, 2) NOT NULL,
    stock_quantity INT DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE addresses (
    address_id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    customer_id BIGINT,
    street VARCHAR(255) NOT NULL,
    city VARCHAR(100) NOT NULL,
    state VARCHAR(100),
    postal_code VARCHAR(255),
    country VARCHAR(100) NOT NULL,
    CONSTRAINT fk_addresses_customer FOREIGN KEY (customer_id)
        REFERENCES customers (customer_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE orders (
    order_id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    customer_id BIGINT,
    order_date TIMESTAMP NOT NULL,
    total_amount DECIMAL(14, 2) NOT NULL,
    status VARCHAR(50),
    CONSTRAINT fk_orders_customer FOREIGN KEY (customer_id)
        REFERENCES customers (customer_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE order_items (
    order_item_id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    order_id BIGINT,
    product_id BIGINT,
    quantity INT NOT NULL,
    unit_price DECIMAL(12, 2) NOT NULL,
    CONSTRAINT fk_order_items_order FOREIGN KEY (order_id)
        REFERENCES orders (order_id),
    CONSTRAINT fk_order_items_product FOREIGN KEY (product_id)
        REFERENCES products (product_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
