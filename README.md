# 商品信息爬虫使用说明

## 📋 功能说明

这个爬虫系统可以：
1. **爬取商品信息**：从二手交易平台获取商品数据
2. **下载图片**：自动下载商品图片到本地
3. **存储数据**：将商品信息保存到MySQL数据库
4. **数据清洗**：自动清理和格式化数据

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置数据库

编辑 `spider.py` 中的数据库配置：

```python
db_config = {
    'host': '127.0.0.1',
    'port': 3306,
    'user': 'root',
    'password': '你的数据库密码',  # 修改这里
    'database': 'used_goods_platform',
    'charset': 'utf8mb4'
}
```

### 3. 运行爬虫

```bash
python spider.py
```

然后选择：
- **选项1**：模拟爬虫（生成测试数据，推荐先用这个测试）
- **选项2**：真实爬虫（需要根据目标网站调整代码）

## 📝 使用示例

### 使用模拟爬虫（推荐）

```python
from spider import MockSpider

db_config = {
    'host': '127.0.0.1',
    'port': 3306,
    'user': 'root',
    'password': '123456',
    'database': 'used_goods_platform',
    'charset': 'utf8mb4'
}

spider = MockSpider(db_config=db_config, image_dir="images")
spider.crawl(max_items=100)  # 生成100个商品
```

### 使用真实爬虫

```python
from spider import XianyuSpider

spider = XianyuSpider(db_config=db_config, image_dir="images")
spider.crawl(max_items=50)  # 爬取50个商品
```

## ⚙️ 自定义爬虫

### 创建新的爬虫类

```python
from spider import ProductSpider

class MyCustomSpider(ProductSpider):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.base_url = "https://example.com"
    
    def crawl(self, max_items=50):
        # 实现你的爬取逻辑
        pass
    
    def parse_item(self, item_element):
        # 解析商品元素
        return {
            'title': '商品标题',
            'price': 99.00,
            'category': '数码',
            'description': '商品描述',
            'image_urls': ['图片URL'],
            'seller_id': 1
        }
```

## 🔧 数据字段说明

爬虫需要返回以下字段：

| 字段 | 类型 | 说明 | 必填 |
|------|------|------|------|
| title | str | 商品标题 | ✅ |
| price | float | 商品价格 | ✅ |
| category | str | 商品分类 | ✅ |
| description | str | 商品描述 | ⭕ |
| original_price | float | 原价 | ⭕ |
| condition | str | 成色（全新/99新等） | ⭕ |
| image_urls | list | 图片URL列表 | ⭕ |
| seller_id | int | 卖家ID | ⭕ |

## ⚠️ 注意事项

### 1. 遵守网站规则
- 查看目标网站的 `robots.txt`
- 遵守网站的使用条款
- 不要过度频繁请求

### 2. 反爬虫处理
- 已内置随机延迟
- 已设置User-Agent
- 建议使用代理IP（如需要）

### 3. 数据去重
- 爬虫会自动检查重复商品（根据标题和价格）
- 已存在的商品会被跳过

### 4. 图片存储
- 图片保存在 `images/` 目录
- 文件名格式：`goods_{商品ID}_{索引}.jpg`
- 图片路径会保存到数据库的 `img_path` 字段

## 🐛 常见问题

### Q: 数据库连接失败？
A: 检查数据库配置是否正确，确保MySQL服务正在运行。

### Q: 图片下载失败？
A: 检查网络连接，确保图片URL可访问。

### Q: 爬取速度太慢？
A: 可以调整 `random_delay()` 的延迟时间，但要注意不要被封。

### Q: 如何爬取其他网站？
A: 继承 `ProductSpider` 类，实现 `crawl()` 和 `parse_item()` 方法。

## 📚 扩展功能

### 添加代理支持

```python
proxies = {
    'http': 'http://proxy.example.com:8080',
    'https': 'https://proxy.example.com:8080'
}
self.session.proxies.update(proxies)
```

### 添加Cookie支持

```python
self.session.cookies.update({
    'cookie_name': 'cookie_value'
})
```

### 使用Selenium（处理JavaScript）

如果需要处理JavaScript渲染的页面，可以使用Selenium：

```python
from selenium import webdriver

driver = webdriver.Chrome()
driver.get(url)
html = driver.page_source
soup = BeautifulSoup(html, 'html.parser')
```

## 📄 许可证

仅供学习和研究使用，请遵守相关法律法规。

