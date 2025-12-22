"""
数据库并发控制工具模块
提供事务管理、行锁、乐观锁等并发控制机制
防止脏读、丢失修改、不可重复读等问题
"""

import pymysql
import pymysql.cursors
from typing import Optional, Callable, Any, Tuple
from contextlib import contextmanager
import time
import threading


class ConcurrencyControl:
    """
    数据库并发控制工具类
    提供统一的事务管理、锁机制和重试策略
    """
    
    def __init__(self, db_manager):
        """
        初始化并发控制工具
        
        Args:
            db_manager: DBManager 实例
        """
        self.db_manager = db_manager
        self.lock_timeout = 5  # 锁超时时间（秒）
        self.max_retries = 3   # 最大重试次数
    
    @contextmanager
    def transaction(self, isolation_level: str = "REPEATABLE READ"):
        """
        事务上下文管理器
        
        Args:
            isolation_level: 事务隔离级别
                - READ UNCOMMITTED: 读未提交（最低，允许脏读）
                - READ COMMITTED: 读已提交（防止脏读）
                - REPEATABLE READ: 可重复读（MySQL默认，防止脏读和不可重复读）
                - SERIALIZABLE: 串行化（最高，完全隔离）
        
        Usage:
            with self.transaction() as conn:
                cur = conn.cursor()
                cur.execute("UPDATE ...")
                conn.commit()
        """
        conn = self.db_manager._get_conn()
        if not conn:
            raise Exception("数据库连接失败")
        
        original_autocommit = conn.autocommit
        original_isolation = None
        
        try:
            # 设置事务隔离级别
            if isolation_level:
                cur = conn.cursor()
                cur.execute(f"SET SESSION TRANSACTION ISOLATION LEVEL {isolation_level}")
                original_isolation = cur.fetchone()
                cur.close()
            
            # 关闭自动提交，开启事务
            conn.autocommit(False)
            yield conn
            
            # 提交事务
            conn.commit()
        except Exception as e:
            # 回滚事务
            conn.rollback()
            raise e
        finally:
            # 恢复原始设置
            try:
                conn.autocommit(original_autocommit)
                if original_isolation:
                    cur = conn.cursor()
                    cur.execute(f"SET SESSION TRANSACTION ISOLATION LEVEL {original_isolation}")
                    cur.close()
            except:
                pass
    
    def select_for_update(self, conn, table: str, where_clause: str, params: tuple, 
                         timeout: int = None) -> Optional[dict]:
        """
        使用行锁查询（SELECT ... FOR UPDATE）
        防止其他事务同时修改该行
        
        Args:
            conn: 数据库连接（必须在事务中）
            table: 表名
            where_clause: WHERE 子句（不包含 WHERE 关键字）
            params: 参数元组
            timeout: 锁超时时间（秒），None 使用默认值
        
        Returns:
            查询结果字典，如果不存在返回 None
        """
        timeout = timeout or self.lock_timeout
        
        sql = f"SELECT * FROM {table} WHERE {where_clause} FOR UPDATE"
        cur = conn.cursor(pymysql.cursors.DictCursor)
        
        try:
            # 设置锁超时
            cur.execute(f"SET innodb_lock_wait_timeout = {timeout}")
            cur.execute(sql, params)
            result = cur.fetchone()
            return result
        except pymysql.err.OperationalError as e:
            if "Lock wait timeout exceeded" in str(e):
                raise Exception(f"获取行锁超时（{timeout}秒），可能其他事务正在占用该行")
            raise e
        finally:
            cur.close()
    
    def update_with_version(self, conn, table: str, pk_field: str, pk_value: Any,
                           updates: dict, version_field: str = "version") -> Tuple[bool, str]:
        """
        使用乐观锁更新（版本号机制）
        防止丢失修改问题
        
        Args:
            conn: 数据库连接（必须在事务中）
            table: 表名
            pk_field: 主键字段名
            pk_value: 主键值
            updates: 要更新的字段字典 {field: value}
            version_field: 版本号字段名（默认 "version"）
        
        Returns:
            (success: bool, message: str)
        """
        cur = conn.cursor(pymysql.cursors.DictCursor)
        
        try:
            # 1. 查询当前版本号
            cur.execute(
                f"SELECT {version_field} FROM {table} WHERE {pk_field} = %s FOR UPDATE",
                (pk_value,)
            )
            row = cur.fetchone()
            
            if not row:
                return False, f"记录不存在: {pk_field}={pk_value}"
            
            current_version = row[version_field]
            
            # 2. 构建更新SQL（包含版本号检查）
            set_clauses = []
            update_params = []
            
            for field, value in updates.items():
                set_clauses.append(f"{field} = %s")
                update_params.append(value)
            
            # 版本号自增
            set_clauses.append(f"{version_field} = {version_field} + 1")
            
            # WHERE 条件包含版本号检查
            where_clause = f"{pk_field} = %s AND {version_field} = %s"
            update_params.extend([pk_value, current_version])
            
            sql = f"UPDATE {table} SET {', '.join(set_clauses)} WHERE {where_clause}"
            
            # 3. 执行更新
            affected_rows = cur.execute(sql, tuple(update_params))
            
            if affected_rows == 0:
                return False, "更新失败：版本号不匹配，数据已被其他事务修改"
            
            return True, "更新成功"
            
        except Exception as e:
            return False, f"更新异常: {str(e)}"
        finally:
            cur.close()
    
    def retry_on_lock_timeout(self, func: Callable, max_retries: int = None, 
                              delay: float = 0.1) -> Any:
        """
        锁超时重试装饰器
        
        Args:
            func: 要执行的函数
            max_retries: 最大重试次数，None 使用默认值
            delay: 重试延迟（秒）
        
        Returns:
            函数执行结果
        """
        max_retries = max_retries or self.max_retries
        
        for attempt in range(max_retries + 1):
            try:
                return func()
            except Exception as e:
                if "Lock wait timeout" in str(e) or "lock wait timeout" in str(e).lower():
                    if attempt < max_retries:
                        print(f"[并发控制] 锁超时，第 {attempt + 1} 次重试...")
                        time.sleep(delay * (attempt + 1))  # 指数退避
                        continue
                    else:
                        raise Exception(f"重试 {max_retries} 次后仍然失败: {str(e)}")
                else:
                    # 非锁超时错误，直接抛出
                    raise e
        
        raise Exception("重试失败")


