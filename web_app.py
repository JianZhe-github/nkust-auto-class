import json
import os
import threading
import uuid
from datetime import datetime

from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

CONFIG_PATH = os.environ.get("CONFIG_PATH", "/data/config.json")
STATUS_PATH = os.environ.get("STATUS_PATH", "/data/status.json")
STATUS_MAX = 100

# In-memory store for test-login jobs
_test_jobs: dict[str, dict] = {}

# ──────────────────────── helpers ────────────────────────

def _ensure_data_dir():
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)


def load_config() -> dict:
    _ensure_data_dir()
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    # Fallback: seed from environment variables (first boot)
    return {
        "user": os.environ.get("NKUST_USER", ""),
        "pass": os.environ.get("NKUST_PASS", ""),
        "interval": int(os.environ.get("INTERVAL", "300")),
        "courses": [],
    }


def save_config(data: dict):
    _ensure_data_dir()
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_status() -> list:
    if os.path.exists(STATUS_PATH):
        with open(STATUS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


# ──────────────────────── routes ─────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/config", methods=["GET"])
def get_config():
    cfg = load_config()
    # Never expose password in plain GET — return masked version
    safe = dict(cfg)
    safe["pass"] = "••••••••" if cfg.get("pass") else ""
    return jsonify(safe)


@app.route("/api/config", methods=["POST"])
def set_config():
    data = request.get_json(force=True)
    cfg = load_config()

    if "user" in data:
        cfg["user"] = str(data["user"]).strip()
    if "pass" in data and data["pass"] != "••••••••":
        cfg["pass"] = str(data["pass"])
    if "interval" in data:
        try:
            cfg["interval"] = max(10, int(data["interval"]))
        except ValueError:
            return jsonify({"error": "interval 必須是數字"}), 400
    if "courses" in data:
        if not isinstance(data["courses"], list):
            return jsonify({"error": "courses 必須是陣列"}), 400
        cfg["courses"] = [str(c).strip() for c in data["courses"] if str(c).strip()]

    save_config(cfg)
    return jsonify({"ok": True})


@app.route("/api/status", methods=["GET"])
def get_status():
    return jsonify(load_status())


# ──────────────────── test-login ─────────────────────────

def _run_test_login(job_id: str, user: str, password: str):
    """Run a real Selenium login test in a background thread."""
    _test_jobs[job_id] = {"status": "running", "result": None}
    try:
        from pyvirtualdisplay import Display
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.common.by import By
        from selenium_stealth import stealth

        display = Display(visible=0, size=(1280, 800))
        display.start()

        options = Options()
        options.add_argument("--window-size=1280,800")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        options.add_argument(
            "--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        )

        driver = webdriver.Chrome(options=options)
        stealth(
            driver,
            languages=["en-US", "en"],
            vendor="Google Inc.",
            platform="Linux x86_64",
            webgl_vendor="Intel Inc.",
            renderer="Intel Iris OpenGL Engine",
            fix_hairline=True,
        )
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {
                "source": """
            (function() {
                const orig = Element.prototype.attachShadow;
                Element.prototype.attachShadow = function(init) {
                    if (init && init.mode === 'closed') {
                        const r = orig.call(this, init);
                        this.__closedShadowRoot = r;
                        return r;
                    }
                    return orig.call(this, init);
                };
                Element.prototype.attachShadow.toString = function() { return orig.toString(); };
            })();
            """
            },
        )

        LOGIN_URL = "https://stdsel.nkust.edu.tw/dispatch"
        driver.get(LOGIN_URL)
        import time
        time.sleep(3)

        driver.find_element(By.NAME, "usernameOrEmailAddress").send_keys(user)
        driver.find_element(By.NAME, "Password").send_keys(password)

        from turnstile_solver import solve
        success = solve(driver, detect_timeout=10, solve_timeout=30, interval=0.5,
                        verify=True, click_method="cdp", enable_logging=False)
        if success is False:
            _test_jobs[job_id] = {"status": "done", "result": "fail", "message": "Turnstile 驗證失敗"}
            driver.quit()
            display.stop()
            return

        driver.find_element(By.ID, "LoginButton").click()
        time.sleep(5)

        if "/StdSelcrsHome/About" in driver.current_url:
            _test_jobs[job_id] = {"status": "done", "result": "ok", "message": "登入成功！"}
        else:
            _test_jobs[job_id] = {"status": "done", "result": "fail", "message": "登入失敗（帳號或密碼錯誤）"}

        driver.quit()
        display.stop()

    except Exception as e:
        _test_jobs[job_id] = {"status": "done", "result": "fail", "message": f"錯誤：{e}"}


@app.route("/api/test-login", methods=["POST"])
def test_login():
    data = request.get_json(force=True)
    user = data.get("user", "").strip()
    password = data.get("pass", "")

    if not user or not password:
        return jsonify({"error": "請填入帳號與密碼"}), 400

    job_id = str(uuid.uuid4())
    t = threading.Thread(target=_run_test_login, args=(job_id, user, password), daemon=True)
    t.start()
    return jsonify({"job_id": job_id})


@app.route("/api/test-login/<job_id>", methods=["GET"])
def test_login_result(job_id):
    job = _test_jobs.get(job_id)
    if job is None:
        return jsonify({"error": "找不到工作"}), 404
    return jsonify(job)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
