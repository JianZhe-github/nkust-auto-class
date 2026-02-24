# 自動加退選腳本
# 設定透過 /data/config.json 讀取（由 Web UI 管理）

import json
import os
import sys
import time
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium_stealth import stealth
from pyvirtualdisplay import Display

print("自動加退選腳本啟動！")

CONFIG_PATH = os.environ.get("CONFIG_PATH", "/data/config.json")
STATUS_PATH = os.environ.get("STATUS_PATH", "/data/status.json")
STATUS_MAX = 100
LOGIN_URL = "https://stdsel.nkust.edu.tw/dispatch"


def load_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        print(f"錯誤：找不到設定檔 {CONFIG_PATH}，請先透過 Web UI 設定帳號密碼與課程。")
        sys.exit(1)
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def append_status(record: dict):
    """Append one enrollment record to status.json (newest-first, max STATUS_MAX)."""
    os.makedirs(os.path.dirname(STATUS_PATH), exist_ok=True)
    records = []
    if os.path.exists(STATUS_PATH):
        try:
            with open(STATUS_PATH, "r", encoding="utf-8") as f:
                records = json.load(f)
        except Exception:
            records = []
    records.insert(0, record)
    records = records[:STATUS_MAX]
    with open(STATUS_PATH, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


# ── 讀取設定 ──────────────────────────────────────────────
cfg = load_config()
USER = cfg.get("user", "").strip()
PASS = cfg.get("pass", "")
course_ids = [c.strip() for c in cfg.get("courses", []) if str(c).strip()]

if not USER or not PASS:
    print("錯誤：設定檔中未填入帳號或密碼，請透過 Web UI 設定。")
    sys.exit(1)

if not course_ids:
    print("⚠ 課程列表為空，無需執行。")
    sys.exit(0)

# [0] 啟動 Xvfb 虛擬顯示器（非 headless，用來繞過 bot 偵測）
print("[0] 啟動 Xvfb 虛擬顯示器...")
display = Display(visible=0, size=(1920, 1080))
display.start()

# [1] 配置 Chrome + Selenium Stealth
print("[1] 配置 Chrome 與 Selenium Stealth...")
options = Options()
options.add_argument('--window-size=1920,1080')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--disable-gpu')
options.add_argument('--disable-blink-features=AutomationControlled')
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option('useAutomationExtension', False)
options.add_argument('--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36')

driver = webdriver.Chrome(options=options)

stealth(driver,
    languages=["en-US", "en"],
    vendor="Google Inc.",
    platform="Linux x86_64",
    webgl_vendor="Intel Inc.",
    renderer="Intel Iris OpenGL Engine",
    fix_hairline=True,
)

# [2] 注入 Shadow DOM Bypass（針對 Cloudflare 隱藏 Root）
print("[2] 注入 Shadow DOM Bypass...")
driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
    "source": """
    (function() {
        const originalAttachShadow = Element.prototype.attachShadow;
        Element.prototype.attachShadow = function(init) {
            if (init && init.mode === 'closed') {
                const root = originalAttachShadow.call(this, init);
                this.__closedShadowRoot = root;
                return root;
            }
            return originalAttachShadow.call(this, init);
        };
        Element.prototype.attachShadow.toString = function() {
            return originalAttachShadow.toString();
        };
    })();
    """
})

driver.get(LOGIN_URL)
time.sleep(3)

# 登入（加上 try-except）
try:
    account_box = driver.find_element(By.NAME, "usernameOrEmailAddress")
    password_box = driver.find_element(By.NAME, "Password")
    account_box.send_keys(USER)
    password_box.send_keys(PASS)

    # [3] 解決 Turnstile CAPTCHA
    print("[3] 開始解決 Turnstile CAPTCHA...")
    from turnstile_solver import solve
    success = solve(
        driver,
        detect_timeout=10,
        solve_timeout=30,
        interval=0.5,
        verify=True,
        click_method="cdp",
        enable_logging=True
    )
    if success is False:
        print("✗ Turnstile 驗證失敗，無法繼續登入")
        driver.quit()
        display.stop()
        sys.exit(1)
    elif success is None:
        print("⚠ 未偵測到 Turnstile，直接嘗試登入...")
    else:
        print("✓ Turnstile 驗證成功！")

    login_btn = driver.find_element(By.ID, "LoginButton")
    login_btn.click()
    time.sleep(5)

    # 判斷是否跳轉到登入後頁面
    if "/StdSelcrsHome/About" in driver.current_url:
        print("登入成功！")
        # 登入成功後跳轉到加選頁面
        base_url = driver.current_url.split("/StdSelcrsHome/About")[0]
        #https://aais4.nkust.edu.tw/StdSelcrs/StdSelcrsHome/About
        driver.get(f"{base_url}/AddSelcrs/AddSelcrs")
        #https://aais4.nkust.edu.tw/StdSelcrs/AddSelcrs/AddSelcrs/
        time.sleep(2)

        # 修改 body 的 class
        driver.execute_script(
            'document.body.className = "sidebar-mini layout-fixed sidebar-closed sidebar-collapse";'
        )

        # 依序查詢每個課程
        for course_id in course_ids:
            selcode_box = driver.find_element(By.ID, "Crsno")
            selcode_box.clear()
            selcode_box.send_keys(course_id)
            search_btn = driver.find_element(By.ID, "bntSearchCourse")
            search_btn.click()
            time.sleep(1)

            show_num_btn = driver.find_element(By.CLASS_NAME, "selcrsnum")
            driver.execute_script("arguments[0].click();", show_num_btn)
            time.sleep(0.5)

            # 提取限修人數和已選上人數（新 HTML 格式）
            precnt_text = driver.execute_script("""
                const labels = Array.from(document.querySelectorAll('label'));
                const label = labels.find(l => l.textContent.includes('限修人數'));
                if (label) {
                    const parent = label.closest('.row');
                    return parent ? parent.textContent.match(/\\d+/)?.[0] : null;
                }
                return null;
            """)
            precnt = int(precnt_text) if precnt_text else 0
            
            selnum_text = driver.execute_script("""
                const badge = document.querySelector('.badge.bg-danger');
                return badge ? badge.textContent.trim() : null;
            """)
            selnum = int(selnum_text) if selnum_text else 0
            
            print(f"課程 {course_id} 限修人數: {precnt}，選上人數: {selnum}")

            close_btn = driver.find_element(By.CLASS_NAME, "cmd_closewindow")
            driver.execute_script("arguments[0].click();", close_btn)
            time.sleep(0.3)

            if selnum < precnt:
                add_btn = driver.find_element(By.CLASS_NAME, "addbutton")
                driver.execute_script("arguments[0].click();", add_btn)
                time.sleep(0.3)
                add_btn = driver.find_element(By.CLASS_NAME, "swal2-confirm")
                driver.execute_script("arguments[0].click();", add_btn)
                result = "有名額，已嘗試加選"
                print(f"課程 {course_id} {result}！")
                time.sleep(1)
            else:
                result = "額滿，未加選"
                print(f"課程 {course_id} {result}")

            append_status({
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "course_id": course_id,
                "result": result,
                "precnt": precnt,
                "selnum": selnum,
            })
    else:
        print("登入失敗，請檢查帳號密碼")
        driver.quit()
        display.stop()
        sys.exit(1)

except Exception as e:
    print(f"失敗: {e}")
    import traceback
    traceback.print_exc()
    driver.quit()
    display.stop()
    sys.exit(1)

# 關閉瀏覽器與虛擬顯示器
driver.quit()
display.stop()
