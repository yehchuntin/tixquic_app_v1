# -*- coding: utf-8 -*-
"""
優化版搶票核心邏輯 - 修復版本
重點修復驗證碼處理和表單送出問題
"""

import datetime
import time
import base64
import re
import os
import sys
import threading
import asyncio
# 處理不同版本的 OpenAI import
try:
    from openai import OpenAI  # 新版 OpenAI 套件 (>= 1.0)
    NEW_OPENAI = True
except ImportError:
    try:
        import openai  # 舊版 OpenAI 套件
        NEW_OPENAI = False
        OpenAI = None
    except ImportError:
        print("❌ 無法找到 OpenAI 套件，請安裝: pip install openai")
        raise
from typing import Dict, Any, Callable, Optional

class OptimizedTicketGrabber:
    def __init__(self, config: Dict[str, Any], api_key: str, log_callback: Callable[[str], None], max_ocr_attempts: int = 3, reload_interval: float = 1.0):
        self.config = config
        self.log = log_callback
        self.is_running = True
        self.max_ocr_attempts = max_ocr_attempts
        self.reload_interval = reload_interval

        # 根據 OpenAI 版本設定客戶端
        if NEW_OPENAI:
            self.openai_client = OpenAI(api_key=api_key)
        else:
            # 舊版 API 設定
            openai.api_key = api_key
            self.openai_client = None

        event = config['event']
        prefs = config.get('preferences', {})
        self.activity_url = event['activityUrl']
        self.ticket_time_str = event['actualTicketTime']
        self.event_name = event['name']
        self.preferred_keywords = prefs.get('preferredKeywords', ['自動選擇'])
        self.preferred_numbers = int(prefs.get('preferredNumbers', 1))
        self.preferred_index = int(prefs.get('preferredIndex', 1))
        self.network_speed = 'unknown'
        self.check_interval = 0.1  # 🚀 縮短檢查間隔到 0.1 秒
        
        # 🚀 新增：優化參數
        self.purchase_button_found = False
        self.pre_sale_refresh_count = 0
        self.last_refresh_time = 0
        
        # 🕐 時間追蹤參數
        self.ticket_start_time = None  # 點擊立即訂購的時間
        self.form_completion_time = None  # 表單完成時間

    def run(self) -> bool:
        """執行搶票，返回是否成功"""
        success = False
        
        try:
            sale_time = self._parse_ticket_time() or datetime.datetime.now()
            now = datetime.datetime.now()
            if sale_time < now:
                self.log("⚠️ 搶票時間已過，仍繼續執行")
            self.log(f"🎯 活動: {self.event_name} ⏰ 搶票時間: {sale_time}")
            
            # 🔧 修正：安全地初始化 Playwright
            browser = self._initialize_playwright_safely()
            if not browser:
                self.log("❌ 無法初始化 Playwright 或連接瀏覽器")
                return False
            
            try:
                # 使用現有的瀏覽器上下文和頁面
                context = browser.contexts[0] if browser.contexts else None
                if not context:
                    self.log("❌ 找不到瀏覽器上下文")
                    return False
                
                page = context.pages[0] if context.pages else context.new_page()
                
                self._initial_load_and_test_speed(page)
                self._smart_wait_for_sale_optimized(page, sale_time)
                
                if not self.is_running: 
                    return False
                    
                success = self._execute_ticket_grab_optimized(page)
                
            finally:
                # 確保清理資源
                try:
                    if hasattr(self, '_playwright_instance'):
                        self._playwright_instance.stop()
                except:
                    pass
                
        except Exception as e:
            self.log(f"❌ 錯誤: {str(e)}")
            
        # 🏁 最終結果顯示
        if self.ticket_start_time:
            total_elapsed = time.time() - self.ticket_start_time
            if success:
                self.log(f"🎉 搶票成功！總耗時：{total_elapsed:.2f} 秒")
            else:
                self.log(f"😞 搶票失敗，總耗時：{total_elapsed:.2f} 秒")
        else:
            self.log("🏁 搶票程序結束")
            
        return success

    def _initialize_playwright_safely(self):
        """安全地初始化 Playwright"""
        
        # 嘗試方法1: 設定 Playwright 環境變數
        try:
            self.log("🔧 設定 Playwright 環境...")
            
            # 檢測編譯環境
            if hasattr(sys, 'frozen') or hasattr(sys, '_MEIPASS'):
                # 編譯版本，設定 Playwright 路徑
                if hasattr(sys, '_MEIPASS'):
                    # PyInstaller
                    base_dir = sys._MEIPASS
                else:
                    # Nuitka
                    base_dir = os.path.dirname(sys.executable)
                
                playwright_dir = os.path.join(base_dir, "_internal")
                if os.path.exists(playwright_dir):
                    os.environ['PLAYWRIGHT_BROWSERS_PATH'] = playwright_dir
                    self.log(f"📁 設定 Playwright 路徑: {playwright_dir}")
        except Exception as e:
            self.log(f"⚠️ 設定 Playwright 環境失敗: {e}")
        
        # 嘗試方法2: 導入並初始化 Playwright
        try:
            self.log("🎭 嘗試初始化 Playwright...")
            from playwright.sync_api import sync_playwright
            
            self._playwright_instance = sync_playwright().start()
            browser = self._connect_to_browser_with_playwright(self._playwright_instance)
            
            if browser:
                return browser
                
        except Exception as e:
            self.log(f"❌ Playwright 初始化失敗: {str(e)}")
        
        return None

    def _connect_to_browser_with_playwright(self, p):
        """使用 Playwright 連接到瀏覽器"""
        
        # 嘗試多個常見的 CDP 端口
        cdp_endpoints = [
            "http://localhost:9222",
            "http://127.0.0.1:9222",
            "http://localhost:9223",
            "http://127.0.0.1:9223"
        ]
        
        for endpoint in cdp_endpoints:
            try:
                self.log(f"🔍 嘗試連接瀏覽器: {endpoint}")
                browser = p.chromium.connect_over_cdp(endpoint)
                self.log("✅ 成功連接到現有瀏覽器")
                return browser
            except Exception as e:
                self.log(f"⚠️ 連接失敗: {endpoint} - {str(e)}")
                continue
        
        return None

    def _initial_load_and_test_speed(self, page):
        """初始載入並測試網速"""
        self.log("📡 測試網速中...")
        start = time.time()
        try:
            # 檢查當前頁面是否已經是目標頁面
            current_url = page.url
            if self.activity_url in current_url:
                self.log("✅ 已在目標頁面")
                load_time = 0.1  # 假設很快
            else:
                page.goto(self.activity_url, wait_until="domcontentloaded", timeout=30000)
                load_time = time.time() - start
                
            # 🚀 根據網速調整策略
            self.network_speed = 'fast' if load_time < 0.8 else 'medium' if load_time < 2 else 'slow'
            self.log(f"🚀 網速為：{self.network_speed}")
            
            # 根據網速調整刷新間隔
            if self.network_speed == 'fast':
                self.reload_interval = 0.8  # 快速網路：0.8秒
            elif self.network_speed == 'medium':
                self.reload_interval = 1.2  # 中等網路：1.2秒
            else:
                self.reload_interval = 2.0  # 慢速網路：2秒
                
            self.log(f"⚙️ 刷新間隔調整為：{self.reload_interval} 秒")
            
        except Exception as e:
            self.log(f"⚠️ 載入頁面失敗: {str(e)}")
            try:
                page.goto(self.activity_url, timeout=15000)
                self.log("✅ 重新載入成功")
            except:
                self.log("❌ 重新載入也失敗")
                raise

    def _smart_wait_for_sale_optimized(self, page, sale_time):
        """優化的智能等待開賣時間 - 精確刷新策略"""
        self.log("⏳ 優化等待開賣...")

        # 🚀 根據網速計算最佳刷新時機
        if self.network_speed == 'fast':
            refresh_before_seconds = 1.0    # 快速網路：開賣前1秒刷新
            final_refresh_before = 0.3      # 最後刷新：開賣前0.3秒
        elif self.network_speed == 'medium':
            refresh_before_seconds = 1.5    # 中等網路：開賣前1.5秒刷新
            final_refresh_before = 0.5      # 最後刷新：開賣前0.5秒
        else:
            refresh_before_seconds = 2.0    # 慢速網路：開賣前2秒刷新
            final_refresh_before = 0.8      # 最後刷新：開賣前0.8秒
        
        self.log(f"⚙️ 網速: {self.network_speed} | 最後刷新時機: 開賣前{final_refresh_before}秒")

        reload_count = 0
        last_major_refresh = 0
        final_refresh_done = False
        
        while self.is_running:
            now = datetime.datetime.now()
            remaining = (sale_time - now).total_seconds()

            # 🚀 階段1：開賣前30秒，增加檢查頻率
            if remaining <= 30 and remaining > refresh_before_seconds:
                self.log(f"🔥 進入高頻檢查模式 (剩餘 {remaining:.1f} 秒)")
                current_time = time.time()
                
                # 高頻刷新
                if current_time - last_major_refresh >= (self.reload_interval * 0.7):
                    self.log(f"⏳ 距離開賣 {remaining:.1f} 秒，第 {reload_count + 1} 次刷新")
                    try:
                        page.reload(wait_until="domcontentloaded", timeout=3000)
                        last_major_refresh = current_time
                        reload_count += 1
                    except Exception as e:
                        self.log(f"⚠️ 刷新錯誤：{e}")
                
                # 在刷新間隔檢查按鈕
                if self._quick_button_check(page):
                    self.log("🎯 提前發現購票按鈕！")
                    break
                    
                time.sleep(0.1)
                continue

            # 🚀 階段2：開賣前關鍵時刻，停止常規刷新，準備精確刷新
            elif remaining <= refresh_before_seconds and remaining > final_refresh_before:
                if not final_refresh_done:
                    self.log(f"⚡ 進入精確等待模式 (剩餘 {remaining:.1f} 秒)")
                    self.log(f"🎯 將在開賣前 {final_refresh_before} 秒執行最後刷新")
                
                # 高頻檢查按鈕（可能提前出現）
                if self._quick_button_check(page):
                    self.log("🎯 關鍵時刻發現購票按鈕！")
                    break
                    
                time.sleep(0.05)  # 每0.05秒檢查
                continue

            # 🚀 階段3：執行開賣前最後刷新
            elif remaining <= final_refresh_before and remaining > -0.5 and not final_refresh_done:
                self.log(f"🔥 執行開賣前最後刷新！(剩餘 {remaining:.2f} 秒)")
                try:
                    refresh_start = time.time()
                    page.reload(wait_until="domcontentloaded", timeout=2000)
                    refresh_end = time.time()
                    refresh_duration = refresh_end - refresh_start
                    self.log(f"✅ 最後刷新完成，耗時 {refresh_duration:.2f} 秒")
                    final_refresh_done = True
                except Exception as e:
                    self.log(f"❌ 最後刷新失敗: {e}")
                    final_refresh_done = True  # 標記為已完成，避免重複嘗試
                
                # 立即檢查按鈕
                if self._quick_button_check(page):
                    self.log("🎯 最後刷新後立即發現按鈕！")
                    break
                continue

            # 🚀 階段4：開賣時間已到，超高頻檢測
            elif remaining <= 0:
                self.log("🕐 搶票時間已到！開始超高速檢測")
                break
            
            # 🚀 正常階段：常規刷新
            else:
                current_time = time.time()
                if current_time - last_major_refresh >= self.reload_interval:
                    self.log(f"⏳ 距離開賣 {remaining:.1f} 秒，第 {reload_count + 1} 次刷新")
                    try:
                        page.reload(wait_until="domcontentloaded", timeout=3000)
                        last_major_refresh = current_time
                        reload_count += 1
                    except Exception as e:
                        self.log(f"⚠️ 刷新錯誤：{e}")

                # 在刷新間隔中也檢查按鈕
                if self._quick_button_check(page):
                    self.log("🎯 常規檢查發現購票按鈕！")
                    break
                    
                time.sleep(0.1)

        # 🚀 最終極的按鈕搜尋（開賣後）
        self._final_button_hunt_precise(page)

    def _final_button_hunt_precise(self, page):
        """開賣後的精確按鈕搜尋 - 多重保險機制"""
        self.log("🔍 開始開賣後精確搜尋...")
        hunt_start_time = time.time()
        
        # 🚀 保險機制1：開賣後立即補充刷新
        try:
            current_time = time.time()
            self.log("🔄 保險刷新1：開賣後立即刷新")
            page.reload(wait_until="domcontentloaded", timeout=1500)
            refresh_time = time.time() - current_time
            self.log(f"⚡ 保險刷新1完成，耗時 {refresh_time:.2f} 秒")
        except Exception as e:
            self.log(f"⚠️ 保險刷新1失敗: {e}")
        
        # 🚀 保險機制2：多重刷新時機點 - 更積極的策略
        refresh_points = [2, 5, 8, 12, 16, 20]  # 開賣後第2、5、8、12、16、20秒刷新
        last_refresh_time = time.time()
        button_check_count = 0
        
        # 超高頻搜尋 - 延長搜尋時間
        for hunt_round in range(300):  # 增加到300次 (約24秒)
            if not self.is_running:
                return

            try:
                # 🚀 多策略同時檢查
                found = self._multi_strategy_button_check(page)
                if found:
                    total_hunt_time = time.time() - hunt_start_time
                    self.log(f"🎯 第 {hunt_round + 1} 輪發現購票按鈕！(搜尋耗時: {total_hunt_time:.2f}秒)")
                    return
                
                button_check_count += 1
                
                # 🛡️ 保險機制：定時刷新 - 更頻繁
                current_time = time.time()
                elapsed_since_start = current_time - last_refresh_time
                
                for refresh_point in refresh_points:
                    if (elapsed_since_start >= refresh_point and 
                        elapsed_since_start < refresh_point + 0.3):  # 0.3秒內執行
                        try:
                            self.log(f"🛡️ 保險刷新：開賣後第 {refresh_point} 秒")
                            refresh_start = time.time()
                            page.reload(wait_until="domcontentloaded", timeout=1200)
                            refresh_duration = time.time() - refresh_start
                            self.log(f"✅ 第 {refresh_point} 秒保險刷新完成，耗時: {refresh_duration:.2f}秒")
                            time.sleep(0.1)  # 刷新後短暫等待
                            break
                        except Exception as e:
                            self.log(f"⚠️ 第 {refresh_point} 秒保險刷新失敗: {e}")
                
                # 🛡️ 保險機制：每50次檢查額外刷新
                if hunt_round > 0 and hunt_round % 50 == 0:
                    self.log(f"🔄 第 {hunt_round} 輪，執行循環保險刷新")
                    try:
                        refresh_start = time.time()
                        page.reload(wait_until="domcontentloaded", timeout=1000)
                        refresh_duration = time.time() - refresh_start
                        self.log(f"✅ 第 {hunt_round} 輪循環刷新完成，耗時: {refresh_duration:.2f}秒")
                    except:
                        self.log(f"⚠️ 第 {hunt_round} 輪循環刷新失敗")
                
                # 🚀 智能檢測：如果長時間沒找到，加強刷新
                if hunt_round == 125:  # 約10秒後
                    self.log("🚨 超過10秒未發現按鈕，執行強制大刷新")
                    try:
                        # 清除緩存的強制刷新
                        page.evaluate("location.reload(true);")
                        time.sleep(1)
                        self.log("✅ 強制大刷新完成")
                    except Exception as e:
                        self.log(f"⚠️ 強制大刷新失敗: {e}")
                
                # 🚀 動態調整檢測頻率
                if hunt_round < 50:
                    # 前5秒：極高頻檢測
                    sleep_time = 0.05
                elif hunt_round < 150:
                    # 5-15秒：高頻檢測  
                    sleep_time = 0.08
                else:
                    # 15秒後：中頻檢測
                    sleep_time = 0.1
                
                # 每20次顯示進度
                if hunt_round % 20 == 0:
                    elapsed = time.time() - hunt_start_time
                    self.log(f"🔍 精確搜尋中... (第{hunt_round + 1}輪, 已搜尋{elapsed:.1f}秒, 檢查{button_check_count}次)")
                
                time.sleep(sleep_time)
                
            except Exception as e:
                self.log(f"⚠️ 精確搜尋錯誤：{str(e)}")
                time.sleep(0.1)

        total_hunt_time = time.time() - hunt_start_time
        self.log(f"⚠️ 精確搜尋完成，未發現購票按鈕 (總搜尋時間: {total_hunt_time:.2f}秒，檢查{button_check_count}次)")
        
        # 🛡️ 最後保險：終極刷新嘗試
        self.log("🚨 執行最後保險刷新")
        try:
            page.goto(page.url, wait_until="domcontentloaded", timeout=3000)
            self.log("✅ 最後保險刷新完成")
            
            # 最後檢查一次
            if self._multi_strategy_button_check(page):
                total_time = time.time() - hunt_start_time
                self.log(f"🎯 最後保險刷新發現按鈕！(總時間: {total_time:.2f}秒)")
        except Exception as e:
            self.log(f"⚠️ 最後保險刷新失敗: {e}")

    def _quick_button_check(self, page):
        """快速按鈕檢查"""
        try:
            # 🚀 多種檢查方式
            selectors_to_check = [
                'button:has-text("立即訂購")',
                'button:has-text("馬上訂購")',
                'a:has-text("立即訂購")',
                'input[value*="立即訂購"]',
                '[onclick*="訂購"]'
            ]
            
            for selector in selectors_to_check:
                try:
                    if page.locator(selector).count() > 0:
                        return True
                except:
                    continue
            
            # 備用 JavaScript 檢查
            found = page.evaluate("""
                () => {
                    const buttons = document.querySelectorAll('button, a, input[type="button"], input[type="submit"]');
                    return Array.from(buttons).some(btn => {
                        const text = (btn.innerText || btn.value || '').toLowerCase();
                        return text.includes('立即訂購') || text.includes('馬上訂購') || text.includes('購買');
                    });
                }
            """)
            return found
            
        except Exception as e:
            return False

    def _multi_strategy_button_check(self, page):
        """多策略按鈕檢查"""
        strategies = [
            # 策略1：文字檢查
            lambda: page.evaluate("""
                () => {
                    const buttons = document.querySelectorAll('button, a, input');
                    return Array.from(buttons).some(b => 
                        (b.innerText || b.value || '').includes('立即訂購')
                    );
                }
            """),
            
            # 策略2：Class 檢查
            lambda: page.evaluate("""
                () => {
                    const buttons = document.querySelectorAll('[class*="buy"], [class*="purchase"], [class*="order"]');
                    return buttons.length > 0;
                }
            """),
            
            # 策略3：可見性檢查
            lambda: page.locator('button:visible, a:visible').filter(has_text="訂購").count() > 0
        ]
        
        for i, strategy in enumerate(strategies):
            try:
                if strategy():
                    self.log(f"✅ 策略 {i+1} 發現按鈕")
                    return True
            except:
                continue
        
        return False

    def _execute_ticket_grab_optimized(self, page) -> bool:
        """優化的執行搶票流程"""
        self.log("🚀 開始優化搶票...")
        
        # 🚀 優化1：預先準備點擊策略
        click_strategies = [
            # 策略1：精確文字匹配
            lambda: self._try_click_by_text(page, ["text=立即訂購", "text=馬上訂購"]),
            # 策略2：包含文字匹配
            lambda: self._try_click_by_contains(page, ["訂購", "購買"]),
            # 策略3：按鈕類型匹配
            lambda: self._try_click_by_button_type(page),
            # 策略4：JavaScript 強制點擊
            lambda: self._try_force_click_js(page)
        ]
        
        # 嘗試所有策略
        for i, strategy in enumerate(click_strategies):
            try:
                self.log(f"🔄 嘗試點擊策略 {i+1}...")
                if strategy():
                    # 🕐 記錄點擊立即訂購的時間點
                    self.ticket_start_time = time.time()
                    self.log(f"✅ 策略 {i+1} 成功點擊購票按鈕")
                    self.log(f"⏰ 開始計時：{datetime.datetime.now().strftime('%H:%M:%S.%f')[:-3]}")
                    
                    return self._select_and_fill_optimized(page)
            except Exception as e:
                self.log(f"⚠️ 策略 {i+1} 失敗: {str(e)}")
                continue
        
        self.log("❌ 所有點擊策略都失敗了")
        return False

    def _try_click_by_text(self, page, selectors):
        """按文字點擊"""
        for sel in selectors:
            try:
                btns = page.locator(sel)
                if btns.count() > 0:
                    btns.nth(min(self.preferred_index - 1, btns.count() - 1)).click(force=True, timeout=1000)
                    return True
            except:
                continue
        return False

    def _try_click_by_contains(self, page, keywords):
        """按包含文字點擊"""
        for keyword in keywords:
            try:
                buttons = page.locator(f'button:has-text("{keyword}"), a:has-text("{keyword}")')
                if buttons.count() > 0:
                    buttons.first.click(force=True, timeout=1000)
                    return True
            except:
                continue
        return False

    def _try_click_by_button_type(self, page):
        """按按鈕類型點擊"""
        try:
            # 尋找看起來像購買按鈕的元素
            found = page.evaluate("""
                () => {
                    const buttons = document.querySelectorAll('button, a, input[type="button"]');
                    for (let btn of buttons) {
                        const text = (btn.innerText || btn.value || '').toLowerCase();
                        const className = (btn.className || '').toLowerCase();
                        
                        if (text.includes('訂購') || text.includes('購買') || 
                            className.includes('buy') || className.includes('purchase')) {
                            btn.click();
                            return true;
                        }
                    }
                    return false;
                }
            """)
            return found
        except:
            return False

    def _try_force_click_js(self, page):
        """JavaScript 強制點擊"""
        try:
            return page.evaluate("""
                () => {
                    // 最強力的點擊嘗試
                    const allElements = document.querySelectorAll('*');
                    const keywords = ['立即訂購', '馬上訂購', '購買', 'buy'];
                    
                    for (let el of allElements) {
                        const text = (el.innerText || el.textContent || el.value || '').toLowerCase();
                        if (keywords.some(keyword => text.includes(keyword.toLowerCase()))) {
                            // 嘗試多種點擊方式
                            try {
                                el.click();
                                return true;
                            } catch (e) {
                                try {
                                    const event = new MouseEvent('click', { bubbles: true });
                                    el.dispatchEvent(event);
                                    return true;
                                } catch (e2) {
                                    // 最後嘗試
                                    if (el.onclick) {
                                        el.onclick();
                                        return true;
                                    }
                                }
                            }
                        }
                    }
                    return false;
                }
            """)
        except:
            return False

    def _select_and_fill_optimized(self, page) -> bool:
        """優化的選擇票區並處理驗證碼"""
        self.log("🎫 優化選擇票區...")
        
        try:
            # 🚀 縮短等待時間
            page.wait_for_selector("li.select_form_b, li.select_form_a", timeout=2000)
        except:
            # 🚀 如果標準選擇器沒找到，嘗試其他可能的選擇器
            try:
                page.wait_for_selector("li[class*='select'], .ticket-area, .seat-area", timeout=1000)
            except:
                self.log("❌ 等待票區選單超時")
                return False
            
        items = page.locator("li.select_form_b, li.select_form_a")
        found = False

        # 🚀 快速選擇票區
        for i in range(items.count()):
            html = items.nth(i).inner_html()
            if "已售完" not in html and any(k in html for k in self.preferred_keywords):
                items.nth(i).click(force=True)
                self.log(f"✅ 選擇票區: {self.preferred_keywords}")
                found = True
                break

        if not found:
            # 🚀 如果沒找到偏好票區，選擇第一個可用的
            for i in range(items.count()):
                html = items.nth(i).inner_html()
                if "已售完" not in html:
                    items.nth(i).click(force=True)
                    self.log(f"✅ 選擇第一個可用票區")
                    found = True
                    break

        if not found:
            self.log("❌ 沒有可選票區")
            return False

        time.sleep(0.1)  # 縮短等待時間

        # 🚀 優化的驗證碼處理
        return self._handle_verification_optimized(page)

    def _handle_verification_optimized(self, page):
        """🔧 修復版本 - 優化的驗證碼處理 + 錯誤重試機制"""
        # 計算從點擊立即訂購到開始處理驗證碼的時間
        if self.ticket_start_time:
            elapsed_to_verification = time.time() - self.ticket_start_time
            self.log(f"📊 從點擊立即訂購到開始驗證碼處理: {elapsed_to_verification:.2f} 秒")
        
        for attempt in range(self.max_ocr_attempts):
            attempt_start_time = time.time()
            try:
                self.log(f"🔄 第 {attempt + 1}/{self.max_ocr_attempts} 次嘗試...")

                # 🔧 修復1：改善同意條款處理
                try:
                    # 先嘗試找到數量選擇
                    select_elements = page.locator("select[name^='TicketForm[ticketPrice]']")
                    if select_elements.count() > 0:
                        page.select_option("select[name^='TicketForm[ticketPrice]']", str(self.preferred_numbers))
                        self.log(f"✅ 選擇票數: {self.preferred_numbers}")
                    
                    # 同意條款處理 - 更穩定的方式
                    agree_checkbox = page.locator("input[name='TicketForm[agree]']")
                    if agree_checkbox.count() > 0 and not agree_checkbox.is_checked():
                        agree_checkbox.check(force=True)
                        self.log("✅ 已勾選同意條款")
                        
                except Exception as e:
                    self.log(f"⚠️ 選擇票數或同意條款時發生問題: {e}")

                # 🔧 修復2：改善驗證碼處理
                captcha_text = self._handle_captcha_fast(page)
                if not captcha_text:
                    self.log("❌ 驗證碼處理失敗，重試")
                    # 🔧 在重試前稍作等待，讓頁面穩定
                    time.sleep(0.5)
                    continue

                # 🔧 修復3：更穩定的驗證碼填入
                try:
                    captcha_input = page.locator("#TicketForm_verifyCode")
                    if captcha_input.count() > 0:
                        # 先清空欄位
                        captcha_input.clear()
                        time.sleep(0.1)
                        # 再填入驗證碼
                        captcha_input.fill(captcha_text, force=True)
                        self.log(f"✍️ 填入驗證碼: {captcha_text}")
                    else:
                        self.log("❌ 找不到驗證碼輸入欄位")
                        continue
                except Exception as e:
                    self.log(f"❌ 填入驗證碼失敗: {e}")
                    continue

                # 🔧 修復4：改善表單送出處理
                current_url = page.url
                submit_success = self._submit_form_with_validation(page)
                
                if not submit_success:
                    self.log("❌ 送出表單失敗")
                    continue

                # 🔧 修復5：改善結果檢測 - 更準確的成功判斷
                success_detected = self._wait_for_form_result(page, current_url)
                
                # 計算當前嘗試的總時間
                attempt_duration = time.time() - attempt_start_time
                total_elapsed = time.time() - self.ticket_start_time if self.ticket_start_time else 0
                
                if success_detected == True:
                    self.form_completion_time = time.time()
                    self.log("🎉 成功送出訂單！")
                    self.log(f"📊 第 {attempt + 1} 次嘗試耗時: {attempt_duration:.2f} 秒")
                    self.log(f"🏆 總搶票時間: {total_elapsed:.2f} 秒 (從點擊立即訂購開始)")
                    return True
                elif success_detected == "captcha_error":
                    # 🔧 優化2：驗證碼錯誤，只按 Enter 關閉 Alert，不刷新頁面
                    self.log(f"⚡ 驗證碼錯誤 Alert 已用 Enter 關閉，直接重新識別 (第 {attempt + 1} 次嘗試耗時: {attempt_duration:.2f} 秒)")
                    
                    # 🚀 不刷新頁面，直接繼續下一輪驗證碼識別
                    # 只需要很短的等待讓頁面狀態穩定
                    time.sleep(0.1)
                    
                    # 🚀 不計入嘗試次數，重置 attempt 計數器
                    attempt -= 1  # 讓下次迴圈時 attempt 保持不變
                    continue
                else:
                    self.log(f"❌ 第 {attempt + 1} 次嘗試失敗，耗時: {attempt_duration:.2f} 秒")
                    self.log(f"📊 累計時間: {total_elapsed:.2f} 秒")
                    
                    # 🔧 在重試前稍作等待
                    time.sleep(0.3)

            except Exception as e:
                attempt_duration = time.time() - attempt_start_time
                total_elapsed = time.time() - self.ticket_start_time if self.ticket_start_time else 0
                self.log(f"⚠️ 第 {attempt + 1} 次嘗試發生錯誤：{str(e)}")
                self.log(f"📊 嘗試耗時: {attempt_duration:.2f} 秒, 累計: {total_elapsed:.2f} 秒")
                time.sleep(0.5)
                continue

        # 計算失敗時的總時間
        total_elapsed = time.time() - self.ticket_start_time if self.ticket_start_time else 0
        self.log("🚫 已達最大嘗試次數，搶票失敗")
        self.log(f"📊 總搶票時間: {total_elapsed:.2f} 秒 (從點擊立即訂購開始)")
        return False

    def _submit_form_with_validation(self, page):
        """🔧 新增 - 帶驗證的表單送出"""
        submit_strategies = [
            # 策略1：標準按鈕點擊
            lambda: self._try_submit_standard(page),
            # 策略2：任何送出按鈕
            lambda: self._try_submit_any(page),
            # 策略3：JavaScript 強制送出
            lambda: self._try_submit_js(page)
        ]
        
        for i, strategy in enumerate(submit_strategies):
            try:
                if strategy():
                    self.log(f"📤 送出策略 {i+1} 執行成功")
                    return True
            except Exception as e:
                self.log(f"⚠️ 送出策略 {i+1} 失敗: {e}")
                continue
        
        return False

    def _try_submit_standard(self, page):
        """標準送出按鈕點擊"""
        submit_btn = page.locator("button.btn.btn-primary.btn-green")
        if submit_btn.count() > 0:
            submit_btn.click(force=True, timeout=1000)
            return True
        return False

    def _try_submit_any(self, page):
        """任何送出按鈕"""
        submit_selectors = [
            'button[type="submit"]',
            'input[type="submit"]',
            'button:has-text("送出")',
            'button:has-text("提交")',
            'button:has-text("確認張數")'
        ]
        
        for selector in submit_selectors:
            try:
                btn = page.locator(selector)
                if btn.count() > 0:
                    btn.first.click(force=True, timeout=1000)
                    return True
            except:
                continue
        return False

    def _try_submit_js(self, page):
        """JavaScript 強制送出"""
        try:
            result = page.evaluate("""
                () => {
                    // 尋找表單
                    const forms = document.querySelectorAll('form');
                    if (forms.length > 0) {
                        forms[0].submit();
                        return true;
                    }
                    
                    // 尋找送出按鈕
                    const submitBtns = document.querySelectorAll('button[type="submit"], input[type="submit"]');
                    if (submitBtns.length > 0) {
                        submitBtns[0].click();
                        return true;
                    }
                    
                    return false;
                }
            """)
            return result
        except:
            return False

    def _wait_for_form_result(self, page, original_url):
        """🔧 新增 - 等待表單處理結果 + 立即檢測驗證碼錯誤"""
        alert_triggered = False
        alert_message = ""
        
        def handle_dialog(dialog):
            nonlocal alert_triggered, alert_message
            alert_triggered = True
            alert_message = dialog.message
            self.log(f"⚠️ 收到 Alert: {alert_message}")
            
            # 🚀 立即檢查是否為驗證碼錯誤，如果是就快速處理
            if self._is_captcha_error_alert(alert_message):
                self.log("⚡ 偵測到驗證碼錯誤，按 Enter 快速關閉")
                
                # 🚀 優化：使用 Enter 而不是 accept()
                try:
                    # 先 accept 關閉對話框
                    dialog.accept()
                    # 然後立即按 Enter 確保關閉
                    page.keyboard.press("Enter")
                except:
                    # 如果按 Enter 失敗，fallback 到 accept
                    try:
                        dialog.accept()
                    except:
                        pass
                return  # 立即返回，不等待
            
            # 非驗證碼錯誤的 Alert，使用正常處理
            try:
                dialog.accept()
            except:
                pass
        
        page.on("dialog", handle_dialog)
        
        try:
            # 🚀 縮短等待間隔，更快速檢測
            for wait_count in range(30):  # 增加檢查次數但縮短間隔
                time.sleep(0.05)  # 縮短到 0.05 秒間隔
                
                # 🚀 優先檢查 Alert（驗證碼錯誤最常見）
                if alert_triggered:
                    if self._is_captcha_error_alert(alert_message):
                        self.log("⚡ 快速檢測到驗證碼錯誤 Alert")
                        
                        # 🚀 額外按一次 Enter 確保 Alert 完全關閉
                        try:
                            time.sleep(0.01)  # 極短等待
                            page.keyboard.press("Enter")
                            self.log("⚡ 已按 Enter 加速關閉 Alert")
                        except:
                            pass
                        
                        return "captcha_error"  # 立即返回，不等待
                    elif any(success_keyword in alert_message for success_keyword in ["成功", "完成", "確認"]):
                        self.log("✅ Alert 顯示成功訊息")
                        return True
                    else:
                        self.log("❌ Alert 顯示其他錯誤訊息")
                        return False
                
                # 檢查頁面是否跳轉
                try:
                    current_url = page.url
                    if current_url != original_url:
                        # 🔧 檢查新頁面是否包含成功指標
                        try:
                            page_content = page.content()
                            if any(success_word in page_content for success_word in ["訂單成功", "購票成功", "預訂成功"]):
                                self.log("✅ 頁面跳轉且顯示成功訊息")
                                return True
                            else:
                                self.log("✅ 頁面已跳轉")
                                return True
                        except:
                            self.log("✅ 頁面已跳轉")
                            return True
                except:
                    # 如果獲取 URL 失敗，繼續等待
                    continue
            
            # 超時但沒有明確結果
            self.log("⏱️ 等待表單結果超時")
            return False
            
        finally:
            page.remove_listener("dialog", handle_dialog)

    def _is_captcha_error_alert(self, alert_message):
        """判斷 Alert 是否為驗證碼錯誤 - 針對 tixcraft 優化"""
        captcha_error_keywords = [
            # 中文關鍵字
            "驗證碼不正確", "驗證碼", 
            "驗證失敗", "验证失败", "驗證錯誤", "验证错误",
            "請重新輸入", "请重新输入", "重新輸入","重新输入",
            "輸入的驗證碼",
            # 英文關鍵字
            "captcha", "verification code", "verify code", "code",
            "incorrect", "invalid", "wrong", "error"
        ]
        
        message_lower = alert_message.lower()
        return any(keyword.lower() in message_lower for keyword in captcha_error_keywords)

    def _handle_captcha_fast(self, page) -> Optional[str]:
        """快速驗證碼處理"""
        captcha_start_time = time.time()
        try:
            img = page.locator("#TicketForm_verifyCode-image")
            img.wait_for(state="visible", timeout=1000)  # 增加等待時間
            
            src = img.get_attribute("src")
            if not src:
                self.log("❌ 無法取得驗證碼圖片 src")
                return None
                
            full_url = f"https://tixcraft.com{src}" if src.startswith("/") else src
            
            # 🚀 快速下載圖片
            download_start_time = time.time()
            self.log("📥 開始下載驗證碼圖片...")
            
            image_base64 = page.evaluate(f'''
                async () => {{
                    try {{
                        const response = await fetch("{full_url}");
                        const buffer = await response.arrayBuffer();
                        return btoa(String.fromCharCode(...new Uint8Array(buffer)));
                    }} catch (e) {{
                        console.error("下載驗證碼圖片失敗:", e);
                        return null;
                    }}
                }}
            ''')
            
            download_end_time = time.time()
            download_duration = download_end_time - download_start_time
            
            if image_base64:
                self.log(f"✅ 圖片下載完成，耗時: {download_duration:.2f} 秒")
                result = self._ocr_with_gpt_fast(image_base64)
                
                total_duration = time.time() - captcha_start_time
                if result:
                    self.log(f"🎯 驗證碼處理完成: '{result}' (總計: {total_duration:.2f} 秒)")
                else:
                    self.log(f"❌ 驗證碼處理失敗 (總計: {total_duration:.2f} 秒)")
                
                return result
            else:
                total_duration = time.time() - captcha_start_time
                self.log(f"❌ 無法下載驗證碼圖片 (耗時: {total_duration:.2f} 秒)")
                
        except Exception as e:
            total_duration = time.time() - captcha_start_time
            self.log(f"❌ 快速驗證碼處理錯誤: {e} (耗時: {total_duration:.2f} 秒)")
        
        return None

    def _ocr_with_gpt_fast(self, image_base64: str) -> Optional[str]:
        """快速 GPT OCR"""
        try:
            if NEW_OPENAI and self.openai_client:
                response = self.openai_client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "just reply 4 letters in this picture"},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}}
                        ]
                    }],
                    max_tokens=10,
                    temperature=0
                )
                result = response.choices[0].message.content.strip()
                
                # 🔧 改善結果處理 - 更嚴格的驗證
                clean_result = re.sub(r'[^a-zA-Z]', '', result)
                if len(clean_result) == 4:
                    return clean_result.lower()
                else:
                    self.log(f"⚠️ GPT 回傳格式不正確: '{result}' -> '{clean_result}'")
                    
        except Exception as e:
            self.log(f"❌ GPT OCR 失敗: {e}")
        
        return None

    def _parse_ticket_time(self) -> Optional[datetime.datetime]:
        """解析搶票時間"""
        try:
            s = self.ticket_time_str
            if not s or s == 'null': 
                return None
            if 'T' in s: 
                return datetime.datetime.fromisoformat(s.replace("Z", ""))
            return datetime.datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
        except:
            return None

    def stop(self):
        """停止執行"""
        self.is_running = False
        self.log("🛑 已停止執行")

# 為了保持向後相容性，保留原類名
class TicketGrabber(OptimizedTicketGrabber):
    pass