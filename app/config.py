# 配置信息（全局常量）
import os

# 邀请链接从环境变量读取（主控机会注入 YDN_INVITE_URL）
# 优先使用 YDN_INVITE_URL，如果不存在则使用 AUTO_URL（向后兼容），最后使用默认值
URL = os.environ.get('YDN_INVITE_URL') or os.environ.get('AUTO_URL') or "https://pplx.ai/hgujy_470143212"

# Windows 系统下默认下载目录：C:\Users\用户名\Downloads
if os.name == 'nt':
    DOWNLOAD_PATH = os.path.join(os.environ['USERPROFILE'], 'Downloads')
else:
    DOWNLOAD_PATH = '/tmp/downloads'  # 非Windows备用，实际用不到

# 浏览器可执行文件路径（默认使用官方 Chrome），可用环境变量 BROWSER_PATH 覆盖
BROWSER_PATH = os.environ.get('BROWSER_PATH', r"C:\Program Files\Google\Chrome\Application\chrome.exe")

# 验证码API，按邮箱拼接
CODE_API_TEMPLATE = "https://cursor.775658833.xyz/api/code?recipient={email}"
