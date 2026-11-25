-- Chỉ chạy trong validation_lab_db riêng; kiểm marker trước khi tạo index thử.
USE shopdb;
CREATE TABLE mcp_validation_lab_identity (
    marker VARCHAR(50) NOT NULL PRIMARY KEY
) ENGINE=InnoDB;
INSERT INTO mcp_validation_lab_identity (marker) VALUES ('mcp-validation-lab-v1');
