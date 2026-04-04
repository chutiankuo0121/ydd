from __future__ import annotations

import random
import threading
import time

from app_config import AirportConfig
from runtime_log import log

from .models import AirportNode, AirportSession
from .ports import PortAllocator
from .subscription import load_airport_nodes
from .xray import XrayRunner, format_exception


REGION_WEIGHTS = {
    "singapore": 50,
    "japan": 30,
    "taiwan_hk": 20,
}
REGION_KEYWORDS = {
    "singapore": ("新加坡", "singapore"),
    "japan": ("日本", "japan"),
    "taiwan_hk": ("台湾", "台灣", "香港", "hong kong", "hongkong"),
}


class AirportManager:
    def __init__(self, config: AirportConfig) -> None:
        self.config = config
        self.port_allocator = PortAllocator(config.base_port, config.port_search_limit)
        self.xray_runner = XrayRunner(
            xray_path=config.xray_path,
            startup_wait_seconds=config.startup_wait_seconds,
            connectivity_test_url=config.connectivity_test_url,
            connectivity_timeout=config.connectivity_timeout,
        )

        self._lock = threading.Lock()
        self._nodes: list[AirportNode] = []
        self._cooldowns: dict[str, float] = {}
        self._active_node_names: set[str] = set()

    def load_nodes(self) -> list[AirportNode]:
        raw_nodes = load_airport_nodes(self.config.subscription_url)
        nodes = [node for node in raw_nodes if self._classify_region(node.name) is not None]
        with self._lock:
            self._nodes = nodes
            self._cooldowns.clear()
            self._active_node_names.clear()
        return nodes

    def ensure_nodes_loaded(self) -> list[AirportNode]:
        with self._lock:
            if self._nodes:
                return list(self._nodes)
        return self.load_nodes()

    def acquire_session(self, owner: str) -> AirportSession:
        nodes = self.ensure_nodes_loaded()
        if not nodes:
            raise RuntimeError("没有从机场订阅中加载到可用节点")

        failures: list[str] = []

        for _ in range(max(1, self.config.max_acquire_attempts)):
            node = self._reserve_next_node()
            if node is None:
                break

            port = None
            session = None
            try:
                port = self.port_allocator.acquire()
                log(f"[机场] 预留本地端口 {port}，尝试节点: {node.name}")
                session = self.xray_runner.start_session(node, port)
                session = self.xray_runner.probe_session(session)
                return session
            except Exception as exc:
                failures.append(f"{node.name}: {format_exception(exc)}")
                log(f"[机场] 节点失败: {node.name} -> {format_exception(exc)}")
                if session is not None:
                    self.xray_runner.stop_session(session)
                if port is not None:
                    self.port_allocator.release(port)
                self._release_failed_node(node, exc)

        detail = failures[-3:]
        if detail:
            raise RuntimeError(
                f"{owner} 无法找到可用机场节点。最近错误: {' | '.join(detail)}"
            )
        raise RuntimeError(f"{owner} 无法找到可用机场节点")

    def release_session(
        self,
        session: AirportSession | None,
        penalize: bool = False,
    ) -> None:
        if session is None:
            return

        self.xray_runner.stop_session(session)
        self.port_allocator.release(session.local_port)

        with self._lock:
            self._active_node_names.discard(session.node.name)
            if penalize:
                self._cooldowns[session.node.name] = (
                    time.monotonic() + self.config.node_failure_cooldown_seconds
                )

    def _reserve_next_node(self) -> AirportNode | None:
        with self._lock:
            if not self._nodes:
                return None

            now = time.monotonic()
            grouped_candidates: dict[str, list[AirportNode]] = {
                "singapore": [],
                "japan": [],
                "taiwan_hk": [],
            }
            for node in self._nodes:
                cooldown_until = self._cooldowns.get(node.name, 0)
                if cooldown_until > now:
                    continue
                if node.name in self._active_node_names:
                    continue

                region = self._classify_region(node.name)
                if region is None:
                    continue
                grouped_candidates[region].append(node)

            available_groups = [
                (region, REGION_WEIGHTS[region], nodes)
                for region, nodes in grouped_candidates.items()
                if nodes
            ]
            if not available_groups:
                return None

            selected_region = random.choices(
                [region for region, _, _ in available_groups],
                weights=[weight for _, weight, _ in available_groups],
                k=1,
            )[0]
            selected_node = random.choice(grouped_candidates[selected_region])
            self._active_node_names.add(selected_node.name)
            return selected_node

        return None

    def _release_failed_node(self, node: AirportNode, exc: Exception) -> None:
        with self._lock:
            self._active_node_names.discard(node.name)
            self._cooldowns[node.name] = (
                time.monotonic() + self.config.node_failure_cooldown_seconds
            )

    @staticmethod
    def _classify_region(node_name: str) -> str | None:
        normalized = node_name.lower()
        for region, keywords in REGION_KEYWORDS.items():
            for keyword in keywords:
                if keyword in normalized:
                    return region
        return None
