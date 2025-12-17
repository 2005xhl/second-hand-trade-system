"""
商品信息爬虫
支持爬取二手交易平台的商品信息并存储到数据库
"""

import requests
from bs4 import BeautifulSoup
import time
import random
import os
import re
import json
from urllib.parse import urljoin, urlparse
import pymysql
from datetime import datetime, timedelta
import hashlib


class ProductSpider:
    """商品爬虫基类"""
    
    def __init__(self, db_config=None, image_dir="images"):
        """
        初始化爬虫
        :param db_config: 数据库配置字典
        :param image_dir: 图片存储目录
        """
        self.db_config = db_config or {
            'host': '127.0.0.1',
            'port': 3306,
            'user': 'root',
            'password': '123456',
            'database': 'used_goods_platform',
            'charset': 'utf8mb4'
        }
        # 图片目录（使用绝对路径，但保存到数据库时使用相对路径）
        self.image_dir = os.path.abspath(image_dir)
        # 确保图片目录存在
        os.makedirs(self.image_dir, exist_ok=True)
        
        self.session = requests.Session()
        
        # 设置请求头，模拟浏览器
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        self.session.headers.update(self.headers)
        
        # 数据库连接
        self.db_conn = None
    
    def connect_db(self):
        """连接数据库"""
        try:
            self.db_conn = pymysql.connect(**self.db_config)
            print("数据库连接成功")
            return True
        except Exception as e:
            print(f"数据库连接失败: {e}")
            return False
    
    def close_db(self):
        """关闭数据库连接"""
        if self.db_conn:
            self.db_conn.close()
    
    def download_image(self, image_url, product_id, index=0):
        """
        下载图片到本地
        :param image_url: 图片URL
        :param product_id: 商品ID（用于命名）
        :param index: 图片索引
        :return: 本地图片路径
        """
        try:
            # 获取图片扩展名
            parsed = urlparse(image_url)
            ext = os.path.splitext(parsed.path)[1] or '.jpg'
            
            # 生成文件名
            filename = f"goods_{product_id}_{index}{ext}"
            filepath = os.path.join(self.image_dir, filename)
            
            # 下载图片
            response = self.session.get(image_url, timeout=10)
            if response.status_code == 200:
                with open(filepath, 'wb') as f:
                    f.write(response.content)
                print(f"  图片下载成功: {filename}")
                return filepath
            else:
                print(f"  图片下载失败: {image_url} (状态码: {response.status_code})")
                return None
        except Exception as e:
            print(f"  图片下载异常: {e}")
            return None
    
    def save_to_database(self, product_data):
        """
        保存商品数据到数据库
        :param product_data: 商品数据字典
        :return: 是否成功
        """
        try:
            cursor = self.db_conn.cursor()
            
            # 检查商品是否已存在（根据标题和价格）
            check_sql = """
                SELECT goods_id FROM goods 
                WHERE title = %s AND price = %s
                LIMIT 1
            """
            cursor.execute(check_sql, (product_data['title'], product_data['price']))
            if cursor.fetchone():
                print(f"  商品已存在，跳过: {product_data['title']}")
                return False
            
            # 如果没有seller_id，使用默认值1（或创建一个默认卖家）
            seller_id = product_data.get('seller_id', 1)
            
            # 插入商品数据（字段需与 used_goods_platform.sql 中的 goods 表结构对齐）
            # 当前 goods 表关键字段：
            # user_id, title, description, category, brand, price, original_price,
            # purchase_time, stock_quantity, sold_count, img_path, status, create_time
            insert_sql = """
                INSERT INTO goods (
                    user_id, title, description, category, brand,
                    price, original_price, purchase_time,
                    stock_quantity, sold_count, img_path, status, create_time
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s, %s, %s
                )
            """
            
            # 处理图片路径（多个图片用逗号分隔）
            img_path = product_data.get('img_path', '')
            if isinstance(img_path, list):
                img_path = ','.join(img_path)
            
            # 简单设置：
            # - brand 使用来源平台或分类名
            # - purchase_time 使用当前日期前若干天
            # - stock_quantity 默认 1，sold_count 默认 0
            # - status 使用 'pending_review'，后续由审核 / 上架流程控制
            brand = product_data.get('brand') or 'SpiderBrand'
            description = product_data.get('description', '')
            category = product_data.get('category', '其他')
            price = product_data.get('price', 0)
            original_price = product_data.get('original_price')
            purchase_days_ago = random.randint(30, 365)
            purchase_time = datetime.now() - timedelta(days=purchase_days_ago)
            
            values = (
                seller_id,  # user_id (卖家ID)
                product_data.get('title', ''),
                description,
                category,
                brand,
                price,
                original_price,
                purchase_time.date(),  # DATE 类型
                1,          # stock_quantity
                0,          # sold_count
                img_path,
                'pending_review',  # 状态：待审核
                datetime.now()
            )
            
            cursor.execute(insert_sql, values)
            self.db_conn.commit()
            
            goods_id = cursor.lastrowid
            print(f"  商品保存成功，ID: {goods_id}")
            cursor.close()
            return True
            
        except Exception as e:
            print(f"  数据库保存失败: {e}")
            self.db_conn.rollback()
            return False
    
    def random_delay(self, min_sec=1, max_sec=3):
        """随机延迟，避免被封"""
        delay = random.uniform(min_sec, max_sec)
        time.sleep(delay)
    
    def clean_text(self, text):
        """清理文本"""
        if not text:
            return ''
        # 移除多余的空白字符
        text = re.sub(r'\s+', ' ', text.strip())
        return text
    
    def extract_price(self, price_str):
        """提取价格数字"""
        if not price_str:
            return 0
        # 提取数字
        numbers = re.findall(r'\d+\.?\d*', str(price_str))
        if numbers:
            return float(numbers[0])
        return 0
    
    def extract_category(self, title, description=''):
        """根据标题和描述推断分类"""
        text = (title + ' ' + description).lower()
        
        category_map = {
            '数码': ['手机', '电脑', '笔记本', '平板', '相机', '耳机', '音响', '数码', 'iphone', 'ipad', 'macbook'],
            '服饰': ['衣服', '鞋子', '包包', '服装', 't恤', '外套', '裤子', '裙子', '运动鞋'],
            '图书': ['书', '教材', '小说', '漫画', '杂志', '图书', '课本'],
            '家居': ['家具', '装饰', '厨具', '收纳', '床', '沙发', '桌子', '椅子'],
        }
        
        for category, keywords in category_map.items():
            if any(keyword in text for keyword in keywords):
                return category
        
        return '其他'
    
    def crawl(self, max_items=50):
        """
        爬取商品（子类需要实现）
        :param max_items: 最大爬取数量
        """
        raise NotImplementedError("子类需要实现crawl方法")


