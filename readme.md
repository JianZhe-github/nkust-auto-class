# NKUST 自動加選

本專案可自動登入 [高雄科技大學加退選系統](https://stdsel.nkust.edu.tw)，自動查詢課程並加選。提供網頁控制介面，支援 Docker 一鍵部署。

## 功能特色

- 自動登入選課系統（Cloudflare Turnstile bypass）
- 網頁 UI 控制設定（帳密、課程、輪詢間隔）
- 測試帳號是否正確的按鈕
- 即時顯示加選紀錄（每 5 秒自動更新）
- 支援 Docker 一鍵部署

## 使用方式

<<<<<<< HEAD
### 1. Python 執行

- `auto_select.py`：主程式
- `course_list.txt`：每行一個課程代碼
- `.env`：帳號密碼設定

#### 帳號密碼設定說明

請將 `stack.env` 內容複製並修改為 `.env`，格式如下：

```
NKUST_USER=你的學號
NKUST_PASS=你的密碼
```

### 2. Docker 部署

#### 執行容器（每 5 分鐘自動執行）
=======
### 1. Docker 部署（推薦）
>>>>>>> 84ab3dd (fix 更新)

1. 啟動容器：
```bash
docker compose up -d --build
```

2. 開啟瀏覽器前往 **http://localhost:5000**

3. 在網頁 UI 設定：
   - 輸入學號與密碼，點擊「測試」確認帳號正確
   - 設定輪詢間隔（秒）
   - 新增要加選的課程代碼
   - 點擊「儲存設定」

設定會自動持久化（保存於 Docker volume），容器重啟後不遺失。

### 2. 本機 Python 執行

安裝依賴：
```bash
pip install selenium selenium-stealth flask pyvirtualdisplay python-dotenv
```

啟動 Web UI：
```bash
python3 web_app.py
# 前往 http://localhost:5000 設定帳密與課程
```

執行加選（設定完成後）：
```bash
python3 auto_select.py
```

## 檔案說明

| 檔案 | 說明 |
|------|------|
| `auto_select.py` | 加選邏輯（使用 Xvfb 虛擬顯示器） |
| `web_app.py` | Flask 網頁 UI 服務 |
| `templates/index.html` | 網頁 UI |
| `entrypoint.sh` | Docker 啟動腳本（Flask + 輪詢） |
| `Dockerfile` | Docker 映像建置設定 |
| `docker-compose.yml` | Docker Compose 設定 |
| `./data/config.json` | 設定檔（由 Web UI 或手動建立） |
| `./data/status.json` | 加選紀錄 |

## 版本比較

| 功能 | Docker | Python 執行 |
|------|--------|---------|
| 易用性 | ⭐⭐⭐ | ⭐⭐ |
| 無視窗模式 | ✅ | ❌ (需 Xvfb) |
| 網頁 UI | ✅ | ✅ |
| 跨平台 | ✅ | ✅ |
| 設定方式 | 網頁 | 網頁 |
| 開箱即用 | ✅ (需 Docker) | ❌ (需安裝依賴) |

## 注意事項

- **Docker：** 推薦生產環境使用（最穩定、最安全）
- **Python 執行：** 需要預裝依賴和 Xvfb（Linux）
- 課程代碼可在選課系統中查詢

## 開發環境

- Python 3.10+
- Selenium + selenium-stealth
- pyvirtualdisplay (Xvfb)
- Flask
- Google Chrome + ChromeDriver

## 聯絡方式

如有問題請開 issue。
