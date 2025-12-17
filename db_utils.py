import hashlib
import pymysql
import pymysql.cursors
import os
import random
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta


class DBManager:
    """
    轻量级数据库封装，处理所有数据库CRUD操作
    """

    def __init__(self, host: str, port: int, user: str, password: str, database: str):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        print(f"[DB INFO] 数据库管理器初始化完成，HOST: {host}, DB: {database}")

    # ---------- 工具方法 ----------
    def _get_conn(self):
        """尝试获取数据库连接，失败时捕获异常并返回 None"""
        try:
            conn = pymysql.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database,
                charset="utf8mb4",
                autocommit=True, # 自动提交，简化事务处理
            )
            return conn
        except Exception as e:
            # 致命修复 1：打印连接错误，防止卡死
            print(f"[DB FATAL] 数据库连接失败! 请检查MySQL服务/密码/IP. 错误: {e}")
            return None

    @staticmethod
    def _md5(text: str) -> str:
        return hashlib.md5(text.encode("utf-8")).hexdigest()

    def ensure_admin_account(self, username: str = "admin", password: str = "admin123") -> None:
        """
        确保管理员账号存在；若不存在则创建，若存在则强制设为管理员并重置密码为默认值。
        """
        conn = self._get_conn()
        if not conn:
            print("[DB WARN] 无法检查/创建管理员账号：数据库连接失败")
            return

        cur = None
        try:
            cur = conn.cursor(pymysql.cursors.DictCursor)
            cur.execute(
                "SELECT user_id, role FROM user WHERE username=%s",
                (username,)
            )
            row = cur.fetchone()
            pwd_hash = self._md5(password)
            if not row:
                # 创建管理员账号
                cur.execute(
                    "INSERT INTO user (username, password_hash, role, status, nickname) VALUES (%s, %s, 'admin', 'active', %s)",
                    (username, pwd_hash, "管理员")
                )
                conn.commit()
                print(f"[DB INFO] 已创建默认管理员账号: {username}")
            else:
                # 更新为管理员角色并重置密码
                cur.execute(
                    "UPDATE user SET role='admin', status='active', password_hash=%s WHERE username=%s",
                    (pwd_hash, username)
                )
                conn.commit()
                print(f"[DB INFO] 已确保管理员账号存在并重置密码: {username}")
        except Exception as e:
            print(f"[DB WARN] 确保管理员账号失败: {e}")
        finally:
            if cur:
                cur.close()
            conn.close()

    # ---------- 基础方法 ----------
    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        if not conn:
            return None
            
        sql = "SELECT user_id, username, password_hash, role, status FROM user WHERE username = %s"
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cur:
                cur.execute(sql, (username,))
                return cur.fetchone()
        except Exception as e:
            print(f"[DB EXEC ERROR] 查询用户失败: {e}")
            return None
        finally:
            conn.close()

    def register_user(self, username: str, password: str, phone: str = None, nickname: str = None) -> Tuple[bool, str, Optional[int], Optional[int]]:
        """实现注册逻辑：新增用户，密码MD5加密
        
        Args:
            username: 用户名（必填）
            password: 密码（必填，会MD5加密）
            phone: 电话（可选）
            nickname: 昵称（可选，默认'新用户'）
        
        Returns:
            (success: bool, message: str, user_id: int or None, error_code: int or None)
            success=True时: user_id为注册成功的用户ID，error_code为None
            success=False时: user_id为None，error_code为错误码（401=用户名已存在, 500=服务器内部错误）
        """
        
        # 1. 检查连接
        conn = self._get_conn()
        if not conn:
            return False, "服务器数据库连接失败，请联系管理员", None, 500
            
        # 2. 校验唯一性 - 如果用户名已存在，返回401错误码
        if self.get_user_by_username(username):
             return False, "该用户名已被使用，不可重复注册，请更换其他用户名", None, 401

        # 3. 密码加密
        password_hash = self._md5(password)
        
        # 4. 设置默认值
        if nickname is None:
            nickname = "新用户"
        
        # 5. 插入数据库（phone 可以为 NULL）
        sql = "INSERT INTO user (username, password_hash, phone, nickname) VALUES (%s, %s, %s, %s)"
        cur = None
        try:
            cur = conn.cursor()
            print(f"[DB DEBUG] 准备插入用户: username={username}, nickname={nickname}, phone={phone}")
            affected_rows = cur.execute(sql, (username, password_hash, phone, nickname))
            print(f"[DB DEBUG] SQL执行完成，影响行数: {affected_rows}")
            # 确保提交（虽然 autocommit=True，但显式提交更安全）
            conn.commit()
            user_id = cur.lastrowid
            print(f"[DB DEBUG] 用户注册成功: {username}, user_id={user_id}")
            return True, "注册成功", user_id, None
        except pymysql.IntegrityError as e:
            # 捕获唯一性约束异常（并发注册或检查遗漏的情况）
            try:
                conn.rollback()
            except:
                pass
            error_code, error_msg = e.args if len(e.args) >= 2 else (e.args[0] if e.args else None, str(e))
            if error_code == 1062:  # Duplicate entry - 用户名重复
                print(f"[DB EXEC ERROR] 用户名重复: {username}, 错误: {error_msg}")
                return False, "该用户名已被使用，不可重复注册，请更换其他用户名", None, 401
            else:
                print(f"[DB EXEC ERROR] 数据库完整性错误: {e}, 错误码: {error_code}")
                return False, f"注册失败: 数据完整性错误", None, 500
        except Exception as e:
            print(f"[DB EXEC ERROR] 注册 SQL 失败: {e}")
            import traceback
            print(f"[DB EXEC ERROR] 详细错误信息: {traceback.format_exc()}")
            # 发生错误时回滚
            try:
                conn.rollback()
            except:
                pass
            return False, f"注册失败: {str(e)}", None, 500
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
            
    def validate_login(self, username: str, password: str) -> Tuple[bool, str, Optional[Dict[str, Any]], Optional[int]]:
        """校验用户名和密码
        
        Returns:
            (success: bool, message: str, user_info: dict or None, error_code: int or None)
            error_code: 401=用户名或密码错误, 403=账号被封禁
        """
        user = self.get_user_by_username(username)
        if not user:
            return False, "用户名或密码错误", None, 401

        if user["status"] != "active":
            return False, "账号已被封禁，请联系管理员", None, 403

        if user["password_hash"] != self._md5(password):
            return False, "用户名或密码错误", None, 401

        return True, "登录成功", {"user_id": user["user_id"], "role": user["role"], "username": user["username"]}, None
    
    # ... (其他方法省略，保持不变)
    def list_users(self) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        if not conn: return []
        
        sql = "SELECT user_id, username, role, status, created_at FROM user ORDER BY user_id DESC"
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cur:
                cur.execute(sql)
                return cur.fetchall()
        except Exception as e:
            print(f"[DB EXEC ERROR] 查询用户列表失败: {e}")
            return []
        finally:
            conn.close()
            
    def update_user_status(self, user_id: int, status: str) -> Tuple[bool, str]:
        conn = self._get_conn()
        if not conn: return False, "服务器数据库连接失败"
        
        if user_id is None or status not in ("active", "blocked"):
            return False, "参数错误"

        sql = "UPDATE user SET status=%s WHERE user_id=%s"
        try:
            with conn.cursor() as cur:
                affected_rows = cur.execute(sql, (status, user_id))
            if affected_rows == 0:
                return False, "未找到该用户ID"
            return True, f"用户ID {user_id} 状态更新为 {status} 成功"
        except Exception as e:
            print(f"[DB EXEC ERROR] 更新用户状态失败: {e}")
            return False, f"更新失败: {str(e)}"
        finally:
            conn.close()
    
    def update_user_nickname(self, username: str, nickname: str) -> Tuple[bool, str]:
        """更新用户昵称
        
        Args:
            username: 用户名（用于标识要修改的用户）
            nickname: 新昵称
        
        Returns:
            (success: bool, message: str)
        """
        conn = self._get_conn()
        if not conn:
            return False, "服务器数据库连接失败，请联系管理员"
        
        if not username or not nickname:
            return False, "缺少用户名或昵称"
        
        # 检查用户是否存在
        user = self.get_user_by_username(username)
        if not user:
            return False, "用户不存在"
        
        sql = "UPDATE user SET nickname=%s WHERE username=%s"
        cur = None
        try:
            cur = conn.cursor()
            print(f"[DB DEBUG] 准备更新用户昵称: username={username}, new_nickname={nickname}")
            affected_rows = cur.execute(sql, (nickname, username))
            print(f"[DB DEBUG] SQL执行完成，影响行数: {affected_rows}")
            conn.commit()
            
            if affected_rows == 0:
                print(f"[DB DEBUG] 未找到用户: {username}")
                return False, "未找到该用户"
            
            print(f"[DB DEBUG] 用户昵称更新成功: username={username}, nickname={nickname}")
            return True, "昵称修改成功"
        except Exception as e:
            print(f"[DB EXEC ERROR] 更新用户昵称失败: {e}")
            import traceback
            print(f"[DB EXEC ERROR] 详细错误信息: {traceback.format_exc()}")
            try:
                conn.rollback()
            except:
                pass
            return False, f"更新失败: {str(e)}"
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

    # ---------- 商品相关方法 ----------
    def add_goods(self, user_id: int, title: str, description: str, category: str,
                  price: float, brand: str = None, original_price: float = None,
                  purchase_time: str = None, stock_quantity: int = 1,
                  img_path: str = None) -> Tuple[bool, str, Optional[int]]:
        """添加商品（发布商品，状态置为 pending_review）"""
        conn = self._get_conn()
        if not conn:
            return False, "服务器数据库连接失败，请联系管理员", None

        sql = """INSERT INTO goods (user_id, title, description, category, price, brand,
                 original_price, purchase_time, stock_quantity, img_path, status)
                 VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending_review')"""

        cur = None
        try:
            cur = conn.cursor()
            print(f"[DB DEBUG] 准备添加商品: user_id={user_id}, title={title}, category={category}")
            cur.execute(sql, (user_id, title, description, category, price, brand,
                              original_price, purchase_time, stock_quantity, img_path))
            goods_id = cur.lastrowid
            conn.commit()
            print(f"[DB DEBUG] 商品添加成功: goods_id={goods_id}")
            return True, "商品发布成功，等待审核", goods_id
        except Exception as e:
            print(f"[DB EXEC ERROR] 添加商品失败: {e}")
            import traceback
            print(f"[DB EXEC ERROR] 详细错误信息: {traceback.format_exc()}")
            try:
                conn.rollback()
            except:
                pass
            return False, f"商品发布失败: {str(e)}", None
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

    def get_goods_list(self, category: str = None, page: int = 1, page_size: int = 20,
                       status: str = None) -> Tuple[bool, str, List[Dict[str, Any]], int]:
        """获取商品列表（分页查询）"""
        conn = self._get_conn()
        if not conn:
            return False, "服务器数据库连接失败", [], 0

        conditions = []
        params = []
        if category:
            conditions.append("category = %s")
            params.append(category)
        if status:
            conditions.append("status = %s")
            params.append(status)
        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

        count_sql = f"SELECT COUNT(*) as total FROM goods {where_clause}"
        offset = (page - 1) * page_size
        list_sql = f"""SELECT g.goods_id, g.user_id, g.title, g.description, g.category,
                       g.brand, g.price, g.original_price, g.purchase_time,
                       g.stock_quantity, g.sold_count, g.img_path, g.status, g.create_time,
                       (SELECT img_path FROM goods_images WHERE goods_id = g.goods_id
                        AND is_primary = 1 ORDER BY display_order LIMIT 1) as primary_image
                       FROM goods g {where_clause}
                       ORDER BY g.create_time DESC LIMIT %s OFFSET %s"""

        cur = None
        try:
            cur = conn.cursor(pymysql.cursors.DictCursor)
            cur.execute(count_sql, params)
            total_result = cur.fetchone()
            total_count = total_result['total'] if total_result else 0

            list_params = params + [page_size, offset]
            cur.execute(list_sql, list_params)
            goods_list = cur.fetchall()

            for goods in goods_list:
                goods_id = goods['goods_id']
                images_sql = """SELECT img_path, display_order, is_primary
                                FROM goods_images
                                WHERE goods_id = %s
                                ORDER BY display_order ASC"""
                cur.execute(images_sql, (goods_id,))
                goods['images'] = cur.fetchall()

            print(f"[DB DEBUG] 查询商品列表成功: category={category}, page={page}, 返回{len(goods_list)}条")
            return True, "查询成功", goods_list, total_count
        except Exception as e:
            print(f"[DB EXEC ERROR] 查询商品列表失败: {e}")
            import traceback
            print(f"[DB EXEC ERROR] 详细错误信息: {traceback.format_exc()}")
            return False, f"查询失败: {str(e)}", [], 0
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

    def audit_goods(self, goods_id: int, status: str, admin_user_id: int = None) -> Tuple[bool, str]:
        """审核商品（管理员操作）"""
        if status not in ('on_sale', 'rejected'):
            return False, "无效的状态值，只能设置为 'on_sale'（在售）或 'rejected'（驳回）"

        conn = self._get_conn()
        if not conn:
            return False, "服务器数据库连接失败"

        sql = "UPDATE goods SET status = %s WHERE goods_id = %s"
        cur = None
        try:
            cur = conn.cursor()
            print(f"[DB DEBUG] 准备审核商品: goods_id={goods_id}, status={status}")
            affected_rows = cur.execute(sql, (status, goods_id))
            conn.commit()

            if affected_rows == 0:
                return False, "商品不存在"

            print(f"[DB DEBUG] 商品审核成功: goods_id={goods_id}, status={status}")
            status_msg = "已通过审核，商品已上架" if status == 'on_sale' else "审核未通过，商品已驳回"
            return True, status_msg
        except Exception as e:
            print(f"[DB EXEC ERROR] 审核商品失败: {e}")
            import traceback
            print(f"[DB EXEC ERROR] 详细错误信息: {traceback.format_exc()}")
            try:
                conn.rollback()
            except:
                pass
            return False, f"审核失败: {str(e)}"
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

    def add_goods_image(self, goods_id: int, img_path: str, display_order: int = 0,
                        is_primary: int = 0) -> Tuple[bool, str]:
        """添加商品图片到 goods_images 表"""
        conn = self._get_conn()
        if not conn:
            return False, "服务器数据库连接失败"

        sql = """INSERT INTO goods_images (goods_id, img_path, display_order, is_primary)
                 VALUES (%s, %s, %s, %s)"""
        cur = None
        try:
            cur = conn.cursor()
            cur.execute(sql, (goods_id, img_path, display_order, is_primary))
            conn.commit()
            print(f"[DB DEBUG] 商品图片添加成功: goods_id={goods_id}, img_path={img_path}")
            return True, "图片添加成功"
        except Exception as e:
            print(f"[DB EXEC ERROR] 添加商品图片失败: {e}")
            try:
                conn.rollback()
            except:
                pass
            return False, f"添加图片失败: {str(e)}"
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

    # ---------- 订单与收藏相关方法 ----------
    def _generate_order_no(self) -> str:
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        suffix = f"{random.randint(0, 9999):04d}"
        return f"ORD{timestamp}{suffix}"

    def get_goods_by_id(self, goods_id: int) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        if not conn:
            return None
        sql = """SELECT goods_id, user_id, title, price, status, stock_quantity
                 FROM goods WHERE goods_id=%s"""
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cur:
                cur.execute(sql, (goods_id,))
                return cur.fetchone()
        except Exception as e:
            print(f"[DB EXEC ERROR] 查询商品失败: {e}")
            return None
        finally:
            conn.close()

    def add_order(self, buyer_id: int, goods_id: int, quantity: int = 1) -> Tuple[bool, str, Optional[int], Optional[str]]:
        """下单：校验商品在售，创建订单（待付款），并将商品置为已售出"""
        conn = self._get_conn()
        if not conn:
            return False, "服务器数据库连接失败", None, None

        cur = None
        try:
            conn.autocommit(False)
            cur = conn.cursor(pymysql.cursors.DictCursor)

            # 查询商品并锁定（包含库存信息）
            cur.execute("SELECT goods_id, user_id, price, status, stock_quantity, sold_count FROM goods WHERE goods_id=%s FOR UPDATE", (goods_id,))
            goods = cur.fetchone()
            if not goods:
                conn.rollback()
                return False, "商品不存在", None, None
            if goods["status"] != "on_sale":
                conn.rollback()
                return False, "商品不可下单（非在售状态）", None, None
            
            # 检查库存是否充足
            current_stock = goods["stock_quantity"]
            if current_stock < quantity:
                conn.rollback()
                return False, f"库存不足，当前库存：{current_stock}，需要：{quantity}", None, None

            seller_id = goods["user_id"]
            price = goods["price"]
            total_price = float(price) * int(quantity)
            order_no = self._generate_order_no()

            # 创建订单
            cur.execute(
                "INSERT INTO `order` (order_no, buyer_id, seller_id, goods_id, quantity, total_price, status) "
                "VALUES (%s, %s, %s, %s, %s, %s, 'pending_payment')",
                (order_no, buyer_id, seller_id, goods_id, quantity, total_price)
            )
            order_id = cur.lastrowid

            # 更新商品：状态改为已售出，减少库存，增加已售数量
            new_stock = current_stock - quantity
            new_sold_count = goods["sold_count"] + quantity
            
            # 如果库存为0，状态改为sold；如果还有库存，保持on_sale（允许继续销售）
            new_status = 'sold' if new_stock == 0 else 'on_sale'
            
            cur.execute(
                "UPDATE goods SET status=%s, stock_quantity=%s, sold_count=%s WHERE goods_id=%s",
                (new_status, new_stock, new_sold_count, goods_id)
            )

            conn.commit()
            print(f"[DB DEBUG] 订单创建成功: order_id={order_id}, order_no={order_no}")
            return True, "下单成功，待付款", order_id, order_no
        except Exception as e:
            print(f"[DB EXEC ERROR] 创建订单失败: {e}")
            import traceback
            print(f"[DB EXEC ERROR] 详细错误信息: {traceback.format_exc()}")
            try:
                conn.rollback()
            except:
                pass
            return False, f"下单失败: {str(e)}", None, None
        finally:
            if cur:
                cur.close()
            try:
                conn.autocommit(True)
            except:
                pass
            if conn:
                conn.close()

    def update_order_status(self, order_id: int, new_status: str) -> Tuple[bool, str]:
        """按流程更新订单状态：pending_payment→pending_shipment→pending_receipt→completed
        注意：订单取消时需要恢复商品库存
        """
        allowed = {
            "pending_payment": "pending_shipment",
            "pending_shipment": "pending_receipt",
            "pending_receipt": "completed",
        }

        conn = self._get_conn()
        if not conn:
            return False, "服务器数据库连接失败"

        cur = None
        try:
            conn.autocommit(False)
            cur = conn.cursor(pymysql.cursors.DictCursor)
            
            # 查询订单信息（包含商品ID和数量）
            cur.execute("SELECT status, goods_id, quantity FROM `order` WHERE order_id=%s FOR UPDATE", (order_id,))
            row = cur.fetchone()
            if not row:
                conn.rollback()
                return False, "订单不存在"

            current_status = row["status"]
            
            # 处理订单取消：恢复商品库存
            if new_status == "canceled" and current_status != "canceled":
                goods_id = row["goods_id"]
                quantity = row["quantity"]
                
                # 恢复商品库存和状态
                cur.execute("SELECT stock_quantity, sold_count, status FROM goods WHERE goods_id=%s FOR UPDATE", (goods_id,))
                goods = cur.fetchone()
                if goods:
                    new_stock = goods["stock_quantity"] + quantity
                    new_sold_count = max(0, goods["sold_count"] - quantity)
                    # 如果商品状态是sold且恢复库存后>0，改回on_sale
                    new_goods_status = 'on_sale' if (goods["status"] == 'sold' and new_stock > 0) else goods["status"]
                    
                    cur.execute(
                        "UPDATE goods SET stock_quantity=%s, sold_count=%s, status=%s WHERE goods_id=%s",
                        (new_stock, new_sold_count, new_goods_status, goods_id)
                    )
                    print(f"[DB DEBUG] 订单取消，恢复商品库存: goods_id={goods_id}, 恢复数量={quantity}")
            
            # 检查状态流转是否合法
            elif new_status != "canceled":
                expected_next = allowed.get(current_status)
                if expected_next != new_status:
                    conn.rollback()
                    return False, f"非法的状态流转，当前状态 {current_status} 无法变更为 {new_status}"

            # 更新订单状态
            cur.execute("UPDATE `order` SET status=%s WHERE order_id=%s", (new_status, order_id))
            conn.commit()
            print(f"[DB DEBUG] 订单状态更新成功: order_id={order_id}, {current_status} -> {new_status}")
            return True, "订单状态更新成功"
        except Exception as e:
            print(f"[DB EXEC ERROR] 更新订单状态失败: {e}")
            import traceback
            print(f"[DB EXEC ERROR] 详细错误信息: {traceback.format_exc()}")
            try:
                conn.rollback()
            except:
                pass
            return False, f"订单状态更新失败: {str(e)}"
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

    def get_orders(self, buyer_id: int, status: str = None) -> Tuple[bool, str, List[Dict[str, Any]]]:
        """按买家ID和可选状态查询订单"""
        conn = self._get_conn()
        if not conn:
            return False, "服务器数据库连接失败", []

        conditions = ["o.buyer_id = %s"]
        params = [buyer_id]
        if status:
            conditions.append("o.status = %s")
            params.append(status)
        where_clause = "WHERE " + " AND ".join(conditions)

        sql = f"""SELECT o.order_id, o.order_no, o.buyer_id, o.seller_id, o.goods_id,
                         o.quantity, o.total_price, o.status, o.created_at, o.updated_at,
                         g.title, g.img_path,
                         (SELECT img_path FROM goods_images WHERE goods_id=g.goods_id AND is_primary=1
                          ORDER BY display_order LIMIT 1) as primary_image
                  FROM `order` o
                  JOIN goods g ON o.goods_id = g.goods_id
                  {where_clause}
                  ORDER BY o.created_at DESC"""

        cur = None
        try:
            cur = conn.cursor(pymysql.cursors.DictCursor)
            cur.execute(sql, params)
            rows = cur.fetchall()
            return True, "查询成功", rows
        except Exception as e:
            print(f"[DB EXEC ERROR] 查询订单失败: {e}")
            import traceback
            print(f"[DB EXEC ERROR] 详细错误信息: {traceback.format_exc()}")
            return False, f"查询订单失败: {str(e)}", []
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

    # ---------- 统计分析相关方法（用于 DATA_STAT） ----------
    def stat_category_goods(self) -> Tuple[bool, str, List[Dict[str, Any]]]:
        """统计各分类商品数量（总数 + 在售数）"""
        conn = self._get_conn()
        if not conn:
            return False, "服务器数据库连接失败", []

        sql = """
            SELECT
              category,
              SUM(CASE WHEN status = 'on_sale' THEN 1 ELSE 0 END) AS on_sale_count,
              COUNT(*) AS total_count
            FROM goods
            GROUP BY category
            ORDER BY total_count DESC
        """
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cur:
                cur.execute(sql)
                rows = cur.fetchall()
                return True, "查询成功", rows
        except Exception as e:
            print(f"[DB EXEC ERROR] 分类商品统计失败: {e}")
            import traceback
            print(f"[DB EXEC ERROR] 详细错误信息: {traceback.format_exc()}")
            return False, f"查询失败: {str(e)}", []
        finally:
            conn.close()

    def stat_user_order_status(self, buyer_id: int) -> Tuple[bool, str, List[Dict[str, Any]]]:
        """统计某个用户的订单状态分布"""
        conn = self._get_conn()
        if not conn:
            return False, "服务器数据库连接失败", []

        sql = """
            SELECT status, COUNT(*) AS cnt
            FROM `order`
            WHERE buyer_id = %s
            GROUP BY status
        """
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cur:
                cur.execute(sql, (buyer_id,))
                rows = cur.fetchall()
                return True, "查询成功", rows
        except Exception as e:
            print(f"[DB EXEC ERROR] 用户订单状态统计失败: {e}")
            import traceback
            print(f"[DB EXEC ERROR] 详细错误信息: {traceback.format_exc()}")
            return False, f"查询失败: {str(e)}", []
        finally:
            conn.close()

    def stat_last_n_days_orders(self, days: int = 7) -> Tuple[bool, str, List[Dict[str, Any]]]:
        """
        统计最近 N 天下单数和成交数（按天）
        返回列表：[{date: 'YYYY-MM-DD', orders: x, completed: y}, ...]
        """
        conn = self._get_conn()
        if not conn:
            return False, "服务器数据库连接失败", []

        # 下单数（按 created_at）
        orders_sql = """
            SELECT DATE(created_at) AS dt, COUNT(*) AS orders
            FROM `order`
            WHERE created_at >= CURDATE() - INTERVAL %s DAY
            GROUP BY DATE(created_at)
        """
        # 成交数（按 completed_at）
        completed_sql = """
            SELECT DATE(completed_at) AS dt, COUNT(*) AS completed
            FROM `order`
            WHERE status = 'completed'
              AND completed_at IS NOT NULL
              AND completed_at >= CURDATE() - INTERVAL %s DAY
            GROUP BY DATE(completed_at)
        """
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cur:
                cur.execute(orders_sql, (days - 1,))
                orders_rows = cur.fetchall()
                cur.execute(completed_sql, (days - 1,))
                completed_rows = cur.fetchall()

            # 转成字典方便 merge
            orders_map = {row["dt"].strftime("%Y-%m-%d"): row["orders"] for row in orders_rows}
            completed_map = {
                row["dt"].strftime("%Y-%m-%d"): row["completed"] for row in completed_rows
            }

            result: List[Dict[str, Any]] = []
            today = datetime.now().date()
            for i in range(days - 1, -1, -1):
                day = today - timedelta(days=i)
                key = day.strftime("%Y-%m-%d")
                result.append(
                    {
                        "date": key,
                        "orders": int(orders_map.get(key, 0)),
                        "completed": int(completed_map.get(key, 0)),
                    }
                )

            return True, "查询成功", result
        except Exception as e:
            print(f"[DB EXEC ERROR] 最近N天下单/成交统计失败: {e}")
            import traceback
            print(f"[DB EXEC ERROR] 详细错误信息: {traceback.format_exc()}")
            return False, f"查询失败: {str(e)}", []
        finally:
            conn.close()

    def stat_hot_categories_top5(self, days: int = 30) -> Tuple[bool, str, List[Dict[str, Any]]]:
        """按成交量统计热门分类 TOP5（最近 days 天）"""
        conn = self._get_conn()
        if not conn:
            return False, "服务器数据库连接失败", []

        sql = """
            SELECT
              g.category,
              COUNT(*) AS completed_orders
            FROM `order` o
            JOIN goods g ON o.goods_id = g.goods_id
            WHERE o.status = 'completed'
              AND o.completed_at IS NOT NULL
              AND o.completed_at >= CURDATE() - INTERVAL %s DAY
            GROUP BY g.category
            ORDER BY completed_orders DESC
            LIMIT 5
        """
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cur:
                cur.execute(sql, (days,))
                rows = cur.fetchall()
                return True, "查询成功", rows
        except Exception as e:
            print(f"[DB EXEC ERROR] 热门分类统计失败: {e}")
            import traceback
            print(f"[DB EXEC ERROR] 详细错误信息: {traceback.format_exc()}")
            return False, f"查询失败: {str(e)}", []
        finally:
            conn.close()

    def stat_user_favorite_categories(self, buyer_id: int) -> Tuple[bool, str, List[Dict[str, Any]]]:
        """按已完成订单统计用户的偏好分类（购买次数）"""
        conn = self._get_conn()
        if not conn:
            return False, "服务器数据库连接失败", []

        sql = """
            SELECT
              g.category,
              COUNT(*) AS buy_count
            FROM `order` o
            JOIN goods g ON o.goods_id = g.goods_id
            WHERE o.buyer_id = %s
              AND o.status = 'completed'
            GROUP BY g.category
            ORDER BY buy_count DESC
        """
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cur:
                cur.execute(sql, (buyer_id,))
                rows = cur.fetchall()
                return True, "查询成功", rows
        except Exception as e:
            print(f"[DB EXEC ERROR] 用户偏好分类统计失败: {e}")
            import traceback
            print(f"[DB EXEC ERROR] 详细错误信息: {traceback.format_exc()}")
            return False, f"查询失败: {str(e)}", []
        finally:
            conn.close()

    def stat_last_n_days_completed(self, days: int = 7) -> Tuple[bool, str, List[Dict[str, Any]]]:
        """
        统计最近 N 天每天的成交数量，用于移动平均 / 预测
        返回：[{date: 'YYYY-MM-DD', completed: x}, ...]
        """
        conn = self._get_conn()
        if not conn:
            return False, "服务器数据库连接失败", []

        sql = """
            SELECT DATE(completed_at) AS dt, COUNT(*) AS completed
            FROM `order`
            WHERE status = 'completed'
              AND completed_at IS NOT NULL
              AND completed_at >= CURDATE() - INTERVAL %s DAY
            GROUP BY DATE(completed_at)
        """
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cur:
                cur.execute(sql, (days - 1,))
                rows = cur.fetchall()

            completed_map = {row["dt"].strftime("%Y-%m-%d"): row["completed"] for row in rows}
            result: List[Dict[str, Any]] = []
            today = datetime.now().date()
            for i in range(days - 1, -1, -1):
                day = today - timedelta(days=i)
                key = day.strftime("%Y-%m-%d")
                result.append({"date": key, "completed": int(completed_map.get(key, 0))})

            return True, "查询成功", result
        except Exception as e:
            print(f"[DB EXEC ERROR] 最近N天成交统计失败: {e}")
            import traceback
            print(f"[DB EXEC ERROR] 详细错误信息: {traceback.format_exc()}")
            return False, f"查询失败: {str(e)}", []
        finally:
            conn.close()

    # ---------- 收藏相关 ----------
    def add_collect(self, user_id: int, goods_id: int) -> Tuple[bool, str]:
        conn = self._get_conn()
        if not conn:
            return False, "服务器数据库连接失败"

        sql = "INSERT INTO collect (user_id, goods_id) VALUES (%s, %s)"
        cur = None
        try:
            cur = conn.cursor()
            cur.execute(sql, (user_id, goods_id))
            conn.commit()
            return True, "收藏成功"
        except pymysql.IntegrityError as e:
            # 1062 重复收藏
            if e.args and e.args[0] == 1062:
                return False, "已收藏该商品"
            return False, f"收藏失败: {e}"
        except Exception as e:
            print(f"[DB EXEC ERROR] 收藏失败: {e}")
            try:
                conn.rollback()
            except:
                pass
            return False, f"收藏失败: {str(e)}"
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

    def get_collects(self, user_id: int) -> Tuple[bool, str, List[Dict[str, Any]]]:
        conn = self._get_conn()
        if not conn:
            return False, "服务器数据库连接失败", []

        sql = """SELECT c.collect_id, c.goods_id, c.collected_at,
                        g.title, g.price, g.status, g.img_path,
                        (SELECT img_path FROM goods_images WHERE goods_id=g.goods_id AND is_primary=1
                         ORDER BY display_order LIMIT 1) as primary_image
                 FROM collect c
                 JOIN goods g ON c.goods_id = g.goods_id
                 WHERE c.user_id = %s
                 ORDER BY c.collected_at DESC"""
        cur = None
        try:
            cur = conn.cursor(pymysql.cursors.DictCursor)
            cur.execute(sql, (user_id,))
            rows = cur.fetchall()
            return True, "查询成功", rows
        except Exception as e:
            print(f"[DB EXEC ERROR] 查询收藏失败: {e}")
            import traceback
            print(f"[DB EXEC ERROR] 详细错误信息: {traceback.format_exc()}")
            return False, f"查询收藏失败: {str(e)}", []
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

    def del_collect(self, user_id: int, goods_id: int) -> Tuple[bool, str]:
        conn = self._get_conn()
        if not conn:
            return False, "服务器数据库连接失败"

        sql = "DELETE FROM collect WHERE user_id=%s AND goods_id=%s"
        cur = None
        try:
            cur = conn.cursor()
            cur.execute(sql, (user_id, goods_id))
            conn.commit()
            if cur.rowcount == 0:
                return False, "未找到收藏记录"
            return True, "取消收藏成功"
        except Exception as e:
            print(f"[DB EXEC ERROR] 取消收藏失败: {e}")
            try:
                conn.rollback()
            except:
                pass
            return False, f"取消收藏失败: {str(e)}"
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
    
    # ---------- 商品相关方法 ----------
    def add_goods(self, user_id: int, title: str, description: str, category: str, 
                   price: float, brand: str = None, original_price: float = None,
                   purchase_time: str = None, stock_quantity: int = 1, 
                   img_path: str = None) -> Tuple[bool, str, Optional[int]]:
        """添加商品（发布商品）
        
        Args:
            user_id: 发布者用户ID
            title: 商品标题
            description: 商品描述
            category: 商品分类
            price: 商品价格（现价）
            brand: 商品品牌（可选）
            original_price: 商品原价（可选）
            purchase_time: 购买时间（可选，格式：YYYY-MM-DD）
            stock_quantity: 库存量（默认1）
            img_path: 商品主图路径（可选）
        
        Returns:
            (success: bool, message: str, goods_id: int or None)
        """
        conn = self._get_conn()
        if not conn:
            return False, "服务器数据库连接失败，请联系管理员", None
        
        sql = """INSERT INTO goods (user_id, title, description, category, price, brand, 
                 original_price, purchase_time, stock_quantity, img_path, status) 
                 VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending_review')"""
        
        cur = None
        try:
            cur = conn.cursor()
            print(f"[DB DEBUG] 准备添加商品: user_id={user_id}, title={title}, category={category}")
            cur.execute(sql, (user_id, title, description, category, price, brand, 
                            original_price, purchase_time, stock_quantity, img_path))
            goods_id = cur.lastrowid
            conn.commit()
            print(f"[DB DEBUG] 商品添加成功: goods_id={goods_id}")
            return True, "商品发布成功，等待审核", goods_id
        except Exception as e:
            print(f"[DB EXEC ERROR] 添加商品失败: {e}")
            import traceback
            print(f"[DB EXEC ERROR] 详细错误信息: {traceback.format_exc()}")
            try:
                conn.rollback()
            except:
                pass
            return False, f"商品发布失败: {str(e)}", None
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
    
    def get_goods_list(self, category: str = None, page: int = 1, page_size: int = 20, 
                       status: str = None) -> Tuple[bool, str, List[Dict[str, Any]], int]:
        """获取商品列表（分页查询）
        
        Args:
            category: 商品分类（可选，None表示查询所有分类）
            page: 页码（从1开始）
            page_size: 每页数量（默认20）
            status: 商品状态（可选，None表示查询所有状态）
        
        Returns:
            (success: bool, message: str, goods_list: List[Dict], total_count: int)
        """
        conn = self._get_conn()
        if not conn:
            return False, "服务器数据库连接失败", [], 0
        
        # 构建查询条件
        conditions = []
        params = []
        
        if category:
            conditions.append("category = %s")
            params.append(category)
        
        if status:
            conditions.append("status = %s")
            params.append(status)
        
        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        
        # 查询总数
        count_sql = f"SELECT COUNT(*) as total FROM goods {where_clause}"
        
        # 查询商品列表（包含图片路径）
        offset = (page - 1) * page_size
        list_sql = f"""SELECT g.goods_id, g.user_id, g.title, g.description, g.category, 
                       g.brand, g.price, g.original_price, g.purchase_time, 
                       g.stock_quantity, g.sold_count, g.img_path, g.status, g.create_time,
                       (SELECT img_path FROM goods_images WHERE goods_id = g.goods_id 
                        AND is_primary = 1 ORDER BY display_order LIMIT 1) as primary_image
                       FROM goods g {where_clause} 
                       ORDER BY g.create_time DESC LIMIT %s OFFSET %s"""
        
        cur = None
        try:
            cur = conn.cursor(pymysql.cursors.DictCursor)
            
            # 查询总数
            cur.execute(count_sql, params)
            total_result = cur.fetchone()
            total_count = total_result['total'] if total_result else 0
            
            # 查询商品列表
            list_params = params + [page_size, offset]
            cur.execute(list_sql, list_params)
            goods_list = cur.fetchall()
            
            # 为每个商品查询所有图片
            for goods in goods_list:
                goods_id = goods['goods_id']
                images_sql = """SELECT img_path, display_order, is_primary 
                               FROM goods_images 
                               WHERE goods_id = %s 
                               ORDER BY display_order ASC"""
                cur.execute(images_sql, (goods_id,))
                goods['images'] = cur.fetchall()
            
            print(f"[DB DEBUG] 查询商品列表成功: category={category}, page={page}, 返回{len(goods_list)}条")
            return True, "查询成功", goods_list, total_count
        except Exception as e:
            print(f"[DB EXEC ERROR] 查询商品列表失败: {e}")
            import traceback
            print(f"[DB EXEC ERROR] 详细错误信息: {traceback.format_exc()}")
            return False, f"查询失败: {str(e)}", [], 0
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
    
    def audit_goods(self, goods_id: int, status: str, admin_user_id: int = None) -> Tuple[bool, str]:
        """审核商品（管理员操作）
        
        Args:
            goods_id: 商品ID
            status: 新状态（'on_sale'=在售, 'rejected'=驳回）
            admin_user_id: 管理员用户ID（可选，用于日志）
        
        Returns:
            (success: bool, message: str)
        """
        if status not in ('on_sale', 'rejected'):
            return False, "无效的状态值，只能设置为 'on_sale'（在售）或 'rejected'（驳回）"
        
        conn = self._get_conn()
        if not conn:
            return False, "服务器数据库连接失败"
        
        sql = "UPDATE goods SET status = %s WHERE goods_id = %s"
        cur = None
        try:
            cur = conn.cursor()
            print(f"[DB DEBUG] 准备审核商品: goods_id={goods_id}, status={status}")
            affected_rows = cur.execute(sql, (status, goods_id))
            conn.commit()
            
            if affected_rows == 0:
                return False, "商品不存在"
            
            print(f"[DB DEBUG] 商品审核成功: goods_id={goods_id}, status={status}")
            status_msg = "已通过审核，商品已上架" if status == 'on_sale' else "审核未通过，商品已驳回"
            return True, status_msg
        except Exception as e:
            print(f"[DB EXEC ERROR] 审核商品失败: {e}")
            import traceback
            print(f"[DB EXEC ERROR] 详细错误信息: {traceback.format_exc()}")
            try:
                conn.rollback()
            except:
                pass
            return False, f"审核失败: {str(e)}"
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
    
    def add_goods_image(self, goods_id: int, img_path: str, display_order: int = 0, 
                        is_primary: int = 0) -> Tuple[bool, str]:
        """添加商品图片到 goods_images 表
        
        Args:
            goods_id: 商品ID
            img_path: 图片路径
            display_order: 显示顺序（默认0）
            is_primary: 是否为主图（1=是，0=否）
        
        Returns:
            (success: bool, message: str)
        """
        conn = self._get_conn()
        if not conn:
            return False, "服务器数据库连接失败"
        
        sql = """INSERT INTO goods_images (goods_id, img_path, display_order, is_primary) 
                 VALUES (%s, %s, %s, %s)"""
        cur = None
        try:
            cur = conn.cursor()
            cur.execute(sql, (goods_id, img_path, display_order, is_primary))
            conn.commit()
            print(f"[DB DEBUG] 商品图片添加成功: goods_id={goods_id}, img_path={img_path}")
            return True, "图片添加成功"
        except Exception as e:
            print(f"[DB EXEC ERROR] 添加商品图片失败: {e}")
            try:
                conn.rollback()
            except:
                pass
            return False, f"添加图片失败: {str(e)}"
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
    
    # ---------- 聊天相关方法 ----------
    def send_chat_message(self, sender_id: int, receiver_id: int, content: str) -> Tuple[bool, str, Optional[int]]:
        """发送聊天消息
        
        Args:
            sender_id: 发送者用户ID
            receiver_id: 接收者用户ID
            content: 消息内容
        
        Returns:
            (success: bool, message: str, message_id: int or None)
        """
        conn = self._get_conn()
        if not conn:
            return False, "服务器数据库连接失败，请联系管理员", None
        
        if not content or not content.strip():
            return False, "消息内容不能为空", None
        
        if sender_id == receiver_id:
            return False, "不能给自己发送消息", None
        
        sql = """INSERT INTO chat (sender_id, receiver_id, content) 
                 VALUES (%s, %s, %s)"""
        cur = None
        try:
            cur = conn.cursor()
            print(f"[DB DEBUG] 准备发送消息: sender_id={sender_id}, receiver_id={receiver_id}")
            cur.execute(sql, (sender_id, receiver_id, content.strip()))
            message_id = cur.lastrowid
            conn.commit()
            print(f"[DB DEBUG] 消息发送成功: message_id={message_id}")
            return True, "消息发送成功", message_id
        except Exception as e:
            print(f"[DB EXEC ERROR] 发送消息失败: {e}")
            import traceback
            print(f"[DB EXEC ERROR] 详细错误信息: {traceback.format_exc()}")
            try:
                conn.rollback()
            except:
                pass
            return False, f"发送消息失败: {str(e)}", None
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
    
    def get_chat_message_by_id(self, message_id: int) -> Optional[Dict[str, Any]]:
        """根据消息ID获取消息详情
        
        Args:
            message_id: 消息ID
        
        Returns:
            消息字典，包含: message_id, sender_id, receiver_id, content, sent_at
        """
        conn = self._get_conn()
        if not conn:
            return None
        
        sql = """SELECT message_id, sender_id, receiver_id, content, sent_at
                 FROM chat
                 WHERE message_id = %s"""
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cur:
                cur.execute(sql, (message_id,))
                return cur.fetchone()
        except Exception as e:
            print(f"[DB EXEC ERROR] 查询消息失败: {e}")
            return None
        finally:
            conn.close()
    
    def get_chat_history(self, user_id: int, other_user_id: int, limit: int = 50, offset: int = 0) -> Tuple[bool, str, List[Dict[str, Any]]]:
        """获取聊天历史记录（两人之间的对话）
        
        Args:
            user_id: 当前用户ID
            other_user_id: 对方用户ID
            limit: 返回消息数量限制（默认50）
            offset: 偏移量（用于分页，默认0）
        
        Returns:
            (success: bool, message: str, messages: List[Dict])
            每条消息包含: message_id, sender_id, receiver_id, content, sent_at
        """
        conn = self._get_conn()
        if not conn:
            return False, "服务器数据库连接失败", []
        
        sql = """SELECT message_id, sender_id, receiver_id, content, sent_at
                 FROM chat
                 WHERE (sender_id = %s AND receiver_id = %s) 
                    OR (sender_id = %s AND receiver_id = %s)
                 ORDER BY sent_at ASC
                 LIMIT %s OFFSET %s"""
        cur = None
        try:
            cur = conn.cursor(pymysql.cursors.DictCursor)
            cur.execute(sql, (user_id, other_user_id, other_user_id, user_id, limit, offset))
            messages = cur.fetchall()
            print(f"[DB DEBUG] 查询聊天记录成功: user_id={user_id}, other_user_id={other_user_id}, 返回{len(messages)}条")
            return True, "查询成功", messages
        except Exception as e:
            print(f"[DB EXEC ERROR] 查询聊天记录失败: {e}")
            import traceback
            print(f"[DB EXEC ERROR] 详细错误信息: {traceback.format_exc()}")
            return False, f"查询失败: {str(e)}", []
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
