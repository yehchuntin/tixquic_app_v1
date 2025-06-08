# 拓元搶票助手 (TixCraft Grabber)

一個自動化的拓元售票系統搶票工具，支援驗證碼識別與自動化購票流程。

## 功能特色

- ✅ 驗證碼自動識別 (使用 GPT-4 Vision)
- ✅ 自動填寫購票表單
- ✅ 支援多票區優先順序設定
- ✅ 精確的時間同步搶票
- ✅ 圖形化操作介面
- ✅ 即時日誌顯示

## 系統需求

- Windows 10/11
- Google Chrome 瀏覽器
- Python 3.8+ (開發用)
- 網路連線

## 開發環境設置

```bash
# 克隆專案
git clone https://github.com/yourusername/tixcraft_app.git
cd tixcraft_app

# 建立虛擬環境
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Mac/Linux

# 安裝依賴
pip install -r requirements.txt

# 安裝 Playwright 瀏覽器
python -m playwright install chromium
```

## 使用方式

### 開發模式
```bash
python src/main.py
```

### 打包執行檔
```bash
python build.py
```

打包完成後，執行檔會在 `dist/TicketGrabber.exe`

## 專案結構

```
tixcraft_app/
├── src/
│   ├── main.py              # 主程式入口
│   ├── api/
│   │   └── firebase_client.py   # Firebase API 客戶端
│   └── utils/
│       ├── ticket_grabber.py    # 搶票核心邏輯
│       └── device_manager.py    # 設備管理
├── assets/
│   └── icon.ico            # 應用程式圖標
├── requirements.txt        # Python 依賴
├── build.py               # 打包腳本
└── README.md
```

## 設定說明

使用者需要：
1. 購買驗證碼
2. 在網站上設定 OpenAI API Key
3. 設定票區偏好

## 注意事項

- 本工具僅供學習研究使用
- 使用者需自行承擔使用風險
- 請遵守拓元售票系統的使用規範

## 授權

MIT License

## 貢獻

歡迎提交 Issue 和 Pull Request！