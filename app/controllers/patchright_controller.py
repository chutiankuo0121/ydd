import random
from patchright.sync_api import sync_playwright

from app_config import AppConfig
from runtime_log import log

from .base_controller import BaseBrowserController


class PatchrightController(BaseBrowserController):

    def __init__(self, app_config: AppConfig, proxy_url: str | None = None):
        super().__init__(app_config=app_config, proxy_url=proxy_url)

    def launch_browser(self):
        try:
            log("[浏览器] Patchright 正在启动驱动...")
            p = sync_playwright().start() 

            log("[浏览器] Patchright 正在启动 Chromium...")
            b = p.chromium.launch(
                headless=False,            
                args=[
                    '--lang=zh-CN',
                    '--proxy-bypass-list=localhost;127.0.0.1;::1',
                ],
                proxy=self.build_proxy_settings()
            )

            return p, b

        except Exception as e:
            log(f"[浏览器] 启动失败: {e}")
            return False, False
        
    def handle_captcha(self, page):

        frame1 = page.frame_locator('iframe[title="验证质询"]')
        frame2 = frame1.frame_locator('iframe[style*="display: block"]')


        for _ in range(0, self.max_captcha_retries + 1):

            page.wait_for_timeout(200)
            loc = frame2.locator('[aria-label="可访问性挑战"]')
            box = loc.bounding_box()
            x = box['x'] + box['width'] / 2 + random.randint(-10, 10)
            y = box['y'] + box['height'] / 2 + random.randint(-10, 10)
            page.mouse.click(x, y)

            loc2 = frame2.locator('[aria-label="再次按下"]')
            box2 = loc2.bounding_box()
            x = box2['x'] + box2['width'] / 2 + random.randint(-20, 20)
            y = box2['y'] + box2['height'] / 2 + random.randint(-13, 13)
            page.mouse.click(x, y)

            try:

                page.locator('.draw').wait_for(state="detached")
                try:

                    # 简单的认为加载8秒后成功，暂不考虑请求.
                    page.locator('[role="status"][aria-label="正在加载..."]').wait_for(timeout=5000)
                    page.wait_for_timeout(8000)
                    if page.get_by_text('一些异常活动').count() or page.get_by_text('此站点正在维护，暂时无法使用，请稍后重试。').count() > 0:
                        print("[Error: Rate limit] - 正常通过验证码，但当前IP注册频率过快。")
                        return False
                    elif frame2.locator('[aria-label="可访问性挑战"]').count() > 0:
                        continue
                    break

                except:

                    if page.get_by_text('取消').count() > 0:
                        break
                    frame1.get_by_text("请再试一次").wait_for(timeout=15000)
                    continue

            except:
                if page.get_by_text('取消').count() > 0:
                     break
                return False
        else: 
            return False

        return True
