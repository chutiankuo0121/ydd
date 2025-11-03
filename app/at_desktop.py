import os
from airtest.core.api import exists, touch, sleep, Template, text, connect_device
import ctypes
from ctypes import wintypes
import requests
from config import CODE_API_TEMPLATE
import random
import logging
from logger import get_logger

logger = get_logger("DESKTOP")

# ============ 获取脚本所在目录的绝对路径 ============
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_IMAGE_DIR = os.path.join(SCRIPT_DIR, "images")

# ============ 降低 Airtest 日志噪音 ============
for _name in [
    "airtest",
    "airtest.core",
    "airtest.core.api",
    "airtest.aircv",
    "airtest.core.win",
]:
    logging.getLogger(_name).setLevel(logging.WARNING)

# ============ Windows 设备初始化 ============

def init_windows_device():
    try:
        connect_device("Windows:///")
        logger.info("Windows 设备已连接")
    except Exception as e:
        raise RuntimeError(f"连接 Windows 设备失败: {e}")

# ============ Windows 窗口控制（仅保留关闭功能） ============
WM_CLOSE = 0x0010
user32 = ctypes.WinDLL('user32', use_last_error=True)

EnumWindows = user32.EnumWindows
EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
GetWindowTextW = user32.GetWindowTextW
GetWindowTextLengthW = user32.GetWindowTextLengthW
IsWindowVisible = user32.IsWindowVisible
PostMessageW = user32.PostMessageW


def _find_window_by_title_substring(title_sub: str):
    matched_hwnd = None
    def _enum_proc(hwnd, lParam):
        nonlocal matched_hwnd
        if not IsWindowVisible(hwnd):
            return True
        length = GetWindowTextLengthW(hwnd)
        if length == 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value or ''
        if title_sub.lower() in title.lower():
            matched_hwnd = hwnd
            return False
        return True
    EnumWindows(EnumWindowsProc(_enum_proc), 0)
    return matched_hwnd


def close_window_by_title_substring(title_sub: str, retries: int = 5, interval: float = 0.3) -> bool:
    for _ in range(retries):
        hwnd = _find_window_by_title_substring(title_sub)
        if hwnd:
            PostMessageW(hwnd, WM_CLOSE, 0, 0)
            sleep(interval)
            if not _find_window_by_title_substring(title_sub):
                # 第一次验证成功，等待3秒后二次验证
                logger.info(f"第一次验证：'{title_sub}' 窗口已关闭，等待3秒进行二次验证")
                sleep(3)
                hwnd_recheck = _find_window_by_title_substring(title_sub)
                if hwnd_recheck:
                    logger.info(f"二次验证：'{title_sub}' 窗口重新出现，继续关闭")
                    PostMessageW(hwnd_recheck, WM_CLOSE, 0, 0)
                    sleep(interval)
                else:
                    logger.info(f"二次验证：'{title_sub}' 窗口确认已关闭")
                return True
        else:
            return False
    return False

# ============ 工具与步骤 ============

def wait_and_click(img_path, max_wait=20, threshold=0.8):
    tpl = Template(img_path, threshold=threshold)
    for _ in range(max_wait):
        pos = exists(tpl)
        if pos:
            try:
                touch(pos)
            except Exception:
                touch(tpl)
            sleep(1)
            return
        sleep(1)
    raise RuntimeError(f"等待元素超时: {os.path.basename(img_path)}")


def launch_installer(installer_path):
    logger.info(f"启动安装程序: {installer_path}")
    os.startfile(installer_path)
    sleep(2)


def auto_install_process(image_path_prefix=None):
    if image_path_prefix is None:
        image_path_prefix = DEFAULT_IMAGE_DIR
    sequence = [
        ("start_install.png", 30, "启动安装"),
        ("launch_comet.png", 60, "等待下载&启动Comet"),
        ("get_started.png", 30, "Get Started"),
        ("do_this_later.png", 30, "稍后再做"),
        ("continue.png", 30, "Continue"),
        ("start_comet.png", 30, "Start Comet")
    ]
    for idx, (img, maxsec, step_name) in enumerate(sequence):
        img_path = os.path.join(image_path_prefix, img)
        # 降低 do_this_later.png 的置信度
        threshold = 0.7 if img == "do_this_later.png" else 0.8
        wait_and_click(img_path, max_wait=maxsec, threshold=threshold)
        # 容错：若5秒内未看到"下一步元素"，则尝试再次点击当前元素（若仍存在）
        if idx < len(sequence) - 1:
            next_img = os.path.join(image_path_prefix, sequence[idx + 1][0])
            # 降低 do_this_later.png 的置信度
            current_threshold = 0.7 if img == "do_this_later.png" else 0.8
            next_threshold = 0.7 if sequence[idx + 1][0] == "do_this_later.png" else 0.8
            current_tpl = Template(img_path, threshold=current_threshold)
            next_tpl = Template(next_img, threshold=next_threshold)
            waited = 0
            while waited < 5:
                if exists(next_tpl):
                    break
                # 如果下一步尚未出现而当前按钮仍在，重试点击一次
                if exists(current_tpl):
                    try:
                        touch(current_tpl)
                    except Exception:
                        pass
                sleep(1)
                waited += 1
        if img == "start_comet.png":
            # 仅关闭可能遮挡的 Windows Settings
            close_window_by_title_substring("Settings", retries=5, interval=0.3)
            logger.running("安装流程完成，Comet 已启动")


