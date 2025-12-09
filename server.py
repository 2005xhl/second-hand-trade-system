import socket
import threading
import json
import sys
from db_utils import DBManager

# =================配置区域=================
SERVER_IP = '10.129.106.38'  
SERVER_PORT = 8888       # 监听端口，确保不被占用
BUFFER_SIZE = 1024       # 单次 socket recv 尝试读取的大小
HEADER_SIZE = 4          # 前置 4 字节长度头

# 数据库配置
DB_HOST = "127.0.0.1"
DB_PORT = 3306
DB_USER = "root"
DB_PASSWORD = "123456"
DB_NAME = "used_goods_platform"

# 全局数据库管理器实例
db_manager = DBManager(DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME)


def recv_exact(sock: socket.socket, size: int) -> bytes:
    """循环读取指定长度，避免拆包问题"""
    chunks = []
    total = 0
    while total < size:
        part = sock.recv(size - total)
        if not part:
            break
        chunks.append(part)
        total += len(part)
    return b"".join(chunks)
# =========================================

def handle_client_request(client_socket, client_addr):
    """
    子线程函数：专门负责处理单个客户端的通信逻辑
    对应任务清单：实现多线程处理 
    """
    print(f"[连接成功] 客户端 {client_addr} 已连接...")
    
    while True:
        try:
            # 1. 先读定长头，得到正文长度
            header = recv_exact(client_socket, HEADER_SIZE)
            if not header:
                print(f"[断开连接] 客户端 {client_addr} 下线了")
                break
            body_len = int.from_bytes(header, "big")
            if body_len <= 0:
                print(f"[异常数据] 客户端 {client_addr} 发送了非法长度")
                break

            # 2. 再按长度读满正文，避免拆包/粘包
            payload = recv_exact(client_socket, body_len)
            if len(payload) != body_len:
                print(f"[异常数据] 客户端 {client_addr} 数据长度不完整")
                break

            data = payload.decode("utf-8")
            print(f"[收到消息] 来自 {client_addr}: {data}")

            # 3. 指令解析逻辑
            if "|" in data:
                cmd_type, json_body = data.split("|", 1)
                
                try:
                    body = json.loads(json_body) if json_body else {}
                except json.JSONDecodeError:
                    response_data = {"code": 400, "msg": "JSON格式错误"}
                    response_str = f"{cmd_type}|{json.dumps(response_data, ensure_ascii=False)}"
                    resp_bytes = response_str.encode("utf-8")
                    resp_header = len(resp_bytes).to_bytes(HEADER_SIZE, "big")
                    client_socket.sendall(resp_header + resp_bytes)
                    continue

                # ================= 任务7：用户注册/登录/权限逻辑 =================
                
                if cmd_type == "REGISTER":
                    # 注册逻辑：校验用户名唯一性，密码MD5加密后存入数据库
                    username = body.get("username")
                    password = body.get("password")
                    phone = body.get("phone")  # 可选，可能是 null
                    nickname = body.get("nickname")  # 可选
                    
                    # 处理前端传来的 null 值（JSON 的 null 在 Python 中可能是 None）
                    if phone is None or phone == "null" or phone == "":
                        phone = None
                    
                    print(f"[SERVER DEBUG] 收到注册请求: username={username}, nickname={nickname}, phone={phone}")
                    
                    if not username or not password:
                        response_data = {"code": 400, "msg": "缺少用户名或密码"}
                        print(f"[SERVER DEBUG] 注册失败: 缺少用户名或密码")
                    else:
                        success, msg, error_code = db_manager.register_user(username, password, phone, nickname)
                        print(f"[SERVER DEBUG] 注册结果: success={success}, msg={msg}, error_code={error_code}")
                        if success:
                            # 成功：返回200
                            response_data = {"code": 200, "msg": msg}
                        else:
                            # 失败：根据错误类型返回不同错误码
                            # code 401: 用户名已存在（不可重复注册）
                            # code 500: 服务器内部错误（数据库连接失败、SQL执行失败等）
                            response_data = {
                                "code": error_code if error_code else 500,
                                "msg": msg
                            }
                            
                elif cmd_type == "LOGIN":
                    # 登录逻辑：校验用户名密码，返回用户ID和角色
                    # 1. 用户输入用户名和密码，点击"登录"
                    # 2. 客户端通过 socket 发送 LOGIN 命令到服务器
                    # 3. 服务器验证：查询数据库检查用户是否存在、验证密码（MD5哈希比对）、检查账号状态
                    # 4. 服务器返回响应：成功（code 200）返回用户信息，失败（code 401）用户名或密码错误，失败（code 403）账号被封禁
                    username = body.get("username")
                    password = body.get("password")
                    
                    if not username or not password:
                        response_data = {"code": 400, "msg": "缺少用户名或密码"}
                    else:
                        success, msg, user_info, error_code = db_manager.validate_login(username, password)
                        if success:
                            # 成功（code 200）：返回用户信息
                            response_data = {
                                "code": 200,
                                "msg": msg,
                                "data": user_info  # 包含 user_id, role, username
                            }
                        else:
                            # 失败：根据错误类型返回不同错误码
                            # code 401: 用户名或密码错误
                            # code 403: 账号被封禁
                            response_data = {
                                "code": error_code if error_code else 401,
                                "msg": msg
                            }
                            
                elif cmd_type == "UPDATE_PROFILE":
                    # 更新用户资料（昵称修改）
                    # 用户登录后，发送 UPDATE_PROFILE 指令修改昵称
                    # 请求格式: UPDATE_PROFILE|{"username": "1234", "nickname": "kaka"}
                    username = body.get("username")
                    nickname = body.get("nickname")
                    
                    print(f"[SERVER DEBUG] 收到更新昵称请求: username={username}, nickname={nickname}")
                    
                    if not nickname:
                        response_data = {"code": 400, "msg": "缺少昵称参数"}
                    elif not username:
                        response_data = {"code": 400, "msg": "缺少用户名参数，请先登录"}
                    else:
                        success, msg = db_manager.update_user_nickname(username, nickname)
                        print(f"[SERVER DEBUG] 更新昵称结果: success={success}, msg={msg}")
                        if success:
                            response_data = {"code": 200, "msg": msg}
                        else:
                            response_data = {"code": 400, "msg": msg}
                            
                elif cmd_type == "USER_MANAGE":
                    # 管理员用户管理接口（查询所有用户、封号/解封）
                    action = body.get("action")
                    user_id = body.get("user_id")
                    
                    if action == "LIST":
                        # 查询所有用户
                        users = db_manager.list_users()
                        response_data = {"code": 200, "msg": "查询成功", "users": users}
                    elif action == "BLOCK":
                        # 封号
                        if not user_id:
                            response_data = {"code": 400, "msg": "缺少用户ID"}
                        else:
                            success, msg = db_manager.update_user_status(user_id, "blocked")
                            response_data = {"code": 200 if success else 400, "msg": msg}
                    elif action == "UNBLOCK":
                        # 解封
                        if not user_id:
                            response_data = {"code": 400, "msg": "缺少用户ID"}
                        else:
                            success, msg = db_manager.update_user_status(user_id, "active")
                            response_data = {"code": 200 if success else 400, "msg": msg}
                    else:
                        response_data = {"code": 400, "msg": f"未知的管理员动作: {action}"}
                        
                else:
                    # 未知指令
                    response_data = {"code": 404, "msg": f"未知指令: {cmd_type}"}

                # 4. 回包同样加长度头
                response_str = f"{cmd_type}|{json.dumps(response_data, ensure_ascii=False)}"
                resp_bytes = response_str.encode("utf-8")
                resp_header = len(resp_bytes).to_bytes(HEADER_SIZE, "big")
                client_socket.sendall(resp_header + resp_bytes)
            else:
                err_msg = "ERROR|格式错误，请使用 '指令|数据' 格式"
                resp_bytes = err_msg.encode("utf-8")
                resp_header = len(resp_bytes).to_bytes(HEADER_SIZE, "big")
                client_socket.sendall(resp_header + resp_bytes)

        except ConnectionResetError:
            print(f"[异常断开] 客户端 {client_addr} 强行关闭了连接")
            break
        except Exception as e:
            print(f"[系统错误] 处理 {client_addr} 时发生错误: {e}")
            break
    
    # 循环结束后关闭该客户端的 Socket
    client_socket.close()

