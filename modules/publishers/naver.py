import os
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

from config import config
from modules.content_generator import BlogPost
from modules.osmu_transformer import to_naver_intro


def _build_driver(headless: bool = True) -> webdriver.Chrome:
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    opts.add_argument(
        "user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver


def _wait(driver: webdriver.Chrome, seconds: float = 2.0) -> None:
    time.sleep(seconds)


class NaverBlogPublisher:
    NAVER_ID = os.getenv("NAVER_ID", "")
    NAVER_PW = os.getenv("NAVER_PW", "")

    LOGIN_URL = "https://nid.naver.com/nidlogin.login"
    WRITE_URL = "https://blog.naver.com/gongtong.blog?redirect=Write"

    def __init__(self, headless: bool = True):
        self.headless = headless

    def _login(self, driver: webdriver.Chrome, wait: WebDriverWait) -> None:
        driver.get(self.LOGIN_URL)
        _wait(driver, 1.5)

        id_input = wait.until(EC.presence_of_element_located((By.ID, "id")))
        id_input.clear()
        id_input.send_keys(self.NAVER_ID)

        pw_input = driver.find_element(By.ID, "pw")
        pw_input.clear()
        pw_input.send_keys(self.NAVER_PW)
        pw_input.send_keys(Keys.RETURN)

        _wait(driver, 3)

        if "nidlogin" in driver.current_url or "로그인" in driver.title:
            raise RuntimeError(
                "네이버 로그인 실패. NAVER_ID/NAVER_PW를 확인하거나 "
                "캡차/2단계 인증을 headless=False 모드로 먼저 처리하세요."
            )

    def _open_editor(self, driver: webdriver.Chrome, wait: WebDriverWait) -> None:
        driver.get("https://blog.naver.com/PostWriteForm.naver")
        _wait(driver, 3)

        try:
            wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, "mainFrame")))
        except Exception:
            pass

    def _fill_title(self, driver: webdriver.Chrome, wait: WebDriverWait, title: str) -> None:
        try:
            title_input = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "input.se-title-input, #title"))
            )
        except Exception:
            title_input = driver.find_element(By.CSS_SELECTOR, "[placeholder*='제목']")
        title_input.click()
        title_input.send_keys(title)

    def _fill_body(self, driver: webdriver.Chrome, wait: WebDriverWait, html_body: str) -> None:
        try:
            body_area = wait.until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, ".se-text-paragraph, .se-component-content")
                )
            )
            body_area.click()
            driver.execute_script(
                """
                const editor = document.querySelector('.se-main-container');
                if (editor) editor.focus();
                document.execCommand('insertHTML', false, arguments[0]);
                """,
                html_body,
            )
        except Exception:
            body_area = driver.find_element(By.ID, "content")
            driver.execute_script(
                "arguments[0].innerHTML = arguments[1];", body_area, html_body
            )

    def _fill_tags(self, driver: webdriver.Chrome, wait: WebDriverWait, tags: list[str]) -> None:
        try:
            tag_input = wait.until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "input.tag-input, input[placeholder*='태그']")
                )
            )
            for tag in tags[:10]:
                tag_input.send_keys(tag)
                tag_input.send_keys(Keys.RETURN)
                _wait(driver, 0.3)
        except Exception:
            pass

    def _publish(self, driver: webdriver.Chrome, wait: WebDriverWait) -> str:
        try:
            publish_btn = wait.until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "button.publish-btn, button[data-action='publish']")
                )
            )
            publish_btn.click()
            _wait(driver, 2)

            confirm_btn = wait.until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "button.confirm-btn, .se-confirm button")
                )
            )
            confirm_btn.click()
            _wait(driver, 3)
        except Exception:
            pass

        return driver.current_url

    def post(self, post: BlogPost, intro: str = "") -> dict:
        naver_id = self.NAVER_ID or os.getenv("NAVER_ID", "")
        naver_pw = self.NAVER_PW or os.getenv("NAVER_PW", "")
        if not naver_id or not naver_pw:
            raise RuntimeError("NAVER_ID 또는 NAVER_PW가 .env에 설정되지 않았습니다.")

        self.NAVER_ID = naver_id
        self.NAVER_PW = naver_pw

        naver_intro = intro or to_naver_intro(post)
        full_html = f"<p>{naver_intro}</p>\n{post.body_html}"

        driver = _build_driver(headless=self.headless)
        wait = WebDriverWait(driver, 15)
        try:
            self._login(driver, wait)
            self._open_editor(driver, wait)
            self._fill_title(driver, wait, post.title)
            _wait(driver, 0.5)
            self._fill_body(driver, wait, full_html)
            _wait(driver, 0.5)
            self._fill_tags(driver, wait, post.tags)
            _wait(driver, 0.5)
            url = self._publish(driver, wait)
            return {"platform": "naver", "url": url, "title": post.title}
        finally:
            driver.quit()


def publish_to_naver(post: BlogPost, headless: bool = True) -> dict:
    publisher = NaverBlogPublisher(headless=headless)
    return publisher.post(post)
