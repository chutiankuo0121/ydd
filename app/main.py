from __future__ import annotations

import argparse
import os

from app_config import load_app_config
from runtime_log import configure_stdout, log


def check_playwright_browsers() -> bool:
    """检测 Playwright 浏览器是否已安装且可用"""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            # 尝试启动 chromium 来验证是否真正可用
            try:
                browser = p.chromium.launch()
                browser.close()
                return True
            except Exception as e:
                # 浏览器未安装或损坏
                return False
    except Exception:
        return False


def ensure_playwright_browsers(log_func=print) -> bool:
    """安装 Playwright 浏览器及其依赖"""
    try:
        import subprocess
        import sys
        
        # 先显示当前 playwright 版本
        try:
            import playwright
            log_func(f"[playwright] package version: {playwright.__version__}")
        except Exception:
            pass
        
        log_func("[playwright] installing chromium with deps...")
        # 使用 --with-deps 确保系统依赖也安装
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "--with-deps", "chromium"],
            capture_output=True,
            text=True,
            timeout=600,  # 增加超时时间，因为下载可能很慢
        )
        if result.returncode == 0:
            log_func("[playwright] chromium installed successfully")
            return True
        else:
            log_func(f"[playwright] install failed:\n{result.stderr[:500]}")
            # 尝试不带 --with-deps 再试一次
            log_func("[playwright] retrying without system deps...")
            result2 = subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                capture_output=True,
                text=True,
                timeout=600,
            )
            if result2.returncode == 0:
                log_func("[playwright] chromium installed (without deps)")
                return True
            else:
                log_func(f"[playwright] retry failed:\n{result2.stderr[:500]}")
                return False
    except subprocess.TimeoutExpired:
        log_func("[playwright] install timeout (600s), please check network")
        return False
    except Exception as e:
        log_func(f"[playwright] install error: {e}")
        return False


def parse_args() -> argparse.Namespace:
    # 获取脚本所在目录，用于默认路径
    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_config = os.path.join(script_dir, "config.json")
    
    parser = argparse.ArgumentParser(description="Run the Outlook registration app.")
    parser.add_argument(
        "--config",
        default=os.getenv("APP_CONFIG_PATH", default_config),
        help="Path to the JSON config file.",
    )
    parser.add_argument(
        "--skip-xray-check",
        action="store_true",
        help="Skip Xray verification and auto-download during startup.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    configure_stdout()

    log(f"[main] loading config: {args.config}")
    app_config = load_app_config(args.config)
    xray_path = app_config.airport.xray_path

    if args.skip_xray_check:
        log("[main] skipping Xray startup checks")
    else:
        from download_xray import check_xray, ensure_xray_available, get_xray_version

        log(f"[main] preparing Xray: {xray_path}")
        xray_ready = check_xray(xray_path)
        if not xray_ready:
            log("[main] Xray missing, downloading and installing")
            xray_ready = ensure_xray_available(
                xray_path=xray_path,
                force_download=False,
                log_func=log,
            )

        if not xray_ready:
            raise FileNotFoundError(
                f"Xray is missing or unusable: {xray_path}. "
                "Run download_xray.py or check your network and permissions."
            )

        version = get_xray_version(xray_path)
        if version:
            log(f"[main] Xray ready: {version}")

    # 检测并安装 Playwright 浏览器
    log("[main] checking playwright browsers")
    if not check_playwright_browsers():
        log("[main] playwright browsers missing, installing")
        if not ensure_playwright_browsers(log_func=log):
            log("[warning] failed to install playwright browsers, browser automation may fail")
    else:
        log("[main] playwright browsers ready")

    log("[main] initializing registration service")
    from registration_service import RegistrationService

    service = RegistrationService(app_config)
    log("[main] starting service")
    service.run()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("\n[stop] received keyboard interrupt, exiting")
