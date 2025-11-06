import json
import os
import random
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver import ActionChains
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

# Requirements: selenium, webdriver-manager
# pip install selenium webdriver-manager

COOKIE_FILE = Path(__file__).parent / "cookie.json"
TARGET_URL = "https://hapitas.jp/item/detail/itemid/98046?apn=itemsharelink&i=25565645&route=pcText"
HOMEPAGE = "https://hapitas.jp/"
LOGIN_URL = "https://hapitas.jp/auth/signin/"

# credentials as requested
LOGIN_EMAIL = "paarunowkey@gmail.com"
LOGIN_PASSWORD = "anaste1204"


def pick_user_agent() -> str:
    # A small list of realistic UA strings; extend as needed
    uas = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
        " Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/605.1.15 (KHTML, like Gecko)"
        " Version/16.6 Safari/605.1.15",
    ]
    return random.choice(uas)


def load_cookies(path: Path):
    if not path.exists():
        print(f"cookie file not found: {path}")
        return []
    with open(path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            print("cookie.json is not valid JSON")
            return []

    # Expecting a list of cookie dicts (as exported by common browser extensions)
    if isinstance(data, dict) and "cookies" in data:
        data = data["cookies"]
    if not isinstance(data, list):
        print("cookie.json: unexpected format (expected list of cookies)")
        return []
    return data


def add_cookies_to_driver(driver, cookies):
    for c in cookies:
        cookie = {
            "name": c.get("name") or c.get("Name"),
            "value": c.get("value") or c.get("Value") or c.get("val"),
            "path": c.get("path", "/"),
        }
        if c.get("domain"):
            cookie["domain"] = c["domain"]
        if c.get("secure") is not None:
            cookie["secure"] = bool(c.get("secure"))
        if c.get("httpOnly") is not None:
            cookie["httpOnly"] = bool(c.get("httpOnly"))
        expiry = c.get("expiry") or c.get("expirationDate") or c.get("expires")
        if expiry is not None:
            try:
                cookie["expiry"] = int(expiry)
            except Exception:
                pass
        try:
            if cookie["name"] and cookie["value"]:
                driver.add_cookie(cookie)
        except Exception as e:
            print(f"skip cookie {cookie.get('name')}: {e}")


def make_driver():
    from webdriver_manager.chrome import ChromeDriverManager

    options = webdriver.ChromeOptions()
    options.add_argument(f"--user-agent={pick_user_agent()}")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("--disable-blink-features=AutomationControlled")
    # options.add_argument("--headless=new")  # keep visible to look human
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1200,800")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    try:
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {
                "source": """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
window.navigator.chrome = {runtime: {}};
Object.defineProperty(navigator, 'languages', {get: () => ['en-US','en']});
Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
"""
            },
        )
    except Exception:
        pass

    return driver


def human_like_wait(min_s=0.5, max_s=1.8):
    time.sleep(random.uniform(min_s, max_s))


