import os
import json
import time
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from http import HTTPStatus
import dashscope
from dashscope.audio.asr import Transcription
import oss2  # 引入官方 OSS SDK

class AudioNotesApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Qwen 智能语音课程笔记生成器 (OSS 高配稳定版)")
        self.root.geometry("680x720")  # 扩大窗口以容纳 OSS 配置项
        self.root.resizable(False, False)
        self.config_path = os.path.join(
            os.getenv("APPDATA") or os.path.expanduser("~"),
            "AudioNotesApp",
            "config.json"
        )
        saved_config = self.load_config()
        
        style = ttk.Style()
        style.theme_use('clam')

        # 变量定义
        self.api_key_var = tk.StringVar(value=saved_config.get("dashscope_api_key") or os.getenv("DASHSCOPE_API_KEY", ""))
        self.llm_model_var = tk.StringVar(value=saved_config.get("llm_model") or "qwen-plus")
        self.audio_path_var = tk.StringVar()
        self.save_path_var = tk.StringVar()
        
        # OSS 相关变量
        self.oss_ak_var = tk.StringVar(value=saved_config.get("oss_access_key_id") or os.getenv("OSS_ACCESS_KEY_ID", ""))
        self.oss_sk_var = tk.StringVar(value=saved_config.get("oss_access_key_secret") or os.getenv("OSS_ACCESS_KEY_SECRET", ""))
        self.oss_endpoint_var = tk.StringVar(value=saved_config.get("oss_endpoint") or "oss-cn-beijing.aliyuncs.com") # 默认北京
        self.oss_bucket_var = tk.StringVar(value=saved_config.get("oss_bucket", ""))
        
        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 1. 基础 API Key 配置
        ttk.Label(main_frame, text="1. 配置百炼 API Key:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.api_entry = ttk.Entry(main_frame, textvariable=self.api_key_var, show="*", width=55)
        self.api_entry.grid(row=1, column=0, columnspan=2, sticky=tk.EW, pady=2)
        self.show_key_var = tk.BooleanVar()
        ttk.Checkbutton(main_frame, text="显示 Key", variable=self.show_key_var, command=self.toggle_api_visibility).grid(row=1, column=2, padx=5)

        ttk.Label(main_frame, text="总结模型名称:").grid(row=2, column=0, sticky=tk.W, pady=2)
        ttk.Entry(main_frame, textvariable=self.llm_model_var, width=55).grid(row=3, column=0, columnspan=2, sticky=tk.EW, pady=2)

        # 2. OSS 独占配置面板
        oss_lf = ttk.LabelFrame(main_frame, text=" 2. 阿里云 OSS 存储配置（绕过本地文件限制） ", padding="10")
        oss_lf.grid(row=4, column=0, columnspan=3, sticky=tk.EW, pady=10)
        
        ttk.Label(oss_lf, text="OSS AccessKey ID:").grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Entry(oss_lf, textvariable=self.oss_ak_var, width=50).grid(row=0, column=1, sticky=tk.EW, pady=2)
        
        ttk.Label(oss_lf, text="OSS AccessKey Secret:").grid(row=1, column=0, sticky=tk.W, pady=2)
        ttk.Entry(oss_lf, textvariable=self.oss_sk_var, show="*", width=50).grid(row=1, column=1, sticky=tk.EW, pady=2)
        
        ttk.Label(oss_lf, text="OSS Endpoint:").grid(row=2, column=0, sticky=tk.W, pady=2)
        ttk.Entry(oss_lf, textvariable=self.oss_endpoint_var, width=50).grid(row=2, column=1, sticky=tk.EW, pady=2)
        
        ttk.Label(oss_lf, text="Bucket 名称:").grid(row=3, column=0, sticky=tk.W, pady=2)
        ttk.Entry(oss_lf, textvariable=self.oss_bucket_var, width=50).grid(row=3, column=1, sticky=tk.EW, pady=2)
        ttk.Button(oss_lf, text="保存配置", command=lambda: self.save_config(show_message=True)).grid(row=4, column=1, sticky=tk.E, pady=(8, 0))

        # 3. 文件选择
        ttk.Label(main_frame, text="3. 选择本地语音文件:").grid(row=5, column=0, sticky=tk.W, pady=5)
        ttk.Entry(main_frame, textvariable=self.audio_path_var, width=55).grid(row=6, column=0, columnspan=2, sticky=tk.EW, pady=2)
        ttk.Button(main_frame, text="浏览文件", command=self.browse_audio).grid(row=6, column=2, padx=5)

        # 4. 保存路径
        ttk.Label(main_frame, text="4. 选择总结笔记保存路径 (.md):").grid(row=7, column=0, sticky=tk.W, pady=5)
        ttk.Entry(main_frame, textvariable=self.save_path_var, width=55).grid(row=8, column=0, columnspan=2, sticky=tk.EW, pady=2)
        ttk.Button(main_frame, text="选择路径", command=self.browse_save_path).grid(row=8, column=2, padx=5)

        # 5. 进度控制条
        ttk.Separator(main_frame, orient='horizontal').grid(row=9, column=0, columnspan=3, sticky=tk.EW, pady=10)
        self.progress_bar = ttk.Progressbar(main_frame, orient='horizontal', mode='indeterminate')
        self.progress_bar.grid(row=10, column=0, columnspan=3, sticky=tk.EW, pady=2)

        self.status_label = ttk.Label(main_frame, text="状态: 等待操作...", foreground="gray")
        self.status_label.grid(row=11, column=0, columnspan=2, sticky=tk.W, pady=5)

        self.start_btn = ttk.Button(main_frame, text="上云并开始生成", command=self.start_process_thread)
        self.start_btn.grid(row=11, column=2, sticky=tk.E, pady=5)

        # 6. 控制台日志
        ttk.Label(main_frame, text="控制台运行日志详情:").grid(row=12, column=0, sticky=tk.W, pady=(5, 2))
        log_frame = ttk.Frame(main_frame)
        log_frame.grid(row=13, column=0, columnspan=3, sticky=tk.NSEW, pady=2)
        
        self.log_text = tk.Text(log_frame, height=8, width=82, bg="#1e1e1e", fg="#d4d4d4", font=("Consolas", 9))
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=scrollbar.set)
        
        self.log_text.tag_config("info", foreground="#6A9955")
        self.log_text.tag_config("error", foreground="#F44336")
        self.log_text.tag_config("success", foreground="#4CAF50")
        
        self.log("系统就绪。请完善参数后启动流水线。")

    def log(self, message, tag="info"):
        def append():
            self.log_text.config(state=tk.NORMAL)
            self.log_text.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {message}\n", tag)
            self.log_text.config(state=tk.DISABLED)
            self.log_text.see(tk.END)
        self.root.after(0, append)

    def toggle_api_visibility(self):
        self.api_entry.config(show="" if self.show_key_var.get() else "*")

    def load_config(self):
        try:
            if not os.path.exists(self.config_path):
                return {}
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            return config if isinstance(config, dict) else {}
        except Exception:
            return {}

    def save_config(self, show_message=False):
        config = {
            "dashscope_api_key": self.api_key_var.get().strip(),
            "llm_model": self.llm_model_var.get().strip(),
            "oss_access_key_id": self.oss_ak_var.get().strip(),
            "oss_access_key_secret": self.oss_sk_var.get().strip(),
            "oss_endpoint": self.oss_endpoint_var.get().strip(),
            "oss_bucket": self.oss_bucket_var.get().strip(),
        }

        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            self.log("配置已保存，下次启动会自动加载。", "success")
            if show_message:
                messagebox.showinfo("保存成功", f"配置已保存到：\n{self.config_path}")
            return True
        except Exception as e:
            self.log(f"配置保存失败：{e}", "error")
            if show_message:
                messagebox.showerror("保存失败", f"配置保存失败：{e}")
            return False

    def browse_audio(self):
        file_path = filedialog.askopenfilename(title="选择语音文件", filetypes=[("音频文件", "*.mp3 *.wav *.aac *.m4a *.flac"), ("所有文件", "*.*")])
        if file_path:
            self.audio_path_var.set(file_path)
            base, _ = os.path.splitext(file_path)
            self.save_path_var.set(f"{base}_课程笔记.md")

    def browse_save_path(self):
        file_path = filedialog.asksaveasfilename(title="保存笔记为", defaultextension=".md", filetypes=[("Markdown 文件", "*.md")])
        if file_path:
            self.save_path_var.set(file_path)

    def extract_transcript_text(self, json_data):
        if not isinstance(json_data, dict):
            return ""

        if isinstance(json_data.get("text"), str):
            return json_data["text"]

        sentences = json_data.get("sentences")
        if isinstance(sentences, list):
            return "".join(sentence.get("text", "") for sentence in sentences if isinstance(sentence, dict))

        transcripts = json_data.get("transcripts")
        if isinstance(transcripts, list):
            parts = []
            for transcript in transcripts:
                if not isinstance(transcript, dict):
                    continue
                if isinstance(transcript.get("text"), str):
                    parts.append(transcript["text"])
                    continue
                transcript_sentences = transcript.get("sentences")
                if isinstance(transcript_sentences, list):
                    parts.extend(
                        sentence.get("text", "")
                        for sentence in transcript_sentences
                        if isinstance(sentence, dict)
                    )
            return "".join(parts)

        return ""

    def start_process_thread(self):
        if not self.api_key_var.get().strip():
            messagebox.showerror("错误", "请配置百炼 API Key！")
            return
        if not self.oss_ak_var.get().strip() or not self.oss_bucket_var.get().strip():
            messagebox.showerror("错误", "OSS 必填配置项（AK/SK/Bucket）不能为空！")
            return
        if not self.audio_path_var.get().strip() or not os.path.exists(self.audio_path_var.get()):
            messagebox.showerror("错误", "请选择有效的本地语音文件！")
            return

        self.save_config()
        self.start_btn.config(state=tk.DISABLED)
        self.progress_bar.start(10)
        threading.Thread(target=self.working_flow, daemon=True).start()

    def working_flow(self):
        # 参数提取
        api_key = self.api_key_var.get().strip()
        llm_model = self.llm_model_var.get().strip() or "qwen-plus"
        dashscope.api_key = api_key
        local_audio = os.path.abspath(self.audio_path_var.get())
        save_path = os.path.abspath(self.save_path_var.get())
        
        oss_ak = self.oss_ak_var.get().strip()
        oss_sk = self.oss_sk_var.get().strip()
        oss_endpoint = self.oss_endpoint_var.get().strip()
        oss_bucket_name = self.oss_bucket_var.get().strip()
        bucket = None
        oss_object_key = None

        try:
            # --------- 预处理阶段: 上传本地音频到阿里云 OSS ---------
            self.update_status("正在上传本地文件到阿里云 OSS...", "blue")
            file_name = os.path.basename(local_audio)
            oss_object_key = f"fun_asr_tasks/{int(time.time())}_{file_name}"
            
            self.log(f"建立 OSS 连接，正在投递 {file_name} 到 Bucket: {oss_object_key}...")
            auth = oss2.Auth(oss_ak, oss_sk)
            bucket = oss2.Bucket(auth, oss_endpoint, oss_bucket_name)
            
            # 执行文件流式上传
            with open(local_audio, 'rb') as fileobj:
                bucket.put_object(oss_object_key, fileobj)
            
            self.log("OSS 文件同步上传成功！正在生成安全的临时私有访问凭证 URL...")
            # 生成有效期为 1 小时 (3600秒) 的签名 URL 供百炼异步拉取
            oss_download_url = bucket.sign_url('GET', oss_object_key, 3600)
            self.log(f"安全链接生成完毕。")

            # --------- 阶段 1: 严格根据官方规范提交 Fun-ASR 异步转写 ---------
            self.update_status("正在向百炼提交 Fun-ASR 转写任务...", "blue")
            self.log("将 OSS 专属凭证 URL 送入百炼平台...")
            transcript_text = ""
            
            task_response = Transcription.async_call(
                model='fun-asr',  # 标签页指定的非实时识别旗舰模型
                file_urls=[oss_download_url]
            )
            
            if task_response.status_code != HTTPStatus.OK:
                raise Exception(f"提交任务失败：{task_response.message}")
                
            task_id = task_response.output.task_id
            self.log(f"任务已被接收。分配 Task ID: {task_id}")

            # 轮询状态
            while True:
                self.update_status("Fun-ASR 正在后台转写语音...", "blue")
                status_response = Transcription.wait(task=task_id)
                if status_response.status_code == HTTPStatus.OK:
                    task_status = status_response.output.task_status
                    self.log(f"状态轮询 - 服务端状态: {task_status}")
                    
                    if task_status == 'SUCCEEDED':
                        results = status_response.output.results[0]
                        if isinstance(results, dict):
                            transcript_url = results.get("transcription_url")
                        else:
                            transcript_url = getattr(results, "transcription_url", None)
                        
                        if not transcript_url:
                            raise Exception(f"转写成功但未返回 transcription_url，原始结果: {results}")
                        
                        if transcript_url.startswith("http"):
                            self.log("转写成功！正在下载对应的文本数据 JSON...")
                            import requests
                            res = requests.get(transcript_url)
                            res.raise_for_status()
                            res.encoding = 'utf-8'
                            try:
                                json_data = res.json()
                                transcript_text = self.extract_transcript_text(json_data)
                                if not transcript_text.strip():
                                    self.log(f"转写 JSON 未识别到正文，顶层字段: {list(json_data.keys())}", "error")
                            except Exception:
                                transcript_text = res.text
                        break
                    elif task_status in ['FAILED', 'CANCELED']:
                        detailed_msg = getattr(status_response.output, 'message', '未知解码异常')
                        raise Exception(f"Fun-ASR 转换中途遇到内部错误: {detailed_msg}")
                else:
                    raise Exception(f"状态同步连接崩溃: {status_response.message}")
                time.sleep(3)

            if not transcript_text.strip():
                raise Exception("转换成功但未捕捉到有效音轨文字。")

            self.log(f"Fun-ASR 执行圆满成功！转换结果字数: {len(transcript_text)}")

            # --------- 阶段 2: 调用 Qwen 提炼生成高阶笔记 ---------
            self.update_status(f"转写完成！正在通过 {llm_model} 生成精炼笔记...", "blue")
            self.log(f"送入大模型 {llm_model} 清洗口水话并输出 Markdown...")
            
            prompt_text = (
                f"请你将以下语音转写出来的原始文本整理成一份高质量的课程总结笔记。\n"
                f"要求：剔除口水话、结构清晰。包含：1.核心主题 2.重点知识点梳理（使用多级标题和列表） 3.金句或行动建议。\n\n"
                f"【原始文本】：\n{transcript_text}"
            )

            from dashscope import Generation
            qwen_response = Generation.call(
                model=llm_model,
                prompt=prompt_text,
                api_key=api_key
            )

            if qwen_response.status_code == HTTPStatus.OK:
                notes_content = qwen_response.output.text
                with open(save_path, "w", encoding="utf-8") as f:
                    f.write(notes_content)
                self.root.after(0, lambda: self.finish_workflow(True, f"处理完成！笔记已保存至：\n{save_path}"))
            else:
                raise Exception(f"大模型总结失败: {qwen_response.message}")

        except Exception as e:
            error_message = str(e)
            self.log(f"💥 运行异常中断原因：{error_message}", "error")
            self.root.after(0, lambda: self.finish_workflow(False, error_message))
        finally:
            if bucket is not None and oss_object_key:
                try:
                    self.log(f"正在删除 OSS 临时文件: {oss_object_key}")
                    bucket.delete_object(oss_object_key)
                    self.log("OSS 临时文件已删除。", "success")
                except Exception as cleanup_error:
                    self.log(f"OSS 临时文件删除失败: {cleanup_error}", "error")

    def update_status(self, text, color):
        self.root.after(0, lambda: self.status_label.config(text=f"状态: {text}", foreground=color))

    def finish_workflow(self, success, msg):
        self.start_btn.config(state=tk.NORMAL)
        self.progress_bar.stop()
        if success:
            self.status_label.config(text="状态: 笔记生成成功！", foreground="green")
            self.log("🎉 生产级链路闭环成功执行完毕！", "success")
            messagebox.showinfo("成功", msg)
        else:
            self.status_label.config(text="状态: 处理出错。", foreground="red")
            messagebox.showerror("生成失败", "执行失败。底层具体的报错原因已在下方控制台用红色字体打印，请查看。")

if __name__ == "__main__":
    root = tk.Tk()
    app = AudioNotesApp(root)
    root.mainloop()