def type_slow(s: str, per_char_delay: float = 0.01):
    for ch in s:
        text(ch)
        sleep(per_char_delay)


def comet_first_run_login(original_email: str, image_path_prefix=None):
    if image_path_prefix is None:
        image_path_prefix = DEFAULT_IMAGE_DIR
    logger.running("开始首次登录流程")
    # 先关闭可能遮挡的 Settings 窗口
    close_window_by_title_substring("Settings", retries=5, interval=0.3)
    sleep(4)
    
    # 并发轮询检测 Cloudflare 认证与邮箱输入框
    email_box = os.path.join(image_path_prefix, "enter_your_email.png")
    cloudflare_box = os.path.join(image_path_prefix, "cloudflare.png")
    email_tpl = Template(email_box, threshold=0.8)
    cloudflare_tpl = Template(cloudflare_box, threshold=0.8)
    
    logger.info("并发轮询检测：邮箱输入框与 Cloudflare 验证")
    max_wait = 20
    for sec in range(max_wait):
        # 先检测邮箱输入框
        pos_email = exists(email_tpl)
        if pos_email:
            logger.info(f"检测到邮箱输入框（{sec+1}s），无需认证")
            break
        
        # 再检测 Cloudflare 认证框
        pos_cloudflare = exists(cloudflare_tpl)
        if pos_cloudflare:
            logger.info(f"检测到 Cloudflare 验证（{sec+1}s），执行认证")
            try:
                touch(pos_cloudflare)
            except Exception:
                touch(cloudflare_tpl)
            sleep(2)
            logger.info("已点击 Cloudflare 验证，继续轮询邮箱输入框")
            # 点击后继续轮询，不 break
        
        sleep(1)
    
    # 继续等待并点击邮箱输入框
    wait_and_click(email_box, max_wait=20)
    sleep(0.2)
    type_slow(original_email, per_char_delay=0.01)
    sleep(0.3)
    
    # 容错：检测 continue_with_email.png，如果 5 秒未出现则回头检查邮箱输入
    cont_btn = os.path.join(image_path_prefix, "continue_with_email.png")
    cont_tpl = Template(cont_btn, threshold=0.8)
    
    logger.info("检测继续按钮（5秒）")
    cont_found = False
    for sec in range(5):
        pos_cont = exists(cont_tpl)
        if pos_cont:
            logger.info(f"发现继续按钮（{sec+1}s）")
            cont_found = True
            break
        sleep(1)
    
    # 如果 5 秒内未发现按钮，检查是否需要重新输入邮箱
    if not cont_found:
        logger.warning("未发现继续按钮，检查是否需要重新输入邮箱")
        pos_email_retry = exists(email_tpl)
        if pos_email_retry:
            logger.info("发现邮箱输入框，重新输入邮箱")
            try:
                touch(pos_email_retry)
            except Exception:
                touch(email_tpl)
            sleep(0.2)
            type_slow(original_email, per_char_delay=0.01)
            sleep(0.3)
            logger.info("已重新输入邮箱，继续检测继续按钮")
        else:
            logger.warning("未发现邮箱输入框")
    
    # 最终等待并点击 continue_with_email.png
    wait_and_click(cont_btn, max_wait=20)


def poll_code(email_addr: str, max_tries: int = 10, interval: int = 3, previous_code: str = None) -> str:
    url = CODE_API_TEMPLATE.format(email=email_addr)
    for _ in range(max_tries):
        try:
            resp = requests.get(url, timeout=5)
            txt = resp.text.strip()
            try:
                j = resp.json()
                code = j.get('code') or txt
            except Exception:
                code = txt
            if code and 3 <= len(code) <= 8:
                # 若与上一次验证码相同，则继续轮询，避免输入旧验证码
                if previous_code and code == previous_code:
                    pass
                else:
                    return code
        except Exception:
            pass
        sleep(interval)
    raise RuntimeError('验证码轮询超时')


