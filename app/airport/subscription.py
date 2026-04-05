from __future__ import annotations

import os
# 强制清除系统代理环境变量，防止 requests 自动使用
for proxy_var in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy']:
    os.environ.pop(proxy_var, None)

import requests
import urllib3
import yaml

from .models import AirportNode

# 禁用 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


CLASH_USER_AGENT = "ClashForWindows/0.20.39"


def load_airport_nodes(subscription_url: str, timeout: int = 30) -> list[AirportNode]:
    resp = requests.get(
        subscription_url,
        headers={"User-Agent": CLASH_USER_AGENT},
        timeout=timeout,
        verify=False,
        proxies={"http": None, "https": None},
    )
    resp.raise_for_status()

    config = yaml.safe_load(resp.text) or {}
    proxies = config.get("proxies") or []

    nodes: list[AirportNode] = []
    for proxy in proxies:
        if (proxy.get("type") or "").lower() != "ss":
            continue

        plugin = (proxy.get("plugin") or "").lower()
        plugin_opts = proxy.get("plugin-opts") or {}
        plugin_mode = (plugin_opts.get("mode") or "http").lower()
        
        # 跳过不支持的 obfs tls 模式节点
        if plugin == "obfs" and plugin_mode == "tls":
            continue
        
        nodes.append(
            AirportNode(
                name=proxy.get("name", ""),
                address=proxy.get("server", ""),
                port=int(proxy.get("port", 443)),
                method=proxy.get("cipher", ""),
                password=proxy.get("password", ""),
                plugin=plugin,
                plugin_mode=(plugin_opts.get("mode") or "http").lower(),
                plugin_host=(plugin_opts.get("host") or "").strip(),
            )
        )

    return nodes


def load_airport_nodes_from_multiple(subscription_urls: list[str], timeout: int = 30) -> list[AirportNode]:
    """从多个订阅 URL 获取节点，合并后返回"""
    all_nodes: list[AirportNode] = []
    errors: list[str] = []
    
    for url in subscription_urls:
        try:
            nodes = load_airport_nodes(url, timeout)
            all_nodes.extend(nodes)
        except Exception as e:
            errors.append(f"{url}: {e}")
            continue
    
    if not all_nodes and errors:
        raise RuntimeError(f"所有订阅获取失败: {'; '.join(errors)}")
    
    return all_nodes
