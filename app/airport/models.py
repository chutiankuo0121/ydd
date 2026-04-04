from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AirportNode:
    name: str
    address: str
    port: int
    method: str
    password: str
    plugin: str = ""
    plugin_mode: str = "http"
    plugin_host: str = ""


@dataclass
class AirportSession:
    node: AirportNode
    local_port: int
    process: object
    config_path: Path
    proxy_url: str
    requests_proxy_url: str
    exit_ip: str = "-"
    country: str = "-"
    region: str = "-"
    latency_ms: int | None = None

    @property
    def address(self) -> str:
        return f"{self.node.address}:{self.node.port}"
