from __future__ import annotations

import requests
import yaml

from .models import AirportNode


CLASH_USER_AGENT = "ClashForWindows/0.20.39"


def load_airport_nodes(subscription_url: str, timeout: int = 30) -> list[AirportNode]:
    resp = requests.get(
        subscription_url,
        headers={"User-Agent": CLASH_USER_AGENT},
        timeout=timeout,
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
