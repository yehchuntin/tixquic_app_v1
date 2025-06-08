# website_package.py - 專為網站下載設計的打包腳本

import os
import subprocess
import shutil
from pathlib import Path
import zipfile
import time

class WebsitePackageBuilder:
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.src_dir = self.project_root / "src"
        self.dist_dir = self.project_root / "dist"
        self.website_package_dir = self.project_root / "website_download"
        
        print(f"📁 項目根目錄: {self.project_root}")
        print(f"📁 源代碼目錄: {self.src_dir}")
    
    def clean_and_prepare(self):
        """清理並準備環境"""
        print("🧹 清理舊檔案...")
        
        # 清理目錄
        if self.dist_dir.exists():
            shutil.rmtree(self.dist_dir)
        if self.website_package_dir.exists():
            shutil.rmtree(self.website_package_dir)
        
        # 創建目錄
        self.dist_dir.mkdir()
        self.website_package_dir.mkdir()
        
        print("✅ 環境準備完成")
    
    def compile_for_website(self):
        """為網站下載編譯"""
        print("\n🔨 編譯網站下載版...")
        
        main_file = self.src_dir / "main.py"
        if not main_file.exists():
            print(f"❌ 找不到主檔案: {main_file}")
            return False
        
        # 網站版編譯命令 - 最穩定的配置
        cmd = [
            "python", "-m", "nuitka",
            "--standalone",  # 使用 standalone 而非 onefile
            f"--output-dir={self.dist_dir}",
            "--output-filename=TixQuic_Grabber.exe",
            "--assume-yes-for-downloads",
            
            # 核心設定
            "--windows-console-mode=disable",  # 無控制台視窗
            "--enable-plugin=tk-inter",
            
            # 包含必要套件
            "--include-package=tkinter",
            "--include-package=requests", 
            "--include-package=playwright",
            "--include-package=openai",
            
            # 優化設定
            "--remove-output",
            
            str(main_file)
        ]
        
        # 加入圖標
        icon_path = self.src_dir / "assets" / "icon.ico"
        if icon_path.exists():
            cmd.append(f"--windows-icon-from-ico={icon_path}")
        
        print("🚀 開始編譯...")
        print("📋 特性: Standalone + 無控制台 + 網站友好")
        print("⏰ 預計時間: 15-20 分鐘")
        
        try:
            start_time = time.time()
            result = subprocess.run(cmd, cwd=self.project_root, check=True)
            
            end_time = time.time()
            compile_time = (end_time - start_time) / 60
            print(f"✅ 編譯完成 (耗時: {compile_time:.1f} 分鐘)")
            
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ 編譯失敗: {e}")
            return False
    
    def find_compiled_app(self):
        """尋找編譯好的應用程式"""
        print("\n🔍 尋找編譯結果...")
        
        possible_locations = [
            self.dist_dir / "main.dist",
            self.dist_dir / "TixQuic_Grabber.dist"
        ]
        
        for location in possible_locations:
            exe_path = location / "TixQuic_Grabber.exe"
            if exe_path.exists():
                print(f"✅ 找到編譯結果: {location}")
                return location
        
        print("❌ 找不到編譯結果")
        return None
    
    def create_website_download_package(self, app_dir):
        """創建網站下載包"""
        print("\n📦 創建網站下載包...")
        
        # 計算應用大小
        total_size = sum(f.stat().st_size for f in app_dir.rglob('*') if f.is_file())
        total_size_mb = total_size / (1024 * 1024)
        print(f"📊 應用大小: {total_size_mb:.1f} MB")
        
        # 複製應用到下載包目錄
        download_app_dir = self.website_package_dir / "TixQuic_Grabber"
        shutil.copytree(app_dir, download_app_dir)
        print(f"✅ 應用已複製到: {download_app_dir}")
        
        # 創建啟動器
        self.create_launcher_scripts()
        
        # 創建使用說明
        self.create_user_guide()
        
        # 創建網站下載 ZIP
        return self.create_download_zip()
    
    def create_launcher_scripts(self):
        """創建啟動腳本"""
        print("🚀 創建啟動腳本...")
        
        # 主啟動腳本
        main_launcher = '''@echo off
title TixQuic Grabber - 專業搶票助手
chcp 65001 >nul

echo.
echo     ██████╗ ██╗██╗  ██╗ ██████╗ ██╗   ██╗██╗ ██████╗
echo     ╚══██╔══╝██║╚██╗██╔╝██╔═══██╗██║   ██║██║██╔════╝
echo        ██║   ██║ ╚███╔╝ ██║   ██║██║   ██║██║██║
echo        ██║   ██║ ██╔██╗ ██║▄▄ ██║██║   ██║██║██║
echo        ██║   ██║██╔╝ ██╗╚██████╔╝╚██████╔╝██║╚██████╗
echo        ╚═╝   ╚═╝╚═╝  ╚═╝ ╚══▀▀═╝  ╚═════╝ ╚═╝ ╚═════╝
echo.
echo                    專業搶票助手 v1.0
echo.
echo     📋 使用步驟:
echo     1. 程式將自動啟動
echo     2. 輸入您的驗證碼
echo     3. 點擊"開啟瀏覽器登入"
echo     4. 在瀏覽器中登入您的帳號
echo     5. 返回程式點擊"開始搶票"
echo.
echo     💡 提示: 啟動可能需要幾秒鐘，請稍候...
echo.

cd /d "%~dp0TixQuic_Grabber"
start "" "TixQuic_Grabber.exe"

echo     ✅ 程式已啟動！
echo.
timeout /t 3 >nul
'''
        
        launcher_path = self.website_package_dir / "🎯 啟動 TixQuic Grabber.bat"
        with open(launcher_path, 'w', encoding='utf-8') as f:
            f.write(main_launcher)
        
        # 故障排除啟動器
        debug_launcher = '''@echo off
title TixQuic Grabber - 故障排除模式
chcp 65001 >nul

echo.
echo     🔧 TixQuic Grabber 故障排除模式
echo     ===============================
echo.
echo     此模式會顯示詳細的錯誤訊息
echo     如果程式無法正常啟動，請使用此模式
echo.
echo     按任意鍵繼續...
pause >nul

echo.
echo     正在啟動故障排除模式...
echo.

cd /d "%~dp0TixQuic_Grabber"
"TixQuic_Grabber.exe"

echo.
echo     程式已結束，請檢查上方是否有錯誤訊息
echo.
pause
'''
        
        debug_path = self.website_package_dir / "🔧 故障排除模式.bat"
        with open(debug_path, 'w', encoding='utf-8') as f:
            f.write(debug_launcher)
        
        print("✅ 啟動腳本已創建")
    
    def create_user_guide(self):
        """創建使用指南"""
        print("📖 創建使用指南...")
        
        user_guide = """# 🎯 TixQuic Grabber 使用指南

## 🚀 快速開始

### 步驟 1: 啟動程式
雙擊 "🎯 啟動 TixQuic Grabber.bat"

### 步驟 2: 輸入驗證碼
在程式中輸入您獲得的驗證碼

### 步驟 3: 開啟瀏覽器
點擊 "開啟瀏覽器登入" 按鈕

### 步驟 4: 登入帳號
在開啟的瀏覽器中登入您的拓元帳號

### 步驟 5: 開始搶票
返回程式，點擊 "開始搶票" 按鈕

## 💡 重要提醒

### 系統需求
- Windows 10 或 Windows 11 (64位元)
- 至少 4GB 記憶體
- 穩定的網路連接

### 使用注意事項
1. **不要關閉瀏覽器**: 搶票過程中請保持瀏覽器開啟
2. **保持網路穩定**: 確保網路連接穩定
3. **提前準備**: 建議在開搶前 5-10 分鐘完成登入

### 常見問題解決

#### 問題 1: 程式無法啟動
**解決方案**:
- 嘗試使用 "🔧 故障排除模式.bat"
- 檢查是否為 Windows 10/11 系統
- 暫時關閉防毒軟體

#### 問題 2: 瀏覽器無法開啟
**解決方案**:
- 確認已安裝 Google Chrome
- 嘗試手動開啟 Chrome 瀏覽器
- 檢查防火牆設定

#### 問題 3: 驗證碼錯誤
**解決方案**:
- 確認驗證碼輸入正確
- 檢查驗證碼是否已過期
- 聯繫提供者獲取新的驗證碼

#### 問題 4: 搶票失敗
**可能原因**:
- 網路延遲
- 票券已售完
- 驗證碼識別錯誤

## 🛡️ 安全說明

- 本軟體不會收集任何個人資料
- 驗證碼僅用於程式功能驗證
- 所有操作都在您的本地電腦進行

## 📞 技術支援

如遇到技術問題，請：
1. 先嘗試故障排除模式
2. 檢查是否符合系統需求
3. 聯繫技術支援並提供錯誤訊息

---
感謝使用 TixQuic Grabber！
祝您搶票成功！ 🎉
"""
        
        guide_path = self.website_package_dir / "📖 使用指南.txt"
        with open(guide_path, 'w', encoding='utf-8') as f:
            f.write(user_guide)
        
        print("✅ 使用指南已創建")
    
    def create_download_zip(self):
        """創建網站下載 ZIP"""
        print("\n📦 創建網站下載 ZIP...")
        
        zip_path = self.project_root / "TixQuic_Grabber_網站下載版.zip"
        
        try:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zipf:
                for file_path in self.website_package_dir.rglob('*'):
                    if file_path.is_file():
                        arcname = file_path.relative_to(self.website_package_dir)
                        zipf.write(file_path, arcname)
            
            zip_size = zip_path.stat().st_size / (1024 * 1024)
            print(f"✅ 網站下載 ZIP 已創建: {zip_path}")
            print(f"📦 ZIP 大小: {zip_size:.1f} MB")
            
            return zip_path
            
        except Exception as e:
            print(f"❌ ZIP 創建失敗: {e}")
            return None
    
    def build_website_package(self):
        """完整的網站包構建流程"""
        print("🌐 開始構建網站下載包...")
        
        # 1. 清理並準備
        self.clean_and_prepare()
        
        # 2. 編譯應用
        if not self.compile_for_website():
            print("❌ 編譯失敗")
            return False
        
        # 3. 尋找編譯結果
        app_dir = self.find_compiled_app()
        if not app_dir:
            print("❌ 找不到編譯結果")
            return False
        
        # 4. 創建下載包
        zip_path = self.create_website_download_package(app_dir)
        if not zip_path:
            print("❌ 下載包創建失敗")
            return False
        
        print("\n🎉 網站下載包構建完成！")
        print("=" * 50)
        print("📋 構建結果:")
        print(f"   📁 下載包目錄: {self.website_package_dir}")
        print(f"   🗜️ 網站 ZIP: {zip_path}")
        
        print("\n🌐 網站部署步驟:")
        print("1. 將 ZIP 檔案上傳到您的網站")
        print("2. 提供下載連結給用戶")
        print("3. 用戶下載後解壓縮即可使用")
        
        print("\n👤 用戶使用流程:")
        print("1. 下載 ZIP 檔案")
        print("2. 解壓縮到任意位置")
        print("3. 雙擊 '🎯 啟動 TixQuic Grabber.bat'")
        print("4. 按照程式指示操作")
        
        return True

if __name__ == "__main__":
    print("=" * 60)
    print("        🌐 TixQuic Grabber 網站下載版構建工具")
    print("=" * 60)
    print("📋 此工具將創建:")
    print("   ✅ 適合網站下載的 ZIP 包")
    print("   ✅ 用戶友好的啟動器")
    print("   ✅ 完整的使用指南")
    print("   ✅ 故障排除工具")
    print("=" * 60)
    print("\n⏰ 預計時間: 15-20 分鐘")
    print("🎯 目標: 創建可直接在網站提供下載的安裝包")
    
    input("\n按 Enter 鍵開始構建...")
    
    builder = WebsitePackageBuilder()
    
    try:
        success = builder.build_website_package()
        
        if success:
            print("\n🎉 網站下載版構建成功！")
            print("📁 您現在可以將 ZIP 檔案放到網站供用戶下載")
        else:
            print("\n❌ 構建失敗，請檢查錯誤訊息")
    
    except KeyboardInterrupt:
        print("\n❌ 構建被用戶中斷")
    except Exception as e:
        print(f"\n❌ 構建錯誤: {e}")
    
    input("\n按 Enter 鍵退出...")