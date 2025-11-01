# 自动化主流程脚本
import os
import sys
import requests
import time
from dp_web import run_with_drissionpage
from at_desktop import main as desktop_main


def send_webhook(status, message="", error=""):
    """发送状态到 Cloudflare Worker webhook"""
    # Worker URL 写死，不再从环境变量读取
    webhook_url = 'https://dollars.775658833.xyz/status'
    
    # 从环境变量获取 task_id（主控电脑会设置）
    task_id = os.environ.get('YDN_TASK_ID', '').strip()
    if not task_id:
        print("[调试] 未发现环境变量 YDN_TASK_ID，跳过发送")
        return
    
    # 从环境变量获取 invite_url（主控电脑会设置）
    invite_url = os.environ.get('YDN_INVITE_URL', '').strip()
    if not invite_url:
        print("[调试] 未发现环境变量 YDN_INVITE_URL，跳过发送")
        return
    
    try:
        data = {
            "task_id": task_id,          # 必填：任务id
            "status": status,            # 必填：running, success, failed
            "invite_url": invite_url,    # 必填：邀请链接
            "message": message,          # 必填：简短消息
        }
        # 选填：失败时填写错误详情
        if error:
            data["error"] = error
        
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
    task_id = os.environ.get('YDN_TASK_ID', '')
    invite_url = os.environ.get('YDN_INVITE_URL', '')
    print("[调试] 读取到环境变量：")
    print(f"  - YDN_TASK_ID     = {task_id or '<空>'}")
    print(f"  - YDN_INVITE_URL  = {invite_url or '<空>'}")
    print(f"  - Webhook URL     = https://dollars.775658833.xyz/status (写死)")


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
