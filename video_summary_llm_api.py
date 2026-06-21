import os
import json
import base64
import threading
import tkinter as tk
from tkinter import messagebox, filedialog
from openai import OpenAI

CONFIG_FILE = ".qwen36_config.json"

class Qwen36VideoAssistantApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Qwen3.6-Plus 本地视频超感官 AI 助理")
        self.root.geometry("750x600")
        
        self.create_widgets()
        self.load_config()

    def create_widgets(self):
        # 1. 密钥配置区域
        frame_config = tk.LabelFrame(self.root, text=" ⚙️ 阿里云百炼平台配置 (Qwen3.6-Plus 专用) ", font=("Microsoft YaHei", 10, "bold"), padx=15, pady=10)
        frame_config.pack(fill="x", padx=20, pady=10)
        
        tk.Label(frame_config, text="百炼 API Key:", font=("Microsoft YaHei", 10)).grid(row=0, column=0, sticky="w", pady=3)
        self.txt_api_key = tk.Entry(frame_config, width=50, font=("Consolas", 10), show="*")
        self.txt_api_key.grid(row=0, column=1, padx=10, pady=3, sticky="w")
        
        self.var_remember = tk.IntVar(value=1)
        chk_remember = tk.Checkbutton(frame_config, text="记住密钥", variable=self.var_remember)
        chk_remember.grid(row=0, column=2, padx=5, sticky="w")
        
        tk.Label(frame_config, text="当前激活模型:", font=("Microsoft YaHei", 10)).grid(row=1, column=0, sticky="w", pady=3)
        lbl_model = tk.Label(frame_config, text="qwen3.6-plus (最新多模态大模型)", font=("Microsoft YaHei", 10, "bold"), fg="#1e62ec")
        lbl_model.grid(row=1, column=1, padx=10, pady=3, sticky="w")

        # 2. 视频选择区
        frame_video = tk.LabelFrame(self.root, text=" 🎬 选择本地视频文件 ", font=("Microsoft YaHei", 10, "bold"), padx=15, pady=10)
        frame_video.pack(fill="x", padx=20, pady=5)
        
        tk.Label(frame_video, text="本地视频路径:", font=("Microsoft YaHei", 10)).pack(side="left")
        self.txt_video_path = tk.Entry(frame_video, width=54, font=("Microsoft YaHei", 10))
        self.txt_video_path.pack(side="left", padx=10)
        btn_browse = tk.Button(frame_video, text=" 浏览... ", command=self.browse_video)
        btn_browse.pack(side="left", padx=5)

        # 3. 提示词定制
        lbl_prompt = tk.Label(self.root, text="💡 定制你的 AI 笔记分析深度提示词 (Prompt):", font=("Microsoft YaHei", 10, "bold"))
        lbl_prompt.pack(anchor="w", padx=20, pady=5)
        self.txt_prompt = tk.Text(self.root, height=4, width=82, font=("Microsoft YaHei", 10))
        self.txt_prompt.pack(padx=20, pady=5)
        self.txt_prompt.insert(tk.END, 
            "你是一个顶级的音视频多模态内容精炼官。请仔细观看并聆听这段视频，为您整理一份高可读性的摘要笔记。\n"
            "要求严格包含：【全局核心综述】、结合视频中出现的画面和PPT整理的【画面详细分节笔记】、以及【核心结论与建议】。"
        )

        # 4. 执行按钮
        self.btn_start = tk.Button(self.root, text="🚀 启动本地数据流映射并唤醒 Qwen3.6-Plus", bg="#1e62ec", fg="white", font=("Microsoft YaHei", 11, "bold"), height=2, command=self.start_workflow_thread)
        self.btn_start.pack(fill="x", padx=20, pady=10)

        # 5. 日志与笔记输出
        self.log_area = tk.Text(self.root, height=14, width=82, font=("Consolas", 10), bg="#f4f4f4")
        self.log_area.pack(padx=20, pady=5)

    def browse_video(self):
        file_path = filedialog.askopenfilename(filetypes=[("视频文件", "*.mp4 *.avi *.mkv *.mov")])
        if file_path:
            self.txt_video_path.delete(0, tk.END)
            self.txt_video_path.insert(0, file_path)

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
                    self.txt_api_key.insert(0, data.get("api_key", ""))
            except: pass

    def save_config(self):
        if self.var_remember.get() == 1:
            with open(CONFIG_FILE, "w") as f: 
                json.dump({"api_key": self.txt_api_key.get().strip()}, f)
        else:
            if os.path.exists(CONFIG_FILE): os.remove(CONFIG_FILE)

    def log(self, text):
        self.log_area.insert(tk.END, text + "\n")
        self.log_area.see(tk.END)

    def start_workflow_thread(self):
        api_key = self.txt_api_key.get().strip()
        video_path = self.txt_video_path.get().strip()
        
        if not api_key or not video_path:
            messagebox.showerror("错误", "请完整填写 API Key 并选择本地视频！")
            return
        if not os.path.exists(video_path):
            messagebox.showerror("错误", "本地视频路径不存在！")
            return
            
        self.save_config()
        self.btn_start.config(state="disabled", text="⚡ Qwen3.6-Plus 正在深度感知视频...")
        self.log_area.delete("1.0", tk.END)
        
        threading.Thread(target=lambda: self.run_pipeline(api_key, video_path)).start()

    def run_pipeline(self, api_key, local_video):
        prompt_text = self.txt_prompt.get("1.0", tk.END).strip()
        
        try:
            self.log("[系统] 正在将本地视频读取为高速 Base64 媒体流...")
            ext = os.path.splitext(local_video)[-1].replace('.', '').lower()
            if ext == 'mov': ext = 'quicktime'
            
            with open(local_video, "rb") as video_file:
                base64_data = base64.b64encode(video_file.read()).decode("utf-8")
            
            # 拼接标准 Data URI
            video_input_uri = f"data:video/{ext};base64,{base64_data}"
            
            self.log("[系统] 媒体流封装完毕。正在建立与阿里云百炼标准 OpenAI 路由的连接...")
            
            # 👉 【核心升级】改用全新的通用 OpenAI 客户端，彻底免疫旧版 SDK 架构变更
            client = OpenAI(
                api_key=api_key,
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
            )
            
            # 使用标准的 chat.completions 接口投喂多模态数据
            response = client.chat.completions.create(
                model="qwen3.6-plus",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "video_url", "video_url": {"url": video_input_uri}},
                            {"type": "text", "text": prompt_text}
                        ]
                    }
                ]
            )
            
            note_content = response.choices[0].message.content
            self.log("\n" + "="*20 + " 🤖 Qwen3.6-Plus 视频多模态摘要成功 " + "="*20)
            self.log(note_content)
            self.log("="*60)
            
            # 同步保存本地落盘笔记
            note_path = os.path.splitext(local_video)[0] + "_Qwen3.6智能笔记.md"
            with open(note_path, "w", encoding="utf-8") as f:
                f.write(note_content)
            self.log(f"\n💾 笔记已自动落盘归档：{os.path.basename(note_path)}")
            messagebox.showinfo("成功", "Qwen3.6-Plus 摘要笔记已成功生成！")
            
        except Exception as e:
            self.log(f"\n❌ 流水线崩溃: {str(e)}")
            self.log("提示：如果是 AccessDenied，请确认您的百炼账户已在模型广场开通 qwen3.6-plus 模型的调用权限。")
        finally:
            self.btn_start.config(state="normal", text="🚀 启动本地数据流映射并唤醒 Qwen3.6-Plus")

if __name__ == "__main__":
    root = tk.Tk()
    app = Qwen36VideoAssistantApp(root)
    root.mainloop()