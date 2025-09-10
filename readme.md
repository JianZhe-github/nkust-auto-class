# NKUST 自動加選

本專案可自動登入 [高雄科技大學加退選系統](http://aais1.nkust.edu.tw/selcrs_dp)，依據 `course_list.txt` 內容自動查詢課程並加選。支援 Docker 部署與定時自動執行。

## 功能特色

- 自動登入選課系統
- 依據課程清單自動查詢並加選
- 支援 Docker 一鍵部署
- 支援環境變數或 `.env` 檔案設定帳號密碼
- 可每 5 分鐘自動執行一次

## 使用方式

### 1. Python 執行

- `auto_select.py`：主程式
- `course_list.txt`：每行一個課程代碼
- `.env`：帳號密碼設定（或用 Docker `-e` 傳入）

#### 帳號密碼設定說明

請將 `stack.env` 內容複製並修改為 `.env`，格式如下：

```
NKUST_USER=你的學號
NKUST_PASS=你的密碼
```

### 2. Docker 部署

#### 執行容器（每 5 分鐘自動執行）

```bash
docker run -d \
  -e NKUST_USER=你的學號 \
  -e NKUST_PASS=你的密碼 \
  -v /你的本機路徑/course_list.txt:/app/course_list.txt \
  --name nkust-auto-class jianzhe61/nkust-auto-class

```


## 注意事項

- 請把要加選的課程編號輸入進`course_list.txt`，一行一個

## 開發環境

- Python 3.11
- Selenium
- chromedriver-autoinstaller
- python-dotenv
- Google Chrome

## 聯絡方式

如有問題請開 issue 或

