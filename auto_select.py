# 自動加退選腳本
# 需安裝 selenium 並下載對應瀏覽器 WebDriver
# 請將 course_list.txt 放在同目錄下

from selenium import webdriver
from selenium.webdriver.common.by import By
import time
from dotenv import load_dotenv
import os
import sys
import chromedriver_autoinstaller

print("自動加退選腳本啟動！")

load_dotenv()
USER = os.getenv("NKUST_USER")
PASS = os.getenv("NKUST_PASS")
LOGIN_URL = "http://aais1.nkust.edu.tw/selcrs_dp"

# 自動安裝 chromedriver
chromedriver_autoinstaller.install()

# 檢查 course_list.txt 是否存在
if not os.path.exists("course_list.txt"):
    print("錯誤：找不到 course_list.txt，請確認檔案是否存在於程式目錄。")
    sys.exit(1)

# 檢查帳號密碼是否有設定
if not USER or not PASS:
    print("錯誤：未設定 NKUST_USER 或 NKUST_PASS，請在 .env 或環境變數中設定。")
    sys.exit(1)

# 讀取課程編號
with open("course_list.txt", "r") as f:
    course_ids = [line.strip() for line in f if line.strip()]

# 啟動瀏覽器
options = webdriver.ChromeOptions()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-gpu')
driver = webdriver.Chrome(options=options)
driver.get(LOGIN_URL)

# 登入（加上 try-except）
try:
    account_box = driver.find_element(By.ID, "UserAccount")
    password_box = driver.find_element(By.NAME, "Password")
    login_btn = driver.find_element(By.ID, "Login")
    account_box.send_keys(USER)
    password_box.send_keys(PASS)
    login_btn.click()
    time.sleep(2)
    # 判斷是否跳轉到登入後頁面
    if "/Home/About" in driver.current_url:
        print("登入成功！")
        # 登入成功後跳轉到加選頁面
        base_url = driver.current_url.split("/Home/About")[0]
        driver.get(f"{base_url}/AddSelect/AddSelectPage")
        time.sleep(2)

        # 修改 body 的 class
        driver.execute_script(
            'document.body.className = "sidebar-mini layout-fixed sidebar-closed sidebar-collapse";'
        )

        # 依序查詢每個課程
        for course_id in course_ids:
            selcode_box = driver.find_element(By.ID, "scr_selcode")
            selcode_box.clear()
            selcode_box.send_keys(course_id)
            search_btn = driver.find_element(By.ID, "courseSearch")
            search_btn.click()
            time.sleep(1)

            show_num_btn = driver.find_element(By.CLASS_NAME, "btn.btn-link.myBtnNum.text-danger.py-0.my-0")
            driver.execute_script("arguments[0].click();", show_num_btn)
            time.sleep(0.5)

            precnt = int(driver.find_element(By.ID, "scr_precnt").text)
            selnum = int(driver.find_element(By.ID, "SelNum").text)
            print(f"課程 {course_id} 限修人數: {precnt}，選上人數: {selnum}")

            close_btn = driver.find_element(By.CLASS_NAME, "close")
            driver.execute_script("arguments[0].click();", close_btn)
            time.sleep(0.3)

            if selnum < precnt:
                add_btn = driver.find_element(By.ID, course_id)
                driver.execute_script("arguments[0].click();", add_btn)
                print(f"課程 {course_id} 有名額，已嘗試加選！")
                time.sleep(1)
    else:
        print("登入失敗，請檢查帳號密碼")
        driver.quit()
        exit()

except Exception as e:
    print(f"失敗: {e}")
    driver.quit()
    exit()

# 關閉瀏覽器
driver.quit()
