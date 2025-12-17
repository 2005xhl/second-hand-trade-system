## 数据统计接口说明（DATA_STAT）

本说明文档仅包含数据可视化看板相关接口，独立于原有业务 API 文档。

---

### 一、总体设计

- **指令名称**：`DATA_STAT`
- **用途**：为前端可视化看板提供所需的统计数据，包括：
  - 分类商品数量（柱状图 / 饼图）
  - 个人订单状态占比（饼图）
  - 最近 7 天下单 / 成交趋势（折线图）
  - 热门分类 TOP5（按成交量）（柱状 / 条形图）
  - 个人喜爱度（按购买商品种类）（饼图 / 条形图）
  - 简单时间序列预测（近 7 天成交量移动平均 → 预测下周需求）

后端实现位置：
- 统计 SQL：`db_utils.py` 中一组 `stat_***` 方法
- 指令处理：`server.py` 中 `elif cmd_type == "DATA_STAT":` 分支

---

### 二、请求格式与使用场景

#### 1. 指令报文格式（通用）

```text
DATA_STAT|{"user_id": 1}
```

- **`user_id`**（可选，int）
  - 若提供：返回“**与该用户相关**”的个人化统计（个人订单状态占比、个人喜爱度）
  - 若不提供：这两个字段返回空数组，其它**全局统计**照常返回

#### 2. 典型使用场景

- **管理员全局看板（不区分具体用户）**

  - 发送示例：

    ```text
    DATA_STAT|{}
    ```

  - 用途：
    - 分类商品数量分布
    - 全站订单趋势（最近 7 天）
    - 热门分类 TOP5
    - 整体成交量预测
  - 响应中：
    - `category_counts` / `last7_trend` / `hot_categories` / `last7_completed_daily` / `next7_forecast` 有数据
    - `my_order_status_ratio` 与 `my_favorite_categories` 为空数组（因为没有指定用户）

- **管理员查看某个用户画像 / 用户个人中心看板**

  - 发送示例：

    ```text
    DATA_STAT|{"user_id": 123}
    ```

  - 用途：
    - 管理员在后台查看某个用户的消费行为（订单状态分布、偏好分类）
    - 普通用户在“个人中心-统计页”查看自己的订单状态占比 & 喜爱分类
  - 响应中：
    - 在全局统计字段之外，`my_order_status_ratio` 与 `my_favorite_categories` 额外返回该用户维度的数据

---

### 三、响应格式（总体结构）

#### 1. 成功响应示例

```json
DATA_STAT|{
  "code": 200,
  "msg": "统计成功",
  "data": {
    "category_counts": [
      {"category": "数码 - 手机 - 苹果", "on_sale_count": 12, "total_count": 18},
      {"category": "图书 - 教材", "on_sale_count": 5, "total_count": 9}
    ],
    "my_order_status_ratio": [
      {"status": "pending_payment",  "cnt": 2},
      {"status": "pending_shipment", "cnt": 1},
      {"status": "completed",        "cnt": 5},
      {"status": "canceled",         "cnt": 1}
    ],
    "last7_trend": [
      {"date": "2025-12-11", "orders": 8, "completed": 5},
      {"date": "2025-12-12", "orders": 6, "completed": 4}
    ],
    "hot_categories": [
      {"category": "数码 - 手机 - 苹果", "completed_orders": 20},
      {"category": "图书 - 教材",       "completed_orders": 12}
    ],
    "my_favorite_categories": [
      {"category": "图书 - 教材", "buy_count": 4},
      {"category": "数码 - 手机 - 苹果", "buy_count": 3}
    ],
    "last7_completed_daily": [
      {"date": "2025-12-11", "completed": 5},
      {"date": "2025-12-12", "completed": 4}
    ],
    "next7_forecast": [
      {"date": "2025-12-18", "predicted_completed": 4.71},
      {"date": "2025-12-19", "predicted_completed": 4.71}
    ]
  }
}
```

#### 2. 失败响应示例

```json
DATA_STAT|{
  "code": 500,
  "msg": "统计失败: 数据库连接失败"
}
```

---

### 四、各字段含义与前端图表映射

#### 1. 分类商品数量（`category_counts`）

- 来源方法：`db_utils.stat_category_goods()`
- 字段说明：
  - **`category`**：字符串，商品分类（如 “数码 - 手机 - 苹果”）
  - **`on_sale_count`**：int，在售商品数量（`status = 'on_sale'`）
  - **`total_count`**：int，该分类的商品总数量

**前端建议：**
- 柱状图：
  - x 轴：`category`
  - y 轴：`on_sale_count` 或 `total_count`
- 饼图：
  - 扇区名称：`category`
  - 数值：`on_sale_count` 或 `total_count`

