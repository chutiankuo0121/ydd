# 自动化主流程脚本
import os
import sys
import requests
import time
from dp_web import run_with_drissionpage
from at_desktop import main as desktop_main


def send_webhook(status, message="", error=""):
    """发送状态到 Cloudflare Worker webhook"""
    webhook_url = os.environ.get('YDN_WEBHOOK_URL', 'https://dollars.775658833.xyz/')
    if not webhook_url:
        print("[调试] 未发现环境变量 YDN_WEBHOOK_URL，跳过发送")
        return
    
    # 从环境变量获取 IP（主控电脑会设置）
    ip = os.environ.get('YDN_CLOUD_IP', '').strip()
    if not ip:
        print("[调试] 未发现环境变量 YDN_CLOUD_IP，跳过发送")
        return
    
    try:
        data = {
            "ip": ip,                    # 必填：云电脑 IP
            "status": status,            # 必填：running, success, failed
            "message": message,          # 选填：简短消息
            "error": error               # 选填：失败原因
        }
        print(f"[调试] 即将发送到 Webhook: {webhook_url}")
        print(f"[调试] Payload: {data}")
        resp = requests.post(webhook_url, json=data, timeout=10)
        print(f"[调试] Webhook 响应: {resp.status_code} {resp.text[:200]}")
        if resp.status_code == 200:
            print(f"[状态] {status}: {message}")
        else:
            print(f"[警告] webhook 返回: {resp.status_code}")
    except Exception as e:
        print(f"[警告] webhook 发送失败: {e}")


def print_injected_env():
    """打印注入到环境的关键变量，便于远程调试。"""
    webhook_url = os.environ.get('YDN_WEBHOOK_URL', '')
    ip = os.environ.get('YDN_CLOUD_IP', '')
    print("[调试] 读取到环境变量：")
    print(f"  - YDN_WEBHOOK_URL = {webhook_url or '<空>'}")
    print(f"  - YDN_CLOUD_IP    = {ip or '<空>'}")


def main():
    try:
        # 启动即打印注入的环境变量
        print_injected_env()
        send_webhook("running", "开始执行自动化流程")
        installer_path, email_addr, first_code = run_with_drissionpage()
        send_webhook("running", "网页自动化完成，开始桌面安装流程")
        desktop_main(installer_path, email_addr, first_code)
        send_webhook("success", "全流程执行成功")
    except Exception as e:
        error_msg = str(e)
        print(f"[错误] {error_msg}")
        send_webhook("failed", f"任务执行失败: {error_msg}", error_msg)
        sys.exit(1)


if __name__ == "__main__":
    main()
