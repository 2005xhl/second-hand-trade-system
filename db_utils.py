import hashlib
import pymysql
import pymysql.cursors
from typing import Any, Dict, List, Optional, Tuple


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

    def register_user(self, username: str, password: str, phone: str = None, nickname: str = None) -> Tuple[bool, str, Optional[int]]:
        """实现注册逻辑：新增用户，密码MD5加密
        
        Args:
            username: 用户名（必填）
            password: 密码（必填，会MD5加密）
            phone: 电话（可选）
            nickname: 昵称（可选，默认'新用户'）
        
        Returns:
            (success: bool, message: str, error_code: int or None)
            error_code: 401=用户名已存在（不可重复注册）, 500=服务器内部错误
        """
        
        # 1. 检查连接
        conn = self._get_conn()
        if not conn:
            return False, "服务器数据库连接失败，请联系管理员", 500
            
        # 2. 校验唯一性 - 如果用户名已存在，返回401错误码
        if self.get_user_by_username(username):
             return False, "该用户名已被使用，不可重复注册，请更换其他用户名", 401

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
            print(f"[DB DEBUG] 用户注册成功: {username}, user_id={cur.lastrowid}")
            return True, "注册成功", None
        except pymysql.IntegrityError as e:
            # 捕获唯一性约束异常（并发注册或检查遗漏的情况）
            try:
                conn.rollback()
            except:
                pass
            error_code, error_msg = e.args if len(e.args) >= 2 else (e.args[0] if e.args else None, str(e))
            if error_code == 1062:  # Duplicate entry - 用户名重复
                print(f"[DB EXEC ERROR] 用户名重复: {username}, 错误: {error_msg}")
                return False, "该用户名已被使用，不可重复注册，请更换其他用户名", 401
            else:
                print(f"[DB EXEC ERROR] 数据库完整性错误: {e}, 错误码: {error_code}")
                return False, f"注册失败: 数据完整性错误", 500
        except Exception as e:
            print(f"[DB EXEC ERROR] 注册 SQL 失败: {e}")
            import traceback
            print(f"[DB EXEC ERROR] 详细错误信息: {traceback.format_exc()}")
            # 发生错误时回滚
            try:
                conn.rollback()
            except:
                pass
            return False, f"注册失败: {str(e)}", 500
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