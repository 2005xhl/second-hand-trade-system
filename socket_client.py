import socket
import threading
import json
import tkinter as tk
from tkinter import messagebox

# 与服务器保持一致的配置
SERVER_IP = "10.129.106.38"
SERVER_PORT = 8888
BUFFER_SIZE = 1024
HEADER_SIZE = 4


class SocketClient:
    """封装客户端连接/发送/接收逻辑"""

    def __init__(self):
        self.client = None
        self.connected = False
        self.lock = threading.Lock()

    def connect(self, host: str, port: int) -> str:
        with self.lock:
            if self.connected and self.client:
                return "已连接"
            try:
                self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.client.connect((host, port))
                self.connected = True
                return "连接成功"
            except Exception as e:
                self.connected = False
                self.client = None
                return f"连接失败: {e}"

    def send_command(self, cmd: str, body: dict) -> str:
        with self.lock:
            if not self.connected or not self.client:
                return "未连接服务器"
            try:
                payload_str = f"{cmd}|{json.dumps(body, ensure_ascii=False)}"
                payload = payload_str.encode("utf-8")
                header = len(payload).to_bytes(HEADER_SIZE, "big")
                # 发送：先发长度头，再发正文
                self.client.sendall(header + payload)

                # 接收：同样先读长度，再按长度读满
                resp_header = self._recv_exact(HEADER_SIZE)
                if not resp_header:
                    return "发送/接收失败: 服务器无响应"
                resp_len = int.from_bytes(resp_header, "big")
                resp_payload = self._recv_exact(resp_len)
                if resp_payload is None or len(resp_payload) != resp_len:
                    return "发送/接收失败: 响应不完整"
                data = resp_payload.decode("utf-8")
                return data
            except Exception as e:
                self.connected = False
                if self.client:
                    try:
                        self.client.close()
                    except Exception:
                        pass
                self.client = None
                return f"发送/接收失败: {e}"

    def _recv_exact(self, size: int) -> bytes | None:
        """循环读取指定长度，避免粘包/拆包"""
        chunks = []
        total = 0
        while total < size:
            part = self.client.recv(size - total)
            if not part:
                return None
            chunks.append(part)
            total += len(part)
        return b"".join(chunks)

    def close(self):
        with self.lock:
            try:
                if self.client:
                    self.client.close()
            finally:
                self.client = None
                self.connected = False


class ClientUI(tk.Tk):
    """简单的 Tkinter 客户端界面，提供连接测试与指令发送"""

    def __init__(self):
        super().__init__()
        self.title("Socket 客户端测试")
        # 加大窗口，避免按钮被遮挡
        self.geometry("520x320")
        self.resizable(False, False)

        self.client = SocketClient()

        # 服务器配置
        frm_conn = tk.LabelFrame(self, text="服务器配置", padx=10, pady=10)
        frm_conn.pack(fill=tk.X, padx=12, pady=10)

        tk.Label(frm_conn, text="IP:").grid(row=0, column=0, sticky="e")
        self.ip_entry = tk.Entry(frm_conn, width=18)
        self.ip_entry.grid(row=0, column=1, padx=5)
        self.ip_entry.insert(0, SERVER_IP)

        tk.Label(frm_conn, text="端口:").grid(row=0, column=2, sticky="e")
        self.port_entry = tk.Entry(frm_conn, width=8)
        self.port_entry.grid(row=0, column=3, padx=5)
        self.port_entry.insert(0, str(SERVER_PORT))

        self.btn_connect = tk.Button(frm_conn, text="连接测试", width=12, command=self.on_connect)
        self.btn_connect.grid(row=0, column=4, padx=8)

        # 指令发送
        frm_cmd = tk.LabelFrame(self, text="指令发送", padx=10, pady=10)
        frm_cmd.pack(fill=tk.X, padx=12, pady=5)
        # 让输入框可伸缩，按钮不被挤出视野
        for i in range(5):
            frm_cmd.columnconfigure(i, weight=1)

        tk.Label(frm_cmd, text="指令头:").grid(row=0, column=0, sticky="e")
        self.cmd_entry = tk.Entry(frm_cmd, width=12)
        self.cmd_entry.grid(row=0, column=1, padx=5, sticky="we")
        self.cmd_entry.insert(0, "TEST")

        tk.Label(frm_cmd, text="JSON内容:").grid(row=0, column=2, sticky="e")
        self.body_entry = tk.Entry(frm_cmd, width=32)
        self.body_entry.grid(row=0, column=3, padx=5, sticky="we")
        self.body_entry.insert(0, '{"msg":"hello"}')

        self.btn_send = tk.Button(frm_cmd, text="发送指令", width=12, command=self.on_send)
        self.btn_send.grid(row=0, column=4, padx=8, sticky="e")

        # 响应展示
        frm_resp = tk.LabelFrame(self, text="响应结果", padx=10, pady=10)
        frm_resp.pack(fill=tk.BOTH, expand=True, padx=12, pady=10)

        self.resp_text = tk.Text(frm_resp, height=6, wrap="word")
        self.resp_text.pack(fill=tk.BOTH, expand=True)

        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def append_resp(self, text: str):
        self.resp_text.insert(tk.END, text + "\n")
        self.resp_text.see(tk.END)

    def on_connect(self):
        host = self.ip_entry.get().strip()
        try:
            port = int(self.port_entry.get().strip())
        except ValueError:
            messagebox.showerror("错误", "端口必须是数字")
            return

        def task():
            result = self.client.connect(host, port)
            self.append_resp(result)
            if result.startswith("连接成功") or result == "已连接":
                messagebox.showinfo("提示", result)
            else:
                messagebox.showerror("错误", result)

        threading.Thread(target=task, daemon=True).start()

    def on_send(self):
        cmd = self.cmd_entry.get().strip()
        if not cmd:
            messagebox.showerror("错误", "指令头不能为空")
            return
        body_str = self.body_entry.get().strip() or "{}"
        try:
            body = json.loads(body_str)
        except Exception as e:
            messagebox.showerror("错误", f"JSON内容解析失败: {e}")
            return

        def task():
            resp = self.client.send_command(cmd, body)
            self.append_resp(f"发送: {cmd}|{body}")
            self.append_resp(f"响应: {resp}")
            if resp.startswith("发送/接收失败") or resp.startswith("未连接"):
                messagebox.showerror("错误", resp)

        threading.Thread(target=task, daemon=True).start()

    def on_close(self):
        self.client.close()
        self.destroy()


if __name__ == "__main__":
    app = ClientUI()
    app.mainloop()

