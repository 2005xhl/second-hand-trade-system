-- 1. 创建数据库
CREATE DATABASE IF NOT EXISTS `used_goods_platform` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;

-- 切换到新创建的数据库
USE `used_goods_platform`;

-- 2. 用户表 (user)
-- 存储所有用户的基本信息，包括角色和加密后的密码
CREATE TABLE `user` (
  `user_id` INT NOT NULL AUTO_INCREMENT COMMENT '用户ID（主键）',
  `username` VARCHAR(50) NOT NULL UNIQUE COMMENT '用户名（唯一）',
  `password_hash` VARCHAR(255) NOT NULL COMMENT '密码哈希（建议 bcrypt/argon2） [cite: 64]',
  `nickname` VARCHAR(50) DEFAULT '新用户' COMMENT '用户昵称',
  `phone` VARCHAR(20) COMMENT '联系电话',
  `avatar_path` VARCHAR(255) COMMENT '用户头像图片保存路径',
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
  `brand` VARCHAR(50) COMMENT '商品品牌',
  `price` DECIMAL(10, 2) NOT NULL COMMENT '商品价格（现价）',
  `original_price` DECIMAL(10, 2) COMMENT '商品原价',
  `purchase_time` DATE COMMENT '购买时间',
  `stock_quantity` INT NOT NULL DEFAULT 1 COMMENT '库存量',
  `sold_count` INT NOT NULL DEFAULT 0 COMMENT '已售件数',
  `img_path` VARCHAR(255) COMMENT '商品主图保存路径（保留用于兼容，建议使用goods_images表）',
  `status` ENUM('pending_review', 'on_sale', 'sold', 'rejected') NOT NULL DEFAULT 'pending_review' COMMENT '商品状态 [cite: 82]',
  `create_time` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间（上架提交时间）',
  `audit_time` TIMESTAMP NULL DEFAULT NULL COMMENT '审核时间（通过/驳回时）',
  `off_time` TIMESTAMP NULL DEFAULT NULL COMMENT '下架时间',
  PRIMARY KEY (`goods_id`),
  INDEX `idx_category` (`category`),
  INDEX `idx_brand` (`brand`),
  -- 关联到 user 表
  FOREIGN KEY (`user_id`) REFERENCES `user`(`user_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='商品表';

-- 3.1. 商品图片表 (goods_images)
-- 存储商品的多个图片路径，支持一个商品上传多张图片
CREATE TABLE `goods_images` (
  `image_id` INT NOT NULL AUTO_INCREMENT COMMENT '图片ID（主键）',
  `goods_id` INT NOT NULL COMMENT '商品ID（外键）',
  `img_path` VARCHAR(255) NOT NULL COMMENT '图片保存路径',
  `display_order` INT NOT NULL DEFAULT 0 COMMENT '显示顺序（数字越小越靠前，用于排序）',
  `is_primary` TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否为主图（1=是，0=否）',
  `uploaded_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '上传时间',
  PRIMARY KEY (`image_id`),
  INDEX `idx_goods_id` (`goods_id`),
  INDEX `idx_display_order` (`goods_id`, `display_order`),
  -- 关联到 goods 表，删除商品时级联删除所有图片记录
  FOREIGN KEY (`goods_id`) REFERENCES `goods`(`goods_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='商品图片表';

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
  `order_no` VARCHAR(64) NOT NULL UNIQUE COMMENT '订单编号（前端显示用，如 ORD202401150001）',
  `buyer_id` INT NOT NULL COMMENT '买家用户ID（外键）',
  `seller_id` INT NOT NULL COMMENT '卖家用户ID（外键）',
  `goods_id` INT NOT NULL COMMENT '商品ID（外键）',
  `quantity` INT NOT NULL DEFAULT 1 COMMENT '购买数量',
  `total_price` DECIMAL(10, 2) NOT NULL COMMENT '订单总价',
  `status` ENUM('pending_payment', 'pending_shipment', 'pending_receipt', 'completed', 'canceled') NOT NULL DEFAULT 'pending_payment' COMMENT '订单状态 [cite: 106]',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间（下单时间）',
  `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间',
  `paid_at` TIMESTAMP NULL DEFAULT NULL COMMENT '支付时间',
  `shipped_at` TIMESTAMP NULL DEFAULT NULL COMMENT '发货时间',
  `received_at` TIMESTAMP NULL DEFAULT NULL COMMENT '收货时间',
  `completed_at` TIMESTAMP NULL DEFAULT NULL COMMENT '完成时间',
  `canceled_at` TIMESTAMP NULL DEFAULT NULL COMMENT '取消时间',
  PRIMARY KEY (`order_id`),
  INDEX `idx_order_no` (`order_no`),
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
