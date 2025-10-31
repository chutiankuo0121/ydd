# 配置信息（全局常量）
import os

# URL 和 浏览器路径优先从环境变量读取
URL = os.environ.get('AUTO_URL', "https://pplx.ai/chutiankuo64723")

# Windows 系统下默认下载目录：C:\Users\用户名\Downloads
if os.name == 'nt':
    DOWNLOAD_PATH = os.path.join(os.environ['USERPROFILE'], 'Downloads')
else:
    DOWNLOAD_PATH = '/tmp/downloads'  # 非Windows备用，实际用不到

# 浏览器可执行文件路径（默认使用官方 Chrome），可用环境变量 BROWSER_PATH 覆盖
BROWSER_PATH = os.environ.get('BROWSER_PATH', r"C:\Program Files\Google\Chrome\Application\chrome.exe")

# 验证码API，按邮箱拼接
CODE_API_TEMPLATE = "https://cursor.775658833.xyz/api/code?recipient={email}"
