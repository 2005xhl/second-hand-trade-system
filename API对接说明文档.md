# 二手交易平台后端API对接说明文档

## 目录
1. [通用说明](#通用说明)
2. [商品相关接口](#商品相关接口)
3. [订单相关接口](#订单相关接口)
4. [收藏相关接口](#收藏相关接口)
5. [数据字段说明](#数据字段说明)
6. [错误码说明](#错误码说明)

---

## 通用说明

### 通信协议
- **协议**: Socket TCP
- **服务器地址**: `10.129.106.38:8888`
- **数据格式**: `指令名|JSON数据`
- **长度头**: 4字节（大端序），表示后续JSON数据的字节长度

### 请求格式
```
[4字节长度头][指令名|JSON数据]
```

### 响应格式
```
[4字节长度头][指令名|JSON响应]
```

### 示例
```python
# 请求
指令: "LOGIN|{\"username\":\"admin\",\"password\":\"admin123\"}"
长度头: 0x0000003A (58字节)

# 响应
指令: "LOGIN|{\"code\":200,\"msg\":\"登录成功\",\"data\":{\"user_id\":1,\"role\":\"admin\",\"username\":\"admin\"}}"
长度头: 0x000000XX (响应数据长度)
```

---

## 商品相关接口

### 1. GOODS_ADD - 发布商品

**功能**: 用户发布商品，状态自动设为"待审核"（pending_review）

**请求格式**:
```json
GOODS_ADD|{
  "user_id": 1,                    // 必填：发布者用户ID
  "title": "二手iPhone 13",        // 必填：商品标题
  "description": "9成新，功能正常", // 可选：商品描述
  "category": "电子产品",           // 必填：商品分类
  "price": 3500.00,                // 必填：商品价格（现价）
  "brand": "Apple",                // 可选：商品品牌
  "original_price": 5999.00,       // 可选：商品原价
  "purchase_time": "2024-01-01",   // 可选：购买时间（格式：YYYY-MM-DD）
  "stock_quantity": 1,             // 可选：库存量（默认1）
  "img_path": "/uploads/goods_images/main.jpg"  // 可选：主图路径
}
```

**响应格式**:
```json
// 成功
{
  "code": 200,
  "msg": "商品发布成功，等待审核",
  "goods_id": 123
}

// 失败
{
  "code": 400,
  "msg": "缺少必填参数（user_id, title, category, price）"
}
```

**错误码**:
- `200`: 发布成功
- `400`: 参数错误或发布失败

---

### 2. GOODS_GET - 获取商品列表

**功能**: 分页查询商品列表，支持按分类和状态筛选

**请求格式**:
```json
GOODS_GET|{
  "category": "电子产品",    // 可选：商品分类（不传则查询所有分类）
  "status": "on_sale",      // 可选：商品状态（pending_review/on_sale/sold/rejected）
  "page": 1,                // 可选：页码（默认1）
  "page_size": 20           // 可选：每页数量（默认20）
}
```

**响应格式**:
```json
// 成功
{
  "code": 200,
  "msg": "查询成功",
  "data": [
    {
      "goods_id": 123,
      "user_id": 1,
      "title": "二手iPhone 13",
      "description": "9成新",
      "category": "电子产品",
      "brand": "Apple",
      "price": 3500.00,
      "original_price": 5999.00,
      "purchase_time": "2024-01-01",
      "stock_quantity": 1,
      "sold_count": 0,
      "img_path": "/uploads/goods_images/main.jpg",
      "status": "on_sale",
      "create_time": "2024-01-15 10:30:00",
      "audit_time": "2024-01-15 10:35:00",
      "off_time": null,
      "primary_image": "/uploads/goods_images/main.jpg",
      "images": [
        {
          "img_path": "/uploads/goods_images/main.jpg",
          "display_order": 0,
          "is_primary": 1
        },
        {
          "img_path": "/uploads/goods_images/detail1.jpg",
          "display_order": 1,
          "is_primary": 0
        }
      ]
    }
  ],
  "total": 100,
  "page": 1,
  "page_size": 20
}

// 失败
{
  "code": 400,
  "msg": "查询失败: 错误信息"
}
```

**商品状态说明**:
- `pending_review`: 待审核
- `on_sale`: 在售
- `sold`: 已售出
- `rejected`: 审核驳回

---

### 3. GOODS_AUDIT - 管理员审核商品

**功能**: 管理员审核商品，更新商品状态

**请求格式**:
```json
GOODS_AUDIT|{
  "goods_id": 123,           // 必填：商品ID
  "status": "on_sale",       // 必填：新状态（on_sale=通过审核上架, rejected=驳回）
  "admin_user_id": 1         // 可选：管理员用户ID（用于日志）
}
```

**响应格式**:
```json
// 成功
{
  "code": 200,
  "msg": "已通过审核，商品已上架"  // 或 "审核未通过，商品已驳回"
}

// 失败
{
  "code": 400,
  "msg": "无效的状态值，只能设置为 'on_sale'（在售）或 'rejected'（驳回）"
}
```

**注意事项**:
- 只有管理员账号（admin/admin123）可以执行此操作
- 状态只能从 `pending_review` 改为 `on_sale` 或 `rejected`
- 审核通过时，`audit_time` 会自动更新为当前时间

---

### 4. IMAGE_UPLOAD - 图片分片上传

**功能**: 上传商品图片（支持分片传输，适合大图片）

**请求格式**:
```json
IMAGE_UPLOAD|{
  "chunk_id": "uuid-123-456",           // 必填：分片唯一标识（同一图片的所有分片使用相同ID）
  "chunk_index": 0,                     // 必填：分片索引（从0开始）
  "total_chunks": 5,                    // 必填：总分片数
  "chunk_data": "base64编码的图片数据",  // 必填：分片数据（base64编码）
  "filename": "product.jpg",           // 可选：原始文件名
  "goods_id": 123,                     // 可选：商品ID（如果提供，会自动关联到商品）
  "is_primary": 1,                     // 可选：是否为主图（1=是，0=否，默认0）
  "display_order": 0                   // 可选：显示顺序（默认0，数字越小越靠前）
}
```

**响应格式**:
```json
// 分片接收中（未全部接收）
{
  "code": 200,
  "msg": "分片接收成功 (3/5)",
  "received": 3,
  "total": 5,
  "chunk_id": "uuid-123-456"
}

// 全部接收完成
{
  "code": 200,
  "msg": "图片上传成功",
  "img_path": "/uploads/goods_images/1705123456_product.jpg",
  "chunk_id": "uuid-123-456"
}

// 失败
{
  "code": 400,
  "msg": "缺少分片参数"
}
```

**上传流程**:
1. 前端将图片分成多个分片（建议每个分片8KB）
2. 对每个分片进行base64编码
3. 依次发送每个分片，使用相同的 `chunk_id`
4. 最后一个分片发送后，服务器会自动拼接并保存
5. 如果提供了 `goods_id`，图片会自动添加到商品图片表

**示例代码**:
```python
# 伪代码示例
chunk_id = generate_uuid()
total_chunks = len(image_data) // CHUNK_SIZE + 1

for i in range(total_chunks):
    chunk = image_data[i*CHUNK_SIZE:(i+1)*CHUNK_SIZE]
    chunk_base64 = base64.b64encode(chunk).decode()
    
    request = {
        "chunk_id": chunk_id,
        "chunk_index": i,
        "total_chunks": total_chunks,
        "chunk_data": chunk_base64,
        "filename": "product.jpg"
    }
    send_command("IMAGE_UPLOAD", request)
```

---

## 订单相关接口

### 1. ORDER_ADD - 创建订单（下单）

**功能**: 用户下单购买商品，自动更新商品状态为"已售出"

**请求格式**:
```json
ORDER_ADD|{
  "buyer_id": 2,        // 必填：买家用户ID
  "goods_id": 123,      // 必填：商品ID
  "quantity": 1         // 可选：购买数量（默认1）
}
```

**响应格式**:
```json
// 成功
{
  "code": 200,
  "msg": "订单创建成功",
  "order_id": 456,
  "order_no": "ORD20240115103000123"
}

// 失败
{
  "code": 400,
  "msg": "商品不存在或不在售状态，无法下单"
}
```

**业务逻辑**:
1. 检查商品是否存在且状态为 `on_sale`（在售）
2. 自动获取卖家ID（商品发布者）
3. 计算订单总价（商品价格 × 数量）
4. 生成唯一订单编号（格式：ORD + YYYYMMDDHHMMSS + 序号）
5. 创建订单，状态为 `pending_payment`（待付款）
6. 更新商品状态为 `sold`（已售出），防止重复下单

**错误码**:
- `200`: 订单创建成功
- `400`: 商品不存在、商品不在售、参数错误

---

### 2. ORDER_UPDATE - 更新订单状态

**功能**: 按订单流程更新订单状态

**请求格式**:
```json
ORDER_UPDATE|{
  "order_id": 456,                    // 必填：订单ID
  "status": "pending_shipment"        // 必填：新状态
}
```

**响应格式**:
```json
// 成功
{
  "code": 200,
  "msg": "订单状态更新成功"
}

// 失败
{
  "code": 400,
  "msg": "无效的状态流转或订单不存在"
}
```

**订单状态流转**:
```
pending_payment（待付款）
    ↓ 支付
pending_shipment（待发货）
    ↓ 发货
pending_receipt（待收货）
    ↓ 确认收货
completed（已完成）

或

pending_payment（待付款）
    ↓ 取消
canceled（已取消）
```

> 前端在点击“支付”“发货”“确认收货”“取消订单”等按钮时，直接发送对应的 `ORDER_UPDATE` 指令即可。

**状态流转规则**:
- `pending_payment` → `pending_shipment`: 支付完成
- `pending_payment` → `canceled`: 取消订单
- `pending_shipment` → `pending_receipt`: 卖家发货
- `pending_receipt` → `completed`: 买家确认收货
- 其他流转视为非法

**时间字段自动更新**:
- `pending_shipment`: 更新 `paid_at`
- `pending_receipt`: 更新 `shipped_at`
- `completed`: 更新 `received_at` 和 `completed_at`
- `canceled`: 更新 `canceled_at`

---

### 3. ORDER_GET - 获取我的订单

**功能**: 查询用户的订单列表，支持按状态筛选

**请求格式**:
```json
ORDER_GET|{
  "buyer_id": 2,              // 必填：买家用户ID（查询我的订单）
  "status": "pending_payment" // 可选：订单状态（不传则查询所有状态）
}
```

**响应格式**:
```json
// 成功
{
  "code": 200,
  "msg": "查询成功",
  "data": [
    {
      "order_id": 456,
      "order_no": "ORD20240115103000123",
      "buyer_id": 2,
      "seller_id": 1,
      "goods_id": 123,
      "quantity": 1,
      "total_price": 3500.00,
      "status": "pending_payment",
      "created_at": "2024-01-15 10:30:00",
      "updated_at": "2024-01-15 10:30:00",
      "paid_at": null,
      "shipped_at": null,
      "received_at": null,
      "completed_at": null,
      "canceled_at": null,
      "title": "二手iPhone 13",
      "img_path": "/uploads/goods_images/main.jpg",
      "primary_image": "/uploads/goods_images/main.jpg"
    }
  ]
}

// 失败
{
  "code": 400,
  "msg": "缺少buyer_id参数"
}
```

**订单状态说明**:
- `pending_payment`: 待付款
- `pending_shipment`: 待发货
- `pending_receipt`: 待收货
- `completed`: 已完成
- `canceled`: 已取消

---

## 收藏相关接口

### 1. COLLECT_ADD - 添加收藏

**功能**: 用户收藏商品

**请求格式**:
```json
COLLECT_ADD|{
  "user_id": 2,      // 必填：用户ID
  "goods_id": 123    // 必填：商品ID
}
```

**响应格式**:
```json
// 成功
{
  "code": 200,
  "msg": "收藏成功"
}

// 失败（已收藏）
{
  "code": 400,
  "msg": "该商品已收藏，不能重复收藏"
}
```

---

### 2. COLLECT_GET - 获取我的收藏

**功能**: 查询用户收藏的商品列表

**请求格式**:
```json
COLLECT_GET|{
  "user_id": 2    // 必填：用户ID
}
```

**响应格式**:
```json
// 成功
{
  "code": 200,
  "msg": "查询成功",
  "data": [
    {
      "collect_id": 789,
      "goods_id": 123,
      "collected_at": "2024-01-15 10:30:00",
      "title": "二手iPhone 13",
      "price": 3500.00,
      "img_path": "/uploads/goods_images/main.jpg",
      "primary_image": "/uploads/goods_images/main.jpg",
      "status": "on_sale"
    }
  ]
}

// 失败
{
  "code": 400,
  "msg": "缺少user_id参数"
}
```

---

### 3. COLLECT_DEL - 取消收藏

**功能**: 用户取消收藏商品

**请求格式**:
```json
COLLECT_DEL|{
  "user_id": 2,      // 必填：用户ID
  "goods_id": 123    // 必填：商品ID
}
```

**响应格式**:
```json
// 成功
{
  "code": 200,
  "msg": "取消收藏成功"
}

// 失败
{
  "code": 400,
  "msg": "未找到该收藏记录"
}
```

---

## 数据字段说明

### 商品表（goods）字段
| 字段名 | 类型 | 说明 |
|--------|------|------|
| goods_id | INT | 商品ID（主键） |
| user_id | INT | 发布者用户ID |
| title | VARCHAR(100) | 商品标题 |
| description | TEXT | 商品描述 |
| category | VARCHAR(50) | 商品分类 |
| brand | VARCHAR(50) | 商品品牌 |
| price | DECIMAL(10,2) | 商品价格（现价） |
| original_price | DECIMAL(10,2) | 商品原价 |
| purchase_time | DATE | 购买时间 |
| stock_quantity | INT | 库存量 |
| sold_count | INT | 已售件数 |
| img_path | VARCHAR(255) | 主图路径（兼容字段） |
| status | ENUM | 商品状态（pending_review/on_sale/sold/rejected） |
| create_time | TIMESTAMP | 创建时间（上架提交时间） |
| audit_time | TIMESTAMP | 审核时间（通过/驳回时） |
| off_time | TIMESTAMP | 下架时间 |

### 订单表（order）字段
| 字段名 | 类型 | 说明 |
|--------|------|------|
| order_id | INT | 订单ID（主键） |
| order_no | VARCHAR(64) | 订单编号（唯一，格式：ORD+时间戳+序号） |
| buyer_id | INT | 买家用户ID |
| seller_id | INT | 卖家用户ID |
| goods_id | INT | 商品ID |
| quantity | INT | 购买数量 |
| total_price | DECIMAL(10,2) | 订单总价 |
| status | ENUM | 订单状态 |
| created_at | TIMESTAMP | 下单时间 |
| updated_at | TIMESTAMP | 最后更新时间 |
| paid_at | TIMESTAMP | 支付时间 |
| shipped_at | TIMESTAMP | 发货时间 |
| received_at | TIMESTAMP | 收货时间 |
| completed_at | TIMESTAMP | 完成时间 |
| canceled_at | TIMESTAMP | 取消时间 |

---

## 错误码说明

### 通用错误码
| 错误码 | 说明 |
|--------|------|
| 200 | 操作成功 |
| 400 | 参数错误、业务逻辑错误 |
| 401 | 用户名或密码错误、用户名已存在 |
| 403 | 账号被封禁、权限不足 |
| 404 | 未知指令 |
| 500 | 服务器内部错误 |

### 商品相关错误
- `400`: 缺少必填参数、商品不存在、商品不在售状态
- `403`: 非管理员尝试审核商品

### 订单相关错误
- `400`: 缺少必填参数、商品不存在、商品不在售、无效的状态流转、订单不存在

### 收藏相关错误
- `400`: 缺少必填参数、商品已收藏、未找到收藏记录

---

## 业务流程示例

### 1. 发布商品流程
```
1. 用户登录 → LOGIN
2. 上传商品图片 → IMAGE_UPLOAD（多次，每张图片）
3. 发布商品 → GOODS_ADD（状态：pending_review）
4. 管理员审核 → GOODS_AUDIT（状态：on_sale 或 rejected）
```

### 2. 购买商品流程
```
1. 浏览商品 → GOODS_GET（status: on_sale）
2. 查看商品详情 → GOODS_GET（单个商品）
3. 下单 → ORDER_ADD（状态：pending_payment，商品状态：sold）
4. 支付 → ORDER_UPDATE（状态：pending_shipment）
5. 卖家发货 → ORDER_UPDATE（状态：pending_receipt）
6. 买家收货 → ORDER_UPDATE（状态：completed）
```

### 3. 收藏商品流程
```
1. 浏览商品 → GOODS_GET
2. 收藏商品 → COLLECT_ADD
3. 查看我的收藏 → COLLECT_GET
4. 取消收藏 → COLLECT_DEL
```

---

## 注意事项

1. **图片上传**: 建议分片大小8KB，大图片需要分多次发送
2. **订单状态**: 必须按照规定的状态流转顺序，不能跳跃
3. **商品状态**: 只有 `on_sale` 状态的商品可以下单
4. **管理员权限**: 只有管理员账号（admin/admin123）可以审核商品
5. **订单编号**: 自动生成，格式为 `ORD + YYYYMMDDHHMMSS + 序号`，保证唯一性
6. **时间字段**: 订单状态更新时会自动更新对应的时间字段

---

## 测试建议

1. **商品发布测试**:
   - 测试必填参数校验
   - 测试图片上传（单张、多张）
   - 测试管理员审核流程

2. **订单流程测试**:
   - 测试正常下单流程
   - 测试重复下单（应该失败）
   - 测试订单状态流转
   - 测试取消订单

3. **收藏功能测试**:
   - 测试添加收藏
   - 测试重复收藏（应该失败）
   - 测试取消收藏
   - 测试查询收藏列表

---

## 联系方式

如有问题，请联系后端开发人员。

