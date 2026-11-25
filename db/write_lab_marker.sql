-- Chỉ chạy trong MySQL write_lab_db riêng; code đo ghi phải kiểm marker trước DDL/INSERT.
USE shopdb;
CREATE TABLE mcp_write_lab_identity (
    marker VARCHAR(50) NOT NULL PRIMARY KEY
) ENGINE=InnoDB;
INSERT INTO mcp_write_lab_identity (marker) VALUES ('mcp-write-lab-v1');
