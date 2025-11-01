"""
统一的日志系统
- 支持不同级别的日志（INFO, WARNING, ERROR, STATUS）
- STATUS 级别的日志会自动推送到 Worker（通过 webhook）
"""
import os
import sys
import requests
from datetime import datetime
from typing import Optional

# 日志级别
LEVEL_INFO = "INFO"
LEVEL_WARNING = "WARNING"
LEVEL_ERROR = "ERROR"
LEVEL_STATUS = "STATUS"  # 会自动推送到 Worker

# Worker URL（写死）
WEBHOOK_URL = 'https://dollars.775658833.xyz/status'


class Logger:
    """统一的日志记录器"""
    
    def __init__(self, module: str = "MAIN"):
        """
        初始化日志记录器
        :param module: 模块名称（用于标识日志来源）
        """
        self.module = module
        self.task_id = os.environ.get('YDN_TASK_ID', '').strip()
        self.invite_url = os.environ.get('YDN_INVITE_URL', '').strip()
    
    def _format_message(self, level: str, message: str) -> str:
        """格式化日志消息"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return f"[{timestamp}] [{level}] [{self.module}] {message}"
    
    def _print(self, level: str, message: str):
        """打印日志到控制台"""
        formatted = self._format_message(level, message)
        print(formatted, file=sys.stdout if level != LEVEL_ERROR else sys.stderr)
    
    def _send_status_to_worker(self, status: str, message: str, error: str = ""):
        """发送状态更新到 Worker"""
        if not self.task_id or not self.invite_url:
            # 如果没有环境变量，静默跳过（不打印调试信息）
            return
        
        try:
            data = {
                "task_id": self.task_id,
                "status": status,  # running, success, failed
                "invite_url": self.invite_url,
                "message": message,
            }
            if error:
                data["error"] = error
            
            resp = requests.post(WEBHOOK_URL, json=data, timeout=10)
            if resp.status_code != 200:
                # 静默失败，不打印调试信息
                pass
        except Exception:
            # 静默失败，不打印调试信息
            pass
    
    def info(self, message: str):
        """信息日志（普通操作信息）"""
        self._print(LEVEL_INFO, message)
    
    def warning(self, message: str):
        """警告日志（可能的问题但不影响运行）"""
        self._print(LEVEL_WARNING, message)
    
    def error(self, message: str):
        """错误日志（严重错误）"""
        self._print(LEVEL_ERROR, message)
    
    def status(self, status: str, message: str, error: str = ""):
        """
        状态日志（会推送到 Worker）
        :param status: running, success, failed
        :param message: 状态消息
        :param error: 错误详情（仅失败时提供）
        """
        self._print(LEVEL_STATUS, f"{status.upper()}: {message}")
        self._send_status_to_worker(status, message, error)
    
    def running(self, message: str):
        """状态：运行中"""
        self.status("running", message)
    
    def success(self, message: str):
        """状态：成功"""
        self.status("success", message)
    
    def failed(self, message: str, error: str = ""):
        """状态：失败"""
        self.status("failed", message, error)


# 全局默认日志记录器
_default_logger = Logger("MAIN")


def get_logger(module: str) -> Logger:
    """
    获取指定模块的日志记录器
    :param module: 模块名称
    :return: Logger 实例
    """
    return Logger(module)


def info(message: str, module: str = "MAIN"):
    """全局信息日志"""
    logger = Logger(module)
    logger.info(message)


def warning(message: str, module: str = "MAIN"):
    """全局警告日志"""
    logger = Logger(module)
    logger.warning(message)


def error(message: str, module: str = "MAIN"):
    """全局错误日志"""
    logger = Logger(module)
    logger.error(message)


def status(status: str, message: str, error: str = "", module: str = "MAIN"):
    """全局状态日志（会推送到 Worker）"""
    logger = Logger(module)
    logger.status(status, message, error)