class OptimisticLockMixin:
    """
    乐观锁混入类
    为表添加版本号字段支持
    """
    
    @staticmethod
    def add_version_field_sql(table_name: str) -> str:
        """
        生成添加版本号字段的SQL（用于数据库迁移）
        
        Args:
            table_name: 表名
        
        Returns:
            SQL 语句
        """
        return f"""
        ALTER TABLE {table_name} 
        ADD COLUMN IF NOT EXISTS version INT NOT NULL DEFAULT 1 
        COMMENT '版本号，用于乐观锁控制';
        """
    
    @staticmethod
    def init_version_field_sql(table_name: str) -> str:
        """
        初始化现有记录的版本号为1
        
        Args:
            table_name: 表名
        
        Returns:
            SQL 语句
        """
        return f"UPDATE {table_name} SET version = 1 WHERE version IS NULL OR version = 0;"


# 使用示例和最佳实践文档
"""
并发控制使用示例：

1. 使用事务和行锁（悲观锁）：
   ```python
   cc = ConcurrencyControl(db_manager)
   
   with cc.transaction(isolation_level="REPEATABLE READ") as conn:
       # 锁定商品行
       goods = cc.select_for_update(
           conn, 
           "goods", 
           "goods_id = %s", 
           (goods_id,)
       )
       
       if goods["stock_quantity"] < quantity:
           raise Exception("库存不足")
       
       # 更新库存
       cur = conn.cursor()
       cur.execute(
           "UPDATE goods SET stock_quantity = stock_quantity - %s WHERE goods_id = %s",
           (quantity, goods_id)
       )
       # 事务会自动提交
   ```

2. 使用乐观锁（版本号）：
   ```python
   cc = ConcurrencyControl(db_manager)
   
   with cc.transaction() as conn:
       success, msg = cc.update_with_version(
           conn,
           "goods",
           "goods_id",
           goods_id,
           {"stock_quantity": new_stock, "status": "sold"},
           version_field="version"
       )
       
       if not success:
           raise Exception(msg)
   ```

3. 重试机制：
   ```python
   cc = ConcurrencyControl(db_manager)
   
   def update_goods():
       with cc.transaction() as conn:
           # ... 更新操作
           pass
   
   result = cc.retry_on_lock_timeout(update_goods, max_retries=3)
   ```

最佳实践：
1. 关键业务操作（下单、库存扣减）使用悲观锁（FOR UPDATE）
2. 非关键操作（更新昵称、描述）使用乐观锁（版本号）
3. 设置合适的事务隔离级别（推荐 REPEATABLE READ）
4. 为关键表添加 version 字段支持乐观锁
5. 使用重试机制处理锁冲突
"""

