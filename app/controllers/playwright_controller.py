from playwright.sync_api import sync_playwright

from app_config import AppConfig
from runtime_log import log

from .base_controller import BaseBrowserController



class PlaywrightController(BaseBrowserController):

    def __init__(self, app_config: AppConfig, proxy_url: str | None = None):
        super().__init__(app_config=app_config, proxy_url=proxy_url)
        self.browser_path = app_config.playwright_browser_path

    def launch_browser(self):
        try:
            log("[浏览器] Playwright 正在启动驱动...")
            p = sync_playwright().start()

            launch_kwargs = {
                "headless": False,
                "args": [
                    "--lang=zh-CN",
                    "--proxy-bypass-list=localhost;127.0.0.1;::1",
                ],
                "proxy": self.build_proxy_settings(),
            }
            if self.browser_path:
                launch_kwargs["executable_path"] = self.browser_path
            log("[浏览器] Playwright 正在启动 Chromium...")
            b = p.chromium.launch(**launch_kwargs)

            return p, b

        except Exception as e:
            log(f"[浏览器] 启动失败: {e}")
            return False, False
    
    def handle_captcha(self, page):

        page.wait_for_event("request", lambda req: req.url.startswith("blob:https://iframe.hsprotect.net/"), timeout=22000)
        page.wait_for_timeout(800)

        for _ in range(0, self.max_captcha_retries + 1):

            page.keyboard.press('Enter')
            page.wait_for_timeout(11500)
            page.keyboard.press('Enter')

            try:
                page.wait_for_event("request", lambda req: req.url.startswith("https://browser.events.data.microsoft.com"), timeout=8000)
                try:
                    page.wait_for_event("request", lambda req: req.url.startswith("https://collector-pxzc5j78di.hsprotect.net/assets/js/bundle"), timeout=1700) 
                    page.wait_for_timeout(2000)
                    continue

                except:
                    if page.get_by_text('一些异常活动').count() or page.get_by_text('此站点正在维护，暂时无法使用，请稍后重试。').count() > 0:
                        print("[Error: Rate limit] - 正常通过验证码，但当前IP注册频率过快。")
                        return False
                    break

            except:
                # raise TimeoutError
                page.wait_for_timeout(5000)
                page.keyboard.press('Enter')
                page.wait_for_event("request", lambda req: req.url.startswith("https://browser.events.data.microsoft.com"), timeout=10000)
                
                try:
                    page.wait_for_event("request", lambda req: req.url.startswith("https://collector-pxzc5j78di.hsprotect.net/assets/js/bundle"), timeout=4000)
                except:
                    break
                page.wait_for_timeout(500)
        else: 
            return False
        
        return True
