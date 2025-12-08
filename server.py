import socket
import threading
import json
import sys

# =================配置区域=================
SERVER_IP = '10.129.106.38'  
SERVER_PORT = 8888       # 监听端口，确保不被占用
BUFFER_SIZE = 1024       # 单次 socket recv 尝试读取的大小
HEADER_SIZE = 4          # 前置 4 字节长度头


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

                response_data = {
                    "code": 200,
                    "msg": f"服务器已收到指令: {cmd_type}",
                    "original_data": json_body
                }

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
