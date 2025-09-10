FROM python:3.11-slim

# 安裝必要套件與 Chrome
RUN apt-get update && \
    apt-get install -y wget unzip cron \
    && wget -O /tmp/chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt-get install -y /tmp/chrome.deb \
    && rm /tmp/chrome.deb \
    && pip install selenium python-dotenv chromedriver-autoinstaller

# 建立工作目錄
WORKDIR /app

# 複製程式與需求檔
COPY auto_select.py course_list.txt ./

# 直接用 shell 迴圈每 5 分鐘執行一次
CMD ["bash", "-c", "while true; do python3 /app/auto_select.py; sleep 300; done"]