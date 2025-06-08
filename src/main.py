# -*- coding: utf-8 -*-
"""
拓元搶票助手 v1.0
主程式入口
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import subprocess
import json
import os
import sys
import time
from datetime import datetime


# 加入當前目錄到 Python 路徑
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 修正 import 路徑
try:
    # 直接從當前目錄的子目錄 import
    from api.firebase_client import FirebaseClient
    from utils.ticket_grabber import TicketGrabber
    from utils.device_manager import DeviceManager
except ImportError as e:
    print(f"❌ 無法載入模組: {e}")
    print("請確認檔案結構和 __init__.py 是否存在")
    print("當前工作目錄:", os.getcwd())
    print("Python 路徑:", sys.path[:3])
    
    # 嘗試相對路徑
    try:
        from .api.firebase_client import FirebaseClient
        from .utils.ticket_grabber import TicketGrabber
        from .utils.device_manager import DeviceManager
    except ImportError:
        print("❌ 相對路徑 import 也失敗")
        sys.exit(1)


class TicketGrabberApp:
    def ensure_chromium_installed():
        user_data_dir = os.path.expanduser("~/.cache/ms-playwright")
        if not os.path.exists(user_data_dir):
            print("📦 第一次執行，安裝 Playwright Chromium...")
            try:
                subprocess.run(["playwright", "install", "chromium"], check=True)
            except Exception as e:
                print(f"❌ 安裝 Chromium 失敗: {e}")

    ensure_chromium_installed()


    def __init__(self):
        self.root = tk.Tk()
        self.root.title("tixquic_app v1.0")
        self.root.geometry("800x600")
        self.root.resizable(False, False)
        
        # 設定圖標（如果有的話）
        try:
            if os.path.exists('src/assets/icon.ico'):
                self.root.iconbitmap('src/assets/icon.ico')
        except:
            pass
        
        # 初始化組件
        self.firebase_client = FirebaseClient()
        if DeviceManager:
            self.device_manager = DeviceManager()
        self.ticket_grabber = None
        
        # 狀態變數
        self.is_verified = False
        self.is_running = False
        self.config = None
        self.verification_code = None
        
        # 建立 GUI
        self.setup_gui()
        
    def setup_gui(self):
        """建立使用者介面"""
        # 頂部框架 - 驗證碼輸入
        top_frame = ttk.LabelFrame(self.root, text="步驟 1: 驗證碼驗證", padding=10)
        top_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(top_frame, text="請輸入驗證碼:").grid(row=0, column=0, sticky="w", padx=5)

        self.code_var = tk.StringVar()
        self.code_entry = ttk.Entry(top_frame, textvariable=self.code_var, width=40)
        self.code_entry.grid(row=0, column=1, padx=5)
        self.code_entry.bind('<Return>', lambda e: self.verify_code())

        self.verify_btn = ttk.Button(top_frame, text="驗證", command=self.verify_code)
        self.verify_btn.grid(row=0, column=2, padx=5)

        # 中間框架 - 活動資訊
        middle_frame = ttk.LabelFrame(self.root, text="步驟 2: 活動資訊", padding=10)
        middle_frame.pack(fill="x", padx=10, pady=5)

        self.info_text = scrolledtext.ScrolledText(middle_frame, height=8, width=80, state='disabled')
        self.info_text.pack(fill="both", expand=True)

        # 控制框架
        control_frame = ttk.Frame(self.root)
        control_frame.pack(pady=10)

        self.open_browser_btn = ttk.Button(
            control_frame, 
            text="開啟瀏覽器登入", 
            command=self.open_browser,
            state='disabled'
        )
        self.open_browser_btn.pack(side="left", padx=5)

        self.start_btn = ttk.Button(
            control_frame, 
            text="開始搶票", 
            command=self.start_grabbing,
            state='disabled'
        )
        self.start_btn.pack(side="left", padx=5)

        self.stop_btn = ttk.Button(
            control_frame, 
            text="停止", 
            command=self.stop_grabbing,
            state='disabled'
        )
        self.stop_btn.pack(side="left", padx=5)

        # OCR 嘗試次數欄位
        ttk.Label(control_frame, text="OCR 嘗試次數：").pack(side="left", padx=5)
        self.ocr_attempts_var = tk.IntVar(value=3)
        self.ocr_entry = ttk.Entry(control_frame, textvariable=self.ocr_attempts_var, width=5)
        self.ocr_entry.pack(side="left")
        
        # reload 設定
        ttk.Label(control_frame, text="Reload 間隔秒數：").pack(side="left", padx=(20, 5))
        self.reload_interval_var = tk.IntVar(value=3)
        self.reload_interval_entry = ttk.Entry(control_frame, textvariable=self.reload_interval_var, width=5)
        self.reload_interval_entry.pack(side="left")

        # 底部框架 - 執行日誌
        bottom_frame = ttk.LabelFrame(self.root, text="執行日誌", padding=10)
        bottom_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.log_text = scrolledtext.ScrolledText(bottom_frame, height=15)
        self.log_text.pack(fill="both", expand=True)

        # 狀態列
        self.status_var = tk.StringVar(value="請輸入驗證碼開始")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief="sunken")
        status_bar.pack(fill="x", side="bottom")
   
    def verify_code(self):
        """驗證驗證碼"""
        code = self.code_var.get().strip()
        if not code:
            messagebox.showwarning("警告", "請輸入驗證碼")
            return
        
        self.verification_code = code
        self.log("🔍 正在驗證驗證碼...")
        self.verify_btn.config(state='disabled')
        self.status_var.set("驗證中...")
        
        # 在背景執行緒中執行驗證
        thread = threading.Thread(target=self._verify_code_async, args=(code,))
        thread.daemon = True
        thread.start()
        
    def _verify_code_async(self, code):
        """非同步驗證驗證碼"""
        try:
            result = self.firebase_client.verify_and_fetch_config(code)
            
            if result['success']:
                self.config = result['data']
                self.is_verified = True
                self.root.after(0, self._on_verify_success)
            elif result.get('can_force_unbind'):
                # 可以強制解綁的情況
                self.root.after(0, lambda: self._handle_force_unbind(result))
            else:
                self.root.after(0, lambda: self._on_verify_error(result['message']))
                
        except Exception as e:
            self.root.after(0, lambda: self._on_verify_error(str(e)))
    
    def _handle_force_unbind(self, result):
        """處理強制解綁的情況"""
        binding_info = result.get('binding_info', {})
        suggestions = binding_info.get('suggestions', [])
        
        message = f"{result['message']}\n\n建議解決方案:\n"
        for i, suggestion in enumerate(suggestions, 1):
            message += f"{i}. {suggestion}\n"
        
        message += "\n是否要強制解綁並在此設備使用？"
        
        if messagebox.askyesno("設備綁定衝突", message):
            self.log("🔄 正在強制解綁...")
            self.verify_btn.config(state='disabled')
            
            # 重新驗證並強制解綁
            thread = threading.Thread(
                target=self._verify_code_with_force_unbind, 
                args=(self.verification_code,)
            )
            thread.daemon = True
            thread.start()
        else:
            self.verify_btn.config(state='normal')
            self.status_var.set("驗證失敗")
    
    def _verify_code_with_force_unbind(self, code):
        """強制解綁重新驗證"""
        try:
            result = self.firebase_client.verify_and_fetch_config(code, force_unbind=True)
            
            if result['success']:
                self.config = result['data']
                self.is_verified = True
                self.root.after(0, self._on_verify_success)
            else:
                self.root.after(0, lambda: self._on_verify_error(result['message']))
                
        except Exception as e:
            self.root.after(0, lambda: self._on_verify_error(str(e)))

    def _on_verify_success(self):
        """驗證成功的處理"""
        self.log("✅ 驗證成功！")
        self.status_var.set("驗證成功")

        # 從 preferences 中取正確格式的值
        prefs = self.config.get('preferences', {})
        seat_list = prefs.get('preferredKeywords', ['自動選擇'])
        ticket_count = int(prefs.get('preferredNumbers', 1))
        session_index = int(prefs.get('preferredIndex', 1))
        
        # 顯示綁定策略信息
        binding_info = self.config.get('bindingInfo', {})
        policy = binding_info.get('policy', 'strict')
        device_id = binding_info.get('deviceId', 'unknown')
        
        policy_text = {
            'strict': '嚴格模式（單設備綁定）',
            'flexible': '彈性模式（可切換設備）',
            'unlimited': '無限制模式'
        }.get(policy, policy)

        info = f"""
