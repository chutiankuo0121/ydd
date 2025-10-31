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
        # 未配置 webhook，静默跳过
        return
    
    # 从环境变量获取 IP（主控电脑会设置）
    ip = os.environ.get('YDN_CLOUD_IP', '')
    if not ip:
        # IP 未配置，静默跳过
        return
    
    try:
        data = {
            "ip": ip,                    # 必填：云电脑 IP
            "status": status,            # 必填：running, success, failed
            "message": message,          # 选填：简短消息
            "error": error               # 选填：失败原因
        }
        resp = requests.post(webhook_url, json=data, timeout=10)
        if resp.status_code == 200:
            print(f"[状态] {status}: {message}")
        else:
            print(f"[警告] webhook 返回: {resp.status_code}")
    except Exception as e:
        print(f"[警告] webhook 发送失败: {e}")


def main():
    try:
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
