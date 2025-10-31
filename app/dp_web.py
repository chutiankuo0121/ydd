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
from utils.email_utils import generate_random_email


def get_code_from_api(email_addr, max_tries=10, interval=3):
    url = CODE_API_TEMPLATE.format(email=email_addr)
    for i in range(max_tries):
        print(f"[验证码] 第{i+1}次轮询 {url}")
        try:
            resp = requests.get(url, timeout=5)
            txt = resp.text.strip()
            try:
                j = resp.json()
                code = j.get('code') or txt
            except Exception:
                code = txt
            if code and 3 <= len(code) <= 8:
                print(f"[验证码] 成功获取: {code}")
                return code
        except Exception as e:
            print(f"[验证码] 请求异常: {e}")
        time.sleep(interval)
    raise RuntimeError('轮询10次验证码API仍未获取到验证码')


def wait_for_installer(download_dir, filename="comet_installer_latest.exe", interval=5, max_tries=30):
    print(f"[下载检测] 在 {download_dir} 轮询检测 {filename}，每{interval}s一次，共{max_tries}次...")
    fpath = os.path.join(download_dir, filename)
    for i in range(max_tries):
        if os.path.exists(fpath):
            print(f"[下载检测] 安装包已检测到: {fpath}")
            return fpath
        print(f"[下载检测] 第{i+1}次，未检测到安装包，等待中...")
        time.sleep(interval)
    raise RuntimeError(f'轮询{max_tries}次，未检测到安装包 {filename}，任务失败！')


def run_with_drissionpage():
    page = None
    user_data_dir = None
    try:
        # 用 set_argument 正确注入 user-data-dir
        rand_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        user_data_dir = os.path.join(tempfile.gettempdir(), f'chrome_tmp_profile_{rand_str}')
        print(f"[隔离] 本次 user-data-dir: {user_data_dir}")
        options = ChromiumOptions()
        options.set_argument('--user-data-dir', user_data_dir)
        page = ChromiumPage(options)
        page.get(URL)
        print(f"DrissionPage （隔离Profile）已启动并访问: {URL}")

        # 1. 点击邀请按钮（英文）
        xpath_invite = 'xpath://div[contains(text(),"Claim invitation")]'
        btn = page.ele(xpath_invite, timeout=20)
        if not btn:
            raise RuntimeError('Invite button not found (Claim invitation)')
        try:
            btn.scroll_to_see()
        except Exception:
            pass
        try:
            btn.click()
            print('Clicked invite button.')
        except Exception:
            page.run_js('arguments[0].click();', btn)
            print('Clicked invite button via JS.')

        # 2. 填邮箱（英文 placeholder）
        input_xpath_en = 'xpath://input[@placeholder="Enter your email"]'
        email_input = page.ele(input_xpath_en, timeout=20)
        if not email_input:
            raise RuntimeError('Email input not found (Enter your email)')
        email_addr = generate_random_email()
        email_input.input(email_addr)
        print(f'Filled email: {email_addr}')
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
            print('Clicked continue button.')
        except Exception:
            page.run_js('arguments[0].click();', cont_btn)
            print('Clicked continue button via JS.')

        # 4. 等待验证码输入框（英文 placeholder）
        code_input_xpath_en = 'xpath://input[@placeholder="Enter Code"]'
        code_input = page.ele(code_input_xpath_en, timeout=20)
        if not code_input:
            raise RuntimeError('Code input not found (Enter Code)')
        print('Code input located, will fetch code...')

        # 5. 获取验证码
        time.sleep(3)
        code = get_code_from_api(email_addr)
        code_input.input(code)
        print(f'Entered code: {code}')
        time.sleep(0.5)

        # 6. 检测安装包下载
        installer_path = None
        try:
            installer_path = wait_for_installer(DOWNLOAD_PATH)
        finally:
            if page:
                page.quit()
                print('[收尾] 已关闭浏览器。')
            if user_data_dir and os.path.exists(user_data_dir):
                shutil.rmtree(user_data_dir, ignore_errors=True)
                print(f'[收尾] 已清理本次 user-data-dir: {user_data_dir}')

        print(f'自动化执行成功，安装包位于: {installer_path}')
        # 返回首次验证码以供桌面端轮询时避开旧验证码
        return installer_path, email_addr, code

    except Exception as e:
        print(f"DrissionPage 启动或操作失败: {e}")
        if page:
            try:
                page.quit()
                print('[收尾-异常] 已关闭浏览器。')
            except: pass
        if user_data_dir and os.path.exists(user_data_dir):
            shutil.rmtree(user_data_dir, ignore_errors=True)
            print(f'[收尾-异常] 已清理本次 user-data-dir: {user_data_dir}')
        sys.exit(1)


if __name__ == "__main__":
    run_with_drissionpage()
