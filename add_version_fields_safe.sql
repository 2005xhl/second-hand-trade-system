-- 为关键表添加版本号字段（用于乐观锁控制）- 安全版本
-- 此版本会检查字段是否存在，避免重复添加报错
-- 执行此脚本后，可以使用乐观锁机制防止丢失修改问题

USE `used_goods_platform`;

-- 使用存储过程安全添加字段（如果不存在）
DELIMITER $$

DROP PROCEDURE IF EXISTS add_column_if_not_exists$$
CREATE PROCEDURE add_column_if_not_exists(
    IN table_name VARCHAR(64),
    IN column_name VARCHAR(64),
    IN column_definition TEXT
)
BEGIN
    DECLARE column_exists INT DEFAULT 0;
    
    -- 检查字段是否存在
    SELECT COUNT(*) INTO column_exists
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = table_name
      AND COLUMN_NAME = column_name;
    
    -- 如果字段不存在，则添加
    IF column_exists = 0 THEN
        SET @sql = CONCAT('ALTER TABLE `', table_name, '` ADD COLUMN `', column_name, '` ', column_definition);
        PREPARE stmt FROM @sql;
        EXECUTE stmt;
        DEALLOCATE PREPARE stmt;
        SELECT CONCAT('字段 ', column_name, ' 已添加到表 ', table_name) AS result;
    ELSE
        SELECT CONCAT('字段 ', column_name, ' 已存在于表 ', table_name, '，跳过') AS result;
    END IF;
END$$

DELIMITER ;

-- 1. 为 goods 表添加版本号字段
CALL add_column_if_not_exists(
    'goods',
    'version',
    'INT NOT NULL DEFAULT 1 COMMENT ''版本号，用于乐观锁控制，每次更新自动递增'''
);

-- 2. 为 order 表添加版本号字段
CALL add_column_if_not_exists(
    'order',
    'version',
    'INT NOT NULL DEFAULT 1 COMMENT ''版本号，用于乐观锁控制，每次更新自动递增'''
);

-- 3. 为 user 表添加版本号字段（可选，用于用户信息更新）
CALL add_column_if_not_exists(
    'user',
    'version',
    'INT NOT NULL DEFAULT 1 COMMENT ''版本号，用于乐观锁控制，每次更新自动递增'''
);

-- 4. 初始化现有记录的版本号为1（使用存储过程安全执行）
-- 注意：如果字段不存在，UPDATE 会报错，所以先检查字段是否存在
DELIMITER $$

DROP PROCEDURE IF EXISTS init_version_if_exists$$
CREATE PROCEDURE init_version_if_exists(
    IN table_name VARCHAR(64)
)
BEGIN
    DECLARE column_exists INT DEFAULT 0;
    
    -- 检查 version 字段是否存在
    SELECT COUNT(*) INTO column_exists
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = table_name
      AND COLUMN_NAME = 'version';
    
    -- 如果字段存在，则初始化
    IF column_exists > 0 THEN
        SET @sql = CONCAT('UPDATE `', table_name, '` SET `version` = 1 WHERE `version` IS NULL OR `version` = 0');
        PREPARE stmt FROM @sql;
        EXECUTE stmt;
        DEALLOCATE PREPARE stmt;
        SELECT CONCAT('表 ', table_name, ' 的 version 字段已初始化') AS result;
    ELSE
        SELECT CONCAT('表 ', table_name, ' 的 version 字段不存在，跳过初始化') AS result;
    END IF;
END$$

DELIMITER ;

-- 初始化各表的版本号
CALL init_version_if_exists('goods');
CALL init_version_if_exists('order');
CALL init_version_if_exists('user');

-- 5. 清理所有临时存储过程
DROP PROCEDURE IF EXISTS init_version_if_exists;
DROP PROCEDURE IF EXISTS add_column_if_not_exists;

SELECT '版本号字段添加完成！' AS result;