def start_server():
    """
    主程序：启动 Socket 服务器监听
    对应任务清单：编写Socket Server脚本 
    """
    # 1. 创建 Socket 对象 (IPv4, TCP协议)
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    # 允许端口复用（防止重启程序时报错 "Address already in use"）
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        # 2. 绑定 IP 和端口
        server.bind((SERVER_IP, SERVER_PORT))
        
        # 3. 开始监听 (最大挂起连接数设为 5)
        server.listen(5)
        print(f"==========================================")
        print(f"二手交易平台后端服务器启动成功")
        print(f"监听地址: {SERVER_IP}:{SERVER_PORT}")
        print(f"等待客户端连接中...")
        print(f"==========================================")
        
        while True:
            # 4. 阻塞等待，直到有新连接进来
            client_sock, client_addr = server.accept()
            
            # 5. 为每个新连接创建一个独立的线程 
            # target=指定线程要执行的函数, args=传递给函数的参数
            client_thread = threading.Thread(target=handle_client_request, args=(client_sock, client_addr))
            
            # 守护线程设置（可选）：主程序退出时子线程也自动退出
            client_thread.daemon = True 
            
            # 启动线程
            client_thread.start()
            
    except Exception as e:
        print(f"服务器启动失败: {e}")
    finally:
        server.close()

if __name__ == '__main__':
    start_server()
