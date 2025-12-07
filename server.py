import socket
import threading
import json
import sys

# =================配置区域=================
SERVER_IP = '10.129.106.38'  
SERVER_PORT = 8888       # 监听端口，确保不被占用
BUFFER_SIZE = 1024       # 一次接收的数据大小
# =========================================

def handle_client_request(client_socket, client_addr):
    """
    子线程函数：专门负责处理单个客户端的通信逻辑
    对应任务清单：实现多线程处理 
    """
    print(f"[连接成功] 客户端 {client_addr} 已连接...")
    
    while True:
        try:
            # 1. 接收客户端发来的数据
            # decode('utf-8') 将字节流转换为字符串
            data = client_socket.recv(BUFFER_SIZE).decode('utf-8')
            
            # 如果收到的数据为空，说明客户端断开了连接
            if not data:
                print(f"[断开连接] 客户端 {client_addr} 下线了")
                break
            
            print(f"[收到消息] 来自 {client_addr}: {data}")
            
            # 2. 指令解析逻辑 
            # 假设通信协议格式为：指令头|JSON数据 (例如: LOGIN|{"user":"test"})
            if "|" in data:
                # 分割指令头和数据体，只分割一次
                cmd_type, json_body = data.split("|", 1)
                
                # 这里暂时做简单响应，后续会连接数据库
                response_data = {
                    "code": 200,
                    "msg": f"服务器已收到指令: {cmd_type}",
                    "original_data": json_body
                }
                
                # 3. 发送响应给客户端
                # 将字典转为JSON字符串发送，保持格式一致：指令头|响应数据
                response_str = f"{cmd_type}|{json.dumps(response_data)}"
                client_socket.send(response_str.encode('utf-8'))
                
            else:
                # 格式不正确时的处理
                client_socket.send("ERROR|格式错误，请使用 '指令|数据' 格式".encode('utf-8'))

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