class XianyuSpider(ProductSpider):
    """闲鱼爬虫（示例，需要根据实际网站结构调整）"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.base_url = "https://www.goofish.com"  # 闲鱼域名示例
    
    def crawl(self, max_items=50):
        """
        爬取闲鱼商品
        注意：这是示例代码，实际使用时需要根据网站结构调整
        """
        print(f"开始爬取闲鱼商品，目标数量: {max_items}")
        
        if not self.connect_db():
            return
        
        try:
            count = 0
            page = 1
            
            while count < max_items:
                # 构建搜索URL（示例）
                search_url = f"{self.base_url}/search?page={page}"
                
                print(f"\n正在爬取第 {page} 页...")
                
                try:
                    response = self.session.get(search_url, timeout=10)
                    if response.status_code != 200:
                        print(f"请求失败，状态码: {response.status_code}")
                        break
                    
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # 解析商品列表（需要根据实际HTML结构调整）
                    # 这里只是示例，实际需要查看网页源代码来确定选择器
                    items = soup.find_all('div', class_='item')  # 示例选择器
                    
                    if not items:
                        print("没有找到商品，可能已到最后一页")
                        break
                    
                    for item in items:
                        if count >= max_items:
                            break
                        
                        try:
                            product_data = self.parse_item(item)
                            if product_data:
                                # 下载图片
                                img_paths = []
                                for idx, img_url in enumerate(product_data.get('image_urls', [])[:3]):  # 最多3张
                                    local_path = self.download_image(img_url, count + 1, idx)
                                    if local_path:
                                        img_paths.append(local_path)
                                
                                product_data['img_path'] = img_paths
                                
                                # 保存到数据库
                                if self.save_to_database(product_data):
                                    count += 1
                                    print(f"已爬取 {count}/{max_items} 个商品")
                                
                                # 随机延迟
                                self.random_delay(1, 2)
                                
                        except Exception as e:
                            print(f"解析商品失败: {e}")
                            continue
                    
                    page += 1
                    self.random_delay(2, 4)  # 翻页延迟
                    
                except Exception as e:
                    print(f"爬取第 {page} 页失败: {e}")
                    break
            
            print(f"\n爬取完成！共爬取 {count} 个商品")
            
        finally:
            self.close_db()
    
    def parse_item(self, item_element):
        """
        解析单个商品元素
        :param item_element: BeautifulSoup元素
        :return: 商品数据字典
        """
        try:
            # 这里需要根据实际HTML结构调整
            # 示例代码：
            title_elem = item_element.find('a', class_='title')
            price_elem = item_element.find('span', class_='price')
            img_elem = item_element.find('img')
            
            if not title_elem or not price_elem:
                return None
            
            title = self.clean_text(title_elem.get_text())
            price = self.extract_price(price_elem.get_text())
            
            # 获取图片URL
            image_urls = []
            if img_elem:
                img_url = img_elem.get('src') or img_elem.get('data-src')
                if img_url:
                    image_urls.append(urljoin(self.base_url, img_url))
            
            # 获取描述（如果有）
            desc_elem = item_element.find('div', class_='desc')
            description = self.clean_text(desc_elem.get_text()) if desc_elem else ''
            
            # 推断分类
            category = self.extract_category(title, description)
            
            return {
                'title': title,
                'price': price,
                'original_price': None,  # 闲鱼通常没有原价
                'condition': '99新',  # 默认值
                'description': description or title,
                'category': category,
                'image_urls': image_urls,
                'seller_id': 1  # 默认卖家ID
            }
            
        except Exception as e:
            print(f"解析商品元素失败: {e}")
            return None


class MockSpider(ProductSpider):
    """模拟爬虫（用于测试，生成假数据）"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.categories = ['数码', '服饰', '图书', '家居', '其他']
        self.conditions = ['全新', '99新', '95新', '9成新', '8成新']
        self.keywords = {
            '数码': ['iPhone', 'MacBook', 'iPad', '相机', '耳机', '音响', '键盘', '鼠标'],
            '服饰': ['T恤', '外套', '鞋子', '包包', '牛仔裤', '运动鞋', '卫衣'],
            '图书': ['教材', '小说', '漫画', '杂志', '课本', '参考书'],
            '家居': ['沙发', '桌子', '椅子', '床', '柜子', '装饰画', '台灯'],
            '其他': ['其他商品', '闲置物品', '二手商品']
        }
    
    def crawl(self, max_items=50):
        """生成模拟商品数据"""
        print(f"开始生成模拟商品数据，目标数量: {max_items}")
        
        if not self.connect_db():
            return
        
        try:
            import random
            from PIL import Image, ImageDraw, ImageFont
            
            for i in range(max_items):
                category = random.choice(self.categories)
                keyword = random.choice(self.keywords[category])
                condition = random.choice(self.conditions)
                
                product_data = {
                    'title': f"{condition}{keyword} {random.choice(['二手', '闲置', '转让'])}",
                    'price': round(random.uniform(50, 2000), 2),
                    'original_price': round(random.uniform(100, 3000), 2) if random.random() > 0.5 else None,
                    'condition': condition,
                    'description': f"这是一件{condition}的{keyword}，功能完好，欢迎咨询。",
                    'category': category,
                    'img_path': [],  # 先不设置图片，保存后获取ID再生成
                    'seller_id': random.randint(1, 10)  # 随机卖家ID
                }
                
                # 先保存商品获取真实ID
                if self.save_to_database(product_data):
                    # 获取刚插入的商品ID
                    cursor = self.db_conn.cursor()
                    cursor.execute("SELECT LAST_INSERT_ID()")
                    goods_id = cursor.fetchone()[0]
                    cursor.close()
                    
                    # 使用真实ID生成占位图片
                    img_paths = self._generate_placeholder_image(goods_id, category, keyword)
                    
                    # 更新数据库中的图片路径
                    if img_paths:
                        cursor = self.db_conn.cursor()
                        img_path_str = ','.join(img_paths)
                        cursor.execute(
                            "UPDATE goods SET img_path = %s WHERE goods_id = %s",
                            (img_path_str, goods_id)
                        )
                        self.db_conn.commit()
                        cursor.close()
                    
                    print(f"已生成 {i+1}/{max_items} 个商品 (ID: {goods_id})")
                
                # 延迟
                time.sleep(0.1)
            
            print(f"\n生成完成！共生成 {max_items} 个商品")
            print(f"图片保存在: {os.path.abspath(self.image_dir)}")
            
        finally:
            self.close_db()
    
    def _generate_placeholder_image(self, product_id, category, keyword):
        """
        生成占位图片
        :param product_id: 商品ID
        :param category: 分类
        :param keyword: 关键词
        :return: 图片路径列表
        """
        try:
            # 创建图片
            img = Image.new('RGB', (800, 600), color=(245, 245, 245))
            draw = ImageDraw.Draw(img)
            
            # 尝试使用中文字体，如果失败则使用默认字体
            try:
                # Windows系统常见字体路径
                font_paths = [
                    'C:/Windows/Fonts/msyh.ttc',  # 微软雅黑
                    'C:/Windows/Fonts/simhei.ttf',  # 黑体
                    'C:/Windows/Fonts/simsun.ttc',  # 宋体
                ]
                font = None
                for path in font_paths:
                    if os.path.exists(path):
                        font = ImageFont.truetype(path, 60)
                        break
                if font is None:
                    font = ImageFont.load_default()
            except:
                font = ImageFont.load_default()
            
            # 绘制文字
            text = f"{category}\n{keyword}"
            # 计算文字位置（居中）
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            position = ((800 - text_width) // 2, (600 - text_height) // 2)
            
            # 绘制文字
            draw.text(position, text, fill=(150, 150, 150), font=font)
            
            # 保存图片（使用绝对路径保存文件）
            filename = f"goods_{product_id}_0.jpg"
            filepath = os.path.join(self.image_dir, filename)
            img.save(filepath, 'JPEG', quality=85)
            
            # 返回相对路径（相对于项目根目录），便于前端访问
            # 假设images目录在项目根目录下
            relative_path = f"images/{filename}"
            
            print(f"  生成占位图片: {filename}")
            return [relative_path]
            
        except Exception as e:
            print(f"  生成占位图片失败: {e}")
            import traceback
            traceback.print_exc()
            # 如果生成失败，返回空列表（前端会显示默认占位图）
            return []


def main():
    """主函数"""
    print("=" * 50)
    print("商品信息爬虫")
    print("=" * 50)
    
    # 数据库配置
    db_config = {
        'host': '127.0.0.1',
        'port': 3306,
        'user': 'root',
        'password': '123456',  # 请修改为你的数据库密码
        'database': 'used_goods_platform',
        'charset': 'utf8mb4'
    }
    
    # 选择爬虫类型
    print("\n请选择爬虫类型：")
    print("1. 模拟爬虫（生成测试数据）")
    print("2. 闲鱼爬虫（需要根据实际网站调整）")
    
    choice = input("请输入选项 (1/2): ").strip()
    
    if choice == '1':
        spider = MockSpider(db_config=db_config, image_dir="images")
        max_items = int(input("请输入要生成的商品数量 (默认50): ") or "50")
        spider.crawl(max_items=max_items)
    elif choice == '2':
        spider = XianyuSpider(db_config=db_config, image_dir="images")
        max_items = int(input("请输入要爬取的商品数量 (默认50): ") or "50")
        print("\n注意：闲鱼爬虫需要根据实际网站结构调整代码！")
        spider.crawl(max_items=max_items)
    else:
        print("无效选项")


if __name__ == "__main__":
    main()
