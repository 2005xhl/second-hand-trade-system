import socket
import threading
import json
import tkinter as tk
from tkinter import messagebox

# 与服务器保持一致的配置
SERVER_IP = "10.129.106.38"
SERVER_PORT = 8888
BUFFER_SIZE = 1024


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
                payload = f"{cmd}|{json.dumps(body, ensure_ascii=False)}"
                self.client.send(payload.encode("utf-8"))
                data = self.client.recv(BUFFER_SIZE).decode("utf-8")
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
        self.geometry("420x260")
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

        tk.Label(frm_cmd, text="指令头:").grid(row=0, column=0, sticky="e")
        self.cmd_entry = tk.Entry(frm_cmd, width=12)
        self.cmd_entry.grid(row=0, column=1, padx=5)
        self.cmd_entry.insert(0, "TEST")

        tk.Label(frm_cmd, text="JSON内容:").grid(row=0, column=2, sticky="e")
        self.body_entry = tk.Entry(frm_cmd, width=28)
        self.body_entry.grid(row=0, column=3, padx=5)
        self.body_entry.insert(0, '{"msg":"hello"}')

        self.btn_send = tk.Button(frm_cmd, text="发送指令", width=12, command=self.on_send)
        self.btn_send.grid(row=0, column=4, padx=8)

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

