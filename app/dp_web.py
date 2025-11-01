from DrissionPage import ChromiumPage, ChromiumOptions
import sys
import time
import requests
import os
import tempfile
import random
import string
import shutil
from config import URL, CODE_API_TEMPLATE, DOWNLOAD_PATH
from airtest.core.api import exists, touch, sleep, Template
from utils.email_utils import generate_random_email
from logger import get_logger

logger = get_logger("WEB")


def get_code_from_api(email_addr, max_tries=10, interval=3):
    url = CODE_API_TEMPLATE.format(email=email_addr)
    for i in range(max_tries):
        logger.info(f"第{i+1}次轮询验证码 API")
        try:
            resp = requests.get(url, timeout=5)
            txt = resp.text.strip()
            try:
                j = resp.json()
                code = j.get('code') or txt
            except Exception:
                code = txt
            if code and 3 <= len(code) <= 8:
                logger.info(f"成功获取验证码: {code}")
                return code
        except Exception as e:
            logger.warning(f"验证码请求异常: {e}")
        time.sleep(interval)
    raise RuntimeError('轮询10次验证码API仍未获取到验证码')


def wait_for_installer(download_dir, filename="comet_installer_latest.exe", interval=5, max_tries=30):
    logger.info(f"开始轮询检测安装包: {filename} (每{interval}s一次，共{max_tries}次)")
    fpath = os.path.join(download_dir, filename)
    for i in range(max_tries):
        if os.path.exists(fpath):
            logger.info(f"安装包已检测到: {fpath}")
            return fpath
        if (i + 1) % 5 == 0:  # 每5次输出一次，减少日志噪音
            logger.info(f"第{i+1}次检测，安装包尚未下载完成")
        time.sleep(interval)
    raise RuntimeError(f'轮询{max_tries}次，未检测到安装包 {filename}，任务失败！')


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_DIR = os.path.join(SCRIPT_DIR, 'images')


def run_with_drissionpage():
    page = None
    user_data_dir = None
    try:
        # 用 set_argument 正确注入 user-data-dir
        rand_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        user_data_dir = os.path.join(tempfile.gettempdir(), f'chrome_tmp_profile_{rand_str}')
        logger.info(f"创建隔离浏览器配置目录: {user_data_dir}")
        options = ChromiumOptions()
        options.set_argument('--user-data-dir', user_data_dir)
        page = ChromiumPage(options)
        page.get(URL)
        logger.info(f"浏览器已启动并访问: {URL}")

        # 1. 点击邀请按钮（英文）
        xpath_invite = 'xpath://div[contains(text(),"Claim invitation")]'
        btn = page.ele(xpath_invite, timeout=12)
        if not btn:
            # 先尝试处理 Cloudflare 人机（通过图片点击）
            cf_img = os.path.join(IMAGE_DIR, 'cloudflare.png')
            logger.info("邀请按钮未找到，尝试检测并处理 Cloudflare 验证")
            try:
                cf_tpl = Template(cf_img, threshold=0.8)
                pos = exists(cf_tpl)
                if pos:
                    logger.info(f"检测到 Cloudflare 验证，执行点击")
                    try:
                        touch(pos)
                    except Exception:
                        touch(cf_tpl)
                    sleep(2)
            except Exception as _e:
                logger.warning(f"检测 Cloudflare 验证异常: {_e}")
            # 再次尝试查找 Invite 按钮
            btn = page.ele(xpath_invite, timeout=12)
            if not btn:
                raise RuntimeError('Invite button not found (Claim invitation)')
        try:
            btn.scroll_to_see()
        except Exception:
            pass
        try:
            btn.click()
            logger.info("已点击邀请按钮")
        except Exception:
            page.run_js('arguments[0].click();', btn)
            logger.info("已通过 JavaScript 点击邀请按钮")

        # 2. 填邮箱（英文 placeholder）
        input_xpath_en = 'xpath://input[@placeholder="Enter your email"]'
        email_input = page.ele(input_xpath_en, timeout=20)
        if not email_input:
            raise RuntimeError('Email input not found (Enter your email)')
        email_addr = generate_random_email()
        email_input.input(email_addr)
        logger.info(f"已输入邮箱: {email_addr}")
        time.sleep(0.5)

        # 3. 点击继续按钮（英文）
        continue_xpath_en = 'xpath://div[contains(text(),"Continue with email")]'
        cont_btn = page.ele(continue_xpath_en, timeout=20)
        if not cont_btn:
            raise RuntimeError('Continue button not found (Continue with email)')
        try:
            cont_btn.scroll_to_see()
        except Exception:
            pass
        try:
            cont_btn.click()
            logger.info("已点击继续按钮")
        except Exception:
            page.run_js('arguments[0].click();', cont_btn)
            logger.info("已通过 JavaScript 点击继续按钮")

        # 4. 等待验证码输入框（英文 placeholder）
        code_input_xpath_en = 'xpath://input[@placeholder="Enter Code"]'
        code_input = page.ele(code_input_xpath_en, timeout=20)
        if not code_input:
            raise RuntimeError('Code input not found (Enter Code)')
        logger.info("验证码输入框已定位，开始获取验证码")

        # 5. 获取验证码
        time.sleep(3)
        code = get_code_from_api(email_addr)
        code_input.input(code)
        logger.info(f"已输入验证码: {code}")
        time.sleep(0.5)

        # 6. 检测安装包下载
        installer_path = None
        try:
            installer_path = wait_for_installer(DOWNLOAD_PATH)
        finally:
            if page:
                page.quit()
                logger.info("已关闭浏览器")
            if user_data_dir and os.path.exists(user_data_dir):
                shutil.rmtree(user_data_dir, ignore_errors=True)
                logger.info(f"已清理浏览器配置目录: {user_data_dir}")

        logger.info(f"网页自动化执行成功，安装包位于: {installer_path}")
        # 返回首次验证码以供桌面端轮询时避开旧验证码
        return installer_path, email_addr, code

    except Exception as e:
        logger.error(f"网页自动化失败: {e}")
        if page:
            try:
                page.quit()
                logger.info("异常处理：已关闭浏览器")
            except: pass
        if user_data_dir and os.path.exists(user_data_dir):
            shutil.rmtree(user_data_dir, ignore_errors=True)
            logger.info(f"异常处理：已清理浏览器配置目录: {user_data_dir}")
        # 重要：抛出异常给上层 main.py 捕获，从而发送 failed 到 Worker
        raise RuntimeError(str(e))


if __name__ == "__main__":
    run_with_drissionpage()
