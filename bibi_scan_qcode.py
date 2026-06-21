import os
import json
import time
import threading
import tkinter as tk
from tkinter import messagebox, filedialog
from PIL import Image, ImageTk
import qrcode as qrcode_lib
import requests
import yt_dlp


COOKIE_FILE = "bili_cookies.json"

class BiliPureRecorderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("B站高清视频免风控录制工具 (原生扫码版)")
        self.root.geometry("650x550")
        
        self.cookies_dict = {}
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"})
        
        self.create_widgets()
        self.check_local_login()
        
    def create_widgets(self):
        self.lbl_status = tk.Label(self.root, text="登录状态: 未登录", font=("Microsoft YaHei", 10, "bold"), fg="red")
        self.lbl_status.pack(anchor="w", padx=20, pady=10)
        
        lbl_url = tk.Label(self.root, text="B站视频链接:", font=("Microsoft YaHei", 10))
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
        
        self.btn_login = tk.Button(frame_btn, text="B站扫码登录", bg="#fb7299", fg="white", font=("Microsoft YaHei", 10, "bold"), command=self.start_login_thread)
        self.btn_login.pack(side="left", padx=10)
        
        self.btn_start = tk.Button(frame_btn, text="开始高清无感录制", bg="#1e62ec", fg="white", font=("Microsoft YaHei", 10, "bold"), command=self.start_record_thread)
        self.btn_start.pack(side="left", padx=10)

        self.log_area = tk.Text(self.root, height=12, width=75, font=("Consolas", 10), bg="#f4f4f4")
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
                    self.cookies_dict = json.load(f)
                # 验证本地 Cookie 效果
                res = self.session.get("https://api.bilibili.com/x/web-interface/nav", cookies=self.cookies_dict).json()
                if res["code"] == 0:
                    uname = res["data"]["uname"]
                    self.lbl_status.config(text=f"登录状态: 已登录 ({uname})", fg="green")
                    self.log(f"[系统] 欢迎回来，{uname}！安全凭证有效。")
                    return
            except:
                pass
        self.lbl_status.config(text="登录状态: 未登录 (可能限制1080P/触发412)", fg="red")

    def start_login_thread(self):
        threading.Thread(target=self.native_scan_login).start()

    def native_scan_login(self):
        """ 原生请求B站官方接口，生成登录二维码 """
        self.log("[登录] 正在申请官方安全登录通道...")
        try:
            # 1. 申请二维码
            r1 = self.session.get("https://pasport.bilibili.com/x/passport-login/web/qrcode/generate").json()
            qr_url = r1["data"]["url"]
            qrcode_key = r1["data"]["qrcode_key"]
            
            # 2. 画出二维码
            qr = qrcode_lib.QRCode()
            qr.add_data(qr_url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            
            qr_win = tk.Toplevel(self.root)
            qr_win.title("请使用手机B站App扫码")
            img_tk = ImageTk.PhotoImage(img)
            lbl_img = tk.Label(qr_win, image=img_tk)
            lbl_img.image = img_tk
            lbl_img.pack(padx=20, pady=20)
            
            self.log("[登录] 二维码已成功弹出，请扫码并在手机端确认...")
            
            # 3. 轮询扫码状态
            while True:
                time.sleep(2)
                if not qr_win.winfo_exists(): 
                    self.log("[登录] 扫码窗口被关闭，登录取消。")
                    break
                    
                r2 = self.session.get(f"https://pasport.bilibili.com/x/passport-login/web/qrcode/poll?qrcode_key={qrcode_key}")
                res_data = r2.json()["data"]
                code = res_data["code"]
                
                if code == 0: # 登录成功！
                    self.log("[登录] 🎉 手机端确认成功！正在提取加密凭证...")
                    # 从返回的 Set-Cookie 响应头或 cookies 自动同步中提取所需的全部 B站凭证
                    cookies = r2.cookies.get_dict()
                    
                    with open(COOKIE_FILE, "w") as f:
                        json.dump(cookies, f)
                        
                    self.cookies_dict = cookies
                    qr_win.destroy()
                    self.check_local_login()
                    break
                elif code == 86615: # 二维码过期
                    self.log("[登录] ❌ 二维码已过期，请重新点击登录。")
                    qr_win.destroy()
                    break
        except Exception as e:
            self.log(f"[登录错误] 通道建立失败: {str(e)}")

    def start_record_thread(self):
        threading.Thread(target=self.record_video).start()

    def ydl_hook(self, d):
        if d['status'] == 'downloading':
            percent = d.get('_percent_str', '0.0%')
            speed = d.get('_speed_str', '未知速度')
            self.root.after(0, self.log, f"正在安全抓取: {percent} | 速度: {speed}")

    def record_video(self):
        url = self.txt_url.get().strip()
        output_dir = self.txt_path.get().strip()
        
        if not url:
            messagebox.showerror("错误", "请输入有效的视频链接！")
            return
            
        self.btn_start.config(state="disabled", text="安全录制中...")
        self.log_area.delete("1.0", tk.END)
        
        temp_name = "secure_temp_video"
        yt_cookie_path = os.path.join(output_dir, "bili_yt_cookies.txt")
        
        # 将我们原生拿到的完整 Cookie 字典，转换为 yt-dlp 兼容的标准 Netscape 文本
        if self.cookies_dict:
            with open(yt_cookie_path, "w", encoding="utf-8") as f:
                f.write("# Netscape HTTP Cookie File\n")
                for k, v in self.cookies_dict.items():
                    f.write(f".bilibili.com\tTRUE\t/\tFALSE\t0\t{k}\t{v}\n")

        ydl_opts = {
            'format': 'bestvideo+bestaudio/best', 
            'outtmpl': os.path.join(output_dir, f'{temp_name}.%(ext)s'), 
            'merge_output_format': 'mp4',
            'progress_hooks': [self.ydl_hook],
            'quiet': True,
            'ffmpeg_location': os.path.abspath(os.getcwd()), 
        }
        
        if os.path.exists(yt_cookie_path):
            ydl_opts['cookiefile'] = yt_cookie_path

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                self.log("[系统] 正在建立与B站的高清加密媒体流通道...")
                info = ydl.extract_info(url, download=True)
                raw_title = info.get('title', '💾高清录制视频')
                
            safe_title = "".join([c for c in raw_title if c not in r'\/:*?"<>|']).strip()[:50]
            merged_file = os.path.join(output_dir, f"{temp_name}.mp4")
            final_file = os.path.join(output_dir, f"{safe_title}.mp4")
            
            if os.path.exists(merged_file):
                if os.path.exists(final_file): os.remove(final_file)
                os.rename(merged_file, final_file)
                self.log(f"\n🎉 完美通关！[已绕过412风控]\n保存文件名: {os.path.basename(final_file)}")
                messagebox.showinfo("成功", "视频已成功高清保存！")
        except Exception as e:
            self.log(f"\n❌ 抓取失败: {str(e)}")
        finally:
            if os.path.exists(yt_cookie_path):
                try: os.remove(yt_cookie_path)
                except: pass
            self.btn_start.config(state="normal", text="开始高清无感录制")

if __name__ == "__main__":
    root = tk.Tk()
    app = BiliPureRecorderApp(root)
    root.mainloop()
