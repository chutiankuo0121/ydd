import string
import secrets
from typing import Optional, List

class EmailDomainPool:
    """邮箱域名池，支持随机或指定获取域名。"""
    def __init__(self, domains: Optional[List[str]] = None):
        self.domains = domains or [
            "010930.xyz",
            "123719141.cfd",
            "123719141.xyz",
            "775658833.xyz",
            "806307287.cfd",
            "806307287.top",
            "806307287.xyz",
            "bjyzq.top",
            "changjian01.top",
            "chuchu01.top",
            "ethan01.top",
            "fjzj01.top",
            "guizhong123.top",
            "qgdnwj.cfd",
            "tiandu01.top",
            "xqqking.top",
            "xttking.top"
        ]
    def get_random_domain(self):
        return secrets.choice(self.domains)
    def all(self) -> List[str]:
        return self.domains

# 默认域名池
default_domain_pool = EmailDomainPool()

def generate_random_email(prefix_length: int = 10, domain: Optional[str] = None, prefix: Optional[str] = None, domain_pool: EmailDomainPool = default_domain_pool) -> str:
    """
    生成随机邮箱地址。
    - 前缀由小写字母和数字组成，默认长度10。
    - 域名若为 None，则从 domain_pool 随机获取。
    - 如提供 prefix，则直接用该前缀（调用方需保证合法性）。
    """
    if prefix is None:
        alphabet = string.ascii_lowercase + string.digits
        prefix = ''.join(secrets.choice(alphabet) for _ in range(prefix_length))
    if domain is None:
        domain = domain_pool.get_random_domain()
    return f"{prefix}@{domain}"
