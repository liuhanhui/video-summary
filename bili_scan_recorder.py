import os
import json
import asyncio
import threading
import tkinter as tk
from tkinter import messagebox, filedialog
import requests
 
# 引入专门对抗B站风控的专用库
from bilibili_api import video, Credential, sync

COOKIE_FILE = "bili_cookies.json"

class BiliNativeRecorderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("B站高清视频免风控录制工具 (B站原生通道版)")
        self.root.geometry("650x550")
        
        self.credential = None
        self.create_widgets()
        self.check_local_login()
        
    def create_widgets(self):
        self.lbl_status = tk.Label(self.root, text="登录状态: 检查中...", font=("Microsoft YaHei", 10, "bold"), fg="orange")
        self.lbl_status.pack(anchor="w", padx=20, pady=10)
        
        lbl_url = tk.Label(self.root, text="B站视频链接 (支持BV号或完整链接):", font=("Microsoft YaHei", 10))
        lbl_url.pack(anchor="w", padx=20, pady=5)
        self.txt_url = tk.Entry(self.root, width=75, font=("Microsoft YaHei", 10))
        self.txt_url.pack(padx=20, pady=5)
        self.txt_url.insert(0, "https://www.bilibili.com/video/BV18yfeB4Ewx/")

        lbl_path = tk.Label(self.root, text="视频保存目录:", font=("Microsoft YaHei", 10))
        lbl_path.pack(anchor="w", padx=20, pady=5)
        frame_path = tk.Frame(self.root)
        frame_path.pack(fill="x", padx=20, pady=5)
        self.txt_path = tk.Entry(frame_path, font=("Microsoft YaHei", 10))
        self.txt_path.pack(side="left", fill="x", expand=True)
        self.txt_path.insert(0, os.getcwd())
        btn_browse = tk.Button(frame_path, text=" 浏览... ", command=self.browse_folder)
        btn_browse.pack(side="right", padx=(10, 0))

        frame_btn = tk.Frame(self.root)
        frame_btn.pack(pady=15)
        
        self.btn_start = tk.Button(frame_btn, text="开始高清无感录制", bg="#1e62ec", fg="white", font=("Microsoft YaHei", 10, "bold"), command=self.start_record_thread)
        self.btn_start.pack(side="left", padx=10)

        self.log_area = tk.Text(self.root, height=15, width=75, font=("Consolas", 10), bg="#f4f4f4")
        self.log_area.pack(padx=20, pady=5)
        
    def browse_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.txt_path.delete(0, tk.END)
            self.txt_path.insert(0, folder)
            
    def log(self, text):
        self.log_area.insert(tk.END, text + "\n")
        self.log_area.see(tk.END)

    def check_local_login(self):
        if os.path.exists(COOKIE_FILE):
            try:
                with open(COOKIE_FILE, "r") as f:
                    data = json.load(f)
                self.credential = Credential(sessdata=data.get("SESSDATA"), bili_jct=data.get("bili_jct"), buvid3=data.get("buvid3"))
                self.lbl_status.config(text="登录状态: 安全凭证已加载成功！", fg="green")
                self.log("[系统] 成功读取原生扫码凭证。")
                return
            except:
                pass
        self.lbl_status.config(text="登录状态: 未找到凭证，请先用上一版代码扫码登录", fg="red")

    def start_record_thread(self):
        threading.Thread(target=self.run_async_download).start()

    def run_async_download(self):
        asyncio.run(self.record_video_native())

    async def record_video_native(self):
        url_input = self.txt_url.get().strip()
        output_dir = self.txt_path.get().strip()
        
        # 提取BV号
        bvid = ""
        if "BV" in url_input:
            parts = url_input.split("/")
            for p in parts:
                if p.startswith("BV"):
                    bvid = p.split("?")[0]
                    break
        if not bvid:
            messagebox.showerror("错误", "请输入包含有效BV号的B站链接！")
            return
            
        self.btn_start.config(state="disabled", text="正在安全抓取...")
        self.log_area.delete("1.0", tk.END)
        self.log(f"[分析] 目标视频BV号: {bvid}")
        
        try:
            # 1. 实例化B站视频对象，自动继承扫码获得的鉴权凭证
            v = video.Video(bvid=bvid, credential=self.credential)
            
            # 2. 获取视频详细信息（绕过 yt-dlp，使用原生网络握手）
            self.log("[系统] 正在通过B站原生通道获取视频元数据...")
            info = await v.get_info()
            title = info['title']
            self.log(f"[视频标题] {title}")
            
            # 3. 获取高清下载流链接
            self.log("[系统] 正在请求高清媒体流下载授权...")
            download_url_data = await v.get_download_url(page_index=0)
            
            # 挑选普通的、已经封装好音视频的普通 MP4 流（durl 模式）
            if "durl" in download_url_data:
                video_url = download_url_data["durl"][0]["url"]
            else:
                # 如果只有分离流，选择最基础的兼容流
                video_url = download_url_data["dash"]["video"][0]["baseUrl"]
                
            # 4. 开始原生安全下载
            self.log("[下载] 成功拿到视频流。正在建立文件下载线程...")
            safe_title = "".join([c for c in title if c not in r'\/:*?"<>|']).strip()[:50]
            final_file = os.path.join(output_dir, f"{safe_title}.mp4")
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://www.bilibili.com" # B站防盗链核心：必须带Referer
            }
            
            # 使用 requests 流式下载，100% 避开任何第三方命令行参数错误
            response = requests.get(video_url, headers=headers, stream=True)
            total_size = int(response.headers.get('content-length', 0))
            
            with open(final_file, 'wb') as f:
                downloaded = 0
                for chunk in response.iter_content(chunk_size=1024*1024):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            percent = (downloaded / total_size) * 100
                            self.root.after(0, self.log, f"正在保存媒体数据: {percent:.1f}%")
                            
            self.log(f"\n🎉 完美录制成功！[已绕过yt-dlp 412限制]")
            self.log(f"文件保存路径: {final_file}")
            messagebox.showinfo("成功", "视频已成功免风控保存！")
            
        except Exception as e:
            self.log(f"\n❌ 抓取错误: {str(e)}")
        finally:
            self.btn_start.config(state="normal", text="开始高清无感录制")

if __name__ == "__main__":
    root = tk.Tk()
    app = BiliNativeRecorderApp(root)
    root.mainloop()
