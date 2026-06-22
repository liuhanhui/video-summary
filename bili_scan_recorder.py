import os
import json
import asyncio
import threading
import tkinter as tk
from tkinter import messagebox, filedialog
import requests
import subprocess
from bilibili_api import video, Credential

COOKIE_FILE = "bili_cookies.json"

class BiliNativeRecorderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("B站高清视频免风控录制工具 (反防刷音画完美版)")
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
        self.btn_start = tk.Button(frame_btn, text="开始高清音视频无感录制", bg="#1e62ec", fg="white", font=("Microsoft YaHei", 10, "bold"), command=self.start_record_thread)
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

    def download_file_safe(self, url, filename, desc="媒体数据"):
        """对抗 10054 的高强度拟真流式下载器"""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.bilibili.com/",
            "Origin": "https://www.bilibili.com",
            "Accept": "*/*",
            "Accept-Encoding": "identity", # 阻止服务器进行意外压缩
            "Connection": "keep-alive"
        }
        
        # 建立高容错会话
        session = requests.Session()
        response = session.get(url, headers=headers, stream=True, timeout=30)
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        
        # 将 chunk 缩小至 256KB 均匀平滑拉取，欺骗 B 站风控
        with open(filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=256 * 1024):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        percent = (downloaded / total_size) * 100
                        self.root.after(0, self.log, f"正在安全下载 {desc}: {percent:.1f}%")

    async def record_video_native(self):
        url_input = self.txt_url.get().strip()
        output_dir = self.txt_path.get().strip()

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
            v = video.Video(bvid=bvid, credential=self.credential)
            self.log("[系统] 正在通过B站原生通道获取视频元数据...")
            info = await v.get_info()
            title = info['title']
            self.log(f"[视频标题] {title}")

            self.log("[系统] 正在请求高清媒体流下载授权...")
            download_url_data = await v.get_download_url(page_index=0)

            safe_title = "".join([c for c in title if c not in r'\/:*?"<>|']).strip()[:50]
            
            video_tmp = os.path.join(output_dir, f"{safe_title}_video.tmp")
            audio_tmp = os.path.join(output_dir, f"{safe_title}_audio.tmp")
            final_file = os.path.join(output_dir, f"{safe_title}.mp4")

            # 智能提取并净化 URL（过滤掉已知的 P2P 垃圾节点，只用主干节点）
            def filter_clean_url(stream_list):
                for stream in stream_list:
                    urls_to_check = [stream["baseUrl"]] + stream.get("backupUrl", [])
                    for url in urls_to_check:
                        if "4483" not in url and "mountaintoys" not in url and "mcdn" not in url:
                            return url
                return stream_list[0]["baseUrl"]

            # 区分 durl 和 dash
            if "durl" in download_url_data:
                self.log("[下载] 检测到复合 MP4 流，正在直连下载...")
                video_url = download_url_data["durl"][0]["url"]
                self.download_file_safe(video_url, final_file, desc="完整视频")
            else:
                self.log("[下载] 检测到高清 DASH 分离流，正在智能安全抓取...")
                video_url = filter_clean_url(download_url_data["dash"]["video"])
                audio_url = filter_clean_url(download_url_data["dash"]["audio"])

                # 1. 下载纯视频
                self.download_file_safe(video_url, video_tmp, desc="视频画面")
                # 2. 下载语音音频
                self.download_file_safe(audio_url, audio_tmp, desc="语音音频")

                # 3. 合并音视频
                self.log("[混流] 正在调用 FFmpeg 无损封装音视频...")
                
                # 智能搜寻系统中的 ffmpeg 路径
                import shutil
                ffmpeg_path = shutil.which("ffmpeg")
                
                # 如果系统变量没搜到，你可以把下面这行前面的 # 去掉，并改成你的绝对路径：
                # ffmpeg_path = r"D:\ffmpeg\bin\ffmpeg.exe"
                
                if not ffmpeg_path:
                    ffmpeg_path = "ffmpeg" # 最后的保底尝试

                # 修复核心错误：去掉了错误的 -strict shooters，换成标准的 copy 封装
                cmd = f'"{ffmpeg_path}" -y -i "{video_tmp}" -i "{audio_tmp}" -c:v copy -c:a aac "{final_file}"'
                
                self.log(f"[执行命令] {cmd}") # 打印出来方便排查
                
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                
                process = subprocess.Popen(cmd, shell=True, startupinfo=startupinfo, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                stdout, stderr = process.communicate()

                # 打印 FFmpeg 具体的报错信息，防止它闷声犯错
                if process.returncode != 0:
                    err_msg = stderr.decode('utf-8', errors='ignore')
                    self.log(f"[FFmpeg详细错误] {err_msg}")
                    raise Exception("FFmpeg 混流合并失败，具体错误请看上方日志。")

                # 只有成功合并了才删除临时文件
                if os.path.exists(video_tmp): os.remove(video_tmp)
                if os.path.exists(audio_tmp): os.remove(audio_tmp)

            self.log(f"\n🎉 完美录制并合并成功！")
            self.log(f"文件保存路径: {final_file}")
            messagebox.showinfo("成功", "高清音视频完美合并，免风控保存成功！")

        except Exception as e:
            self.log(f"\n❌ 抓取或合并错误: {str(e)}")
        finally:
            self.btn_start.config(state="normal", text="开始高清音视频无感录制")

if __name__ == "__main__":
    root = tk.Tk()
    app = BiliNativeRecorderApp(root)
    root.mainloop()