def main():
    cookies = load_cookies(COOKIE_FILE)
    driver = make_driver()
    wait = WebDriverWait(driver, 20)

    try:
        # Go to homepage first so cookie domains align
        driver.get(HOMEPAGE)
        human_like_wait(1.0, 2.0)

        if cookies:
            add_cookies_to_driver(driver, cookies)
            driver.refresh()
            human_like_wait(1.0, 2.5)

        # Go to signin page and fill login form
        driver.get(LOGIN_URL)
        human_like_wait(1.0, 2.0)

        try:
            email_el = wait.until(EC.presence_of_element_located((By.ID, "email_main")))
            pwd_el = wait.until(EC.presence_of_element_located((By.ID, "password_main")))
            # fill with provided credentials
            email_el.clear()
            human_like_wait(0.2, 0.6)
            email_el.send_keys(LOGIN_EMAIL)
            human_like_wait(0.3, 0.7)
            pwd_el.clear()
            human_like_wait(0.2, 0.6)
            pwd_el.send_keys(LOGIN_PASSWORD)
            human_like_wait(0.3, 0.7)

            # click the login button (may trigger invisible reCAPTCHA)
            login_btn = wait.until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, 'input.btn_login_main_white.g-recaptcha, input[value="ログイン"]')
                )
            )
            actions = ActionChains(driver)
            actions.move_to_element(login_btn).pause(random.uniform(0.2, 0.6))
            actions.move_by_offset(random.randint(-4, 4), random.randint(-3, 3)).pause(random.uniform(0.05, 0.2))
            actions.click(login_btn)
            actions.perform()
            human_like_wait(30.0, 32.0)
        except Exception as e:
            print("login form not found or fill failed:", e)

        # Loop settings (randomize number of iterations to look more human)
        MIN_LOOPS = 999
        MAX_LOOPS = 1000
        loops = random.randint(MIN_LOOPS, MAX_LOOPS)
        print(f"Starting post-login loop: {loops} iterations")

        for i in range(1, loops + 1):
            print(f"Iteration {i}/{loops} — navigating to target")
            driver.get(TARGET_URL)
            human_like_wait(1.0, 2.5)

            selector = "li.detail_item_buttons a.detail_btn_point_link.js-set-local-storage-for-go-to-shop"
            try:
                elem = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
            except Exception as e:
                print(f"button not found on iteration {i}: {e}")
                # wait a bit and continue to next iteration
                human_like_wait(5.0, 10.0)
                continue

            # Human-like mouse movement and click
            actions = ActionChains(driver)
            actions.move_to_element(elem).pause(random.uniform(0.2, 0.7))
            actions.move_by_offset(random.randint(-6, 6), random.randint(-4, 4)).pause(random.uniform(0.1, 0.4))
            actions.click()
            actions.perform()

            human_like_wait(0.8, 1.6)

            # If the link opens in a new tab, switch to it, wait, scroll down a few times, then close
            handles = driver.window_handles
            if len(handles) > 1:
                new_handle = handles[-1]
                original_handle = handles[0]
                driver.switch_to.window(new_handle)

                # Wait for the page to load (at least 5s as requested)
                human_like_wait(5.0, 5.5)

                # Perform a few human-like scrolls/swipes down the page
                try:
                    # number of scroll actions
                    n_scrolls = random.randint(3, 7)
                    for _ in range(n_scrolls):
                        # scroll by a random amount (px)
                        scroll_px = random.randint(300, 900)
                        driver.execute_script("window.scrollBy({left: 0, top: arguments[0], behavior: 'smooth'});", scroll_px)
                        # small human-like pause between swipes
                        human_like_wait(0.6, 1.6)
                    # final small pause to simulate reading
                    human_like_wait(2.0, 4.0)
                except Exception:
                    # fallback: send PAGE_DOWN a few times
                    for _ in range(random.randint(2, 5)):
                        ActionChains(driver).send_keys(Keys.PAGE_DOWN).perform()
                        human_like_wait(0.5, 1.2)

                # Close the new tab and switch back
                try:
                    driver.close()
                except Exception:
                    pass
                # switch back to the original window
                try:
                    driver.switch_to.window(original_handle)
                except Exception:
                    if driver.window_handles:
                        driver.switch_to.window(driver.window_handles[0])

            # Random wait between iterations to simulate human variability
            ITER_MIN = 5.0   # seconds (adjust as needed)
            ITER_MAX = 60.0  # seconds (adjust as needed)
            interval = random.uniform(ITER_MIN, ITER_MAX)
            print(f"Iteration {i} done. Sleeping {interval:.1f}s before next iteration.")
            human_like_wait(interval, interval + random.uniform(0.5, 3.0))

        print("Loop finished. Keeping browser open briefly.")
        human_like_wait(3.0, 6.0)

    except Exception as e:
        print("error:", e)
    finally:
        driver.quit()


if __name__ == "__main__":
    main()