-- 1. 创建数据库
CREATE DATABASE IF NOT EXISTS `used_goods_platform` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;

-- 切换到新创建的数据库
USE `used_goods_platform`;

-- 2. 用户表 (user)
-- 存储所有用户的基本信息，包括角色和加密后的密码
CREATE TABLE `user` (
  `user_id` INT NOT NULL AUTO_INCREMENT COMMENT '用户ID（主键）',
  `username` VARCHAR(50) NOT NULL UNIQUE COMMENT '用户名（唯一）',
  `password_hash` VARCHAR(128) NOT NULL COMMENT 'MD5加密后的密码 [cite: 64]',
  `nickname` VARCHAR(50) DEFAULT '新用户' COMMENT '用户昵称',
  `phone` VARCHAR(20) COMMENT '联系电话',
  `role` ENUM('normal', 'admin') NOT NULL DEFAULT 'normal' COMMENT '用户角色（普通/管理员） [cite: 65]',
  `status` ENUM('active', 'blocked') NOT NULL DEFAULT 'active' COMMENT '账号状态（活跃/封禁） [cite: 66]',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`user_id`),
  INDEX `idx_username` (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户表';

-- 3. 商品表 (goods)
-- 存储所有发布的商品信息
CREATE TABLE `goods` (
  `goods_id` INT NOT NULL AUTO_INCREMENT COMMENT '商品ID（主键）',
  `user_id` INT NOT NULL COMMENT '发布者用户ID（外键）',
  `title` VARCHAR(100) NOT NULL COMMENT '商品标题',
  `description` TEXT COMMENT '商品描述',
  `category` VARCHAR(50) NOT NULL COMMENT '商品分类',
  `price` DECIMAL(10, 2) NOT NULL COMMENT '商品价格',
  `img_path` VARCHAR(255) COMMENT '商品图片保存路径 [cite: 85]',
  `status` ENUM('pending_review', 'on_sale', 'sold', 'rejected') NOT NULL DEFAULT 'pending_review' COMMENT '商品状态 [cite: 82]',
  `published_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '发布时间',
  PRIMARY KEY (`goods_id`),
  INDEX `idx_category` (`category`),
  -- 关联到 user 表
  FOREIGN KEY (`user_id`) REFERENCES `user`(`user_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='商品表';

-- 4. 收藏表 (collect)
-- 存储用户收藏的商品记录
CREATE TABLE `collect` (
  `collect_id` INT NOT NULL AUTO_INCREMENT COMMENT '收藏ID（主键）',
  `user_id` INT NOT NULL COMMENT '用户ID（外键）',
  `goods_id` INT NOT NULL COMMENT '商品ID（外键）',
  `collected_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '收藏时间',
  PRIMARY KEY (`collect_id`),
  -- 复合唯一索引，防止重复收藏
  UNIQUE KEY `uk_user_goods` (`user_id`, `goods_id`),
  -- 关联到 user 表
  FOREIGN KEY (`user_id`) REFERENCES `user`(`user_id`) ON DELETE CASCADE,
  -- 关联到 goods 表
  FOREIGN KEY (`goods_id`) REFERENCES `goods`(`goods_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='收藏表';

-- 5. 订单表 (order)
-- 存储交易订单信息和状态流转
CREATE TABLE `order` (
  `order_id` INT NOT NULL AUTO_INCREMENT COMMENT '订单ID（主键）',
  `buyer_id` INT NOT NULL COMMENT '买家用户ID（外键）',
  `seller_id` INT NOT NULL COMMENT '卖家用户ID（外键）',
  `goods_id` INT NOT NULL COMMENT '商品ID（外键）',
  `total_price` DECIMAL(10, 2) NOT NULL COMMENT '订单总价',
  `status` ENUM('pending_payment', 'pending_shipment', 'pending_receipt', 'completed', 'canceled') NOT NULL DEFAULT 'pending_payment' COMMENT '订单状态 [cite: 106]',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间',
  PRIMARY KEY (`order_id`),
  INDEX `idx_buyer` (`buyer_id`),
  INDEX `idx_seller` (`seller_id`),
  -- 关联到 user 表 (买家)
  FOREIGN KEY (`buyer_id`) REFERENCES `user`(`user_id`) ON DELETE RESTRICT,
  -- 关联到 user 表 (卖家)
  FOREIGN KEY (`seller_id`) REFERENCES `user`(`user_id`) ON DELETE RESTRICT,
  -- 关联到 goods 表
  FOREIGN KEY (`goods_id`) REFERENCES `goods`(`goods_id`) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='订单表';

-- 6. 聊天表 (chat)
-- 存储买卖双方的聊天记录
CREATE TABLE `chat` (
  `message_id` INT NOT NULL AUTO_INCREMENT COMMENT '消息ID（主键）',
  `sender_id` INT NOT NULL COMMENT '发送者用户ID（外键）',
  `receiver_id` INT NOT NULL COMMENT '接收者用户ID（外键）',
  `content` TEXT NOT NULL COMMENT '消息内容',
  `sent_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '发送时间',
  PRIMARY KEY (`message_id`),
  INDEX `idx_sender_receiver` (`sender_id`, `receiver_id`),
  -- 关联到 user 表 (发送者)
  FOREIGN KEY (`sender_id`) REFERENCES `user`(`user_id`) ON DELETE CASCADE,
  -- 关联到 user 表 (接收者)
  FOREIGN KEY (`receiver_id`) REFERENCES `user`(`user_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='聊天记录表';

-- 7. 日志表 (log)
-- 记录系统关键操作，例如管理员操作、异常记录
CREATE TABLE `log` (
  `log_id` INT NOT NULL AUTO_INCREMENT COMMENT '日志ID（主键）',
  `user_id` INT COMMENT '操作用户ID（可选）',
  `operation_type` VARCHAR(50) NOT NULL COMMENT '操作类型（如 LOGIN, GOODS_ADD, USER_MANAGE）',
  `details` TEXT COMMENT '操作详情',
  `ip_address` VARCHAR(45) COMMENT '操作IP地址',
  `log_time` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '记录时间',
  PRIMARY KEY (`log_id`),
  INDEX `idx_log_time` (`log_time`),
  FOREIGN KEY (`user_id`) REFERENCES `user`(`user_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='系统日志表';