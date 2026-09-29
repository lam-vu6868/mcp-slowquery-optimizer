-- ============================================
-- MCP SLOW QUERY OPTIMIZER — MYSQL INIT
-- Cập nhật: 29/09/2026
-- Chạy tự động khi container khởi động lần đầu
-- ============================================

-- ---------- 1. BẬT SLOW QUERY LOG ----------
SET GLOBAL slow_query_log = 'ON';
SET GLOBAL long_query_time = 0.5;
SET GLOBAL log_output = 'FILE,TABLE';  -- FILE cho pt-query-digest, TABLE cho Tool 1
SET GLOBAL log_queries_not_using_indexes = 'OFF';  -- Tránh log spam

-- ---------- 2. USER READ-ONLY (Tool 1-5 dùng) ----------
DROP USER IF EXISTS 'readonly_user'@'%';
CREATE USER 'readonly_user'@'%' IDENTIFIED BY 'readonly_pass';
GRANT SELECT ON shopdb.* TO 'readonly_user'@'%';
GRANT PROCESS ON *.* TO 'readonly_user'@'%';  -- Để đọc performance_schema
GRANT SELECT ON performance_schema.* TO 'readonly_user'@'%';
FLUSH PRIVILEGES;

-- ---------- 3. USER INDEX ADMIN (CHỈ Tool 6 dùng) ----------
DROP USER IF EXISTS 'index_admin'@'%';
CREATE USER 'index_admin'@'%' IDENTIFIED BY 'admin_pass';

-- CHỈ cho phép thao tác INDEX — KHÔNG cho DROP TABLE, DELETE, UPDATE
GRANT INDEX ON shopdb.* TO 'index_admin'@'%';
GRANT SELECT ON shopdb.* TO 'index_admin'@'%';   -- Cần để kiểm tra trước khi tạo index
GRANT ALTER ON shopdb.* TO 'index_admin'@'%';    -- Cho ALTER INDEX ... VISIBLE/INVISIBLE
FLUSH PRIVILEGES;

-- ---------- 4. CẤU HÌNH PERFORMANCE_SCHEMA ----------
UPDATE performance_schema.setup_consumers
SET ENABLED = 'YES'
WHERE NAME IN (
  'events_statements_current',
  'events_statements_history',
  'events_statements_history_long'
);

UPDATE performance_schema.setup_instruments
SET ENABLED = 'YES', TIMED = 'YES'
WHERE NAME LIKE 'statement/%';

-- ---------- 5. KIỂM TRA ----------
SELECT '✅ MySQL init xong!' AS status;
SELECT user, host FROM mysql.user WHERE user IN ('readonly_user', 'index_admin');
SHOW VARIABLES LIKE 'slow_query_log';
SHOW VARIABLES LIKE 'log_output';
SHOW VARIABLES LIKE 'long_query_time';