from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests

from .models import AirportNode, AirportSession


def requests_supports_socks() -> bool:
    return importlib.util.find_spec("socks") is not None


def get_socks_dependency_message() -> str:
    python_cmd = sys.executable or "python"
    return (
        "当前 Python 环境缺少 PySocks，requests 还不能通过 socks5h 代理发请求。"
        f" 请先运行: {python_cmd} -m pip install PySocks"
    )


def ensure_requests_socks_support() -> None:
    if not requests_supports_socks():
        raise RuntimeError(get_socks_dependency_message())


def format_exception(exc: Exception) -> str:
    message = str(exc).strip()
    if not message:
        return exc.__class__.__name__
    return f"{exc.__class__.__name__}: {message}"


def normalize_requests_proxy_url(proxy_url: str) -> str:
    if proxy_url.startswith("socks5://"):
        return "socks5h://" + proxy_url[len("socks5://") :]
    return proxy_url


def build_requests_proxies(proxy_or_port: str | int) -> dict[str, str]:
    if isinstance(proxy_or_port, int):
        proxy_url = f"socks5h://127.0.0.1:{proxy_or_port}"
    else:
        proxy_url = normalize_requests_proxy_url(proxy_or_port)
    return {"http": proxy_url, "https": proxy_url}


def build_xray_config(node: AirportNode, port: int, loglevel: str = "warning") -> dict:
    return {
        "log": {"loglevel": loglevel},
        "inbounds": [
            {
                "port": port,
                "listen": "127.0.0.1",
                "protocol": "socks",
                "settings": {"udp": True},
            }
        ],
        "outbounds": [build_shadowsocks_outbound(node)],
    }


def build_shadowsocks_outbound(node: AirportNode) -> dict:
    outbound = {
        "protocol": "shadowsocks",
        "settings": {
            "servers": [
                {
                    "address": node.address,
                    "port": node.port,
                    "method": node.method,
                    "password": node.password,
                }
            ]
        },
    }

    plugin = (node.plugin or "").lower()
    if not plugin:
        return outbound

    if plugin != "obfs":
        raise ValueError(f"暂不支持的 Shadowsocks 插件: {plugin}")

    plugin_mode = (node.plugin_mode or "http").lower()
    if plugin_mode != "http":
        raise ValueError(f"暂不支持的 obfs 模式: {plugin_mode}")

    plugin_host = node.plugin_host or "www.bing.com"
    outbound["streamSettings"] = {
        "network": "tcp",
        "tcpSettings": {
            "header": {
                "type": "http",
                "request": {
                    "version": "1.1",
                    "method": "GET",
                    "path": ["/"],
                    "headers": {
                        "Host": [plugin_host],
                        "User-Agent": [
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                        ],
                        "Accept-Encoding": ["gzip, deflate"],
                        "Connection": ["keep-alive"],
                        "Pragma": ["no-cache"],
                    },
                },
            }
        },
    }
    return outbound


class XrayRunner:
    def __init__(
        self,
        xray_path: Path,
        startup_wait_seconds: float,
        connectivity_test_url: str,
        connectivity_timeout: int,
    ) -> None:
        self.xray_path = Path(xray_path)
        self.startup_wait_seconds = startup_wait_seconds
        self.connectivity_test_url = connectivity_test_url
        self.connectivity_timeout = connectivity_timeout

    def start_session(self, node: AirportNode, port: int) -> AirportSession:
        if not self.xray_path.exists():
            raise FileNotFoundError(f"找不到 xray.exe: {self.xray_path}")

        config = build_xray_config(node, port, loglevel="warning")
        config_path = Path(tempfile.gettempdir()) / f"xray_{port}.json"
        with config_path.open("w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False)

        process = subprocess.Popen(
            [str(self.xray_path), "run", "-c", str(config_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            cwd=str(self.xray_path.parent),
        )
        time.sleep(self.startup_wait_seconds)

        if process.poll() is not None:
            _, stderr = process.communicate()
            error_msg = stderr.decode("utf-8", errors="ignore").strip() or "未知错误"
            try:
                config_path.unlink()
            except OSError:
                pass
            raise RuntimeError(f"Xray 启动失败: {error_msg[:200]}")

        proxy_url = f"socks5://127.0.0.1:{port}"
        return AirportSession(
            node=node,
            local_port=port,
            process=process,
            config_path=config_path,
            proxy_url=proxy_url,
            requests_proxy_url=normalize_requests_proxy_url(proxy_url),
        )

    def probe_session(self, session: AirportSession) -> AirportSession:
        start = time.time()
        resp = requests.get(
            self.connectivity_test_url,
            proxies=build_requests_proxies(session.requests_proxy_url),
            timeout=self.connectivity_timeout,
        )
        resp.raise_for_status()

        latency_ms = int((time.time() - start) * 1000)
        info = resp.json()

        session.exit_ip = info.get("ip", "-")
        session.country = info.get("country", "-")
        session.region = info.get("region", "-")
        session.latency_ms = latency_ms
        return session

    def stop_session(self, session: AirportSession | None) -> None:
        if session is None:
            return

        process = session.process
        if process:
            try:
                process.terminate()
                process.wait(timeout=3)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass

        try:
            session.config_path.unlink()
        except OSError:
            pass