#### 2. 个人订单状态占比（`my_order_status_ratio`）

- 前提：请求体中提供了 `user_id`
- 来源方法：`db_utils.stat_user_order_status(buyer_id)`
- 字段说明：
  - **`status`**：订单状态枚举
    - `pending_payment`：待付款
    - `pending_shipment`：待发货
    - `pending_receipt`：待收货
    - `completed`：已完成
    - `canceled`：已取消
  - **`cnt`**：int，该状态下订单数量

**前端建议：**
- 饼图：
  - 扇区名称：将 `status` 转成人类可读中文
  - 数值：`cnt`
- 占比：前端自行计算 `cnt / sum(cnt)`。

#### 3. 最近 7 天下单 / 成交趋势（`last7_trend`）

- 来源方法：`db_utils.stat_last_n_days_orders(7)`
- 字段说明（列表中的每一项）：
  - **`date`**：`"YYYY-MM-DD"` 字符串，连续的自然日（包含没有订单的天，补 0）
  - **`orders`**：int，当天创建的订单数量（按 `created_at`）
  - **`completed`**：int，当天完成的订单数量（按 `completed_at` 且 `status='completed'`）

**前端建议：**
- 折线图：
  - x 轴：`date`
  - y 轴1：`orders`
  - y 轴2：`completed`（可两条线叠加）

#### 4. 热门分类 TOP5（按成交量）（`hot_categories`）

- 来源方法：`db_utils.stat_hot_categories_top5(days=30)`
- 筛选条件：近 30 天内，`order.status='completed'`，按分类聚合
- 字段说明：
  - **`category`**：分类名称
  - **`completed_orders`**：int，该分类内完成订单数

**前端建议：**
- 横向条形图 / 柱状图：
  - x 轴：`completed_orders`
  - y 轴：`category`
  - 只取前 5 条（后端已 LIMIT 5）

#### 5. 个人喜爱度（购买商品种类）（`my_favorite_categories`）

- 前提：请求体中提供了 `user_id`
- 来源方法：`db_utils.stat_user_favorite_categories(buyer_id)`
- 统计口径：该用户作为买家、`status='completed'` 的订单，按商品分类统计购买次数
- 字段说明：
  - **`category`**：分类名称
  - **`buy_count`**：int，该用户在此分类下完成购买的次数

**前端建议：**
- 饼图：展示用户在各分类的购买占比（喜爱度）
- 条形图：x 轴为 `category`，y 轴为 `buy_count`
- 可用于推荐逻辑：在该用户偏好高的分类下优先展示商品。

#### 6. 最近 7 天成交量 & 简单预测（`last7_completed_daily` + `next7_forecast`）

##### 6.1 最近 7 天每天成交量（`last7_completed_daily`）

- 来源方法：`db_utils.stat_last_n_days_completed(7)`
- 字段说明：
  - **`date`**：`"YYYY-MM-DD"`，连续 7 天
  - **`completed`**：int，当天完成订单数

##### 6.2 简单时间序列外推（`next7_forecast`）

- 计算逻辑（已在后端实现于 `DATA_STAT` 分支中）：
  1. 对 `last7_completed_daily` 中的 `completed` 取平均值：  
     \[
     \text{avg\_completed} = \frac{\sum completed}{7}
     \]
  2. 未来 7 天的 `predicted_completed` 统一使用这个平均值（四舍五入保留两位小数）
  3. `date` 从“明天”起连续 7 天

- 字段说明：
  - **`date`**：未来第 1~7 天的日期
  - **`predicted_completed`**：float，预测的完成订单数量（移动平均）

**前端建议：**
- 折线图（可与历史数据拼在一起）：
  - 用不同颜色/虚线表示预测区间
  - x 轴时间连续，从过去 7 天到未来 7 天

---

### 五、前端对接小结

- **请求**：统一使用 Socket 协议，发送：

```text
DATA_STAT|{"user_id": 当前登录用户ID}
```

- **核心数据源**（前端只需读，不需要再算 SQL）：
  - `data.category_counts`            → 分类商品数量图
  - `data.my_order_status_ratio`     → 个人订单状态占比饼图
  - `data.last7_trend`               → 最近 7 天下单 / 成交趋势折线图
  - `data.hot_categories`            → 热门分类 TOP5
  - `data.my_favorite_categories`    → 个人喜爱度（分类偏好）
  - `data.last7_completed_daily`     → 历史成交折线（用于表现“最近 7 天表现”）
  - `data.next7_forecast`            → 预测曲线（简单移动平均）

前端根据以上字段直接映射到图表即可，无需再做复杂的聚合运算。若后续需要补充更多指标，可以在 `db_utils.py` 中新增统计方法，并在 `DATA_STAT` 的 `data` 字段中扩展即可。