def comet_enter_code(original_email: str, image_path_prefix=None, next_img: str = None, previous_code: str = None):
    if image_path_prefix is None:
        image_path_prefix = DEFAULT_IMAGE_DIR
    code_box = os.path.join(image_path_prefix, "enter_code.png")
    wait_and_click(code_box, max_wait=20)
    sleep(5)
    code = poll_code(original_email, previous_code=previous_code)
    text(code)
    logger.running("验证码输入完成")
    if next_img:
        wait_and_click(os.path.join(image_path_prefix, next_img), max_wait=20)


def try_click(img_path, timeout=10):
    """尝试在指定时间内点击图片，成功返回 True，不存在返回 False。"""
    name = os.path.basename(img_path)
    tpl = Template(img_path, threshold=0.8)
    for sec in range(timeout):
        pos = exists(tpl)
        if pos:
            logger.info(f"检测到 {name}（{sec+1}s）")
            try:
                touch(pos)
            except Exception:
                touch(tpl)
            sleep(0.5)
            logger.info(f"已点击 {name}")
            return True
        sleep(1)
    logger.info(f"未发现 {name}（{timeout}s）")
    return False


def comet_post_login_dismiss_tour(image_path_prefix=None) -> bool:
    if image_path_prefix is None:
        image_path_prefix = DEFAULT_IMAGE_DIR
    """
    返回值：
    - True  -> 路径A：点击 x 后继续问问题
    - False -> 路径B：发现 ask_anything2，直接结束（不问问题）
    并发轮询风格：在同一时间窗口内同时检测两种可能，先命中的优先。
    """
    skip = os.path.join(image_path_prefix, "skip.png")
    skip_anyway = os.path.join(image_path_prefix, "skip_anyway.png")
    ask2 = os.path.join(image_path_prefix, "ask_anything2.png")
    close_x = os.path.join(image_path_prefix, "x.png")

    logger.info("预处理：检测 skip / skip_anyway 按钮")
    hit_skip = try_click(skip, timeout=10)
    hit_skip_anyway = try_click(skip_anyway, timeout=10)

    # 同时检测 ask_anything2 与 x，先命中的优先
    logger.info("并发轮询：ask_anything2 与 x")
    ask2_tpl = Template(ask2, threshold=0.8)
    x_tpl = Template(close_x, threshold=0.8)
    max_wait = 20
    for sec in range(max_wait):
        pos_ask2 = exists(ask2_tpl)
        if pos_ask2:
            logger.info(f"检测到 ask_anything2（{sec+1}s），执行路径B（直接结束）")
            try:
                touch(pos_ask2)
            except Exception:
                touch(ask2_tpl)
            sleep(0.5)
            return False
        pos_x = exists(x_tpl)
        if pos_x:
            logger.info(f"检测到 x 按钮（{sec+1}s），执行路径A（继续问问题）")
            try:
                touch(pos_x)
            except Exception:
                touch(x_tpl)
            sleep(0.5)
            return True
        sleep(1)

    logger.warning("超时未检测到 ask_anything2 / x，默认进入路径A（继续问问题）")
    return True


def comet_ask_anything(image_path_prefix=None):
    if image_path_prefix is None:
        image_path_prefix = DEFAULT_IMAGE_DIR
    questions = [
        "If you could have dinner with any fictional character, who would it be and what would you ask them?",
        "If you could instantly master any language (other than English), which one would you choose and why?",
        "What’s the best piece of ‘random advice’ you’ve ever received?"
    ]
    ask_box = os.path.join(image_path_prefix, "ask_anything.png")
    wait_and_click(ask_box, max_wait=20)
    text(random.choice(questions))
    sleep(0.5)
    next_btn = os.path.join(image_path_prefix, "next.png")
    wait_and_click(next_btn, max_wait=20, threshold=0.7)


def main(installer_path, original_email, previous_code):
    init_windows_device()
    launch_installer(installer_path)
    logger.running("安装程序已启动")
    auto_install_process()
    logger.running("安装流程完成，准备首次登录")
    comet_first_run_login(original_email)
    comet_enter_code(original_email, previous_code=previous_code)
    need_ask = comet_post_login_dismiss_tour()
    if need_ask:
        logger.running("回答问题流程")
        comet_ask_anything()
    logger.info("桌面自动化全流程完成")
