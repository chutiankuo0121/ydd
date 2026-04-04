import random
import time
from abc import ABC, abstractmethod

from faker import Faker

from app_config import AppConfig


class BaseBrowserController(ABC):
    """
    Shared browser automation logic.
    Each controller instance owns exactly one browser process.
    """

    def __init__(self, app_config: AppConfig, proxy_url: str | None = None):
        self.app_config = app_config
        self.wait_time = app_config.bot_protection_wait * 1000
        self.max_captcha_retries = app_config.max_captcha_retries
        self.proxy = proxy_url or app_config.proxy
        self.email_domain = app_config.email_domain

        self.playwright = None
        self.browser = None

    @abstractmethod
    def launch_browser(self):
        """
        Start and return `(playwright_instance, browser_instance)`.
        """

    @abstractmethod
    def handle_captcha(self, page):
        """
        Captcha solving flow.
        """

    def build_proxy_settings(self):
        if not self.proxy:
            return None
        return {
            "server": self.proxy,
            "bypass": "localhost,127.0.0.1,::1",
        }

    def get_thread_browser(self):
        if self.browser is None:
            playwright, browser = self.launch_browser()
            if not playwright:
                return False
            self.playwright = playwright
            self.browser = browser
        return self.browser

    def get_thread_page(self):
        browser = self.get_thread_browser()
        if not browser:
            return False
        context = browser.new_context()
        return context.new_page()

    def clean_up(self, page=None, type="all_browser"):
        if type == "done_browser" and page:
            try:
                page.context.close()
            except Exception:
                pass

        elif type == "all_browser":
            if self.browser:
                try:
                    self.browser.close()
                except Exception:
                    pass
                self.browser = None
            if self.playwright:
                try:
                    self.playwright.stop()
                except Exception:
                    pass
                self.playwright = None

    def outlook_register(self, page, email, password):
        """
        Common registration flow.
        """
        fake = Faker()

        lastname = fake.last_name()
        firstname = fake.first_name()
        year = str(random.randint(1960, 2005))
        month = str(random.randint(1, 12))
        day = str(random.randint(1, 28))

        try:
            page.goto(
                "https://outlook.live.com/mail/0/?prompt=create_account",
                timeout=20000,
                wait_until="domcontentloaded",
            )
            page.get_by_text("同意并继续").wait_for(timeout=30000)
            start_time = time.time()
            page.wait_for_timeout(0.1 * self.wait_time)
            page.get_by_text("同意并继续").click(timeout=30000)

        except Exception:
            print("[Error: IP] - IP质量不佳，无法进入注册界面。")
            return False

        try:
            if self.email_domain == "hotmail.com":
                try:
                    page.locator("#domainDropdownId").click(timeout=5000)
                    page.locator("div[role=\"option\"]").first.wait_for(timeout=3000)
                    options = page.locator("div[role=\"option\"]").all()
                    for opt in options:
                        if "hotmail" in opt.inner_text():
                            opt.click(timeout=3000)
                            break

                    selected = page.locator("[data-testid=\"truncatedSelectedText\"]")
                    if selected.is_visible():
                        print(f"[Info] 域名: {selected.inner_text()}")

                except Exception as exc:
                    print(f"[Info] 选择 hotmail.com 失败: {exc}")

            page.locator("[aria-label=\"新建电子邮件\"]").type(
                email, delay=0.006 * self.wait_time, timeout=10000
            )
            page.locator("[data-testid=\"primaryButton\"]").click(timeout=5000)
            page.wait_for_timeout(0.02 * self.wait_time)
            page.locator("[type=\"password\"]").type(
                password, delay=0.004 * self.wait_time, timeout=10000
            )
            page.wait_for_timeout(0.02 * self.wait_time)
            page.locator("[data-testid=\"primaryButton\"]").click(timeout=5000)

            page.wait_for_timeout(0.03 * self.wait_time)
            page.locator("[name=\"BirthYear\"]").fill(year, timeout=10000)

            try:
                page.wait_for_timeout(0.02 * self.wait_time)
                page.locator("[name=\"BirthMonth\"]").select_option(
                    value=month, timeout=1000
                )
                page.wait_for_timeout(0.05 * self.wait_time)
                page.locator("[name=\"BirthDay\"]").select_option(value=day)

            except Exception:
                page.locator("[name=\"BirthMonth\"]").click()
                page.wait_for_timeout(0.02 * self.wait_time)
                page.locator(f"[role=\"option\"]:text-is(\"{month}月\")").click()
                page.wait_for_timeout(0.04 * self.wait_time)
                page.locator("[name=\"BirthDay\"]").click()
                page.wait_for_timeout(0.03 * self.wait_time)
                page.locator(f"[role=\"option\"]:text-is(\"{day}日\")").click()
                page.locator("[data-testid=\"primaryButton\"]").click(timeout=5000)

            page.locator("#lastNameInput").type(
                lastname, delay=0.002 * self.wait_time, timeout=10000
            )
            page.wait_for_timeout(0.02 * self.wait_time)
            page.locator("#firstNameInput").fill(firstname, timeout=10000)

            if time.time() - start_time < self.wait_time / 1000:
                page.wait_for_timeout(
                    self.wait_time - (time.time() - start_time) * 1000
                )

            page.locator("[data-testid=\"primaryButton\"]").click(timeout=5000)
            page.locator(
                "span > [href=\"https://go.microsoft.com/fwlink/?LinkID=521839\"]"
            ).wait_for(state="detached", timeout=22000)

            page.wait_for_timeout(400)

            if (
                page.get_by_text("一些异常活动").count()
                or page.get_by_text("此站点正在维护，暂时无法使用，请稍后重试。").count()
                > 0
            ):
                print(
                    "[Error: IP or browser] - 当前IP注册频率过快。检查IP与是否为指纹浏览器并关闭了无头模式。"
                )
                return False

            if page.locator("iframe#enforcementFrame").count() > 0:
                print("[Error: FunCaptcha] - 验证码类型错误，非按压验证码。")
                return False

            captcha_result = self.handle_captcha(page)

            if not captcha_result:
                raise TimeoutError

        except Exception as exc:
            print(exc)
            print("[Error: IP] - 加载超时或因触发机器人检测导致按压次数达到最大仍未通过。")
            return False

        print(f"[Success: Email Registration] - {email}@{self.email_domain}: {password}")

        try:
            try:
                cancel_btn = page.get_by_text("取消")
                if cancel_btn.count() > 0:
                    cancel_btn.click(timeout=10000)
                    print("[Info] 点击了'取消'按钮")
                    page.wait_for_timeout(1000)
            except Exception:
                pass

            outlook_found = False
            max_check_time = 15
            start_time = time.time()

            while time.time() - start_time < max_check_time:
                try:
                    outlook_span = page.locator("span.hpyHhmSe9hmk5gopLr9a5Q\\=\\=")
                    if outlook_span.count() > 0:
                        print("[Info] 检测到 Outlook 标签，注册成功")
                        outlook_found = True
                        break
                except Exception:
                    pass

                try:
                    if (
                        page.locator("[aria-label=\"新邮件\"]").count() > 0
                        or page.get_by_text("收件箱").count() > 0
                        or page.get_by_text("欢迎使用 Outlook").count() > 0
                    ):
                        print("[Info] 检测到邮箱界面元素，注册成功")
                        outlook_found = True
                        break
                except Exception:
                    pass

                try:
                    current_url = page.url
                    if "outlook.live.com" in current_url and "/mail/" in current_url:
                        print("[Info] 检测到 Outlook 邮箱 URL，注册成功")
                        outlook_found = True
                        break
                except Exception:
                    pass

                page.wait_for_timeout(500)

            if outlook_found:
                print("[Success] 邮箱注册完成，准备获取 OAuth token")
                return True

            print("[Warning] 未检测到 Outlook 成功标志，但继续尝试获取 token")
            return True

        except Exception as exc:
            print(f"[Info] 注册后检测流程异常: {exc}")
            return True
