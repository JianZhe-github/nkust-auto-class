#!/bin/bash
set -e

# Ensure data directory exists
mkdir -p /data

# Create empty config.json if it doesn't exist (prevents auto_select from crashing)
CONFIG_PATH="${CONFIG_PATH:-/data/config.json}"
if [ ! -f "$CONFIG_PATH" ]; then
  echo '{"user":"","pass":"","interval":300,"courses":[]}' > "$CONFIG_PATH"
  echo "[entrypoint] 初始化設定檔：$CONFIG_PATH"
fi

# Start Flask web server in background
echo "[entrypoint] 啟動 Flask Web UI (port 5000)..."
python3 /app/web_app.py > /tmp/flask.log 2>&1 &
FLASK_PID=$!
sleep 2  # Give Flask time to start

# Polling loop: read interval from config each iteration
echo "[entrypoint] 開始輪詢加選..."
while true; do
  # Read config and check if courses list is non-empty
  read -r INTERVAL COURSES_COUNT < <(python3 -c "
import json, os
p = os.environ.get('CONFIG_PATH', '/data/config.json')
try:
    if os.path.exists(p):
        d = json.load(open(p))
        interval = max(10, int(d.get('interval', 300)))
        courses_count = len(d.get('courses', []))
        print(f'{interval} {courses_count}')
    else:
        print('300 0')
except:
    print('300 0')
" 2>/dev/null || echo "300 0")

  if [ "$COURSES_COUNT" -gt 0 ]; then
    echo "[entrypoint] 執行加選（課程數：$COURSES_COUNT，間隔：${INTERVAL}秒）..."
    python3 /app/auto_select.py || true  # Don't fail on script error
  else
    echo "[entrypoint] 尚未設定課程，跳過此次執行"
  fi

  echo "[entrypoint] 等待 ${INTERVAL} 秒後再次執行..."
  sleep "$INTERVAL"
done
