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
LOGIN_EMAIL = "hogehoge@gmail.com"
LOGIN_PASSWORD = "password1234"


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


def click_accept_button(driver, timeout=8):
    """
    ページ上の Cookie 同意ダイアログの「OK」ボタンを確実に押すユーティリティ。
    タイムアウト内で複数セレクタを試行し、表示されているボタンを JS click で確実に押す。
    """
    start = time.time()
    selectors = [
        'button[data-action="consent"][data-action-type="accept"]',
        'button.accept.uc-accept-button',
        '#accept',
        'button.uc-accept-button',
        "//button[normalize-space(.)='OK']",
        "footer .buttons .accept",
        "#uc-main-dialog button[data-action-type='accept']",
    ]
    while time.time() - start < timeout:
        for sel in selectors:
            try:
                if sel.startswith("//"):
                    els = driver.find_elements(By.XPATH, sel)
                else:
                    els = driver.find_elements(By.CSS_SELECTOR, sel)
            except Exception:
                els = []
            for el in els:
                try:
                    if not el.is_displayed() or not el.is_enabled():
                        continue
                    # スクロールして視認位置に移し、JSでクリック（より確実）
                    try:
                        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                        human_like_wait(0.15, 0.4)
                    except Exception:
                        pass
                    try:
                        driver.execute_script("arguments[0].click();", el)
                    except Exception:
                        # fallback to ActionChains click
                        try:
                            ActionChains(driver).move_to_element(el).click().perform()
                        except Exception:
                            continue
                    # 押した後、ボタンやダイアログが消えるまで短く待つ
                    human_like_wait(0.6, 1.2)
                    # 確認: 同意ダイアログが消えたかをチェック
                    try:
                        # if uc-main-dialog not present or not displayed -> success
                        dlg = driver.find_elements(By.ID, "uc-main-dialog")
                        if not dlg or not dlg[0].is_displayed():
                            return True
                    except Exception:
                        return True
                except Exception:
                    continue
        # 見つからなかった／消えなかった場合は短く待って再試行
        human_like_wait(0.4, 0.9)
    return False


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

            # If the link opens in a new tab, switch to it, wait, scroll down a few times, then interact and close
            handles = driver.window_handles
            if len(handles) > 1:
                new_handle = handles[-1]
                original_handle = handles[0]
                driver.switch_to.window(new_handle)

                # Wait for the page to load (at least 5s as requested)
                human_like_wait(5.0, 6.0)

                # --- 変更: スライド開始前に必ず「OK」を押す ---
                try:
                    ok_clicked = click_accept_button(driver, timeout=8)
                    if ok_clicked:
                        print("Consent OK clicked.")
                    else:
                        print("Consent OK not found or not clickable (timed out).")
                except Exception as e:
                    print("error while clicking consent OK:", e)
                # --- ここまで ---

                # Perform a few human-like scrolls/swipes down the page
                try:
                    n_scrolls = random.randint(3, 7)
                    for _ in range(n_scrolls):
                        scroll_px = random.randint(300, 900)
                        driver.execute_script(
                            "window.scrollBy({left: 0, top: arguments[0], behavior: 'smooth'});",
                            scroll_px,
                        )
                        human_like_wait(0.6, 1.6)
                    human_like_wait(1.5, 3.0)
                except Exception:
                    for _ in range(random.randint(2, 5)):
                        ActionChains(driver).send_keys(Keys.PAGE_DOWN).perform()
                        human_like_wait(0.5, 1.2)

                # 1) Click the "料金プランをチェック" CTA (first one / visible)
                try:
                    cta_sel = 'button[data-action="ctaButton"], button.VHolYY.tjDLq2.e4r_YY.IKMUBE'
                    cta_btn = WebDriverWait(driver, 8).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, cta_sel))
                    )
                    actions = ActionChains(driver)
                    actions.move_to_element(cta_btn).pause(random.uniform(0.2, 0.6))
                    actions.move_by_offset(random.randint(-4, 4), random.randint(-3, 3)).pause(0.1)
                    actions.click().perform()
                    human_like_wait(5.0, 6.0)
                except Exception as e:
                    print("CTA click failed:", e)

                # 2) スライド内の「料金を見る」ボタンを探してランダムにクリック（スライド領域内に限定）
                try:
                    # スライドが開くのを待つ（result-list-ready またはスライドアウトセクション）
                    slide_container = None
                    try:
                        slide_container = WebDriverWait(driver, 8).until(
                            lambda d: d.find_element(By.CSS_SELECTOR, "section._5Gfu3K, div[data-testid='result-list-ready'], div[data-testid='deals-slideout'], div[data-testid='all-slideout-deals']")
                        )
                    except Exception:
                        # 見つからなくても次の検索でページ全体を対象にする
                        slide_container = None

                    if slide_container:
                        view_buttons = slide_container.find_elements(
                            By.XPATH,
                            ".//button[contains(normalize-space(.),'料金を見る') or contains(normalize-space(.),'料金を見る')]"
                        )
                    else:
                        view_buttons = driver.find_elements(
                            By.XPATH,
                            "//button[contains(normalize-space(.),'料金を見る')]"
                        )

                    # 最終手段: data-testid 属性で探す
                    if not view_buttons:
                        view_buttons = driver.find_elements(By.CSS_SELECTOR, 'button[data-testid="champion-deal"], button[data-cos="viewDealButton"], button[data-testid="clickOutButton"]')

                    if view_buttons:
                        picked = random.choice(view_buttons)
                        # スムーズにスクロールして可視化→クリック
                        try:
                            driver.execute_script("arguments[0].scrollIntoView({behavior:'smooth', block:'center'});", picked)
                        except Exception:
                            pass
                        human_like_wait(0.3, 0.9)
                        actions = ActionChains(driver)
                        actions.move_to_element(picked).pause(random.uniform(0.15, 0.6))
                        actions.move_by_offset(random.randint(-3, 3), random.randint(-2, 2)).pause(0.05)
                        actions.click().perform()
                        human_like_wait(1.0, 2.5)
                    else:
                        print("slideout: '料金を見る' ボタンが見つかりませんでした")
                except Exception as e:
                    print("champion-deal / slideout click failed:", e)

                # 3) On the deals list, randomly pick one "料金プランをチェック" and click it
                try:
                    # Prefer buttons containing the label text, fallback to known class
                    plan_buttons = driver.find_elements(
                        By.XPATH,
                        "//button[contains(normalize-space(.),'料金プランをチェック')] | //button[contains(@class,'VHolYY')]",
                    )
                    if plan_buttons:
                        pick = random.choice(plan_buttons)
                        # scroll into view and click
                        driver.execute_script("arguments[0].scrollIntoView({behavior:'smooth', block:'center'});", pick)
                        human_like_wait(0.5, 1.2)
                        actions = ActionChains(driver)
                        actions.move_to_element(pick).pause(random.uniform(0.2, 0.6))
                        actions.click().perform()
                        human_like_wait(3.0, 5.0)
                    else:
                        print("no plan buttons found to click")
                except Exception as e:
                    print("random plan click failed:", e)

                # allow a short extra read time, then close the tab and switch back
                human_like_wait(5.0, 6.0)
                try:
                    # Close all open tabs/windows that are not the hapitas domain.
                    # Keep the original_handle (hapitas) open and switch back to it.
                    handles_now = list(driver.window_handles)
                    for h in handles_now:
                        try:
                            driver.switch_to.window(h)
                            url = ""
                            try:
                                url = driver.current_url or ""
                            except Exception:
                                url = ""
                            # If the current tab is not hapitas, close it
                            if "hapitas.jp" not in url:
                                try:
                                    driver.close()
                                except Exception:
                                    pass
                        except Exception:
                            # ignore any switch/close errors and continue
                            continue

                    # Ensure we switch back to the original hapitas tab if possible
                    if original_handle in driver.window_handles:
                        driver.switch_to.window(original_handle)
                    elif driver.window_handles:
                        driver.switch_to.window(driver.window_handles[0])
                except Exception:
                    # fallback: try to leave at least one window open
                    try:
                        if driver.window_handles:
                            driver.switch_to.window(driver.window_handles[0])
                    except Exception:
                        pass

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