活動名稱: {self.config['event']['name']}
活動場地: {self.config['event']['venue']}
搶票網址: {self.config['event']['activityUrl']}
搶票時間: {self.config['event']['actualTicketTime']}

您的偏好設定:
- 優先票區: {', '.join(seat_list)}
- 購買張數: {ticket_count}
- 按鈕順序: 第 {session_index} 個

設備綁定狀態:
- 綁定策略: {policy_text}
- 設備ID: {device_id[:16]}...
        """

        self.info_text.config(state='normal')
        self.info_text.delete(1.0, tk.END)
        self.info_text.insert(1.0, info)
        self.info_text.config(state='disabled')

        self.open_browser_btn.config(state='normal')
        self.start_btn.config(state='normal')

        self.update_countdown()

    def _on_verify_error(self, error_msg):
        """驗證失敗的處理"""
        self.log(f"❌ 驗證失敗: {error_msg}")
        self.status_var.set("驗證失敗")
        messagebox.showerror("錯誤", error_msg)
        self.verify_btn.config(state='normal')
        
    def open_browser(self):
        """開啟瀏覽器登入頁面"""
        try:
            import shutil

            # 嘗試找到 chrome 可執行檔
            chrome_path = shutil.which("chrome") or shutil.which("chrome.exe")
            if not chrome_path:
                # fallback: 常見路徑
                default_paths = [
                    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
                    "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe"
                ]
                for path in default_paths:
                    if os.path.exists(path):
                        chrome_path = path
                        break

            if not chrome_path:
                raise FileNotFoundError("找不到 Chrome 瀏覽器，請確認已安裝")

            cmd = [
                chrome_path,
                "--remote-debugging-port=9222",
                "--user-data-dir=C:\\chrome_debug"
            ]
            subprocess.Popen(cmd)
            self.log("✅ 瀏覽器已開啟，請登入您的拓元帳號")
            messagebox.showinfo("提示", "瀏覽器已開啟，請先登入您的拓元帳號！")

        except Exception as e:
            self.log(f"❌ 開啟瀏覽器失敗: {str(e)}")
            messagebox.showerror("錯誤", f"開啟瀏覽器失敗: {str(e)}")

            
    def update_countdown(self):
        """更新倒數計時"""
        if not self.is_verified or self.is_running:
            return
            
        try:
            ticket_time_str = self.config['event'].get('actualTicketTime')
            if not ticket_time_str:
                return
                
            # 解析時間（處理不同格式）
            if 'T' in ticket_time_str:
                ticket_time = datetime.fromisoformat(ticket_time_str.replace('Z', ''))
            else:
                ticket_time = datetime.strptime(ticket_time_str, "%Y-%m-%d %H:%M:%S")
                
            now = datetime.now()
            diff = (ticket_time - now).total_seconds()
            
            if diff > 0:
                hours = int(diff // 3600)
                minutes = int((diff % 3600) // 60)
                seconds = int(diff % 60)
                countdown_str = f"距離開搶: {hours:02d}:{minutes:02d}:{seconds:02d}"
                self.status_var.set(countdown_str)
                self.root.after(1000, self.update_countdown)
            else:
                self.status_var.set("搶票時間已到！")
                
        except Exception as e:
            self.log(f"倒數計時錯誤: {str(e)}")
            
    def start_grabbing(self):
        """開始搶票"""
        if not self.is_verified:
            messagebox.showwarning("警告", "請先驗證驗證碼")
            return
            
        self.is_running = True
        self.start_btn.config(state='disabled')
        self.stop_btn.config(state='normal')
        self.open_browser_btn.config(state='disabled')
        self.log("🚀 開始執行搶票程式...")
        
        # 檢查 API Key
        api_key = self.config.get('apiKey', '')
        if api_key:
            self.log(f"🔑 已載入 OpenAI API Key (前10碼: {api_key[:10]}...)")
        else:
            self.log("⚠️ 未找到 OpenAI API Key")
        
        # 建立搶票器實例
        self.ticket_grabber = TicketGrabber(
            config=self.config,
            api_key=api_key,
            log_callback=self.log,
            max_ocr_attempts=self.ocr_attempts_var.get(),
            reload_interval=self.reload_interval_var.get(),
        )
        
        # 在背景執行緒中執行搶票
        thread = threading.Thread(target=self._run_grabber)
        thread.daemon = True
        thread.start()
        
    def _run_grabber(self):
        """執行搶票"""
        try:
            success = self.ticket_grabber.run()
            
            # 搶票完成後標記為已使用
            if self.verification_code:
                details = {
                    "success": success,
                    "completion_time": time.time()
                }
                self.firebase_client.mark_code_as_used(
                    self.verification_code, 
                    "completed" if success else "failed",
                    details
                )
                
        except Exception as e:
            self.log(f"❌ 搶票過程發生錯誤: {str(e)}")
        finally:
            self.root.after(0, self._on_grabbing_complete)
            
    def _on_grabbing_complete(self):
        """搶票完成後的處理"""
        self.is_running = False
        self.start_btn.config(state='normal')
        self.stop_btn.config(state='disabled')
        self.open_browser_btn.config(state='normal')
        self.log("🏁 搶票程式執行完畢")
        
    def stop_grabbing(self):
        """停止搶票"""
        if self.ticket_grabber:
            self.ticket_grabber.stop()
        self.is_running = False
        self.start_btn.config(state='normal')
        self.stop_btn.config(state='disabled')
        self.open_browser_btn.config(state='normal')
        self.log("⏹️ 已停止搶票")
        
    def log(self, message):
        """寫入日誌"""
        timestamp = datetime.now().strftime("[%H:%M:%S]")
        log_message = f"{timestamp} {message}\n"
        
        self.log_text.insert(tk.END, log_message)
        self.log_text.see(tk.END)
        self.root.update_idletasks()
        
    def run(self):
        """執行主程式"""
        self.log("🎫 拓元搶票助手 v1.0 啟動成功")
        self.log("📝 請輸入驗證碼開始使用")
        self.root.mainloop()

if __name__ == "__main__":
    app = TicketGrabberApp()
    app.run()